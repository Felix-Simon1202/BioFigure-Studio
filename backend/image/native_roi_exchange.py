"""Source-bound, allocation-bounded ImageJ1 ROI file and ZIP exchange (v2)."""

from __future__ import annotations

from base64 import b64decode
from hashlib import sha256
from binascii import Error as Base64Error
from io import BytesIO
import json
from math import isfinite
import re
import struct
from threading import Event
from typing import Any, Callable
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile

from backend.image.assets import ImageAsset, verify_asset_bytes
from backend.image.roi_path import validate_shape_path as _shape_path
from backend.image.native_area_geometry import CLASSES, TYPE_CODES, validate_area_roi
from backend.image.non_area_measure import NATIVE_TYPE_CODES, validate_non_area_roi
from backend.image.selection import build_plane_selection, stack_plane_count


MAX_ITEMS = 64
MAX_ROI_BYTES = 32 * 1024
MAX_ARCHIVE_BYTES = 1024 * 1024
MANIFEST = "biofigure-source.json"
AREA_KINDS = {"rectangle", "oval", "polygon", "freehand", "traced", "spline_polygon",
              "rotated_rectangle", "rotated_ellipse", "shape"}
NON_AREA_KINDS = {"line", "polyline", "freeline", "angle", "point", "multipoint"}
GEOMETRY_TOLERANCE = 1e-4


def _source(asset: ImageAsset, cancel: Event) -> dict[str, Any]:
    axes = asset.metadata.get("axes") if asset.metadata else None
    if not isinstance(axes, list):
        raise ValueError("请先由固定 Fiji 检查图像轴。")
    verify_asset_bytes(asset, cancel)
    return {"sha256": asset.sha256, "bytes": asset.bytes, "axes": axes}



def _normalized_collection(asset: ImageAsset, document: Any, identity: dict[str, Any]) -> dict[str, Any]:
    if (not isinstance(document, dict) or set(document) != {"version", "source", "items"}
            or document["version"] != "2.0" or document["source"] != identity):
        raise ValueError("ROI 交换集合版本或来源摘要/轴不匹配。")
    items = document["items"]
    if not isinstance(items, list) or not 1 <= len(items) <= MAX_ITEMS:
        raise ValueError("原生 ROI 集合须有 1–64 项。")
    seen = set()
    checked = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "name", "indices", "roi"}:
            raise ValueError("ROI 项包含缺失或未知字段。")
        identifier, name = item["id"], item["name"]
        if (not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier)
                or identifier in seen or not isinstance(name, str) or not 1 <= len(name) <= 80
                or name != name.strip() or any(not character.isprintable() for character in name)):
            raise ValueError("ROI 项 ID 或名称无效或重复。")
        seen.add(identifier)
        axes, plane, width, height = build_plane_selection(asset, item["indices"])
        if stack_plane_count(axes) > 64:
            raise ValueError("ROI 交换至多支持 64 个线性平面。")
        roi = item["roi"]
        if not isinstance(roi, dict):
            raise ValueError("ROI 几何须为版本化对象。")
        kind = roi.get("kind")
        if not isinstance(kind, str):
            raise ValueError("ROI 几何类型须为字符串。")
        if kind in AREA_KINDS:
            normalized = validate_area_roi(roi, width, height)
        elif kind in NON_AREA_KINDS:
            normalized = validate_non_area_roi(roi, width, height, stack_plane_count(axes))
        elif kind == "shape_path":
            if set(roi) != {"version", "kind", "path"} or roi.get("version") != "1.0":
                raise ValueError("原生 ShapeRoi 路径参数不匹配。")
            normalized = {"version": "1.0", "kind": kind,
                          "path": _shape_path(roi["path"], width, height)}
        else:
            raise ValueError("尚未适配的原生 ROI 类型。")
        checked.append({"id": identifier, "name": name, "indices": plane, "roi": normalized})
    result = {"version": "2.0", "source": identity, "items": checked}
    if len(json.dumps(result, ensure_ascii=False).encode("utf-8")) > 256 * 1024:
        raise ValueError("ROI 集合正文超过 256 KiB。")
    return result


def validate_exchange_collection(asset: ImageAsset, document: Any, cancel: Event) -> dict[str, Any]:
    return _normalized_collection(asset, document, _source(asset, cancel))


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 2], "big")


def _i32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 4], "big", signed=True)


def _point(data: bytes, offset: int) -> float:
    value = struct.unpack_from(">f", data, offset)[0]
    if not isfinite(value):
        raise ValueError("ROI 二进制坐标包含非有限浮点数。")
    return value


def preflight_roi(data: bytes) -> dict[str, int | bool]:
    """Reject allocation-bearing offsets before RoiDecoder sees untrusted bytes."""
    if not 64 <= len(data) <= MAX_ROI_BYTES or data[:4] != b"Iout":
        raise ValueError("ROI 文件长度或魔数无效。")
    version, kind, subtype, options = _u16(data, 4), data[6], _u16(data, 48), _u16(data, 50)
    count, shape_count, hdr2 = _u16(data, 16), _i32(data, 36), _i32(data, 60)
    if not 217 <= version <= 229 or kind not in (0, 1, 2, 3, 4, 5, 7, 8, 9, 10):
        raise ValueError("ROI 版本或类型不受支持。")
    if options & ~(1 | 128 | 256 | 8192):
        raise ValueError("ROI 包含未适配的选项位。")
    if subtype not in (0, 3, 5) or (subtype and not (kind == 7 or kind == 0 and subtype == 5)):
        raise ValueError("ROI 子型不受支持。")
    if _i32(data, 40) or _i32(data, 44) or _u16(data, 54):
        raise ValueError("ROI 样式、填充或圆角属性未适配。")
    if shape_count:
        if kind != 1 or subtype or count or not 1 <= shape_count <= 4096:
            raise ValueError("ShapeRoi 路径头无效。")
        end = 64 + 4 * shape_count
        if end > len(data):
            raise ValueError("ShapeRoi 路径数据截断。")
        values = struct.unpack_from(f">{shape_count}f", data, 64)
        if any(not isfinite(value) for value in values):
            raise ValueError("ShapeRoi 路径有非有限坐标。")
        _shape_path(list(values), 2**24, 2**24)
    else:
        if (kind in (1, 2, 3) and count != 0 or kind == 0 and subtype == 0 and not 3 <= count <= 64
                or kind in (4, 5) and not 2 <= count <= 64
                or kind == 9 and count != 3 or kind == 10 and not 1 <= count <= 64
                or kind == 8 and not 3 <= count <= 64
                or kind == 7 and subtype == 3 and count != 72
                or kind in (0, 7) and subtype == 5 and count != 4
                or kind == 7 and subtype == 0 and not 3 <= count <= 64):
            raise ValueError("ROI 顶点数与原生类型不匹配。")
        if kind in (1, 2, 3) or subtype:
            for offset in (18, 22, 26, 30):
                _point(data, offset)
            if subtype:
                _point(data, 52)
        end = 64 + count * (12 if options & 128 else 4)
        if end > len(data):
            raise ValueError("ROI 顶点数据截断。")
        if options & 128 and count:
            for offset in range(64 + count * 4, end, 4):
                _point(data, offset)
    if hdr2:
        if hdr2 < end or hdr2 + 64 > len(data):
            raise ValueError("ROI 扩展头越界或覆盖数据。")
        for start_offset, length_offset, cap in ((16, 20, 80), (40, 44, 0)):
            start, length = _i32(data, hdr2 + start_offset), _i32(data, hdr2 + length_offset)
            if length < 0 or length > cap or start < 0 or (length and (start < hdr2 + 64
                    or start + 2 * length > len(data))):
                raise ValueError("ROI 名称或属性指针无效。")
        if _i32(data, hdr2 + 32) or _u16(data, hdr2 + 30):
            raise ValueError("ROI 图片或组字段不受支持。")
        if not 0 <= _point(data, hdr2 + 36) <= 32:
            raise ValueError("ROI 原生线宽超出交换范围。")
        if any(not 0 <= _i32(data, hdr2 + offset) <= 64 for offset in (4, 8, 12)):
            raise ValueError("ROI C/Z/T 位置超出交换上限。")
        counter_offset = _i32(data, hdr2 + 48)
        if counter_offset and (kind != 10 or counter_offset < hdr2 + 64
                               or counter_offset + count * 4 > len(data)):
            raise ValueError("ROI 点计数器指针越界。")
        if counter_offset:
            for index in range(count):
                value = _i32(data, counter_offset + index * 4)
                if not 0 <= value >> 8 <= 64 or value & 255 > 99:
                    raise ValueError("ROI 逐点位置或计数器超出交换上限。")
    elif kind == 10:
        raise ValueError("点 ROI 缺少必要扩展头。")
    return {"version": version, "encoded_type": kind, "subtype": subtype,
            "point_count": count, "shape_values": shape_count, "rotated_header_repair":
                kind == 0 and subtype == 5}


def _flat_name(name: str) -> bool:
    return (bool(name) and len(name) <= 100 and name == name.strip()
            and not name.startswith(".") and not name.endswith(" ")
            and "/" not in name and "\\" not in name and ":" not in name and "\x00" not in name
            and all(character.isprintable() for character in name))


def preflight_zip(data: bytes, identity: dict[str, Any]) -> tuple[list[tuple[str, bytes]], bool]:
    if not 0 < len(data) <= MAX_ARCHIVE_BYTES:
        raise ValueError("ROI ZIP 原始字节超过 1 MiB。")
    entries: list[tuple[str, bytes]] = []
    bound = False
    try:
        with ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= MAX_ITEMS + 1:
                raise ValueError("ROI ZIP 条目数量无效。")
            seen, total = set(), 0
            for info in infos:
                name = info.filename
                if (not _flat_name(name) or name.casefold() in seen or info.is_dir() or info.flag_bits & 1
                        or (info.external_attr >> 16) & 0o170000 == 0o120000
                        or info.compress_type not in (ZIP_STORED, ZIP_DEFLATED)
                        or info.file_size > (4096 if name == MANIFEST else MAX_ROI_BYTES)
                        or info.file_size > 100 * max(1, info.compress_size)):
                    raise ValueError("ROI ZIP 条目路径、加密、类型、大小或压缩比无效。")
                seen.add(name.casefold())
                total += info.file_size
                if total > MAX_ARCHIVE_BYTES:
                    raise ValueError("ROI ZIP 展开量超过 1 MiB。")
                content = archive.read(info)
                if len(content) != info.file_size:
                    raise ValueError("ROI ZIP 条目展开长度不一致。")
                if name == MANIFEST:
                    if json.loads(content) != identity:
                        raise ValueError("ROI ZIP 来源摘要、字节或轴不匹配。")
                    bound = True
                elif name.lower().endswith(".roi"):
                    preflight_roi(content)
                    entries.append((name, content))
                else:
                    raise ValueError("ROI ZIP 包含未知成员。")
    except (BadZipFile, UnicodeDecodeError, json.JSONDecodeError, OSError) as error:
        raise ValueError("ROI ZIP 格式无效。") from error
    if not 1 <= len(entries) <= MAX_ITEMS:
        raise ValueError("ROI ZIP 须包含 1–64 个原生 ROI。")
    return entries, bound


def _verify_proof(proof: Any, roi: dict[str, Any], encoded: bytes | None = None) -> None:
    kind = roi["kind"]
    expected_class = CLASSES.get(kind) if kind in AREA_KINDS else (
        "ij.gui.ShapeRoi" if kind == "shape_path" else "ij.gui.Line" if kind == "line" else
        "ij.gui.PointRoi" if kind in {"point", "multipoint"} else "ij.gui.PolygonRoi")
    expected_type = 9 if kind == "shape_path" else TYPE_CODES.get(kind, NATIVE_TYPE_CODES.get(kind))
    if (not isinstance(proof, dict) or proof.get("class_name") != expected_class
            or type(proof.get("type_code")) is not int or proof["type_code"] != expected_type
            or type(proof.get("encoded_bytes")) is not int or not 64 <= proof["encoded_bytes"] <= MAX_ROI_BYTES
            or not isinstance(proof.get("byte_sha256"), str) or not re.fullmatch(r"[0-9a-f]{64}", proof["byte_sha256"])
            or type(proof.get("subpixel")) is not bool
            or type(proof.get("rotated_header_repaired")) is not bool
            or proof.get("spline_fit") is not (kind == "spline_polygon")
            or type(proof.get("shape_path_values")) is not int
            or not 0 <= proof["shape_path_values"] <= 4096
            or (kind in {"shape", "shape_path"}) != (proof["shape_path_values"] > 0)):
        raise ValueError("原生 ROI 编解码证据与类型或容量不一致。")
    if encoded is not None and (proof["encoded_bytes"] != len(encoded) or proof["byte_sha256"] != sha256(encoded).hexdigest()):
        raise ValueError("原生 ROI 输出文件与编解码摘要不一致。")


def run_roi_exchange(
    asset: ImageAsset, operation: str, cancel: Event, runner: Callable[..., dict[str, Any]],
    *, collection: dict[str, Any] | None = None, file_bytes: bytes | None = None,
) -> dict[str, Any]:
    if operation not in {"export_zip", "export_roi", "import_zip", "import_roi"}:
        raise ValueError("未知原生 ROI 交换操作。")
    identity = _source(asset, cancel)
    if operation.startswith("export"):
        if file_bytes is not None:
            raise ValueError("导出不得包含导入文件。")
        checked = _normalized_collection(asset, collection, identity)
        if operation == "export_roi" and len(checked["items"]) != 1:
            raise ValueError("单 ROI 文件导出只能包含一项。")
        request = {"operation": operation, "collection": checked, "source_sha256": asset.sha256,
                   "source_axes": identity["axes"]}
    else:
        if collection is not None or not isinstance(file_bytes, bytes):
            raise ValueError("导入须提供原始 ROI 文件或 ZIP 字节。")
        if operation == "import_zip":
            entries, bound = preflight_zip(file_bytes, identity)
        else:
            preflight_roi(file_bytes)
            entries, bound = [("imported.roi", file_bytes)], False
        from base64 import b64encode
        request = {"operation": operation, "source_axes": identity["axes"], "entries": [
            {"filename": name, "base64": b64encode(content).decode("ascii")}
            for name, content in entries], "source_sha256": asset.sha256}
    payload = runner(asset, uuid4().hex, cancel, request)
    if payload.get("source_sha256") != asset.sha256 or payload.get("operation") != operation:
        raise ValueError("原生 ROI 交换输出未绑定所选源图和操作。")
    if operation.startswith("export"):
        encoded = payload.get("archive_base64") if operation == "export_zip" else payload.get("roi_base64")
        if not isinstance(encoded, str) or len(encoded) > 2 * MAX_ARCHIVE_BYTES:
            raise ValueError("原生 ROI 输出长度无效。")
        try:
            result_bytes = b64decode(encoded, validate=True)
        except (ValueError, Base64Error) as error:
            raise ValueError("原生 ROI 输出 Base64 无效。") from error
        if operation == "export_zip":
            entries, bound = preflight_zip(result_bytes, identity)
            if not bound or len(entries) != len(checked["items"]):
                raise ValueError("原生 ROI ZIP 缺少来源绑定或项目。")
        else:
            preflight_roi(result_bytes)
            entries = [("exported.roi", result_bytes)]
        proofs = payload.get("proofs")
        if not isinstance(proofs, list) or len(proofs) != len(checked["items"]):
            raise ValueError("原生 ROI 导出缺少逐项编解码证据。")
        for proof, item, (_, content) in zip(proofs, checked["items"], entries, strict=True):
            _verify_proof(proof, item["roi"], content)
        return {"version": "2.0", "operation": operation, "source": identity,
                "bytes": result_bytes, "proofs": payload.get("proofs")}
    imported = payload.get("items")
    if not isinstance(imported, list) or len(imported) != len(request["entries"]):
        raise ValueError("原生 ROI 导入项目数不匹配。")
    numbered = []
    for item in imported:
        if not isinstance(item, dict) or set(item) != {"name", "indices", "roi", "proof"}:
            raise ValueError("原生 ROI 导入缺少身份或几何字段。")
        numbered.append({"id": uuid4().hex, "name": item["name"],
                         "indices": item["indices"], "roi": item["roi"]})
    checked = _normalized_collection(asset, {"version": "2.0", "source": identity,
                                              "items": numbered}, identity)
    for item, original in zip(checked["items"], imported, strict=True):
        _verify_proof(original["proof"], item["roi"])
    return {"version": "2.0", "operation": operation, "source": identity,
            "manifest_matches_source": bound, "collection": checked,
            "proofs": [item["proof"] for item in imported]}
