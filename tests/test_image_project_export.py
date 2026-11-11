import asyncio
from functools import partial
from hashlib import sha256
from io import BytesIO
from threading import Semaphore
from zipfile import ZipFile

from fastapi import UploadFile
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from backend.image import api, project_export
from backend.image.assets import ImageAssetStore
from backend.image.montage import render_exact_grid
from backend.image.results import ImageResultStore
from backend.api.app import app


@pytest.fixture
def saved_grid(tmp_path):
    assets = ImageAssetStore(tmp_path / "assets")
    results = ImageResultStore(tmp_path / "results")
    data = BytesIO()
    Image.new("RGBA", (24, 24), (199, 33, 77, 0)).save(data, format="PNG")
    original = data.getvalue()
    asset = asyncio.run(assets.add(UploadFile(BytesIO(original), filename="原图.png")))
    identifier, output = results.reserve()
    proof = render_exact_grid([asset], 1, 3, output)
    results.finish(identifier, proof)
    results.set_annotations(identifier, [{"kind": "text", "text": "A", "x": 2,
                                        "y": 12, "font_px": 8, "color": "#000000"}])
    try:
        yield assets, results, asset, identifier, original
    finally:
        assets.close()
        results.close()


def test_http_export_contains_original_bytes_and_annotations_and_cleans(tmp_path, monkeypatch, saved_grid):
    assets, results, asset, identifier, original = saved_grid
    root = tmp_path / "exports"
    gate = Semaphore(1)
    monkeypatch.setattr(api, "store", assets)
    monkeypatch.setattr(api, "results", results)
    monkeypatch.setattr(api, "prepare_project_export", partial(project_export.prepare_project_export,
                                                             root=root, gate=gate))
    before = sha256(results.get(identifier).path.read_bytes()).hexdigest()
    response = TestClient(app).get(f"/api/image/results/{identifier}/project")
    assert response.status_code == 200 and ".bfsimg" in response.headers["content-disposition"]
    with ZipFile(BytesIO(response.content)) as archive:
        import json
        manifest = json.loads(archive.read("project.json"))
        assert archive.read("sources/0.bin") == original
        assert manifest["grid"] == {"columns": 1, "gap_px": 3}
        assert manifest["annotations"][0]["text"] == "A"
        assert manifest["sources"][0]["original_name"] == "原图.png"
    assert list(root.iterdir()) == [] and gate.acquire(blocking=False)
    gate.release()
    assert sha256(results.get(identifier).path.read_bytes()).hexdigest() == before
    assert assets.get(asset.id).path.read_bytes() == original


def test_source_lease_and_download_admission_last_until_their_boundaries(tmp_path, monkeypatch, saved_grid):
    assets, results, asset, identifier, _ = saved_grid
    gate = Semaphore(1)
    save = project_export.save_grid_project

    def checked_save(*args):
        with pytest.raises(ValueError, match="任务"):
            assets.remove(asset.id)
        return save(*args)

    monkeypatch.setattr(project_export, "save_grid_project", checked_save)
    exported = project_export.prepare_project_export(identifier, assets, results, root=tmp_path / "exports", gate=gate)
    try:
        with pytest.raises(project_export.ProjectExportBusy):
            project_export.prepare_project_export(identifier, assets, results, root=tmp_path / "exports", gate=gate)
        # A completed archive is self-contained and no longer leases the source.
        assets.remove(asset.id)
        assert exported.path.is_file()
    finally:
        exported.close()
        exported.close()
    assert not exported.path.exists()
    assert gate.acquire(blocking=False) and not gate.acquire(blocking=False)
    gate.release()


@pytest.mark.parametrize("failure", ["missing_source", "tampered_source"])
def test_export_failure_releases_admission_and_leaves_no_temp_files(tmp_path, saved_grid, failure):
    assets, results, asset, identifier, _ = saved_grid
    if failure == "missing_source":
        assets.remove(asset.id)
    else:
        asset.path.write_bytes(b"changed")
    root = tmp_path / "exports"
    gate = Semaphore(1)
    with pytest.raises((KeyError, ValueError)):
        project_export.prepare_project_export(identifier, assets, results, root=root, gate=gate)
    assert list(root.iterdir()) == [] and gate.acquire(blocking=False)
    gate.release()
    # A failed save does not delete the existing result.
    assert results.get(identifier).path.is_file()


def test_response_send_failure_also_cleans_export(tmp_path, saved_grid):
    assets, results, _, identifier, _ = saved_grid
    root = tmp_path / "exports"
    gate = Semaphore(1)
    exported = project_export.prepare_project_export(identifier, assets, results, root=root, gate=gate)
    response = api.ManagedFileResponse(exported.path, cleanup=exported.close)

    async def send(message):
        assert message["type"] != "http.response.pathsend"
        if message["type"] == "http.response.body":
            raise OSError("synthetic disconnected client")

    async def receive():
        return {"type": "http.disconnect"}

    with pytest.raises(OSError):
        asyncio.run(response({"type": "http", "method": "GET", "headers": [],
                              "extensions": {"http.response.pathsend": {}}}, receive, send))
    assert list(root.iterdir()) == [] and gate.acquire(blocking=False)
    gate.release()
