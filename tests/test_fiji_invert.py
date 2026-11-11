"""Independent pixel guard around the pinned Fiji Invert command."""

from hashlib import sha256

from PIL import Image
import pytest

from backend.image.assets import ImageAsset
from backend.image.invert import validate_invert_input, verify_inversion


def test_non_inverted_fiji_result_is_never_published(tmp_path):
    source_path = tmp_path / "source.tif"
    output_path = tmp_path / "output.tif"
    original = Image.frombytes("L", (3, 2), bytes([0, 1, 120, 220, 254, 255]))
    original.save(source_path)
    original.save(output_path)
    asset = ImageAsset("a" * 32, "source.tif", source_path.stat().st_size,
                       sha256(source_path.read_bytes()).hexdigest(), source_path)
    validate_invert_input(asset)
    with pytest.raises(ValueError, match="逐像素核验不一致"):
        verify_inversion(asset, output_path)
