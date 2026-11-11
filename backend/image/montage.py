"""Exact-pixel grid assembly for the image workspace.

This is a new layout operation, not a replacement for Fiji stitching or
registration algorithms. Input pixels are placed without resampling; any
format or mode which cannot make that guarantee is rejected.
"""

from __future__ import annotations

from contextlib import ExitStack
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import Event
import warnings

from PIL import Image

from backend.image.assets import ImageAsset
from backend.image.calibration import shared_spacing, spacing_tags, verify_spacing_tags


MAX_GRID_PIXELS = 16_000_000
MAX_INPUTS = 8
SUPPORTED_MODES = frozenset({"L", "I;16", "F", "RGB", "RGBA"})


class MontageCancelled(RuntimeError):
    pass


@dataclass(frozen=True)
class GridPlacement:
    asset_id: str
    x: int
    y: int
    width: int
    height: int
    pixel_sha256: str
    different_pixels: int = 0
    source_axes: list[dict[str, object]] | None = None
    source_bit_depth: int | None = None
    source_pixel_type: str | None = None

    def public(self) -> dict[str, object]:
        return self.__dict__.copy()


@dataclass(frozen=True)
class GridProof:
    width: int
    height: int
    mode: str
    format: str
    output_sha256: str
    placements: tuple[GridPlacement, ...]
    verified_pixels: int
    spatial_spacing: dict | None = None
    grid_recipe: dict[str, int] | None = None

    def public(self) -> dict[str, object]:
        return {
            "width": self.width, "height": self.height, "mode": self.mode,
            "format": self.format, "output_sha256": self.output_sha256,
            "placements": [item.public() for item in self.placements],
            "verified_pixels": self.verified_pixels,
            "different_pixels": 0,
            "pixel_identity_verified": True,
            "metadata_preserved": False,
            "spatial_spacing": self.spatial_spacing,
            "spatial_spacing_preserved": self.spatial_spacing is not None,
            "grid_recipe": self.grid_recipe,
        }


def _file_hash(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def render_exact_grid(assets: list[ImageAsset], columns: int, gap_px: int,
                      output: Path, cancel: Event | None = None) -> GridProof:
    def check_cancel() -> None:
        if cancel is not None and cancel.is_set():
            raise MontageCancelled()

    if not 1 <= len(assets) <= MAX_INPUTS:
        raise ValueError("图像网格需要 1 至 8 张已导入的源图像。")
    if not 1 <= columns <= len(assets) or not 0 <= gap_px <= 1000:
        raise ValueError("网格列数或间距不在允许范围内。")
    if output.exists():
        raise ValueError("输出目标已存在。")

    with ExitStack() as stack:
        images: list[Image.Image] = []
        modes: set[str] = set()
        for asset in assets:
            check_cancel()
            if _file_hash(asset.path) != asset.sha256:
                raise ValueError("源图像字节与导入摘要不符。")
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                image = stack.enter_context(Image.open(asset.path))
            if image.width * image.height > MAX_GRID_PIXELS:
                raise ValueError("源图像超过单张 1,600 万像素上限。")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("多帧或图像栈需要显式选择轴与帧；当前原像素网格不做隐式选择。")
            if image.mode not in SUPPORTED_MODES:
                raise ValueError(f"像素模式 {image.mode} 尚不能保证原样拼版。")
            image.load()
            images.append(image)
            modes.add(image.mode)
        if len(modes) != 1:
            raise ValueError("原像素网格要求所有源图像采用相同位深和通道模式。")
        mode = next(iter(modes))

        rows = (len(images) + columns - 1) // columns
        col_widths = [max(image.width for index, image in enumerate(images) if index % columns == column)
                      for column in range(columns)]
        row_heights = [max(image.height for index, image in enumerate(images) if index // columns == row)
                       for row in range(rows)]
        width = sum(col_widths) + gap_px * (columns - 1)
        height = sum(row_heights) + gap_px * (rows - 1)
        if width * height > MAX_GRID_PIXELS or width > 65535 or height > 65535:
            raise ValueError("网格超过 1,600 万像素或格式尺寸上限。")

        background: int | float | tuple[int, ...] = (0, 0, 0, 0) if mode == "RGBA" else (
            (0, 0, 0) if mode == "RGB" else 0)
        canvas = Image.new(mode, (width, height), background)
        x_positions = [sum(col_widths[:column]) + gap_px * column for column in range(columns)]
        y_positions = [sum(row_heights[:row]) + gap_px * row for row in range(rows)]
        placements: list[GridPlacement] = []
        for index, (asset, image) in enumerate(zip(assets, images)):
            check_cancel()
            x = x_positions[index % columns]
            y = y_positions[index // columns]
            canvas.paste(image, (x, y))  # No mask: RGBA alpha is copied, not composited.
            placements.append(GridPlacement(asset.id, x, y, image.width, image.height,
                                            sha256(image.tobytes()).hexdigest(),
                                            source_axes=asset.metadata.get("axes") if asset.metadata else None,
                                            source_bit_depth=asset.metadata.get("bit_depth") if asset.metadata else None,
                                            source_pixel_type=asset.metadata.get("pixel_type") if asset.metadata else None))

        encoded = BytesIO()
        spacing = shared_spacing(assets, [image.size for image in images])
        try:
            check_cancel()
            canvas.save(encoded, format="TIFF", compression="raw",
                        **({"tiffinfo": spacing_tags(spacing)} if spacing else {}))
            encoded.seek(0)
            with Image.open(encoded) as saved:
                if saved.mode != mode or saved.size != (width, height):
                    raise ValueError("输出格式改变了像素模式或尺寸。")
                if spacing:
                    verify_spacing_tags(saved, spacing)
                for placement, source in zip(placements, images):
                    actual = saved.crop((placement.x, placement.y,
                                         placement.x + placement.width,
                                         placement.y + placement.height))
                    try:
                        if sha256(actual.tobytes()).hexdigest() != placement.pixel_sha256:
                            source_bytes = source.tobytes()
                            output_bytes = actual.tobytes()
                            stride = {"L": 1, "I;16": 2, "F": 4, "RGB": 3, "RGBA": 4}[mode]
                            differences = [index for index in range(placement.width * placement.height)
                                           if source_bytes[index * stride:(index + 1) * stride]
                                           != output_bytes[index * stride:(index + 1) * stride]]
                            first = differences[0] if differences else 0
                            raise ValueError(f"保存后的像素不一致：{len(differences)} 处，首处坐标 "
                                             f"({placement.x + first % placement.width}, "
                                             f"{placement.y + first // placement.width})。")
                    finally:
                        actual.close()
            output.parent.mkdir(parents=True, exist_ok=True)
            check_cancel()
            encoded.seek(0)
            created = False
            try:
                with output.open("xb") as stream:
                    created = True
                    for chunk in iter(lambda: encoded.read(4 * 1024 * 1024), b""):
                        stream.write(chunk)
                check_cancel()
            except BaseException:
                if created:
                    output.unlink(missing_ok=True)
                raise
        finally:
            encoded.close()
        return GridProof(width, height, mode, "TIFF", _file_hash(output),
                         tuple(placements), sum(item.width * item.height for item in placements), spacing,
                         {"columns": columns, "gap_px": gap_px})
