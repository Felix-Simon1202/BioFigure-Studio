"""Deliberate corruptions of saved grids for the independent acceptance tool."""

from hashlib import sha256

import numpy as np
from PIL import Image
import pytest

from scripts.generate_image_acceptance_fixtures import generate
from scripts.verify_image_grid_result import verify_grid


@pytest.fixture
def saved_grid(tmp_path):
    root = tmp_path / "fixtures"
    generate(root)

    def build(filename):
        source = np.load(root / (filename + ".expected.npy"), allow_pickle=False)
        h, w = source.shape[:2]
        assembled = np.zeros((h + 2, w * 2 + 5, *source.shape[2:]), dtype=source.dtype)
        assembled[1:1 + h, 1:1 + w] = source
        assembled[1:1 + h, w + 4:2 * w + 4] = source
        output = tmp_path / "grid.tif"
        Image.fromarray(assembled).save(output)
        with Image.open(output) as opened:
            mode = opened.mode
        proof = {"width": assembled.shape[1], "height": assembled.shape[0],
                 "mode": mode, "format": "TIFF", "verified_pixels": 2 * w * h,
                 "output_sha256": sha256(output.read_bytes()).hexdigest(),
                 "placements": [
                     {"asset_id": "a", "x": 1, "y": 1, "width": w, "height": h},
                     {"asset_id": "b", "x": w + 4, "y": 1, "width": w, "height": h},
                 ]}
        return root, output, proof, {"a": filename, "b": filename}, assembled

    return build


@pytest.mark.parametrize("filename", [
    "rgb8.tif", "rgba8.png", "灰度16_非等距标定.tif", "float32_signed.tif", "odd_rgb8.tif",
])
def test_independent_checker_accepts_exact_bits_for_each_supported_fixture(saved_grid, filename):
    root, output, proof, mapping, _ = saved_grid(filename)
    report = verify_grid(root, output, proof, mapping)
    assert report["pixel_identity_verified"]
    assert not report["metadata_verified"]


def test_checker_detects_change_to_rgb_hidden_by_zero_alpha(saved_grid):
    root, output, proof, mapping, pixels = saved_grid("rgba8.png")
    assert pixels[1, 1, 3] == 0
    pixels[1, 1, 0] = 0
    Image.fromarray(pixels).save(output)
    # A producer recomputing its file hash must not hide a sample mismatch.
    proof["output_sha256"] = sha256(output.read_bytes()).hexdigest()
    report = verify_grid(root, output, proof, mapping)
    assert not report["pixel_identity_verified"]
    region = report["regions"][0]
    assert region["different_pixels"] == region["different_samples"] == 1
    assert region["first_difference"] == {"source_xy": [0, 0], "output_xy": [1, 1]}


def test_checker_detects_background_and_false_reported_count(saved_grid):
    root, output, proof, mapping, pixels = saved_grid("rgb8.tif")
    pixels[0, 0, 0] = 1
    Image.fromarray(pixels).save(output)
    proof["output_sha256"] = sha256(output.read_bytes()).hexdigest()
    proof["verified_pixels"] -= 1
    report = verify_grid(root, output, proof, mapping)
    assert not report["background_is_zero"]
    assert not report["reported_pixel_count_matches"]
    assert not report["pixel_identity_verified"]
    assert all(item["pixel_identity_verified"] for item in report["regions"])


def test_checker_detects_signed_zero_bit_change_in_float_image(saved_grid):
    root, output, proof, mapping, pixels = saved_grid("float32_signed.tif")
    assert pixels[1, 3] == 0 and not np.signbit(pixels[1, 3])
    pixels[1, 3] = -0.0
    Image.fromarray(pixels).save(output)
    proof["output_sha256"] = sha256(output.read_bytes()).hexdigest()
    report = verify_grid(root, output, proof, mapping)
    assert not report["pixel_identity_verified"]
    assert report["regions"][0]["different_samples"] == 1


def test_checker_rejects_lower_bit_depth_and_changed_file_hash(saved_grid):
    root, output, proof, mapping, pixels = saved_grid("灰度16_非等距标定.tif")
    Image.fromarray(pixels.astype(np.uint8)).save(output)
    report = verify_grid(root, output, proof, mapping)
    assert not report["output_hash_matches"]
    assert not report["pixel_identity_verified"]
    assert not report["regions"][0]["dtype_matches"]


@pytest.mark.parametrize("invalid", ["overlap", "outside", "fraction", "missing_source", "budget"])
def test_checker_refuses_ambiguous_geometry_or_unbounded_decode(saved_grid, invalid):
    root, output, proof, mapping, _ = saved_grid("rgb8.tif")
    options = {}
    if invalid == "overlap":
        proof["placements"][1]["x"] = 2
    elif invalid == "outside":
        proof["placements"][1]["x"] = 10000
    elif invalid == "fraction":
        proof["placements"][0]["x"] = 1.5
    elif invalid == "missing_source":
        mapping["unused"] = "odd_rgb8.tif"
    else:
        options["max_pixels"] = 1
    with pytest.raises(ValueError):
        verify_grid(root, output, proof, mapping, **options)
