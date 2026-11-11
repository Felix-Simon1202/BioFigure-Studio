"""Bounded display PNGs; never overwrite scientific image samples."""

from io import BytesIO
from pathlib import Path
from hashlib import sha256
import warnings

import numpy as np
from PIL import Image

from backend.image.assets import ImageAsset
from backend.image.selection import build_plane_selection


MAX_PREVIEW_SOURCE_PIXELS = 16_000_000
MAX_PREVIEW_EDGE = 1024
MAX_SOURCE_PREVIEW_BYTES = 128 * 1024 * 1024
MAX_SOURCE_PREVIEW_FRAMES = 64


def display_png(path: Path, *, frame_index: int | None = None,
                expected_size: tuple[int, int] | None = None) -> tuple[bytes, dict[str, str]]:
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(path) as original:
            if original.width * original.height > MAX_PREVIEW_SOURCE_PIXELS or (
                    frame_index is None and original.n_frames != 1):
                raise ValueError("预览仅支持容量范围内的单平面成品。")
            if frame_index is not None:
                if not 0 <= frame_index < original.n_frames or original.size != expected_size:
                    raise ValueError("预览平面与已检查图像轴不一致。")
                original.seek(frame_index)
            headers = {"Cache-Control": "no-store", "X-Preview-Only": "true"}
            if original.mode in {"RGB", "RGBA", "L"}:
                image = original.copy()
                headers["X-Display-Mapping"] = "original-8bit"
            elif original.mode in {"I;16", "I;16L", "I;16B", "F", "I"}:
                pixels = np.asarray(original)
                finite = np.isfinite(pixels)
                minimum = float(pixels[finite].min()) if finite.any() else 0.0
                maximum = float(pixels[finite].max()) if finite.any() else 0.0
                shown = np.zeros(pixels.shape, dtype=np.uint8)
                if maximum > minimum:
                    # Row blocks bound conversion scratch space. Arithmetic is
                    # float64 so opposite large float32 endpoints stay finite.
                    for start in range(0, pixels.shape[0], 128):
                        block = pixels[start:start + 128].astype(np.float64)
                        valid = finite[start:start + 128]
                        block[~valid] = minimum
                        values = (block - minimum) / (maximum - minimum) * 255
                        shown[start:start + 128] = np.clip(values, 0, 255).astype(np.uint8)
                image = Image.fromarray(shown)
                headers.update({"X-Display-Mapping": "finite-min-max-linear",
                                "X-Display-Min": repr(minimum), "X-Display-Max": repr(maximum),
                                "X-Nonfinite-Display": "black"})
            else:
                raise ValueError("此成品的像素模式暂不支持显示预览。")
    try:
        image.thumbnail((MAX_PREVIEW_EDGE, MAX_PREVIEW_EDGE), Image.Resampling.NEAREST)
        with BytesIO() as encoded:
            image.save(encoded, format="PNG")
            return encoded.getvalue(), headers
    finally:
        image.close()


def source_plane_png(asset: ImageAsset, indices: dict[str, int]) -> tuple[bytes, dict[str, str]]:
    """Display-only view of a Fiji-inspected ImageJ 16-bit TIFF plane."""
    axes, normalized, width, height = build_plane_selection(asset, indices)
    if (asset.bytes > MAX_SOURCE_PREVIEW_BYTES or width * height > MAX_PREVIEW_SOURCE_PIXELS
            or asset.metadata.get("bit_depth") != 16):
        raise ValueError("源图预览目前限 128 MiB、单平面 1600 万像素以内的 16 位灰度 TIFF。")
    lengths = {axis["name"]: axis["length"] for axis in axes}
    channels, slices, frames = (lengths.get("Channel", 1), lengths.get("Z", 1),
                                lengths.get("Time", 1))
    frame_count = channels * slices * frames
    if frame_count > MAX_SOURCE_PREVIEW_FRAMES:
        raise ValueError("源图预览最多支持 64 个平面。")
    frame_index = ((normalized.get("T", 0) * slices + normalized.get("Z", 0))
                   * channels + normalized.get("C", 0))
    digest = sha256()
    with asset.path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != asset.sha256:
        raise ValueError("源图像与导入摘要不符。")
    with Image.open(asset.path) as original:
        description = str(original.tag_v2.get(270, "")) if original.format == "TIFF" else ""
        header = dict(line.split("=", 1) for line in description.splitlines() if "=" in line)
        imagej_counts_match = (header.get("ImageJ") is not None
                               and header.get("images") == str(frame_count)
                               and header.get("channels", "1") == str(channels)
                               and header.get("slices", "1") == str(slices)
                               and header.get("frames", "1") == str(frames)
                               and header.get("hyperstack") == "true")
        if (original.format != "TIFF" or original.size != (width, height)
                or original.n_frames != frame_count or original.mode not in {"I;16", "I;16L", "I;16B"}
                or (frame_count > 1 and not imagej_counts_match)):
            raise ValueError("源图预览需要与 Fiji 已检查轴一致的 16 位灰度 TIFF。")
        original.seek(frame_index)
        if original.size != (width, height) or original.mode not in {"I;16", "I;16L", "I;16B"}:
            raise ValueError("所选 TIFF 页与 Fiji 已检查的 16 位图像轴不一致。")
    data, headers = display_png(asset.path, frame_index=frame_index,
                                expected_size=(width, height))
    headers["X-Source-Plane"] = str(frame_index)
    headers["X-Source-Indices"] = ",".join(f"{key}={normalized.get(key, 0)}" for key in ("C", "Z", "T"))
    return data, headers
