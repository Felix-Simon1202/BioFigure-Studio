"""Negative controls for the independent image input acceptance checker."""

import json

import numpy as np
import pytest

from scripts.compare_imagej_fixtures import compare
from scripts.generate_image_acceptance_fixtures import generate


@pytest.fixture
def fixture_probe(tmp_path):
    root = tmp_path / "fixtures"
    manifest = generate(root)
    items = []
    for reference in manifest["items"]:
        pixels = np.load(root / reference["expected_array"], allow_pickle=False)
        sizes = dict(zip(reference["axes"], pixels.shape))
        rgb = reference["axes"] == "YXS"
        if rgb:
            samples = ((pixels[..., 0].astype(np.uint32) << 16)
                       | (pixels[..., 1].astype(np.uint32) << 8)
                       | pixels[..., 2].astype(np.uint32))
        else:
            samples = pixels
        items.append({
            "file": reference["file"], "file_sha256": reference["file_sha256"], "opened": True,
            "width": sizes["X"], "height": sizes["Y"],
            "channels": sizes.get("C", 1), "z_slices": sizes.get("Z", 1),
            "frames": sizes.get("T", 1),
            "planes": sizes.get("C", 1) * sizes.get("Z", 1) * sizes.get("T", 1),
            "bit_depth": 24 if rgb else reference["bit_depth"],
            "pixel_width": (reference["pixel_size_um_xy"] or [1, 1])[0],
            "pixel_height": (reference["pixel_size_um_xy"] or [1, 1])[1],
            "pixel_depth": reference["z_spacing_um"] or 1, "unit": "um",
            "frame_interval": reference["frame_interval_seconds"] or 0,
            "time_unit": "sec", "samples": samples.reshape(-1).tolist(),
        })
    inspection = root / "probe.json"

    def run():
        inspection.write_text(json.dumps({"imagej_version": "synthetic-negative-control", "items": items}), encoding="utf-8")
        return {item["file"]: item for item in compare(root, inspection)["results"]}

    return root, items, run


def test_checker_never_accepts_alpha_absence_even_when_rgb_matches(fixture_probe):
    _, _, run = fixture_probe
    results = run()
    assert sum(item["source_preserved"] for item in results.values()) == 7
    assert results["rgba8.png"]["different_pixels"] == 0
    assert not results["rgba8.png"]["alpha_preserved"]
    assert not results["rgba8.png"]["source_preserved"]


@pytest.mark.parametrize("field,value", [
    ("channels", 1), ("planes", 3), ("bit_depth", 8),
    ("pixel_width", 0.5), ("unit", "inch"),
])
def test_checker_rejects_axis_type_and_calibration_changes(fixture_probe, field, value):
    _, items, run = fixture_probe
    item = next(item for item in items if item["file"] == "channels16.tif")
    item[field] = value
    assert not run()["channels16.tif"]["source_preserved"]


def test_checker_detects_float_sample_and_time_unit_changes(fixture_probe):
    _, items, run = fixture_probe
    floating = next(item for item in items if item["file"] == "float32_signed.tif")
    floating["samples"][0] = 0
    timed = next(item for item in items if item["file"] == "time16.tif")
    timed["time_unit"] = "minute"
    results = run()
    assert results["float32_signed.tif"]["different_pixels"] == 1
    assert not results["float32_signed.tif"]["source_preserved"]
    assert not results["time16.tif"]["time_matches"]
    assert not results["time16.tif"]["source_preserved"]


def test_checker_rejects_stale_reference_and_source(fixture_probe):
    root, _, run = fixture_probe
    reference = root / "rgb8.tif.expected.npy"
    original = np.load(reference, allow_pickle=False)
    np.save(reference, original.astype(np.float32), allow_pickle=False)
    (root / "odd_rgb8.tif").write_bytes(b"changed after probe")
    results = run()
    for filename in ("rgb8.tif", "odd_rgb8.tif"):
        assert not results[filename]["baseline_matches"]
        assert not results[filename]["source_preserved"]


def test_fixture_generator_refuses_existing_output(fixture_probe):
    root, _, _ = fixture_probe
    with pytest.raises(FileExistsError):
        generate(root)
