"""Separate vector annotations for an exact-pixel grid result."""

from __future__ import annotations

import math
import re
from typing import Any
import xml.etree.ElementTree as ET

from backend.image.montage import GridProof
from backend.image.calibration import axis_spacing


SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)
MAX_ANNOTATIONS = 32


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} 必须是有限数字。")
    return float(value)


def _color(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        raise ValueError("标注颜色必须是六位十六进制 RGB。")
    return value.lower()


def create_overlay(proof: GridProof, items: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], bytes]:
    if not isinstance(items, list) or len(items) > MAX_ANNOTATIONS:
        raise ValueError("标注最多 32 项。")
    root = ET.Element(f"{{{SVG_NS}}}svg", {
        "width": str(proof.width), "height": str(proof.height),
        "viewBox": f"0 0 {proof.width} {proof.height}",
        "role": "img", "aria-label": "BioFigure 独立图像标注层",
    })
    normalized: list[dict[str, Any]] = []
    placement_by_id = {placement.asset_id: placement for placement in proof.placements}
    for item in items:
        if not isinstance(item, dict):
            raise ValueError("标注项目必须是对象。")
        kind = item.get("kind")
        if kind in ("text", "number"):
            if set(item) != {"kind", "text", "x", "y", "font_px", "color"}:
                raise ValueError("文字或编号标注包含缺失或未知字段。")
            value = item["text"]
            if (not isinstance(value, str) or not value or len(value) > 80
                    or any(not char.isprintable() for char in value)):
                raise ValueError("标注文字为空、过长或含控制字符。")
            if kind == "number" and not re.fullmatch(r"[0-9]{1,4}", value):
                raise ValueError("编号必须为 1 至 4 位数字。")
            x = _number(item["x"], "标注 X")
            y = _number(item["y"], "标注 Y")
            font = _number(item["font_px"], "字号")
            if not (0 <= x < proof.width and 0 <= y < proof.height and 8 <= font <= 96):
                raise ValueError("文字坐标或字号超出图像范围。")
            color = _color(item["color"])
            node = ET.SubElement(root, f"{{{SVG_NS}}}text", {
                "x": f"{x:g}", "y": f"{y:g}", "fill": color,
                "font-size": f"{font:g}", "font-family": "sans-serif",
            })
            node.text = value
            normalized.append({"kind": kind, "text": value, "x": x, "y": y,
                               "font_px": font, "color": color})
        elif kind == "scale_bar":
            required = {"kind", "asset_id", "offset_x", "offset_y", "length_um",
                        "color"}
            if not required.issubset(item) or not set(item).issubset(required | {"length_px", "calibration_source", "x_um_per_pixel"}):
                raise ValueError("比例尺包含缺失或未知字段。")
            asset_id = item["asset_id"]
            if not isinstance(asset_id, str) or asset_id not in placement_by_id:
                raise ValueError("比例尺必须绑定此网格中的源图块。")
            placement = placement_by_id[asset_id]
            offset_x = _number(item["offset_x"], "比例尺 X")
            offset_y = _number(item["offset_y"], "比例尺 Y")
            length_um = _number(item["length_um"], "比例尺长度")
            calibration_source = item.get("calibration_source", "user_explicit")
            if calibration_source == "fiji_inspected_axes":
                spacing = axis_spacing(placement.source_axes, (placement.width, placement.height))
                if spacing is None:
                    raise ValueError("此图块没有可用的已核验物理标定。")
                x_um_per_pixel = spacing[0]
                if "x_um_per_pixel" in item and _number(item["x_um_per_pixel"], "X 轴标定") != x_um_per_pixel:
                    raise ValueError("比例尺标定与已核验图块不一致。")
            elif calibration_source == "user_explicit" and "x_um_per_pixel" in item:
                x_um_per_pixel = _number(item["x_um_per_pixel"], "X 轴标定")
            else:
                raise ValueError("比例尺标定来源无效或缺少手填标定。")
            if length_um <= 0 or x_um_per_pixel <= 0:
                raise ValueError("比例尺长度和 X 轴标定必须为正数。")
            length_px = length_um / x_um_per_pixel
            if ("length_px" in item and not math.isclose(_number(item["length_px"], "像素长度"),
                                                       length_px, rel_tol=0, abs_tol=1e-9)):
                raise ValueError("比例尺像素长度与输入标定不一致。")
            if (not 0 <= offset_x < placement.width or not 0 <= offset_y < placement.height
                    or not math.isfinite(length_px) or length_px < 1
                    or offset_x + length_px > placement.width):
                raise ValueError("比例尺超出其绑定图块，或短于一个像素。")
            color = _color(item["color"])
            x = placement.x + offset_x
            y = placement.y + offset_y
            ET.SubElement(root, f"{{{SVG_NS}}}line", {
                "x1": f"{x:g}", "y1": f"{y:g}", "x2": f"{x + length_px:g}",
                "y2": f"{y:g}", "stroke": color, "stroke-width": "3",
            })
            caption = ET.SubElement(root, f"{{{SVG_NS}}}text", {
                "x": f"{x + length_px / 2:g}", "y": f"{max(0, y - 5):g}",
                "text-anchor": "middle", "fill": color, "font-size": "12",
                "font-family": "sans-serif",
            })
            caption.text = f"{length_um:g} µm"
            normalized.append({"kind": kind, "asset_id": asset_id,
                               "offset_x": offset_x, "offset_y": offset_y,
                               "length_um": length_um,
                               "x_um_per_pixel": x_um_per_pixel,
                               "length_px": length_px, "color": color,
                               "calibration_source": calibration_source})
        else:
            raise ValueError("未知图像标注类型。")
    return normalized, ET.tostring(root, encoding="utf-8", xml_declaration=True)
