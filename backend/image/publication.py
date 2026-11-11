"""Bounded source preparation for the image panel in a mixed publication figure."""

from dataclasses import dataclass
import math

import numpy as np
from PIL import Image, UnidentifiedImageError

from backend.core.specs import FigureImagePanel, FigureSpec
from backend.image.assets import ImageAsset, verify_asset_bytes


MAX_FIGURE_IMAGE_BYTES = 64 * 1024 * 1024
MAX_FIGURE_IMAGE_PIXELS = 8_000_000


@dataclass(frozen=True)
class PublicationImage:
    pixels: np.ndarray
    source_width: int
    source_height: int
    scale_bar_pixels: float
    effective_dpi: float

    def check(self, spec: FigureSpec) -> dict[str, object]:
        return {
            "source_pixels": [self.source_width, self.source_height],
            "placed_pixels": [self.pixels.shape[1], self.pixels.shape[0]],
            "effective_dpi": round(self.effective_dpi, 2),
            "output_dpi": spec.dpi,
            "below_output_dpi": self.effective_dpi < spec.dpi,
        }


def prepare_publication_image(asset: ImageAsset, panel: FigureImagePanel, spec: FigureSpec) -> PublicationImage:
    if asset.bytes > MAX_FIGURE_IMAGE_BYTES:
        raise ValueError("图版源图超过 64 MiB，请选择单平面的较小原图。")
    verify_asset_bytes(asset)
    try:
        with Image.open(asset.path, formats=["PNG", "TIFF"]) as image:
            width, height = image.size
            if width * height > MAX_FIGURE_IMAGE_PIXELS:
                raise ValueError("图版源图超过 800 万像素。")
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError("图版首版只接受单平面 PNG 或 TIFF。")
            if image.mode not in {"L", "I;16", "I;16B", "I;16L", "RGB", "RGBA"}:
                raise ValueError("图版首版支持 8/16 位灰度和 8 位 RGB/RGBA 图像。")
            if image.mode in {"RGB", "RGBA"}:
                if image.format == "TIFF":
                    high_bit_color = any(depth != 8 for depth in image.tag_v2.get(258, (8,)))
                else:
                    with asset.path.open("rb") as header:
                        header.seek(24)
                        high_bit_color = header.read(1) != b"\x08"
                if high_bit_color:
                    raise ValueError("图版首版仅支持 8 位彩色图像。")
            if image.getexif().get(274, 1) != 1:
                raise ValueError("请先明确处理源图的旋转方向，再标定比例尺。")
            crop = panel.crop
            if crop and (crop.x + crop.width > width or crop.y + crop.height > height):
                raise ValueError("裁切区域超出源图。")
            placed = image.crop((crop.x, crop.y, crop.x + crop.width, crop.y + crop.height)) if crop else image
            pixels = np.asarray(placed)
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError) as error:
        raise ValueError("无法读取图版图像，请选择有效的单平面 PNG 或 TIFF。") from error

    placed_height, placed_width = pixels.shape[:2]
    bar_pixels = panel.scale_bar_um / panel.x_um_per_pixel
    if not math.isfinite(bar_pixels) or not 1 <= bar_pixels <= placed_width * 0.86:
        raise ValueError("比例尺必须至少为 1 像素，并能在裁切后的图像内留出边距。")
    rows = (spec.panel_count + spec.columns - 1) // spec.columns
    cell_width = (spec.width_mm - spec.margin_left_mm - spec.margin_right_mm - spec.panel_gap_mm * (spec.columns - 1)) / spec.columns
    cell_height = (spec.height_mm - spec.margin_top_mm - spec.margin_bottom_mm - spec.panel_gap_mm * (rows - 1)) / rows
    effective_dpi = 25.4 * max(placed_width / cell_width, placed_height / cell_height)
    return PublicationImage(pixels, width, height, bar_pixels, effective_dpi)
