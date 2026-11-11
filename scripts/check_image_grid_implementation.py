"""Run the reviewed local grid implementation against independent fixtures.

Developer-only opt-in tool: the implementation directory is an explicit local
checkout, and the destination must be new. No runtime download or HTTP service.
"""

import argparse
from hashlib import sha256
import importlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_image_grid_result import verify_grid  # noqa: E402


def check(implementation: Path, fixtures: Path, destination: Path) -> dict:
    implementation = implementation.resolve()
    module_file = implementation / "backend" / "image" / "montage.py"
    module_hash = sha256(module_file.read_bytes()).hexdigest()
    sys.path.insert(0, str(implementation))
    production = importlib.import_module("backend.image.montage")
    if Path(production.__file__).resolve() != module_file:
        raise ValueError("A different implementation module was already imported")
    destination.mkdir(parents=True, exist_ok=False)
    cases = {
        "rgb_different_sizes": ["rgb8.tif", "odd_rgb8.tif"],
        "rgba_hidden_rgb": ["rgba8.png", "rgba8.png"],
        "uint16": ["灰度16_非等距标定.tif"] * 2,
        "float32": ["float32_signed.tif"] * 2,
    }
    results = []
    for label, files in cases.items():
        assets, mapping = [], {}
        for index, name in enumerate(files):
            source = fixtures / name
            data_hash = sha256(source.read_bytes()).hexdigest()
            identifier = sha256(f"{label}:{index}".encode()).hexdigest()[:32]
            assets.append(production.ImageAsset(identifier, name, source.stat().st_size, data_hash, source))
            mapping[identifier] = name
        output = destination / f"{label}.tif"
        proof = production.render_exact_grid(assets, 2, 3, output).public()
        report = verify_grid(fixtures, output, proof, mapping)
        (destination / f"{label}.contract.json").write_text(
            json.dumps({"proof": proof, "fixture_for_asset": mapping}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        results.append({"case": label, "proof": proof, "independent_report": report})
    if sha256(module_file.read_bytes()).hexdigest() != module_hash:
        raise ValueError("Implementation changed during verification; repeat against a stable snapshot")
    evidence = {
        "schema_version": "1.0", "date": "2026-10-23", "source": "synthetic fixtures only",
        "implementation_file": "backend/image/montage.py", "implementation_sha256": module_hash,
        "scope": "four saved single-plane grids; does not verify metadata, stacks, annotations, batch, UI or full Fiji parity",
        "all_grids_preserved": all(item["independent_report"]["pixel_identity_verified"] for item in results),
        "cases": results,
    }
    (destination / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("implementation", type=Path)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    result = check(args.implementation, args.fixtures, args.destination)
    print(f"Independent grid checks: {sum(item['independent_report']['pixel_identity_verified'] for item in result['cases'])}/{len(result['cases'])}")
    raise SystemExit(0 if result["all_grids_preserved"] else 1)
