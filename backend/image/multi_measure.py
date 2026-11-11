"""Source-bound adapter for the fixed ImageJ1 ROI Manager Multi Measure command."""

from __future__ import annotations

import json
import math
from threading import Event
from typing import Any
from uuid import uuid4

from backend.image.assets import ImageAsset
from backend.image.fiji_process import native_multi_measure
from backend.image.roi_collection import validate_collection
from backend.image.selection import EXTRA_MEASUREMENTS, build_plane_selection
from scripts.prepare_fiji_runtime import EXPECTED_SHA256


MAX_SELECTED_ROIS = 16
MAX_STACK_PLANES = 64
MAX_RUNS = 3
MAX_TABLE_VALUES = 12_288
MAX_CANDIDATE_PIXELS = 16_000_000
MAX_NATIVE_REPORT_BYTES = 4 * 1024 * 1024


def run_native_multi_measure(
    asset: ImageAsset,
    collection: dict[str, Any],
    selected_roi_ids: list[str],
    current_plane: dict[str, int],
    runs: list[dict[str, bool]],
    measurement_flags: list[str],
    cancel: Event,
) -> dict[str, Any]:
    """Validate the frozen contract, then execute every run in one fixed Fiji process."""
    document = validate_collection(asset, collection)
    if (not isinstance(selected_roi_ids, list) or not 1 <= len(selected_roi_ids) <= MAX_SELECTED_ROIS
            or any(not isinstance(value, str) for value in selected_roi_ids)
            or len(selected_roi_ids) != len(set(selected_roi_ids))):
        raise ValueError("Multi Measure 须有序选择 1 至 16 个不重复 ROI。")
    by_id = {item["id"]: item for item in document["items"]}
    if any(identifier not in by_id for identifier in selected_roi_ids):
        raise ValueError("Multi Measure 选择包含集合之外的 ROI。")
    selected = {**document, "items": [by_id[identifier] for identifier in selected_roi_ids]}
    if len({item["name"] for item in selected["items"]}) != len(selected["items"]):
        raise ValueError("Multi Measure 所选 ROI 名称须互异，以保留原生结果列。")
    axes, plane, _, _ = build_plane_selection(asset, current_plane)
    stack_planes = 1
    for axis in axes:
        if axis["name"] in ("Channel", "Z", "Time"):
            stack_planes *= axis["length"]
    if stack_planes > MAX_STACK_PLANES:
        raise ValueError("Multi Measure 当前限定 64 个线性栈平面。")
    option_keys = {"measure_all", "one_row_per_slice", "append_results"}
    if (not isinstance(runs, list) or not 1 <= len(runs) <= MAX_RUNS
            or any(not isinstance(run, dict) or set(run) != option_keys
                   or any(type(run[key]) is not bool for key in option_keys) for run in runs)):
        raise ValueError("Multi Measure 每次运行须明确提供三个布尔选项，最多三次。")
    if (not isinstance(measurement_flags, list)
            or any(not isinstance(flag, str) for flag in measurement_flags)
            or len(measurement_flags) != len(set(measurement_flags))
            or any(flag not in EXTRA_MEASUREMENTS for flag in measurement_flags)):
        raise ValueError("Multi Measure 统计选项无效或重复。")
    flags = [flag for flag in EXTRA_MEASUREMENTS if flag in measurement_flags]
    traversed = sum(stack_planes if run["measure_all"] else 1 for run in runs)
    fields = 4 + sum(2 if flag == "integrated_density" else 1 for flag in flags)
    if traversed * len(selected_roi_ids) * fields > MAX_TABLE_VALUES:
        raise ValueError("Multi Measure 表格数值超出 12288 项上限。")
    candidates = sum(item["roi"]["width"] * item["roi"]["height"] for item in selected["items"])
    if candidates * traversed > MAX_CANDIDATE_PIXELS:
        raise ValueError("Multi Measure 候选像素读取量超出 1600 万。")
    # Native rows repeat full column names (including ROI names), and append
    # returns earlier rows again. Budget serialized reports, not just new cells.
    history = {True: 0, False: 0}
    estimate = 192 * 1024
    name_bytes = max(len(json.dumps(item["name"], ensure_ascii=True)) for item in selected["items"])
    for run in runs:
        wide = run["one_row_per_slice"]
        added = (stack_planes if run["measure_all"] else 1) * (1 if wide else len(selected_roi_ids))
        history[wide] = (history[wide] if run["append_results"] else 0) + added
        columns = fields * (len(selected_roi_ids) if wide else 1) + 1
        estimate += history[wide] * columns * ((name_bytes if wide else 0) + 72)
    if estimate > MAX_NATIVE_REPORT_BYTES:
        raise ValueError("Multi Measure 原生结果预估超过 4 MiB，请减少 ROI、运行次数或名称长度。")
    payload = native_multi_measure(asset, uuid4().hex, cancel, selected, plane, runs, flags)
    if (payload.get("source") != selected["source"] or payload.get("current_plane") != plane
            or payload.get("measurement_flags") != flags
            or not isinstance(payload.get("runs"), list) or len(payload["runs"]) != len(runs)
            or not isinstance(payload.get("roi_order"), list)
            or payload["roi_order"] != [{"id": item["id"], "name": item["name"],
                "saved_indices": item["indices"], "roi": item["roi"]} for item in selected["items"]]):
        raise ValueError("Multi Measure 固定 Fiji 结果与提交契约不一致。")
    lengths = {axis["name"]: axis["length"] for axis in axes}
    channels, slices = lengths.get("Channel", 1), lengths.get("Z", 1)
    mapping = [{"stack_index": index + 1, "C": index % channels,
                "Z": (index // channels) % slices, "T": index // (channels * slices)}
               for index in range(stack_planes)]
    current_index = (plane.get("T", 0) * slices + plane.get("Z", 0)) * channels + plane.get("C", 0) + 1
    if payload.get("stack_planes") != mapping or payload.get("current_stack_index") != current_index:
        raise ValueError("Multi Measure 线性平面映射与源图不一致。")
    expected_by_layout = {True: 0, False: 0}
    rows_by_layout = {True: [], False: []}
    for options, table in zip(runs, payload["runs"]):
        expected = (stack_planes if options["measure_all"] else 1)
        if not options["one_row_per_slice"]:
            expected *= len(selected_roi_ids)
        previous = expected_by_layout[options["one_row_per_slice"]] if options["append_results"] else 0
        expected_by_layout[options["one_row_per_slice"]] = previous + expected
        if (table.get("options") != options or table.get("row_count") != previous + expected
                or table.get("new_row_start") != previous or table.get("new_row_count") != expected
                or not isinstance(table.get("headings"), list)
                or not isinstance(table.get("rows"), list)
                or len(table["rows"]) != table["row_count"]):
            raise ValueError("Multi Measure 原生表格行数或运行选项不一致。")
        headings = table["headings"]
        metrics = ["Area", "Mean", "Min", "Max"]
        metrics += [label for flag, labels in (("std_dev", ["StdDev"]), ("median", ["Median"]),
            ("mode", ["Mode"]), ("integrated_density", ["IntDen", "RawIntDen"])) if flag in flags for label in labels]
        required = {f"{metric}({item['name']})" for metric in metrics for item in selected["items"]} if options["one_row_per_slice"] else set(metrics)
        layout_key = options["one_row_per_slice"]
        if previous and table["rows"][:previous] != rows_by_layout[layout_key]:
            raise ValueError("Multi Measure 追加结果改变了此前原生表格。")
        rows_by_layout[layout_key] = table["rows"]
        if (table.get("layout") != ("one_row_per_slice" if options["one_row_per_slice"] else "one_row_per_measurement")
                or not required.issubset(headings) or any(not isinstance(heading, str) for heading in headings)
                or len(headings) != len(set(headings))
                or any(not isinstance(row, dict) or set(row) != set(headings)
                       or any(type(value) not in (int, float) or not math.isfinite(value) for value in row.values())
                       for row in table["rows"])):
            raise ValueError("Multi Measure 原生列名、布局或数值无效。")
    return {**{key: value for key, value in payload.items() if key != "ok"},
            "fiji_archive_sha256": EXPECTED_SHA256}
