"""Independently check a saved grid against synthetic NumPy source references.

This acceptance tool does not import the production montage implementation.
It verifies sample bits and placement, not scientific metadata or Fiji parity.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import warnings

import numpy as np
from PIL import Image


def _hash_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_grid(fixtures: Path, output: Path, proof: dict,
                fixture_for_asset: dict[str, str], max_pixels: int = 16_000_000) -> dict:
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    references = {item["file"]: item for item in manifest["items"]}
    placements = proof.get("placements", [])
    if not placements or len(placements) > 1024:
        raise ValueError("Expected between 1 and 1024 explicitly mapped placements")
    if set(fixture_for_asset) != {item["asset_id"] for item in placements}:
        raise ValueError("Every requested source must have a placement and a fixture reference")
    rectangles = []
    for item in placements:
        if any(type(item.get(key)) is not int for key in ("x", "y", "width", "height")):
            raise ValueError("Placements must use integer coordinates and dimensions")
        x, y, width, height = (item[key] for key in ("x", "y", "width", "height"))
        if min(x, y) < 0 or min(width, height) <= 0:
            raise ValueError("Placements must be positive rectangles inside the output")
        for ax, ay, aw, ah in rectangles:
            if x < ax + aw and ax < x + width and y < ay + ah and ay < y + height:
                raise ValueError("Overlapping placements cannot prove the strict grid invariant")
        rectangles.append((x, y, width, height))

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        with Image.open(output) as saved:
            if saved.width * saved.height > max_pixels:
                raise ValueError("Output exceeds the acceptance reader's explicit pixel budget")
            if saved.n_frames != 1:
                raise ValueError("Stack output requires an explicit axis-aware acceptance mapping")
            actual_format, actual_mode, actual_size = saved.format, saved.mode, saved.size
            pixels = np.array(saved)
    width, height = actual_size
    if any(x + w > width or y + h > height for x, y, w, h in rectangles):
        raise ValueError("Placement extends outside the saved output")
    geometry_matches = (proof.get("width") == width and proof.get("height") == height
                        and proof.get("mode") == actual_mode and proof.get("format") == actual_format)
    output_hash_matches = proof.get("output_sha256") == _hash_file(output)
    occupied = np.zeros((height, width), dtype=bool)
    results = []
    for item in placements:
        reference = references[fixture_for_asset[item["asset_id"]]]
        if reference["axes"] not in {"YX", "YXS"}:
            raise ValueError("A C/Z/T fixture requires an explicit axis-aware acceptance mapping")
        expected = np.load(fixtures / reference["expected_array"], mmap_mode="r", allow_pickle=False)
        header = json.dumps({"dtype": expected.dtype.str, "shape": list(expected.shape)}, sort_keys=True).encode()
        expected_hash = sha256(header + b"\n" + np.ascontiguousarray(expected).tobytes()).hexdigest()
        baseline_matches = (expected_hash == reference["pixel_sha256"]
                            and _hash_file(fixtures / reference["file"]) == reference["file_sha256"])
        x, y, w, h = (item[key] for key in ("x", "y", "width", "height"))
        occupied[y:y + h, x:x + w] = True
        region = pixels[y:y + h, x:x + w]
        shape_matches = region.shape == expected.shape
        dtype_matches = region.dtype.str == expected.dtype.str
        different_samples = different_pixels = first_difference = None
        if shape_matches and dtype_matches:
            # Void comparisons preserve all sample bits, including float signed
            # zero, NaN payloads and RGBA RGB values hidden under zero alpha.
            sample_type = np.dtype(f"V{expected.dtype.itemsize}")
            changed = region.view(sample_type) != expected.view(sample_type)
            changed_pixels = np.any(changed, axis=-1) if changed.ndim == 3 else changed
            different_samples = int(np.count_nonzero(changed))
            different_pixels = int(np.count_nonzero(changed_pixels))
            if different_pixels:
                first_y, first_x = np.argwhere(changed_pixels)[0]
                first_difference = {"source_xy": [int(first_x), int(first_y)],
                                    "output_xy": [x + int(first_x), y + int(first_y)]}
        results.append({
            "asset_id": item["asset_id"], "fixture_file": reference["file"],
            "baseline_matches": baseline_matches, "shape_matches": shape_matches,
            "dtype_matches": dtype_matches, "compared_pixels": w * h,
            "different_samples": different_samples, "different_pixels": different_pixels,
            "first_difference": first_difference,
            "pixel_identity_verified": bool(baseline_matches and shape_matches and dtype_matches and different_samples == 0),
        })
    background = pixels[~occupied]
    background_is_zero = bool(np.all(background == 0))
    count_matches = proof.get("verified_pixels") == sum(item["compared_pixels"] for item in results)
    return {
        "scope": "strict non-overlapping single-plane grid sample bits; metadata not verified",
        "metadata_verified": False, "geometry_matches": geometry_matches,
        "output_hash_matches": output_hash_matches, "reported_pixel_count_matches": count_matches,
        "background_is_zero": background_is_zero, "regions": results,
        "pixel_identity_verified": bool(geometry_matches and output_hash_matches and count_matches
                                        and background_is_zero and all(item["pixel_identity_verified"] for item in results)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("output_image", type=Path)
    parser.add_argument("contract", type=Path, help="JSON with proof and fixture_for_asset fields")
    parser.add_argument("report", type=Path)
    options = parser.parse_args()
    contract = json.loads(options.contract.read_text(encoding="utf-8"))
    result = verify_grid(options.fixtures, options.output_image, contract["proof"], contract["fixture_for_asset"])
    options.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Pixel identity verified: {result['pixel_identity_verified']}")
    raise SystemExit(0 if result["pixel_identity_verified"] else 1)
