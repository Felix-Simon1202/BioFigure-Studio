"""Safety and truthfulness checks for the incomplete Fiji integration."""

import json
import asyncio
from io import BytesIO
from hashlib import sha256
import pytest

from fastapi.testclient import TestClient
from fastapi import UploadFile

from backend.api.app import app
from backend.image import api, catalog
from backend.image import assets
from backend.image import fiji_process
from backend.image.assets import ImageAssetStore
from scripts.prepare_fiji_runtime import EXPECTED_SHA256, inspect_archive


def test_image_inventory_never_marks_discovery_as_parity(tmp_path, monkeypatch):
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps({"schema_version": "1.0", "snapshot_id": "test", "items": [
        {"id": "one", "status": {"discovered": True, "source_reviewed": False,
                                  "runtime_verified": False, "ui_adapted": False,
                                  "parity_verified": False}},
    ]}), encoding="utf-8")
    result = catalog.load_inventory(path)
    assert result["counts"] == {"discovered": 1, "source_reviewed": 0,
                                 "runtime_verified": 0, "ui_adapted": 0,
                                 "parity_verified": 0}


def test_asset_upload_uses_opaque_reference(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path)
    monkeypatch.setattr(api, "store", temporary_store)
    client = TestClient(app)
    response = client.post("/api/image/assets", files={"file": ("folder/test.ome.tif", b"synthetic", "image/tiff")})
    assert response.status_code == 201
    payload = response.json()
    assert payload["sha256"] and payload["original_name"] == "test.ome.tif"
    assert "path" not in payload
    assert payload["metadata_status"] == "not_inspected"
    assert client.get("/api/image/assets/" + payload["id"]).status_code == 200
    assert client.delete("/api/image/assets/" + payload["id"]).status_code == 204
    assert list(tmp_path.rglob("*.tif")) == []
    assert client.get("/api/image/assets/missing").status_code == 404
    temporary_store.close()


def test_asset_quota_and_cancellation_leave_no_partial_file(tmp_path, monkeypatch):
    monkeypatch.setattr(assets, "MAX_SESSION_BYTES", 5)
    temporary_store = ImageAssetStore(tmp_path)
    first = UploadFile(file=BytesIO(b"1234"), filename="first.tif")
    asyncio.run(temporary_store.add(first))
    second = UploadFile(file=BytesIO(b"567"), filename="second.tif")
    try:
        asyncio.run(temporary_store.add(second))
    except ValueError:
        pass
    else:
        raise AssertionError("Expected upload to respect the total quota")
    assert len(list(temporary_store.session.iterdir())) == 1

    class CancelledUpload:
        filename = "cancelled.tif"
        size = None
        reads = 0
        closed = False

        async def read(self, _size):
            self.reads += 1
            if self.reads == 1:
                return b"x"
            raise asyncio.CancelledError

        async def close(self):
            self.closed = True

    cancelled = CancelledUpload()
    try:
        asyncio.run(temporary_store.add(cancelled))
    except asyncio.CancelledError:
        pass
    else:
        raise AssertionError("Expected cancellation")
    assert cancelled.closed
    assert len(list(temporary_store.session.iterdir())) == 1
    temporary_store.close()
    assert not temporary_store.session.exists()


def test_official_archive_checksum_required(tmp_path):
    fake = tmp_path / "fiji-latest-win64-jdk.zip"
    fake.write_bytes(b"not official")
    try:
        inspect_archive(fake)
    except ValueError as error:
        assert "SHA-256 mismatch" in str(error)
    else:
        raise AssertionError(f"Expected official SHA-256 {EXPECTED_SHA256} to be enforced")


def test_runtime_receipt_cannot_escape_pinned_directory(tmp_path, monkeypatch):
    runtime = tmp_path / "Fiji.app"
    runtime.mkdir()
    (runtime / "fiji-windows-x64.exe").write_bytes(b"launcher")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"archive_sha256": EXPECTED_SHA256,
                                   "components": [{"path": "../outside.bin", "bytes": 1,
                                                   "sha256": "0" * 64}]}), encoding="utf-8")
    monkeypatch.setattr(fiji_process, "RUNTIME", runtime)
    monkeypatch.setattr(fiji_process, "RECEIPT", receipt)
    try:
        fiji_process.verify_runtime()
    except fiji_process.FijiUnavailable as error:
        assert "不受控路径" in str(error)
    else:
        raise AssertionError("Expected traversal in runtime receipt to be rejected")


def test_runtime_rejects_unlisted_plugin(tmp_path, monkeypatch):
    runtime = tmp_path / "Fiji.app"
    runtime.mkdir()
    for name in ("jars", "plugins", "scripts", "macros", "java", "lib"):
        (runtime / name).mkdir()
    launcher = runtime / "fiji-windows-x64.exe"
    launcher.write_bytes(b"launcher")
    (runtime / "plugins" / "unreviewed.jar").write_bytes(b"plugin")
    receipt = tmp_path / "receipt.json"
    receipt.write_text(json.dumps({"archive_sha256": EXPECTED_SHA256,
                                   "components": [{"path": launcher.name, "bytes": launcher.stat().st_size,
                                                   "sha256": sha256(launcher.read_bytes()).hexdigest()}]}), encoding="utf-8")
    monkeypatch.setattr(fiji_process, "RUNTIME", runtime)
    monkeypatch.setattr(fiji_process, "RECEIPT", receipt)
    with pytest.raises(fiji_process.FijiUnavailable, match="清单之外"):
        fiji_process.verify_runtime()


def test_asset_lease_prevents_submit_remove_race(tmp_path):
    temporary_store = ImageAssetStore(tmp_path)
    source = UploadFile(file=BytesIO(b"synthetic"), filename="lease.tif")
    asset = asyncio.run(temporary_store.add(source))
    assert temporary_store.acquire(asset.id) == asset
    with pytest.raises(ValueError, match="任务中使用"):
        temporary_store.remove(asset.id)
    temporary_store.release(asset.id)
    temporary_store.remove(asset.id)
    assert not asset.path.exists()
    temporary_store.close()


def test_fixed_script_report_budget_rejects_growth_and_cleans_process(tmp_path, monkeypatch):
    from threading import Event
    from uuid import uuid4
    source = tmp_path / 'synthetic.tif'; source.write_bytes(b'synthetic')
    asset = assets.ImageAsset(id='synthetic', name='synthetic.tif', bytes=9,
        sha256=sha256(b'synthetic').hexdigest(), path=source)
    monkeypatch.setattr(fiji_process, 'JOBS_ROOT', tmp_path / 'jobs')
    monkeypatch.setattr(fiji_process, 'verify_runtime', lambda: tmp_path / 'launcher.exe')
    stopped = []
    class Process:
        pid = 12345
        def __init__(self, *args, **kwargs):
            request = json.loads(Path(kwargs['env']['BFS_FIJI_JOB_JSON']).read_text(encoding='utf-8'))
            Path(request['output_path']).write_bytes(b'x' * 65537)
        def poll(self): return None if not stopped else 0
        def terminate(self): stopped.append(True)
        def wait(self, timeout): return 0
    from pathlib import Path
    monkeypatch.setattr(fiji_process.subprocess, 'Popen', Process)
    monkeypatch.setattr(fiji_process.subprocess, 'run', lambda *args, **kwargs: None)
    monkeypatch.setattr(fiji_process.time, 'sleep', lambda *_: (_ for _ in ()).throw(AssertionError('oversize report waited')))
    with pytest.raises(ValueError, match='容量上限'):
        fiji_process._run_script(asset, uuid4().hex, Event(), fiji_process.SCRIPT)
    assert stopped and list((tmp_path / 'jobs').iterdir()) == []
