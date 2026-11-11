from hashlib import sha256
import json
from zipfile import ZipFile

import numpy as np
from PIL import Image
import pytest

from backend.image.assets import ImageAsset
from backend.image.montage import render_exact_grid
from backend.image.project import read_grid_project, save_grid_project


def project(tmp_path):
    assets = []
    for index in range(2):
        path = tmp_path / f"original-{index}.png"
        Image.new("RGBA", (24 + index, 20), (199, 33, 77, index)).save(path)
        assets.append(ImageAsset(f"input-{index}", path.name, path.stat().st_size,
                                 sha256(path.read_bytes()).hexdigest(), path))
    proof = render_exact_grid(assets, 2, 3, tmp_path / "grid.tif")
    annotations = [{"kind": "scale_bar", "asset_id": assets[0].id, "offset_x": 2,
                    "offset_y": 15, "length_um": 1, "x_um_per_pixel": 0.25,
                    "color": "#000000"}]
    target = tmp_path / "project.bfsimg"
    save_grid_project(assets, proof, annotations, target)
    return assets, target


def rewrite(original, target, mutate_manifest=None, mutate_member=None, extra=None):
    with ZipFile(original) as source, ZipFile(target, "x") as output:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "project.json" and mutate_manifest:
                manifest = json.loads(data)
                mutate_manifest(manifest)
                data = json.dumps(manifest).encode()
            elif mutate_member and item.filename == "sources/0.bin":
                data = b"x" * len(data)
            output.writestr(item.filename, data)
        if extra:
            output.writestr(extra, b"unexpected")


def test_portable_recipe_retains_original_bytes_and_pending_verification(tmp_path):
    assets, package = project(tmp_path)
    pending = read_grid_project(package, tmp_path / "restored")
    assert pending.verification_status == "requires_fresh_inspection"
    assert pending.manifest.grid.columns == 2 and pending.manifest.grid.gap_px == 3
    assert pending.manifest.annotations[0]["asset_id"] == "s0"
    for asset, path in zip(assets, pending.source_paths):
        assert path.read_bytes() == asset.path.read_bytes()
        with Image.open(path) as image:
            assert image.getpixel((0, 0))[:3] == (199, 33, 77)
    reopened = [ImageAsset(s.key, s.original_name, s.bytes, s.sha256, path)
                for s, path in zip(pending.manifest.sources, pending.source_paths)]
    proof = render_exact_grid(reopened, pending.manifest.grid.columns,
                              pending.manifest.grid.gap_px, tmp_path / "regenerated.tif")
    with Image.open(tmp_path / "grid.tif") as first, Image.open(tmp_path / "regenerated.tif") as second:
        assert np.array_equal(np.asarray(first), np.asarray(second))
    assert proof.grid_recipe == {"columns": 2, "gap_px": 3}


@pytest.mark.parametrize("case", ["unknown_field", "path", "digest", "extra"])
def test_invalid_packages_are_rejected_without_partial_extraction(tmp_path, case):
    _, package = project(tmp_path)
    changed = tmp_path / "changed.bfsimg"
    mutate = (lambda m: m.update(command="execute me")) if case == "unknown_field" else (
        lambda m: m["sources"][0].update(member="../escape.tif")) if case == "path" else None
    rewrite(package, changed, mutate, case == "digest", "../outside.txt" if case == "extra" else None)
    destination = tmp_path / "restore"
    with pytest.raises(ValueError):
        read_grid_project(changed, destination)
    assert not destination.exists() and not (tmp_path / "outside.txt").exists()


def test_existing_export_or_destination_is_never_overwritten(tmp_path):
    assets, package = project(tmp_path)
    before = package.read_bytes()
    proof = render_exact_grid(assets, 2, 3, tmp_path / "second.tif")
    with pytest.raises(FileExistsError):
        save_grid_project(assets, proof, [], package)
    assert package.read_bytes() == before
    destination = tmp_path / "existing"
    destination.mkdir()
    marker = destination / "keep.txt"
    marker.write_text("keep")
    with pytest.raises(FileExistsError):
        read_grid_project(package, destination)
    assert marker.read_text() == "keep"


def test_recorded_axes_remain_claims_without_promoting_to_live_assets(tmp_path):
    _, package = project(tmp_path)
    changed = tmp_path / "claims.bfsimg"
    rewrite(package, changed, lambda m: m["sources"][0].update(
        recorded_metadata={"axes": [{"name": "X", "scale": 999, "unit": "um"}]}))
    pending = read_grid_project(changed, tmp_path / "pending")
    assert pending.verification_status == "requires_fresh_inspection"
    assert pending.manifest.sources[0].recorded_metadata["axes"][0]["scale"] == 999
