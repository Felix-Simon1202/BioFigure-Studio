"""Fixed ImageJ1 Measure for line, angle and point ROI types."""

from __future__ import annotations

from math import hypot, isclose, isfinite
import struct
from threading import Event
from typing import Any
from uuid import uuid4

from backend.image.assets import ImageAsset
from backend.image.fiji_process import native_non_area_measure
from backend.image.selection import build_plane_selection, linear_stack_index, stack_plane_count
from backend.image.set_measurements import MEASUREMENT_BITS, validate_native_settings, prepare_measurement_redirect
from scripts.prepare_fiji_runtime import EXPECTED_SHA256


LINE_KINDS = {"line", "polyline", "freeline"}
POINT_KINDS = {"point", "multipoint"}
MAX_POINTS = 64
MAX_PLANES = 64
MAX_BOUNDS_PIXELS = 1_000_000
NATIVE_TYPE_CODES = {"line": 5, "polyline": 6, "freeline": 7, "angle": 8, "point": 10, "multipoint": 10}


def validate_non_area_roi(roi: dict[str, Any], width: int, height: int, stack_count: int) -> dict[str, Any]:
    if not isinstance(roi, dict) or roi.get("version") != "1.0":
        raise ValueError("非面积 ROI 须使用 1.0 版本契约。")
    kind = roi.get("kind")
    if not isinstance(kind, str) or kind not in LINE_KINDS | POINT_KINDS | {"angle"}:
        raise ValueError("未支持的非面积 ROI 类型。")
    keys = {"version", "kind", "points"}
    if kind in LINE_KINDS:
        keys.add("stroke_width")
    if kind in POINT_KINDS:
        keys |= {key for key in ("point_positions", "point_counters") if key in roi}
    if set(roi) != keys:
        raise ValueError("ROI 类型参数不匹配。")
    points = roi.get("points")
    minimum = 1 if kind == "point" else 3 if kind == "angle" else 2
    maximum = 1 if kind == "point" else 3 if kind == "angle" else 2 if kind == "line" else MAX_POINTS
    if not isinstance(points, list) or not minimum <= len(points) <= maximum:
        raise ValueError("ROI 点数不符合原生类型范围。")
    normalized_points = []
    for point in points:
        if (not isinstance(point, dict) or set(point) != {"x", "y"}
                or any(type(point[key]) not in (int, float) or not isfinite(point[key])
                       for key in ("x", "y"))
                or not 0 <= point["x"] < width or not 0 <= point["y"] < height):
            raise ValueError("ROI 坐标须为图像范围内的有限浮点数。")
        normalized_points.append({"x": float(point["x"]), "y": float(point["y"])})
    if kind in LINE_KINDS | {"angle"}:
        if not any(hypot(b["x"] - a["x"], b["y"] - a["y"]) > 0
                   for a, b in zip(normalized_points, normalized_points[1:])):
            raise ValueError("线或角 ROI 不可为零长度。")
        if kind == "angle" and any(a == b for a, b in zip(normalized_points, normalized_points[1:])):
            raise ValueError("角的相邻顶点须互异。")
    span_x = max(p["x"] for p in normalized_points) - min(p["x"] for p in normalized_points)
    span_y = max(p["y"] for p in normalized_points) - min(p["y"] for p in normalized_points)
    padding = 32 if kind in LINE_KINDS else 1
    if (span_x + padding) * (span_y + padding) > MAX_BOUNDS_PIXELS:
        raise ValueError("ROI 包围范围超过 100 万候选像素。")
    checked: dict[str, Any] = {"version": "1.0", "kind": kind, "points": normalized_points}
    if kind in LINE_KINDS:
        stroke = roi["stroke_width"]
        if type(stroke) not in (int, float) or not isfinite(stroke) or not 1 <= stroke <= 32:
            raise ValueError("线宽须为 1–32 的有限像素数。")
        checked["stroke_width"] = float(stroke)
    if kind in POINT_KINDS:
        for key, maximum_value in (("point_positions", stack_count), ("point_counters", 99)):
            values = roi.get(key, [0] * len(points))
            if (not isinstance(values, list) or len(values) != len(points)
                    or any(type(value) is not int or not 0 <= value <= maximum_value for value in values)):
                raise ValueError("逐点栈位置或计数无效。")
            checked[key] = values
    return checked


def run_native_non_area_measure(
    asset: ImageAsset, current_plane: dict[str, int], roi: dict[str, Any],
    settings: dict[str, Any], redirect_asset: ImageAsset | None,
    redirect_plane: dict[str, int] | None, cancel: Event,
) -> dict[str, Any]:
    axes, plane, width, height = build_plane_selection(asset, current_plane)
    stack_count = stack_plane_count(axes)
    if stack_count > MAX_PLANES:
        raise ValueError("非面积 ROI 测量最多支持 64 个线性平面。")
    checked_roi = validate_non_area_roi(roi, width, height, stack_count)
    checked_settings = validate_native_settings(settings)
    redirect = prepare_measurement_redirect(asset, axes, plane, redirect_asset, redirect_plane, cancel)
    payload = native_non_area_measure(asset, uuid4().hex, cancel, axes, plane, checked_roi,
                                      checked_settings, redirect)
    expected_rows = len(checked_roi["points"]) if checked_roi["kind"] in POINT_KINDS else 1
    if (payload.get("source_sha256") != asset.sha256
            or payload.get("redirect_sha256") != (redirect_asset.sha256 if redirect_asset else None)
            or payload.get("current_plane") != plane or payload.get("roi") != checked_roi
            or payload.get("settings") != checked_settings or type(payload.get("row_count")) is not int
            or payload.get("row_count") != expected_rows
            or payload.get("redirect_plane") != (redirect["plane"] if redirect else None)
            or not isinstance(payload.get("headings"), list)
            or not isinstance(payload.get("rows"), list) or len(payload["rows"]) != expected_rows):
        raise ValueError("非面积原生结果与输入或行数不一致。")
    native = payload.get("native_roi")
    expected_class = ("ij.gui.Line" if checked_roi["kind"] == "line" else
                      "ij.gui.PointRoi" if checked_roi["kind"] in POINT_KINDS else
                      "ij.gui.PolygonRoi")
    if (not isinstance(native, dict) or native.get("class_name") != expected_class
            or native.get("subpixel") is not True or type(native.get("type_code")) is not int
            or native.get("type_code") != NATIVE_TYPE_CODES[checked_roi["kind"]]
            or type(payload.get("source_stack_index")) is not int
            or payload.get("source_stack_index") != linear_stack_index(axes, plane)):
        raise ValueError("固定 ImageJ1 未保留请求的原生 ROI 类型或平面。")
    if checked_roi["kind"] in LINE_KINDS and (type(native.get("stroke_width")) not in (int, float)
            or not isclose(native["stroke_width"], checked_roi["stroke_width"], abs_tol=1e-5)):
        raise ValueError("固定 ImageJ1 未保留请求的线宽。")
    if checked_roi["kind"] in POINT_KINDS and (
            native.get("point_positions") != checked_roi["point_positions"]
            or native.get("point_counters") != checked_roi["point_counters"]):
        raise ValueError("固定 ImageJ1 未保留逐点位置或计数。")
    sampled_index = payload.get("sampled_stack_index")
    sampled_count = stack_plane_count(redirect["axes"]) if redirect else stack_count
    expected_index = linear_stack_index(redirect["axes"], redirect["plane"]) if redirect else linear_stack_index(axes, plane)
    if (type(sampled_index) is not int or not 1 <= sampled_index <= sampled_count
            or (checked_roi["kind"] not in POINT_KINDS and sampled_index != expected_index)):
        raise ValueError("非面积测量的采样栈位置无效。")
    points = native.get("points")
    if not isinstance(points, list) or len(points) != len(checked_roi["points"]):
        raise ValueError("原生 ROI 顶点数量与请求不符。")
    for actual, requested in zip(points, checked_roi["points"], strict=True):
        if not isinstance(actual, dict) or set(actual) != {"x", "y"}:
            raise ValueError("原生 ROI 顶点结构不完整。")
        for key in ("x", "y"):
            value = actual[key]
            expected = requested[key] if checked_roi["kind"] == "line" else struct.unpack("!f", struct.pack("!f", requested[key]))[0]
            tolerance = 1e-12 if checked_roi["kind"] == "line" else max(1e-6, abs(expected) * 1.2e-7)
            if type(value) not in (int, float) or not isfinite(value) or not isclose(value, expected, rel_tol=0, abs_tol=tolerance):
                raise ValueError("原生 ROI 坐标与原生数值精度下的请求不一致。")
    if type(payload.get("measurement_bits")) is not int or payload["measurement_bits"] != sum(
            MEASUREMENT_BITS[name] for name in checked_settings["measurements"]):
        raise ValueError("原生测量位与请求不一致。")
    before, after = payload.get("overlay_count_before"), payload.get("overlay_count")
    if (type(before) is not int or before < 0 or type(after) is not int
            or after != before + (1 if "add_to_overlay" in checked_settings["measurements"] else 0)):
        raise ValueError("原生 overlay 未按设置执行。")
    labels, displayed, non_finite = (payload.get(key) for key in ("labels", "displayed_rows", "non_finite_headings"))
    if (not isinstance(labels, list) or len(labels) != expected_rows
            or any(label is not None and not isinstance(label, str) for label in labels)
            or not isinstance(displayed, list) or len(displayed) != expected_rows
            or any(not isinstance(row, str) for row in displayed)
            or not isinstance(non_finite, list) or len(non_finite) != expected_rows):
        raise ValueError("原生行标签、显示文本或非有限值记录不完整。")
    headings = payload["headings"]
    if len(headings) > 128 or any(not isinstance(name, str) for name in headings) or len(headings) != len(set(headings)):
        raise ValueError("非面积原生列名重复或无效。")
    for index, row in enumerate(payload["rows"]):
        if (not isinstance(row, dict) or set(row) != set(headings)
                or any(value is not None and (type(value) not in (int, float) or not isfinite(value))
                       for value in row.values())):
            raise ValueError("非面积原生结果数值或列不一致。")
        invalid = non_finite[index]
        if (not isinstance(invalid, list) or any(not isinstance(value, str) for value in invalid)
                or len(invalid) != len(set(invalid)) or set(invalid) != {key for key, value in row.items() if value is None}):
            raise ValueError("非面积原生结果的空值标记不一致。")
    return {**{key: value for key, value in payload.items() if key != "ok"},
            "fiji_archive_sha256": EXPECTED_SHA256}
