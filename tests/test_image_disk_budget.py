from types import SimpleNamespace
from threading import Event, Semaphore
import asyncio

import pytest

from backend.image import storage, project_import, project_export
from backend.image import assets as asset_module
from backend.image.assets import ImageAssetStore
from backend.image.results import ImageResultStore


def test_writes_on_same_volume_are_added_before_free_space_check(tmp_path, monkeypatch):
    first = tmp_path / "a"
    second = tmp_path / "not-created" / "b"
    calls = []

    def usage(path):
        calls.append(path)
        return SimpleNamespace(free=storage.DISK_HEADROOM_BYTES + 299)

    monkeypatch.setattr(storage.shutil, "disk_usage", usage)
    with pytest.raises(ValueError, match="磁盘"):
        storage.require_disk_space([(first, 100), (second, 200)])
    assert len(calls) == 1
    storage.require_disk_space([(first, 100), (second, 199)])
    assert not first.exists() and not second.exists()


def test_low_space_refuses_import_before_extraction_or_fiji(tmp_path, monkeypatch):
    # Reuse a real package fixture builder, without running its tests or Fiji.
    from test_image_project import project
    _, package = project(tmp_path)
    assets = ImageAssetStore(tmp_path / "assets")
    results = ImageResultStore(tmp_path / "results")
    identifier, output = results.reserve()
    calls = []
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    monkeypatch.setattr(project_import, "inspect_asset", lambda *args: calls.append(True))
    try:
        with pytest.raises(ValueError, match="磁盘"):
            project_import.restore_grid_project(package, assets, results, identifier, output,
                "no-space", Event(), root=tmp_path / "staging")
        results.discard(identifier)
        assert calls == [] and list((tmp_path / "staging").iterdir()) == []
        assert assets.all_public() == results.all_public() == []
        assert assets._pending_count == assets._pending_bytes == 0
    finally:
        assets.close()
        results.close()


def test_low_space_export_cleans_temp_and_releases_source_lease(tmp_path, monkeypatch):
    from test_image_project import project
    from backend.image.montage import render_exact_grid
    sources, _ = project(tmp_path)
    assets = ImageAssetStore(tmp_path / "assets")
    adopted = assets.adopt_many(sources)
    results = ImageResultStore(tmp_path / "results")
    identifier, output = results.reserve()
    results.finish(identifier, render_exact_grid(adopted, 2, 3, output))
    gate = Semaphore(1)
    root = tmp_path / "exports"
    monkeypatch.setattr(storage.shutil, "disk_usage", lambda path: SimpleNamespace(free=0))
    try:
        with pytest.raises(ValueError, match="磁盘"):
            project_export.prepare_project_export(identifier, assets, results, root=root, gate=gate)
        assert list(root.iterdir()) == [] and assets._leases == {}
        assert gate.acquire(blocking=False)
        gate.release()
        assert results.get(identifier).path.is_file()
    finally:
        assets.close()
        results.close()


def test_space_pressure_during_upload_refunds_all_pending_bytes(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    calls = []

    def space(writes):
        calls.append(writes)
        if len(calls) == 3:
            raise ValueError("synthetic disk pressure after first chunk")

    class Upload:
        filename = "test.tif"
        size = None
        closed = False
        chunks = [b"aa", b"bb", b""]

        async def read(self, size):
            return self.chunks.pop(0)

        async def close(self):
            self.closed = True

    monkeypatch.setattr(asset_module, "require_disk_space", space)
    upload = Upload()
    try:
        with pytest.raises(ValueError, match="disk pressure"):
            asyncio.run(store.add(upload))
        assert upload.closed and store.all_public() == []
        assert store._pending_count == store._pending_bytes == 0
        assert list(store.session.iterdir()) == []
    finally:
        store.close()
