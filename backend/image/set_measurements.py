"""Bounded, source-bound access to all area-ROI ImageJ1 Set Measurements options."""

from __future__ import annotations

from math import isfinite
from threading import Event
from typing import Any
from uuid import uuid4

from backend.image.assets import ImageAsset, verify_asset_bytes
from backend.image.fiji_process import native_set_measurements
from backend.image.selection import ImageSelection, build_plane_selection, build_selection, linear_stack_index, stack_plane_count
from scripts.prepare_fiji_runtime import EXPECTED_SHA256


MEASUREMENT_OPTIONS = (
    "area", "mean", "std_dev", "mode", "min_max", "centroid", "center_of_mass",
    "perimeter", "bounding_rectangle", "fit_ellipse", "shape_descriptors", "feret",
    "integrated_density", "median", "skewness", "kurtosis", "area_fraction",
    "stack_position", "limit_to_threshold", "display_label", "invert_y",
    "scientific_notation", "add_to_overlay", "nan_empty_cells",
)


# Verified against constants of the pinned ij-1.54p JAR, not a web runtime.
MEASUREMENT_BITS = dict(zip(MEASUREMENT_OPTIONS, (
    1, 2, 4, 8, 16, 32, 64, 128, 512, 2048, 8192, 16384, 32768,
    65536, 131072, 262144, 524288, 1048576, 256, 1024, 4096, 2097152, 4194304, 8388608,
), strict=True))


def validate_native_settings(settings: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(settings, dict) or set(settings) != {"measurements", "decimal_places", "threshold"}:
        raise ValueError("Set Measurements 须完整提供选项、显示精度与阈值。")
    options = settings["measurements"]
    if (not isinstance(options, list) or any(not isinstance(value, str) for value in options)
            or len(options) != len(set(options)) or any(value not in MEASUREMENT_OPTIONS for value in options)):
        raise ValueError("Set Measurements 选项无效或重复。")
    options = [value for value in MEASUREMENT_OPTIONS if value in options]
    precision = settings["decimal_places"]
    if type(precision) is not int or not 0 <= precision <= 9:
        raise ValueError("ImageJ1 显示小数位须为 0–9。")
    threshold = settings["threshold"]
    if threshold is not None:
        if (not isinstance(threshold, dict) or set(threshold) != {"min", "max"}
                or any(type(threshold[key]) not in (int, float) or not isfinite(threshold[key])
                       for key in ("min", "max")) or threshold["min"] > threshold["max"]):
            raise ValueError("阈值须为有限的 min/max，且 min 不大于 max。")
    if "limit_to_threshold" in options and threshold is None:
        raise ValueError("勾选 Limit to threshold 须显式提供阈值。")
    return {"measurements": options, "decimal_places": precision,
            "threshold": dict(threshold) if threshold is not None else None}


def validate_measurement_redirect(asset: ImageAsset, axes: list[dict[str, Any]], plane: dict[str, int],
                                  redirect_asset: ImageAsset | None,
                                  redirect_plane: dict[str, int] | None) -> dict | None:
    if redirect_asset is None:
        if redirect_plane is not None:
            raise ValueError("未选择重定向来源时不得提供目标平面。")
        return None
    if redirect_asset.id == asset.id or redirect_asset.path == asset.path:
        raise ValueError("重定向目标须为第二个来源资产。")
    target_axes, target_plane, tw, th = build_plane_selection(redirect_asset, redirect_plane)
    _, _, width, height = build_plane_selection(asset, plane)
    if (tw, th) != (width, height):
        raise ValueError("重定向图像 X/Y 尺寸须与主源相同。")
    count, target_count = stack_plane_count(axes), stack_plane_count(target_axes)
    if target_count not in (1, count) or count > 64:
        raise ValueError("重定向目标必须单平面或与主源有相同线性栈长度，最多 64 页。")
    if target_count > 1 and linear_stack_index(axes, plane) != linear_stack_index(target_axes, target_plane):
        raise ValueError("重定向栈须选择与主源相同的线性平面。")
    return {"id": redirect_asset.id, "path": str(redirect_asset.path),
            "sha256": redirect_asset.sha256, "bytes": redirect_asset.bytes,
            "axes": target_axes, "plane": target_plane}


def prepare_measurement_redirect(asset: ImageAsset, axes: list[dict[str, Any]], plane: dict[str, int],
                                 redirect_asset: ImageAsset | None,
                                 redirect_plane: dict[str, int] | None, cancel: Event) -> dict | None:
    redirect = validate_measurement_redirect(asset, axes, plane, redirect_asset, redirect_plane)
    if redirect_asset is not None:
        verify_asset_bytes(redirect_asset, cancel)
    return redirect


def run_native_set_measurements(
    asset: ImageAsset,
    selection: ImageSelection,
    settings: dict[str, Any],
    redirect_asset: ImageAsset | None,
    redirect_plane: dict[str, int] | None,
    cancel: Event,
) -> dict[str, Any]:
    if not isinstance(selection, ImageSelection):
        raise ValueError("须提供已核验的面积 ROI 与平面选择。")
    checked = build_selection(asset, selection.indices,
                              None if selection.roi.get("kind") == "full" else selection.roi)
    if checked.public() != selection.public():
        raise ValueError("选择与当前固定 Fiji 来源轴不一致。")
    request_settings = validate_native_settings(settings)
    options = request_settings["measurements"]
    redirect = prepare_measurement_redirect(asset, selection.source_axes, selection.indices,
                                            redirect_asset, redirect_plane, cancel)
    payload = native_set_measurements(asset, uuid4().hex, cancel, selection.public(), request_settings, redirect)
    if (payload.get("selection") != selection.public() or payload.get("settings") != request_settings
            or payload.get("source_sha256") != asset.sha256
            or payload.get("redirect_sha256") != (redirect_asset.sha256 if redirect_asset else None)
            or payload.get("redirect_plane") != (redirect["plane"] if redirect else None)
            or type(payload.get("row_count")) is not int or payload.get("row_count") != 1):
        raise ValueError("固定 ImageJ1 Measure 结果与来源或设置不一致。")
    headings, row = payload.get("headings"), payload.get("row")
    if (not isinstance(headings, list) or len(headings) > 128
            or any(not isinstance(heading, str) for heading in headings) or len(headings) != len(set(headings))
            or not isinstance(row, dict) or set(row) != set(headings)
            or any(value is not None and (type(value) not in (int, float) or not isfinite(value))
                   for value in row.values())):
        raise ValueError("固定 ImageJ1 Measure 结果列或数值无效。")
    source_index = linear_stack_index(selection.source_axes, selection.indices)
    sampled_index = linear_stack_index(redirect["axes"], redirect["plane"]) if redirect else source_index
    non_finite = payload.get("non_finite_headings")
    before, after = payload.get("overlay_count_before"), payload.get("overlay_count")
    if (type(payload.get("measurement_bits")) is not int
            or payload["measurement_bits"] != sum(MEASUREMENT_BITS[value] for value in options)
            or type(payload.get("source_stack_index")) is not int or type(payload.get("sampled_stack_index")) is not int
            or payload.get("source_stack_index") != source_index or payload.get("sampled_stack_index") != sampled_index
            or not isinstance(non_finite, list) or any(not isinstance(value, str) for value in non_finite)
            or len(non_finite) != len(set(non_finite)) or set(non_finite) != {key for key, value in row.items() if value is None}
            or type(before) is not int or type(after) is not int or before < 0
            or after != before + (1 if "add_to_overlay" in options else 0)
            or not isinstance(payload.get("displayed_row"), str)
            or (payload.get("label") is not None and not isinstance(payload["label"], str))):
        raise ValueError("固定 Measure 的设置位、平面、空值或 overlay 行为不一致。")
    return {**{key: value for key, value in payload.items() if key != "ok"},
            "fiji_archive_sha256": EXPECTED_SHA256}
