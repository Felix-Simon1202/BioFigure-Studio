from dataclasses import replace
from hashlib import sha256

import numpy as np
from PIL import Image
import pytest

from backend.image.assets import ImageAsset
from backend.image.calibration import shared_spacing
from backend.image.montage import render_exact_grid


def source(tmp_path):
    path = tmp_path / "source.tif"
    pixels = np.arange(24 * 32, dtype=np.uint16).reshape(24, 32) * 73
    Image.fromarray(pixels).save(path)
    metadata = {"axes": [{"name": "X", "length": 32, "scale": 0.25, "unit": "um"},
                         {"name": "Y", "length": 24, "scale": 0.5, "unit": "um"}]}
    return ImageAsset("first", path.name, path.stat().st_size, sha256(path.read_bytes()).hexdigest(), path, metadata), pixels


def test_grid_retains_nonisotropic_spacing_without_claiming_full_metadata(tmp_path):
    asset, expected = source(tmp_path)
    output = tmp_path / "grid.tif"
    proof = render_exact_grid([asset, replace(asset, id="second")], 2, 3, output)
    assert proof.public()["spatial_spacing_preserved"]
    assert not proof.public()["metadata_preserved"]
    with Image.open(output) as saved:
        assert float(saved.tag_v2[282]) == 4 and float(saved.tag_v2[283]) == 2
        assert saved.tag_v2[296] == 1 and "unit=um\n" in saved.tag_v2[270]
        pixels = np.asarray(saved)
        assert pixels.dtype == expected.dtype
        assert np.array_equal(pixels[:, :32], expected)
        assert np.array_equal(pixels[:, 35:], expected)


@pytest.mark.parametrize("field,value", [("scale", 0.3), ("scale", 0), ("scale", float("nan")),
                                         ("scale", True), ("unit", "inch"), ("length", 33)])
def test_mixed_or_invalid_calibration_never_becomes_shared_scale(tmp_path, field, value):
    asset, _ = source(tmp_path)
    axes = [dict(axis) for axis in asset.metadata["axes"]]
    axes[0][field] = value
    other = replace(asset, id="second", metadata={"axes": axes})
    assert shared_spacing([asset, other], [(32, 24), (32, 24)]) is None


def test_equivalent_units_and_missing_metadata_are_explicit(tmp_path):
    asset, _ = source(tmp_path)
    other = replace(asset, id="second", metadata={"axes": [
        {"name": "X", "length": 32, "scale": 250, "unit": "nm"},
        {"name": "Y", "length": 24, "scale": 500, "unit": "nm"}]})
    assert shared_spacing([asset, other], [(32, 24)] * 2)["x_um_per_pixel"] == 0.25
    assert shared_spacing([asset, replace(other, metadata=None)], [(32, 24)] * 2) is None
