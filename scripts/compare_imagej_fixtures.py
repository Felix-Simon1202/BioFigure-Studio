"""Compare the independent ImageJ read probe with generated NumPy references."""

import argparse
from hashlib import sha256
import json
from pathlib import Path

import numpy as np


def compare(root: Path, inspection: Path) -> dict:
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    observed = json.loads(inspection.read_text(encoding="utf-8"))
    by_name = {item["file"]: item for item in observed["items"]}
    results = []
    for reference in manifest["items"]:
        item = by_name.get(reference["file"])
        if not item or not item.get("opened"):
            results.append({"file": reference["file"], "source_preserved": False, "reason": "not opened"})
            continue
        expected = np.load(root / reference["expected_array"], allow_pickle=False)
        header = json.dumps({"dtype": expected.dtype.str, "shape": list(expected.shape)}, sort_keys=True).encode()
        pixel_hash = sha256(header + b"\n" + np.ascontiguousarray(expected).tobytes()).hexdigest()
        baseline_matches = (pixel_hash == reference["pixel_sha256"]
                            and item.get("file_sha256") == reference["file_sha256"]
                            and sha256((root / reference["file"]).read_bytes()).hexdigest() == reference["file_sha256"])
        axes = reference["axes"]
        sizes = dict(zip(axes, expected.shape))
        rgb = axes == "YXS"
        if rgb:
            expected_samples = (expected[..., 0].astype(np.uint32) << 16) | (expected[..., 1].astype(np.uint32) << 8) | expected[..., 2].astype(np.uint32)
            actual = np.asarray(item["samples"], dtype=np.int64).astype(np.uint32) & 0xFFFFFF
        else:
            expected_samples = expected
            actual = np.asarray(item["samples"])
        shape_matches = actual.size == expected_samples.size
        different = int(np.count_nonzero(actual.reshape(expected_samples.shape) != expected_samples)) if shape_matches else None
        dimensions_match = all(item[key] == value for key, value in {
            "width": sizes["X"], "height": sizes["Y"], "channels": sizes.get("C", 1),
            "z_slices": sizes.get("Z", 1), "frames": sizes.get("T", 1),
        }.items())
        expected_bit_depth = 24 if rgb else reference["bit_depth"]
        dtype_matches = item["bit_depth"] == expected_bit_depth
        planes_match = item["planes"] == sizes.get("C", 1) * sizes.get("Z", 1) * sizes.get("T", 1)
        scale_matches = True
        if reference["pixel_size_um_xy"] is not None:
            scale_matches = bool(np.allclose(reference["pixel_size_um_xy"], [item["pixel_width"], item["pixel_height"]], rtol=0, atol=1e-12)) and item["unit"] in {"um", "µm", "micron"}
        if reference["z_spacing_um"] is not None:
            scale_matches = scale_matches and item["pixel_depth"] == reference["z_spacing_um"]
        time_matches = reference["frame_interval_seconds"] is None or (item["frame_interval"] == reference["frame_interval_seconds"] and item["time_unit"] in {"sec", "s", "second"})
        alpha_preserved = not (rgb and sizes["S"] == 4)
        results.append({
            "file": reference["file"], "different_pixels": different,
            "baseline_matches": baseline_matches, "planes_match": planes_match,
            "dimensions_match": dimensions_match, "bit_depth_matches": dtype_matches,
            "scale_matches": scale_matches, "time_matches": time_matches,
            "alpha_preserved": alpha_preserved,
            "source_preserved": bool(baseline_matches and different == 0 and dimensions_match and planes_match and dtype_matches and scale_matches and time_matches and alpha_preserved),
            "note": "ImageJ1 24-bit image exposes no alpha channel; original RGBA must be retained independently." if not alpha_preserved else "",
        })
    return {"imagej_version": observed["imagej_version"], "imagej_core_sha256": observed.get("imagej_core_sha256"), "scope": "ImageJ1 input decoding only, not command/GUI parity", "all_sources_preserved": all(item["source_preserved"] for item in results), "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("inspection", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = compare(args.fixtures, args.inspection)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for item in result["results"]:
        print(json.dumps(item, ensure_ascii=True))
    raise SystemExit(0 if result["all_sources_preserved"] else 1)
