import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from hashlib import sha256
from io import BytesIO
from threading import Event

from fastapi import UploadFile
import pytest

from backend.image import assets as module
from backend.image.assets import ImageAsset, ImageAssetImportCancelled, ImageAssetStore


def source(tmp_path, name, data):
    path = tmp_path / name
    path.write_bytes(data)
    return ImageAsset(name, name, len(data), sha256(data).hexdigest(), path)


def test_transaction_publishes_all_sources_and_preserves_originals(tmp_path):
    store = ImageAssetStore(tmp_path / "assets")
    original = [source(tmp_path, "first.tif", b"first"), source(tmp_path, "second.png", b"second")]
    try:
        copied = store.adopt_many(original)
        assert {item["id"] for item in store.all_public()} == {item.id for item in copied}
        for before, after in zip(original, copied):
            assert before.path.read_bytes() == after.path.read_bytes()
            assert before.path != after.path and after.metadata is None
        assert store._pending_count == store._pending_bytes == 0
    finally:
        store.close()


def test_failed_second_source_rolls_back_without_deleting_existing_assets(tmp_path):
    store = ImageAssetStore(tmp_path / "assets")
    existing = asyncio.run(store.add(UploadFile(BytesIO(b"keep"), filename="keep.tif")))
    first = source(tmp_path, "first.tif", b"first")
    second = replace(source(tmp_path, "second.tif", b"second"), sha256="0" * 64)
    try:
        with pytest.raises(ValueError):
            store.adopt_many([first, second])
        assert [item["id"] for item in store.all_public()] == [existing.id]
        assert existing.path.read_bytes() == b"keep"
        assert len(list(store.session.iterdir())) == 1
        assert store._pending_count == store._pending_bytes == 0
    finally:
        store.close()


def test_partial_import_is_invisible_and_upload_shares_its_reserved_budget(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets", max_assets=3, max_session_bytes=10)
    sources = [source(tmp_path, f"{i}.tif", b"1234") for i in range(2)]
    original = module._copy_import_source
    entered, resume = Event(), Event()

    def held(asset, target, cancel):
        if asset.id == sources[1].id:
            entered.set()
            assert resume.wait(5)
        return original(asset, target, cancel)

    monkeypatch.setattr(module, "_copy_import_source", held)
    try:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(store.adopt_many, sources)
            try:
                assert entered.wait(5)
                assert store.all_public() == []
                assert len(list(store.session.iterdir())) == 1
                with pytest.raises(ValueError):
                    asyncio.run(store.add(UploadFile(BytesIO(b"abc"), filename="third.tif")))
                with pytest.raises(ValueError):
                    store.close()
            finally:
                resume.set()
            assert len(future.result(5)) == 2
        assert len(store.all_public()) == 2
        assert store._pending_count == store._pending_bytes == 0
    finally:
        store.close()


def test_upload_reservation_blocks_import_and_cancellation_refunds_it(tmp_path):
    store = ImageAssetStore(tmp_path / "assets", max_session_bytes=10)
    incoming = source(tmp_path, "import.tif", b"12345678")

    async def run():
        paused = asyncio.Event()
        waiting = asyncio.Event()

        class PausedUpload:
            filename, size, reads = "upload.tif", None, 0

            async def read(self, _):
                self.reads += 1
                if self.reads == 1:
                    return b"1234"
                paused.set()
                await waiting.wait()
                return b""

            async def close(self):
                pass

        task = asyncio.create_task(store.add(PausedUpload()))
        await asyncio.wait_for(paused.wait(), 2)
        try:
            with pytest.raises(ValueError):
                store.adopt_many([incoming])
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task

    try:
        asyncio.run(run())
        assert store._pending_count == store._pending_bytes == 0
        assert list(store.session.iterdir()) == []
        assert len(store.adopt_many([incoming])) == 1
    finally:
        store.close()


def test_cancelled_import_never_publishes_or_leaves_owned_files(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    originals = [source(tmp_path, f"{i}.tif", b"123") for i in range(2)]
    cancel = Event()
    original_copy = module._copy_import_source

    def cancel_after_copy(asset, target, token):
        original_copy(asset, target, token)
        cancel.set()

    monkeypatch.setattr(module, "_copy_import_source", cancel_after_copy)
    try:
        with pytest.raises(ImageAssetImportCancelled):
            store.adopt_many(originals, cancel)
        assert store.all_public() == [] and list(store.session.iterdir()) == []
        assert store._pending_count == store._pending_bytes == 0
    finally:
        store.close()


def test_staged_transaction_cannot_publish_after_context_exit(tmp_path):
    store = ImageAssetStore(tmp_path / "assets")
    incoming = source(tmp_path, "input.tif", b"123")
    try:
        with store.stage_many([incoming]) as staged:
            assert store.all_public() == []
        assert list(store.session.iterdir()) == []
        with pytest.raises(ValueError, match="事务已结束"):
            staged.commit()
        assert store.all_public() == []
        assert store._pending_count == store._pending_bytes == 0
    finally:
        store.close()
