"""Portable, source-bound local ROI collections for reviewed Fiji selections."""

from __future__ import annotations

from io import BytesIO
import json
import math
import re
import struct
from typing import Any
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile

from backend.image.assets import ImageAsset, verify_asset_bytes
from backend.image.selection import build_selection


MAX_ROIS = 64
MAX_COLLECTION_BYTES = 128 * 1024
MAX_NATIVE_ZIP_BYTES = 512 * 1024
NATIVE_MANIFEST = "biofigure-source.json"


def source_identity(asset: ImageAsset) -> dict[str, Any]:
    if not asset.metadata or not isinstance(asset.metadata.get("axes"), list):
        raise ValueError("请先使用 Fiji 检查源图，再管理 ROI 集合。")
    verify_asset_bytes(asset)
    return {"sha256": asset.sha256, "bytes": asset.bytes,
            "axes": asset.metadata["axes"]}


def validate_collection(asset: ImageAsset, document: Any) -> dict[str, Any]:
    source = source_identity(asset)
    if (not isinstance(document, dict) or set(document) != {"version", "source", "items"}
            or document["version"] != "1.0" or document["source"] != source):
        raise ValueError("ROI 集合版本或源图摘要/轴与当前图像不符。")
    items = document["items"]
    if not isinstance(items, list) or len(items) > MAX_ROIS:
        raise ValueError("ROI 集合最多包含 64 项。")
    normalized: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "name", "indices", "roi"}:
            raise ValueError("ROI 集合项目包含缺失或未知字段。")
        identifier, name = item["id"], item["name"]
        if (not isinstance(identifier, str) or not re.fullmatch(r"[0-9a-f]{32}", identifier)
                or identifier in seen_ids):
            raise ValueError("ROI 项目 ID 缺失、重复或无效。")
        if (not isinstance(name, str) or not 1 <= len(name.strip()) <= 80
                or name != name.strip() or any(not char.isprintable() for char in name)):
            raise ValueError("ROI 名称须为 1 至 80 个可打印字符。")
        seen_ids.add(identifier)
        selection = build_selection(asset, item["indices"], item["roi"])
        normalized.append({"id": identifier, "name": name,
                           "indices": selection.indices, "roi": selection.roi})
    return {"version": "1.0", "source": source, "items": normalized}


def _inspect_roi_header(content: bytes) -> None:
    # Offsets verified from the pinned ij-1.54p RoiDecoder constants. Bound
    # allocation-bearing fields before handing untrusted bytes to Java.
    if len(content) < 64 or content[:4] != b"Iout":
        raise ValueError("原生 ROI 头无效。")
    def integer(offset):
        return int.from_bytes(content[offset:offset + 4], "big", signed=True)

    def short(offset):
        return int.from_bytes(content[offset:offset + 2], "big")
    kind = content[6]
    if kind not in (0, 1, 2) or integer(36) != 0 or short(48) != 0:
        raise ValueError("当前原生 ROI 仅支持普通矩形、椭圆与多边形。")
    if short(50) & 1 or (kind == 1 and short(54)):
        raise ValueError("样条或圆角 ROI 尚未适配。")
    subpixel = bool(short(50) & 128) and short(4) >= 222

    def integral_floats(offset, count):
        for value in struct.unpack_from(f">{count}f", content, offset):
            if not math.isfinite(value) or not value.is_integer():
                raise ValueError("当前原生 ROI 不接受亚像素边界或顶点。")

    if kind in (1, 2) and subpixel and short(4) >= 223:
        integral_floats(18, 4)
    if kind == 0:
        count = short(16)
        stride = 12 if subpixel else 4
        if not 3 <= count <= 32 or 64 + count * stride > len(content):
            raise ValueError("多边形坐标数量或数据长度无效。")
        if subpixel:
            integral_floats(64 + count * 4, count * 2)
    header2 = integer(60)
    if header2:
        if header2 < 64 or header2 + 64 > len(content):
            raise ValueError("ROI 扩展头越界。")
        for offset, length_offset in ((16, 20), (40, 44)):
            start, length = integer(header2 + offset), integer(header2 + length_offset)
            if start < 0 or length < 0 or (length and start + 2 * length > len(content)):
                raise ValueError("ROI 名称或属性指针越界。")


def inspect_native_zip(data: bytes, asset: ImageAsset) -> tuple[list[tuple[str, bytes]], bool]:
    if not 0 < len(data) <= MAX_NATIVE_ZIP_BYTES:
        raise ValueError("原生 ROI ZIP 必须小于 512 KiB。")
    entries: list[tuple[str, bytes]] = []
    source_bound = False
    try:
        with ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if not 1 <= len(infos) <= MAX_ROIS + 1:
                raise ValueError("原生 ROI ZIP 须包含 1 至 64 个条目。")
            seen: set[str] = set()
            expanded = 0
            for info in infos:
                name = info.filename
                if (name in seen or "/" in name or "\\" in name or name.startswith(".")
                        or info.is_dir() or info.flag_bits & 1 or info.file_size > 16384
                        or info.compress_type not in (ZIP_STORED, ZIP_DEFLATED)):
                    raise ValueError("原生 ROI ZIP 条目名称、大小或加密状态无效。")
                seen.add(name)
                expanded += info.file_size
                if expanded > MAX_NATIVE_ZIP_BYTES or (info.compress_size and info.file_size > 100 * info.compress_size):
                    raise ValueError("原生 ROI ZIP 展开量超出上限。")
                content = archive.read(info)
                if name == NATIVE_MANIFEST:
                    manifest = json.loads(content)
                    if manifest != source_identity(asset):
                        raise ValueError("原生 ROI ZIP 的源图摘要或轴与当前图像不符。")
                    source_bound = True
                elif name.lower().endswith(".roi") and len(content) >= 64 and content[:4] == b"Iout":
                    _inspect_roi_header(content)
                    entries.append((name, content))
                else:
                    raise ValueError("原生 ROI ZIP 包含不受支持的条目。")
    except (BadZipFile, UnicodeDecodeError, json.JSONDecodeError, OSError) as error:
        raise ValueError("原生 ROI ZIP 格式无效。") from error
    if not 1 <= len(entries) <= MAX_ROIS:
        raise ValueError("原生 ROI ZIP 须包含 1 至 64 个 .roi 条目。")
    return entries, source_bound


def bind_native_zip(data: bytes, asset: ImageAsset) -> bytes:
    entries, _ = inspect_native_zip(data, asset)
    encoded = BytesIO()
    with ZipFile(encoded, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries:
            archive.writestr(name, content)
        archive.writestr(NATIVE_MANIFEST, json.dumps(source_identity(asset), ensure_ascii=False, sort_keys=True))
    result = encoded.getvalue()
    if len(result) > MAX_NATIVE_ZIP_BYTES:
        raise ValueError("原生 ROI ZIP 超过 512 KiB。")
    return result
