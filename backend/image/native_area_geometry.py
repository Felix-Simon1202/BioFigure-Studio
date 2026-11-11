"""Bounded native ImageJ1 area ROI geometry; the shared runner is injected by integration."""

from __future__ import annotations

from math import ceil, floor, hypot, isclose, isfinite
import struct
from threading import Event
from typing import Any, Callable
from uuid import uuid4

from backend.image.assets import ImageAsset, verify_asset_bytes
from backend.image.roi_path import validate_shape_path
from backend.image.selection import build_plane_selection, linear_stack_index, stack_plane_count
from backend.image.set_measurements import (MEASUREMENT_BITS, prepare_measurement_redirect,
                                            validate_native_settings)
from scripts.prepare_fiji_runtime import EXPECTED_SHA256


MAX_PIXELS = 1_000_000
SIMPLE_KINDS = {"rectangle", "oval", "polygon", "freehand", "traced",
                "spline_polygon", "rotated_rectangle", "rotated_ellipse"}
TYPE_CODES = {"rectangle": 0, "oval": 1, "polygon": 2, "freehand": 3,
              "traced": 4, "spline_polygon": 2, "rotated_rectangle": 2,
              "rotated_ellipse": 3, "shape": 9}
TYPE_CODES["shape_path"] = 9
CLASSES = {"rectangle": "ij.gui.Roi", "oval": "ij.gui.OvalRoi",
           "polygon": "ij.gui.PolygonRoi", "freehand": "ij.gui.PolygonRoi",
           "traced": "ij.gui.PolygonRoi", "spline_polygon": "ij.gui.PolygonRoi",
           "rotated_rectangle": "ij.gui.RotatedRectRoi", "rotated_ellipse": "ij.gui.EllipseRoi",
           "shape": "ij.gui.ShapeRoi"}
CLASSES["shape_path"] = "ij.gui.ShapeRoi"


def _number(value: Any) -> float:
    if type(value) not in (int, float) or not isfinite(value):
        raise ValueError("ROI 几何参数须为有限数值。")
    return float(value)


def _intersect(a: tuple[float, float], b: tuple[float, float],
               c: tuple[float, float], d: tuple[float, float]) -> bool:
    def turn(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    u, v, w, z = turn(a, b, c), turn(a, b, d), turn(c, d, a), turn(c, d, b)
    return ((u == 0 and min(a[0], b[0]) <= c[0] <= max(a[0], b[0])
             and min(a[1], b[1]) <= c[1] <= max(a[1], b[1]))
            or (v == 0 and min(a[0], b[0]) <= d[0] <= max(a[0], b[0])
                and min(a[1], b[1]) <= d[1] <= max(a[1], b[1]))
            or (w == 0 and min(c[0], d[0]) <= a[0] <= max(c[0], d[0])
                and min(c[1], d[1]) <= a[1] <= max(c[1], d[1]))
            or (z == 0 and min(c[0], d[0]) <= b[0] <= max(c[0], d[0])
                and min(c[1], d[1]) <= b[1] <= max(c[1], d[1]))
            or (u > 0) != (v > 0) and (w > 0) != (z > 0))


def _simple(roi: Any, width: int, height: int) -> tuple[dict[str, Any], tuple[float, float, float, float]]:
    if (not isinstance(roi, dict) or roi.get("version") != "1.0"
            or not isinstance(roi.get("kind"), str) or roi["kind"] not in SIMPLE_KINDS):
        raise ValueError("面积 ROI 须使用 1.0 原生类型契约。")
    kind = roi["kind"]
    if kind in {"rectangle", "oval"}:
        if set(roi) != {"version", "kind", "x", "y", "width", "height"}:
            raise ValueError("矩形/椭圆参数不匹配。")
        x, y, w, h = (_number(roi[key]) for key in ("x", "y", "width", "height"))
        if w <= 0 or h <= 0:
            raise ValueError("ROI 尺寸须为正。")
        checked = {"version": "1.0", "kind": kind, "x": x, "y": y, "width": w, "height": h}
        box = (x, y, x + w, y + h)
    elif kind in {"rotated_rectangle", "rotated_ellipse"}:
        extra = "rect_width" if kind == "rotated_rectangle" else "aspect_ratio"
        if set(roi) != {"version", "kind", "x1", "y1", "x2", "y2", extra}:
            raise ValueError("旋转 ROI 参数不匹配。")
        x1, y1, x2, y2, value = (_number(roi[key]) for key in ("x1", "y1", "x2", "y2", extra))
        length = hypot(x2 - x1, y2 - y1)
        if length <= 0 or (kind == "rotated_rectangle" and value <= 0) or (
                kind == "rotated_ellipse" and not 0 < value <= 1):
            raise ValueError("旋转 ROI 轴线、宽度或长短轴比无效。")
        if kind == "rotated_rectangle":
            offset_x, offset_y = abs(y2 - y1) * value / (2 * length), abs(x2 - x1) * value / (2 * length)
            box = (min(x1, x2) - offset_x, min(y1, y2) - offset_y,
                   max(x1, x2) + offset_x, max(y1, y2) + offset_y)
        else:
            # Exact axis-aligned extents of the rotated major/minor ellipse axes.
            radius_x = hypot(x2 - x1, (y2 - y1) * value) / 2
            radius_y = hypot(y2 - y1, (x2 - x1) * value) / 2
            cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
            box = (cx - radius_x, cy - radius_y, cx + radius_x, cy + radius_y)
        checked = {"version": "1.0", "kind": kind, "x1": x1, "y1": y1,
                   "x2": x2, "y2": y2, extra: value}
    else:
        keys = {"version", "kind", "points"} | ({"evaluation_points"} if kind == "spline_polygon" else set())
        if set(roi) != keys or not isinstance(roi["points"], list) or not 3 <= len(roi["points"]) <= 64:
            raise ValueError("原生面积路径须有 3–64 个顶点。")
        points = []
        for point in roi["points"]:
            if not isinstance(point, dict) or set(point) != {"x", "y"}:
                raise ValueError("顶点须为 x/y 坐标。")
            x, y = _number(point["x"]), _number(point["y"])
            if kind == "traced" and (not x.is_integer() or not y.is_integer()):
                raise ValueError("TRACED_ROI 须使用整数追踪节点。")
            points.append({"x": x, "y": y})
        tuples = [(p["x"], p["y"]) for p in points]
        if len(set(tuples)) != len(tuples):
            raise ValueError("面积路径顶点不可重复。")
        signed = sum(a[0] * b[1] - b[0] * a[1]
                     for a, b in zip(tuples, tuples[1:] + tuples[:1]))
        if abs(signed) < 1e-8:
            raise ValueError("面积路径不可退化为线。")
        n = len(tuples)
        for i in range(n):
            for j in range(i + 2, n):
                if (i == 0 and j == n - 1):
                    continue
                if _intersect(tuples[i], tuples[(i + 1) % n], tuples[j], tuples[(j + 1) % n]):
                    raise ValueError("本版拒绝自交面积路径。")
        checked = {"version": "1.0", "kind": kind, "points": points}
        if kind == "spline_polygon":
            count = roi["evaluation_points"]
            if type(count) is not int or not 8 <= count <= 512:
                raise ValueError("样条拟合点数须为 8–512。")
            checked["evaluation_points"] = count
        box = (min(x for x, _ in tuples), min(y for _, y in tuples),
               max(x for x, _ in tuples), max(y for _, y in tuples))
    if (box[0] < 0 or box[1] < 0 or box[2] > width or box[3] > height
            or (ceil(box[2]) - floor(box[0])) * (ceil(box[3]) - floor(box[1])) > MAX_PIXELS):
        raise ValueError("ROI 超出源图或 100 万候选像素上限。")
    return checked, box


def validate_area_roi(roi: Any, width: int, height: int) -> dict[str, Any]:
    if isinstance(roi, dict) and roi.get("kind") == "shape_path":
        if set(roi) != {"version", "kind", "path"} or roi.get("version") != "1.0":
            raise ValueError("原生复合路径参数不匹配。")
        return {"version": "1.0", "kind": "shape_path", "path": validate_shape_path(roi["path"], width, height)}
    if isinstance(roi, dict) and roi.get("kind") == "shape":
        if (set(roi) != {"version", "kind", "operation", "operands"} or roi.get("version") != "1.0"
                or not isinstance(roi["operation"], str) or roi["operation"] not in {"union", "intersection", "xor", "subtract"}
                or not isinstance(roi["operands"], list) or not 2 <= len(roi["operands"]) <= 8):
            raise ValueError("ShapeRoi 组合参数无效。")
        checked, boxes = [], []
        for item in roi["operands"]:
            normalized, box = _simple(item, width, height)
            checked.append(normalized)
            boxes.append(box)
        x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
        x1, y1 = max(b[2] for b in boxes), max(b[3] for b in boxes)
        if (ceil(x1) - floor(x0)) * (ceil(y1) - floor(y0)) > MAX_PIXELS:
            raise ValueError("组合 ROI 超过 100 万候选像素。")
        return {"version": "1.0", "kind": "shape", "operation": roi["operation"], "operands": checked}
    return _simple(roi, width, height)[0]


def run_native_area_geometry_measure(
    asset: ImageAsset, current_plane: dict[str, int], roi: dict[str, Any],
    settings: dict[str, Any], redirect_asset: ImageAsset | None,
    redirect_plane: dict[str, int] | None, cancel: Event,
    runner: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    axes, plane, width, height = build_plane_selection(asset, current_plane)
    if stack_plane_count(axes) > 64:
        raise ValueError("面积 ROI 测量最多支持 64 个线性平面。")
    checked_roi = validate_area_roi(roi, width, height)
    checked_settings = validate_native_settings(settings)
    verify_asset_bytes(asset, cancel)
    redirect = prepare_measurement_redirect(asset, axes, plane, redirect_asset, redirect_plane, cancel)
    expected_bits = sum(MEASUREMENT_BITS[item] for item in checked_settings["measurements"])
    payload = runner(asset, uuid4().hex, cancel, axes, plane, checked_roi,
                     checked_settings, expected_bits, redirect)
    native = payload.get("native_roi")
    if (payload.get("source_sha256") != asset.sha256
            or payload.get("redirect_sha256") != (redirect_asset.sha256 if redirect_asset else None)
            or payload.get("current_plane") != plane or payload.get("roi") != checked_roi
            or payload.get("redirect_plane") != (redirect["plane"] if redirect else None)
            or payload.get("settings") != checked_settings
            or type(payload.get("measurement_bits")) is not int or payload.get("measurement_bits") != expected_bits
            or type(payload.get("source_stack_index")) is not int
            or payload.get("source_stack_index") != linear_stack_index(axes, plane)
            or type(payload.get("sampled_stack_index")) is not int
            or payload.get("sampled_stack_index") != (linear_stack_index(redirect["axes"], redirect["plane"])
                                                        if redirect else linear_stack_index(axes, plane))
            or not isinstance(native, dict) or native.get("class_name") != CLASSES[checked_roi["kind"]]
            or type(native.get("type_code")) is not int or native.get("type_code") != TYPE_CODES[checked_roi["kind"]]
            or type(payload.get("row_count")) is not int or payload.get("row_count") != 1):
        raise ValueError("固定 ImageJ1 面积结果未保留来源、类型、设置或平面。")
    kind = checked_roi["kind"]
    if (kind in {"rectangle", "oval", "rotated_rectangle", "rotated_ellipse"}
            and native.get("subpixel") is not True):
        raise ValueError("固定 ImageJ1 未保留亚像素面积 ROI。")
    if native.get("spline_fit") is not (kind == "spline_polygon"):
        raise ValueError("固定 ImageJ1 样条状态与请求不一致。")
    outline = native.get("float_outline")
    if (not isinstance(outline, list) or not 3 <= len(outline) <= 4096
            or any(not isinstance(p, dict) or set(p) != {"x", "y"}
                   or any(type(p[k]) not in (int, float) or not isfinite(p[k])
                          or not -0.01 <= p[k] <= (width if k == "x" else height) + 0.01
                          for k in ("x", "y"))
                   for p in outline)):
        raise ValueError("固定 ImageJ1 未返回完整有限浮点轮廓。")
    bounds = native.get("bounds")
    if (not isinstance(bounds, dict) or set(bounds) != {"x", "y", "width", "height"}
            or any(type(bounds[key]) not in (int, float) or not isfinite(bounds[key]) for key in bounds)
            or bounds["x"] < 0 or bounds["y"] < 0 or bounds["width"] <= 0 or bounds["height"] <= 0
            or bounds["x"] + bounds["width"] > width or bounds["y"] + bounds["height"] > height
            or bounds["width"] * bounds["height"] > MAX_PIXELS):
        raise ValueError("固定 ImageJ1 面积 ROI 原生包围盒无效。")
    if kind == "spline_polygon" and len(outline) != checked_roi["evaluation_points"]:
        raise ValueError("固定 ImageJ1 样条拟合点数未保留。")
    if kind in {"rectangle", "oval"}:
        actual_bounds = native.get("float_bounds")
        if (not isinstance(actual_bounds, dict) or set(actual_bounds) != {"x", "y", "width", "height"}
                or any(type(actual_bounds[key]) not in (int, float) or not isfinite(actual_bounds[key])
                       or not isclose(actual_bounds[key], checked_roi[key], rel_tol=0, abs_tol=1e-6)
                       for key in actual_bounds)):
            raise ValueError("固定 ImageJ1 未保留矩形/椭圆的实际亚像素范围。")
    if kind in {"polygon", "freehand", "traced"}:
        if len(outline) != len(checked_roi["points"]):
            raise ValueError("固定 ImageJ1 面积节点数未保留。")
        for actual, requested in zip(outline, checked_roi["points"], strict=True):
            for key in ("x", "y"):
                expected = struct.unpack("!f", struct.pack("!f", requested[key]))[0]
                if not isclose(actual[key], expected, rel_tol=0, abs_tol=max(1e-6, abs(expected) * 1.2e-7)):
                    raise ValueError("固定 ImageJ1 未保留实际原生浮点节点。")
    if kind in {"rotated_rectangle", "rotated_ellipse"}:
        params = native.get("native_params")
        extra = "rect_width" if kind == "rotated_rectangle" else "aspect_ratio"
        expected = [checked_roi[key] for key in ("x1", "y1", "x2", "y2", extra)]
        if (not isinstance(params, list) or len(params) != 5
                or any(type(value) not in (int, float) or not isfinite(value)
                       or not isclose(value, goal, abs_tol=1e-4, rel_tol=0)
                       for value, goal in zip(params, expected))):
            raise ValueError("固定 ImageJ1 未保留旋转形状参数。")
    if kind in {"shape", "shape_path"} and (not isinstance(native.get("shape_path"), list)
                            or not native["shape_path"] or len(native["shape_path"]) > 4096
                            or any(type(value) not in (int, float) or not isfinite(value)
                                   for value in native["shape_path"])):
        raise ValueError("固定 ImageJ1 未保留 ShapeRoi 复合路径。")
    if kind == "shape_path":
        expected = [struct.unpack("!f", struct.pack("!f", value))[0] for value in checked_roi["path"]]
        if len(expected) != len(native["shape_path"]) or any(not isclose(actual, value, rel_tol=0, abs_tol=1e-5)
                for actual, value in zip(native["shape_path"], expected)):
            raise ValueError("原生复合路径在测量时被改变。")
    headings, row = payload.get("headings"), payload.get("row")
    invalid = payload.get("non_finite_headings")
    if (not isinstance(headings, list) or len(headings) > 128
            or any(not isinstance(x, str) for x in headings) or len(headings) != len(set(headings)) or not isinstance(row, dict)
            or set(row) != set(headings) or any(v is not None and (type(v) not in (int, float) or not isfinite(v))
                                             for v in row.values())
            or not isinstance(invalid, list) or any(not isinstance(value, str) for value in invalid)
            or len(invalid) != len(set(invalid))
            or set(invalid) != {key for key, value in row.items() if value is None}
            or type(payload.get("overlay_count_before")) is not int
            or payload["overlay_count_before"] < 0 or type(payload.get("overlay_count")) is not int
            or payload.get("overlay_count") != payload["overlay_count_before"]
            + (1 if "add_to_overlay" in checked_settings["measurements"] else 0)
            or not isinstance(payload.get("displayed_row"), str)
            or (payload.get("label") is not None and not isinstance(payload["label"], str))):
        raise ValueError("固定 ImageJ1 面积结果列、数值或 overlay 不一致。")
    for name in ("source_calibration", "sampled_calibration"):
        calibration = payload.get(name)
        if (not isinstance(calibration, dict)
                or any(type(calibration.get(key)) not in (int, float)
                       or not isfinite(calibration[key]) or calibration[key] <= 0
                       for key in ("pixel_width", "pixel_height"))
                or any(not isinstance(calibration.get(key), str)
                       for key in ("unit", "value_unit"))):
            raise ValueError("固定 ImageJ1 标定摘要无效。")
    return {**{key: value for key, value in payload.items() if key != "ok"},
            "fiji_archive_sha256": EXPECTED_SHA256}
