"""Transaction tests use a stub inspector; the opt-in test runs actual Fiji."""

import asyncio
from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
from threading import Event
from zipfile import ZipFile

from fastapi import UploadFile
from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest

from backend.api.app import app
from backend.image import api, fiji_process, project_import
from backend.image.assets import ImageAsset, ImageAssetStore, ImageAssetImportCancelled
from backend.image.calibration import spacing_tags
from backend.image.jobs import ImageJobManager
from backend.image.montage import render_exact_grid
from backend.image.project import save_grid_project
from backend.image.results import ImageResultStore


def metadata():
    return {"axes": [{"name": "X", "length": 24, "unit": "um", "scale": .25},
                     {"name": "Y", "length": 20, "unit": "um", "scale": .5}],
            "pixel_type": "net.imglib2.type.numeric.integer.UnsignedShortType", "bit_depth": 16,
            "channels": None}


@pytest.fixture
def package(tmp_path):
    originals = []
    arrays = []
    for index in range(2):
        path = tmp_path / f"原图{index}.tif"
        pixels = (np.arange(480, dtype=np.uint16).reshape(20, 24) * 117 + index).astype(np.uint16)
        Image.fromarray(pixels).save(path, tiffinfo=spacing_tags({"x_um_per_pixel": .25, "y_um_per_pixel": .5}))
        originals.append(ImageAsset(f"old-{index}", path.name, path.stat().st_size,
            sha256(path.read_bytes()).hexdigest(), path, metadata()))
        arrays.append(pixels)
    proof = render_exact_grid(originals, 2, 3, tmp_path / "old-grid.tif")
    source = tmp_path / "original.bfsimg"
    save_grid_project(originals, proof, [{"kind": "scale_bar", "asset_id": "old-0",
        "offset_x": 2, "offset_y": 15, "length_um": 1, "color": "#000000",
        "calibration_source": "fiji_inspected_axes"}], source)
    # Package claims are forged, while its original source bytes are unchanged.
    changed = tmp_path / "claims.bfsimg"
    with ZipFile(source) as archive, ZipFile(changed, "x") as output:
        for item in archive.infolist():
            data = archive.read(item.filename)
            if item.filename == "project.json":
                manifest = json.loads(data)
                manifest["sources"][0]["recorded_metadata"]["axes"][0]["scale"] = 999
                data = json.dumps(manifest).encode()
            output.writestr(item.filename, data)
    return changed, originals, arrays


@pytest.fixture
def stores(tmp_path):
    assets = ImageAssetStore(tmp_path / "assets")
    results = ImageResultStore(tmp_path / "results")
    try:
        yield assets, results
    finally:
        assets.close()
        results.close()


def test_rebuild_uses_fresh_axes_and_rebinds_annotations(tmp_path, monkeypatch, package, stores):
    archive, originals, arrays = package
    assets, results = stores
    calls = []

    def inspect(source, job_id, cancel):
        assert source.metadata is None and assets.all_public() == []
        calls.append(source.id)
        return metadata()

    monkeypatch.setattr(project_import, "inspect_asset", inspect)
    identifier, output = results.reserve()
    restored = project_import.restore_grid_project(archive, assets, results, identifier, output,
        "test-import", Event(), root=tmp_path / "staging")
    assert calls == ["s0", "s1"] and len(assets.all_public()) == 2
    assert restored["source_verification"] == "fresh_fiji_inspection"
    assert all(asset["metadata_status"] == "fiji_inspected" for asset in restored["assets"])
    first = assets.get(restored["assets"][0]["id"])
    assert first.metadata["axes"][0]["scale"] == .25
    assert first.path.read_bytes() == originals[0].path.read_bytes()
    annotation = results.get_annotations(identifier)["items"][0]
    assert annotation["asset_id"] == first.id and annotation["length_px"] == 4
    with Image.open(output) as image:
        actual = np.asarray(image)
        assert np.array_equal(actual[:, :24], arrays[0])
        assert np.array_equal(actual[:, 27:51], arrays[1])
    assert list((tmp_path / "staging").iterdir()) == []


@pytest.mark.parametrize("failure", ["inspection", "capacity", "cancel", "publication"])
def test_failures_keep_existing_assets_and_publish_no_partial_project(tmp_path, monkeypatch, package, stores, failure):
    archive, _, _ = package
    assets, results = stores
    old = asyncio.run(assets.add(UploadFile(BytesIO(b"old bytes"), filename="keep.tif")))
    if failure == "capacity":
        assets.max_assets = 2
    calls = []

    def inspect(source, job_id, cancel):
        calls.append(source.id)
        if failure == "inspection" and len(calls) == 2:
            raise ValueError("synthetic failed inspection")
        return metadata()

    monkeypatch.setattr(project_import, "inspect_asset", inspect)
    cancel = Event()
    render = project_import.render_exact_grid

    def rendered(*args):
        proof = render(*args)
        assert len(assets.all_public()) == 1 and results.all_public() == []
        if failure == "cancel":
            cancel.set()
        return proof

    monkeypatch.setattr(project_import, "render_exact_grid", rendered)
    if failure == "publication":
        monkeypatch.setattr(results, "finish", lambda *a, **kw: (_ for _ in ()).throw(ValueError("full result budget")))
    identifier, output = results.reserve()
    with pytest.raises((ValueError, ImageAssetImportCancelled)):
        project_import.restore_grid_project(archive, assets, results, identifier, output,
            "failed-import", cancel, root=tmp_path / "staging")
    results.discard(identifier)
    assert len(assets.all_public()) == 1 and assets.get(old.id).path.read_bytes() == b"old bytes"
    assert results.all_public() == [] and list(results.session.iterdir()) == []
    assert assets._pending_count == assets._pending_bytes == 0
    assert len(list(assets.session.iterdir())) == 1
    assert list((tmp_path / "staging").iterdir()) == []


def test_http_import_admission_cancel_cleanup_and_retry(tmp_path, monkeypatch, package, stores):
    archive, _, _ = package
    assets, results = stores
    manager = ImageJobManager()
    started = Event()
    paused = Event()

    def inspect(source, job_id, cancel):
        started.set()
        while not paused.wait(.01):
            if cancel.is_set():
                raise fiji_process.FijiCancelled()
        return metadata()

    monkeypatch.setattr(project_import, "inspect_asset", inspect)
    monkeypatch.setattr(api, "store", assets)
    monkeypatch.setattr(api, "results", results)
    monkeypatch.setattr(api, "manager", manager)
    monkeypatch.setattr(api, "PROJECT_INPUT_ROOT", tmp_path / "inputs")
    client = TestClient(app)
    data = archive.read_bytes()
    try:
        response = client.post("/api/image/jobs/open-project", files={"file": ("project.bfsimg", data)})
        assert response.status_code == 202 and started.wait(2)
        identifier = response.json()["id"]
        assert client.post("/api/image/jobs/open-project", files={"file": ("second.bfsimg", data)}).status_code == 429
        assert client.post("/api/image/jobs/batch-grid", files={"files": ("x.tif", b"x")},
                           data={"group_size": "1", "columns": "1"}).status_code == 429
        client.post(f"/api/image/jobs/{identifier}/cancel")
        manager.get(identifier).future.result(timeout=5)
        assert manager.get(identifier).state == "cancelled"
        assert assets.all_public() == results.all_public() == []
        assert list((tmp_path / "inputs").iterdir()) == []
        paused.set()
        retry = client.post("/api/image/jobs/open-project", files={"file": ("retry.bfsimg", data)})
        assert retry.status_code == 202
        job = manager.get(retry.json()["id"])
        job.future.result(timeout=5)
        assert job.state == "succeeded", job.error
        assert client.post(f"/api/image/jobs/{job.id}/cancel").json()["state"] == "succeeded"
        assert len(assets.all_public()) == 2 and len(results.all_public()) == 1
        assert list((tmp_path / "inputs").iterdir()) == []
    finally:
        paused.set()
        manager.close()


@pytest.mark.parametrize("mode", ["cancel_queued", "executor_refuses"])
def test_project_submission_or_queued_cancellation_releases_all_reservations(tmp_path, monkeypatch, package, stores, mode):
    archive, _, _ = package
    assets, results = stores
    archive_store = ImageAssetStore(tmp_path / "queued-input")
    item = asyncio.run(archive_store.add(UploadFile(BytesIO(archive.read_bytes()), filename="queued.bfsimg")))
    manager = ImageJobManager()
    released = []
    blocker = Event()
    entered = Event()

    def hold_executor():
        entered.set()
        blocker.wait(5)

    try:
        if mode == "executor_refuses":
            manager._executor.shutdown()
            with pytest.raises(RuntimeError):
                manager.submit_project(archive_store, item.id, assets, results)
            assert archive_store._leases == {}
            assert manager.all_public() == []
            archive_store.close()
        else:
            manager._executor.submit(hold_executor)
            assert entered.wait(2)
            job = manager.submit_project(archive_store, item.id, assets, results,
                admission_release=lambda: released.append(True))
            assert manager.cancel(job.id).state == "cancelled"
            assert released == [True] and not archive_store.session.exists()
        assert results._reserved == set() and results.all_public() == []
        assert list(results.session.iterdir()) == [] and assets.all_public() == []
    finally:
        blocker.set()
        manager.close()
        if archive_store.session.exists():
            archive_store.close()


@pytest.mark.skipif(os.environ.get("BFS_FIJI_PROJECT_RUNTIME") is None,
                    reason="Opt in with the audited local Fiji runtime path")
def test_actual_fiji_reopens_project_and_rejects_forged_metadata(tmp_path, monkeypatch, package, stores):
    runtime = Path(os.environ["BFS_FIJI_PROJECT_RUNTIME"])
    monkeypatch.setattr(fiji_process, "RUNTIME", runtime)
    monkeypatch.setattr(fiji_process, "RECEIPT", runtime.parent / "runtime-receipt.json")
    monkeypatch.setattr(fiji_process, "_verified_stats", None)
    archive, _, arrays = package
    assets, results = stores
    identifier, output = results.reserve()
    restored = project_import.restore_grid_project(archive, assets, results, identifier, output,
        "actual-project", Event(), root=tmp_path / "staging")
    assert len(restored["assets"]) == 2
    first = assets.get(restored["assets"][0]["id"])
    assert first.metadata["bit_depth"] == 16
    assert first.metadata["axes"][0]["scale"] == .25
    with Image.open(output) as image:
        assert np.array_equal(np.asarray(image)[:, :24], arrays[0])
        assert np.array_equal(np.asarray(image)[:, 27:51], arrays[1])
    assert results.get_annotations(identifier)["items"][0]["length_px"] == 4
