"""Exercise actual response bodies and result publication/cancellation races."""

import asyncio
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
from threading import Event, Thread

from fastapi import HTTPException, UploadFile
from PIL import Image
import pytest

from backend.image import api
from backend.image.assets import ImageAssetStore
from backend.image.jobs import ImageJobManager
from backend.image.results import ImageResultStore


@dataclass
class Proof:
    output_sha256: str

    def public(self):
        return {"unit_test_file_lifecycle": True}


@pytest.mark.parametrize("kind", ["tiff", "batch"])
@pytest.mark.parametrize("outcome", ["complete", "send_error", "cancelled", "range_error"])
def test_response_lease_blocks_remove_and_is_released_on_every_exit(tmp_path, monkeypatch, kind, outcome):
    store = ImageResultStore(tmp_path / "results", extension=".tif" if kind == "tiff" else ".zip",
        mime_type="image/tiff" if kind == "tiff" else "application/zip")
    monkeypatch.setattr(api, "results" if kind == "tiff" else "batch_results", store)
    identifier, output = store.reserve()
    data = b"synthetic stream payload" * 10000
    output.write_bytes(data)
    store.finish(identifier, Proof(sha256(data).hexdigest()))
    response = api.download_result(identifier) if kind == "tiff" else api.download_batch_result(identifier)
    assert store._leases == {identifier: 1}
    received, statuses = [], []

    async def receive():
        return {"type": "http.disconnect"}

    async def send(message):
        assert message["type"] != "http.response.pathsend"
        with pytest.raises(HTTPException) as refused:
            (api.delete_result if kind == "tiff" else api.delete_batch_result)(identifier)
        assert refused.value.status_code == 409
        with pytest.raises(ValueError, match="下载"):
            store.close()
        with pytest.raises(ValueError, match="下载"):
            store.discard(identifier)
        if message["type"] == "http.response.start":
            statuses.append(message["status"])
        if message["type"] == "http.response.body":
            if outcome == "send_error":
                raise OSError("synthetic broken connection")
            if outcome == "cancelled":
                raise asyncio.CancelledError()
            received.append(message.get("body", b""))

    headers = [(b"range", b"bytes=999999999-")] if outcome == "range_error" else []
    try:
        if outcome in ("send_error", "cancelled"):
            with pytest.raises(OSError if outcome == "send_error" else asyncio.CancelledError):
                asyncio.run(response({"type": "http", "method": "GET", "headers": headers,
                    "extensions": {"http.response.pathsend": {}}}, receive, send))
        else:
            asyncio.run(response({"type": "http", "method": "GET", "headers": headers,
                "extensions": {"http.response.pathsend": {}}}, receive, send))
            assert statuses == [416 if outcome == "range_error" else 200]
            if outcome == "complete":
                assert b"".join(received) == data
        assert store._leases == {} and output.read_bytes() == data
        store.remove(identifier)
        assert not output.exists()
    finally:
        store.close()


def test_response_construction_failure_releases_lease(tmp_path, monkeypatch):
    store = ImageResultStore(tmp_path / "results")
    identifier, output = store.reserve()
    output.write_bytes(b"payload")
    store.finish(identifier, Proof(sha256(b"payload").hexdigest()))

    def rejected(*args, **kwargs):
        raise ValueError("synthetic construction failure")

    monkeypatch.setattr(api, "ManagedFileResponse", rejected)
    try:
        with pytest.raises(ValueError):
            api._leased_result_response(store, identifier)
        assert store._leases == {}
        store.remove(identifier)
    finally:
        store.close()


def test_cancel_after_publication_does_not_delete_a_result_being_downloaded(tmp_path, monkeypatch):
    assets = ImageAssetStore(tmp_path / "assets")
    outputs = ImageResultStore(tmp_path / "outputs")
    manager = ImageJobManager()
    source = BytesIO()
    Image.new("RGBA", (8, 6), (199, 33, 77, 0)).save(source, format="PNG")
    asset = asyncio.run(assets.add(UploadFile(BytesIO(source.getvalue()), filename="test.png")))
    published, resume, cancel_started = Event(), Event(), Event()
    original_finish = outputs.finish

    def paused_finish(*args, **kwargs):
        saved = original_finish(*args, **kwargs)
        published.set()
        assert resume.wait(5)
        return saved

    monkeypatch.setattr(outputs, "finish", paused_finish)
    thread = None
    response = None
    try:
        job = manager.submit_grid(assets, outputs, [asset.id], 1, 0)
        assert published.wait(2)
        response = api._leased_result_response(outputs, job.result_id)

        def cancel():
            cancel_started.set()
            manager.cancel(job.id)

        thread = Thread(target=cancel)
        thread.start()
        assert cancel_started.wait(2)
        resume.set()
        thread.join(2)
        assert not thread.is_alive()
        job.future.result(timeout=2)
        assert job.state == "succeeded" and not job.cancel.is_set()
        assert assets._leases == {} and outputs.get(job.result_id).path.is_file()

        async def receive():
            return {"type": "http.disconnect"}

        async def send(message):
            pass

        asyncio.run(response({"type": "http", "method": "GET", "headers": []}, receive, send))
        assert outputs._leases == {}
        outputs.remove(job.result_id)
    finally:
        resume.set()
        if thread:
            thread.join(2)
        manager.close()
        assets.close()
        outputs.close()
