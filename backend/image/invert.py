"""Independent verification of the fixed Fiji 8-bit data inversion adapter."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from PIL import Image

from backend.image.assets import ImageAsset


MAX_INVERT_PIXELS = 16_000_000
_INVERT_TABLE = bytes(255 - value for value in range(256))


def validate_invert_input(source: ImageAsset) -> None:
    with Image.open(source.path) as image:
        if (image.format != "TIFF" or image.mode != "L" or
                getattr(image, "n_frames", 1) != 1 or
                not 1 <= image.width * image.height <= MAX_INVERT_PIXELS):
            raise ValueError("Fiji 反相目前仅支持 1600 万像素以内的单帧 8 位灰度 TIFF。")


@dataclass(frozen=True)
class InvertProof:
    width: int
    height: int
    source_sha256: str
    output_sha256: str
    verified_pixels: int

    def public(self) -> dict[str, object]:
        return {"command": "net.imagej.plugins.commands.assign.InvertDataValues",
                "width": self.width, "height": self.height,
                "source_sha256": self.source_sha256, "output_sha256": self.output_sha256,
                "verified_pixels": self.verified_pixels, "different_pixels": 0,
                "metadata_preserved": False}


def verify_inversion(source: ImageAsset, output: Path) -> InvertProof:
    with Image.open(source.path) as before, Image.open(output) as after:
        before.load()
        after.load()
        width, height = before.size
        if (before.mode != "L" or after.mode != "L" or after.size != before.size
                or not 1 <= width * height <= MAX_INVERT_PIXELS):
            raise ValueError("Fiji 反相仅支持 1600 万像素以内的单帧 8 位灰度图。")
        if after.tobytes() != before.tobytes().translate(_INVERT_TABLE):
            raise ValueError("Fiji 反相成品与独立逐像素核验不一致。")
    digest = sha256()
    with output.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return InvertProof(width, height, source.sha256, digest.hexdigest(), width * height)
