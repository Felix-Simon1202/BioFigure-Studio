"""Portable ROI names and source binding survive a fresh local asset ID."""

import asyncio
import json
from io import BytesIO
from time import monotonic, sleep
from zipfile import ZIP_DEFLATED, ZipFile
from uuid import uuid4
from threading import Event, Lock, get_ident
import pytest
from starlette.requests import Request
from fastapi import HTTPException

from fastapi import UploadFile
from fastapi.testclient import TestClient
import pytest

from backend.api.app import app
from backend.image import api
from backend.image import jobs as image_jobs
from backend.image.assets import ImageAssetStore
from backend.image.fiji_process import FijiCancelled
from backend.image.jobs import ImageJobManager
from backend.image.roi_collection import inspect_native_zip, source_identity


def _inspected(store: ImageAssetStore, content: bytes):
    asset = asyncio.run(store.add(UploadFile(filename="synthetic.tif", file=BytesIO(content))))
    store.acquire(asset.id)
    store.set_metadata(asset.id, {"axes": [
        {"name": "X", "length": 12}, {"name": "Y", "length": 9},
        {"name": "Channel", "length": 2}, {"name": "Z", "length": 3},
        {"name": "Time", "length": 2},
    ], "bit_depth": 16})
    store.release(asset.id)
    return asset.id


def test_roi_collection_roundtrip_and_source_hash(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", store)
    client = TestClient(app)
    first = _inspected(store, b"synthetic-image-bytes")
    source = client.get(f"/api/image/assets/{first}/roi-collection/source")
    assert source.status_code == 200
    document = {"version": "1.0", "source": source.json(), "items": [
        {"id": uuid4().hex, "name": "细胞核 A", "indices": {"C": 1, "Z": 2, "T": 1},
         "roi": {"kind": "ellipse", "x": 1, "y": 2, "width": 7, "height": 5}},
        {"id": uuid4().hex, "name": "三角形 B", "indices": {"C": 0, "Z": 1, "T": 0},
         "roi": {"kind": "polygon", "points": [
             {"x": 1, "y": 1}, {"x": 8, "y": 1}, {"x": 2, "y": 7}]}},
    ]}
    validated = client.post(f"/api/image/assets/{first}/roi-collection/validate", json=document)
    assert validated.status_code == 200, validated.text
    assert [item["name"] for item in validated.json()["items"]] == ["细胞核 A", "三角形 B"]
    second = _inspected(store, b"synthetic-image-bytes")
    reopened = client.post(f"/api/image/assets/{second}/roi-collection/validate", json=validated.json())
    assert reopened.status_code == 200
    assert reopened.json() == validated.json()
    wrong = _inspected(store, b"different-image-bytes")
    assert client.post(f"/api/image/assets/{wrong}/roi-collection/validate", json=document).status_code == 422
    store.get(second).path.write_bytes(b"changed-after-upload")
    assert client.post(f"/api/image/assets/{second}/roi-collection/validate", json=document).status_code == 422
    store.close()


def test_roi_collection_rejects_invalid_members(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", store)
    client = TestClient(app)
    asset_id = _inspected(store, b"synthetic-image-bytes")
    source = client.get(f"/api/image/assets/{asset_id}/roi-collection/source").json()
    endpoint = f"/api/image/assets/{asset_id}/roi-collection/validate"
    item = {"id": uuid4().hex, "name": "ROI", "indices": {"C": 1, "Z": 2, "T": 1},
            "roi": {"x": 1, "y": 1, "width": 2, "height": 2}}
    for changed in ({**item, "name": ""}, {**item, "indices": {"C": 9, "Z": 2, "T": 1}},
                    {**item, "roi": {"x": 11, "y": 1, "width": 2, "height": 2}}):
        assert client.post(endpoint, json={"version": "1.0", "source": source,
                                           "items": [changed]}).status_code == 422
    assert client.post(endpoint, json={"version": "1.0", "source": source,
                                       "items": [item, item]}).status_code == 422
    different_axes = {**source, "axes": [{**source["axes"][0], "length": 13}, *source["axes"][1:]]}
    assert client.post(endpoint, json={"version": "1.0", "source": different_axes,
                                       "items": [item]}).status_code == 422
    assert client.post(endpoint, content=b" " * (128 * 1024 + 1)).status_code == 413
    store.close()


@pytest.mark.parametrize("cancel_request", [False, True])
def test_collection_verification_keeps_loop_responsive_and_worker_owns_lease(tmp_path, monkeypatch, cancel_request):
    store = ImageAssetStore(tmp_path / "assets")
    identifier = _inspected(store, b"synthetic-image-bytes")
    gate = Lock()
    started, resume, finished = Event(), Event(), Event()
    worker_threads = []
    monkeypatch.setattr(api, "store", store)
    monkeypatch.setattr(api, "_roi_collection_gate", gate)

    def held_validation(asset, document):
        worker_threads.append(get_ident())
        started.set()
        assert resume.wait(5)
        finished.set()
        return {"validated": True}

    monkeypatch.setattr(api, "validate_collection", held_validation)

    async def run():
        loop_thread = get_ident()

        async def receive():
            return {"type": "http.request", "body": b"{}", "more_body": False}

        request = Request({"type": "http", "method": "POST", "path": "/test", "headers": []}, receive)
        task = asyncio.create_task(api.validate_roi_collection(identifier, request))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            assert len(worker_threads) == 1 and worker_threads[0] != loop_thread
            if cancel_request:
                task.cancel()
                await asyncio.sleep(0)
            # Cancellation of the requester must not release a running worker's
            # source lease, nor block the loop while the worker is paused.
            await asyncio.wait_for(asyncio.sleep(0), .2)
            assert store._leases == {identifier: 1}
            with pytest.raises(ValueError, match="任务中使用"):
                store.remove(identifier)
            with pytest.raises(HTTPException) as rejected:
                api.get_roi_collection_source(identifier)
            assert rejected.value.status_code == 429
        finally:
            resume.set()
            if cancel_request:
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                assert await task == {"validated": True}
            assert await asyncio.to_thread(finished.wait, 2)
            assert await asyncio.to_thread(lambda: gate.acquire(timeout=2))
            gate.release()
        assert store._leases == {}

    try:
        asyncio.run(run())
    finally:
        resume.set()
        store.close()

def test_native_roi_zip_rejects_unsafe_entries_and_wrong_source(tmp_path):
    store = ImageAssetStore(tmp_path / "assets")
    asset = store.get(_inspected(store, b"synthetic-image-bytes"))

    def archive(entries):
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as packed:
            for name, data in entries:
                packed.writestr(name, data)
        return output.getvalue()

    header = bytearray(b"Iout" + bytes(60))
    header[4:6] = (228).to_bytes(2, "big")
    header[6] = 1  # A simple rectangular RoiDecoder record, not an empty polygon.
    header[12:14] = (2).to_bytes(2, "big")
    header[14:16] = (2).to_bytes(2, "big")
    roi = bytes(header)
    plain = archive([("cell.roi", roi)])
    assert inspect_native_zip(plain, asset)[1] is False
    bound = archive([("cell.roi", roi), ("biofigure-source.json", json.dumps(source_identity(asset)))])
    assert inspect_native_zip(bound, asset)[1] is True
    for entries in [
        [("../cell.roi", roi)],
        [("cell.roi", roi), ("cell.roi", roi)],
        [("cell.roi", b"wrong" + bytes(60))],
        [("cell.roi", roi), ("biofigure-source.json", "{}")],
        [("cell.roi", roi * 300)],
    ]:
        with pytest.raises(ValueError):
            inspect_native_zip(archive(entries), asset)
    store.close()


def test_collection_measure_does_not_publish_partial_or_cancelled_rows(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    asset_id = _inspected(store, b"synthetic-image-bytes")
    asset = store.get(asset_id)
    document = {"version": "1.0", "source": source_identity(asset), "items": [
        {"id": uuid4().hex, "name": "ROI", "indices": {"C": 1, "Z": 2, "T": 1},
         "roi": {"kind": "rectangle", "x": 1, "y": 1, "width": 2, "height": 2}},
    ]}
    manager = ImageJobManager()

    def settled(identifier):
        deadline = monotonic() + 3
        while monotonic() < deadline:
            job = manager.get(identifier).public()
            if job["state"] not in ("queued", "running"):
                return job
            sleep(0.01)
        raise AssertionError("collection job did not settle")

    monkeypatch.setattr(image_jobs, "measure_roi_collection", lambda *_: {
        "source": document["source"], "extra_measurements": [], "rows": [],
        "roi_manager_multi_measure_equivalent": False})
    failed = settled(manager.submit_collection_measure(store, asset_id, document, []).id)
    assert failed["state"] == "failed" and failed["result"] is None

    def until_cancel(_asset, _id, cancel, _collection, _extras):
        cancel.wait(2)
        raise FijiCancelled()

    monkeypatch.setattr(image_jobs, "measure_roi_collection", until_cancel)
    running = manager.submit_collection_measure(store, asset_id, document, [])
    manager.cancel(running.id)
    cancelled = settled(running.id)
    assert cancelled["state"] == "cancelled" and cancelled["result"] is None
    manager.close()
    store.close()


def test_collection_measure_rejects_invalid_request_before_fiji(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", store)
    asset_id = _inspected(store, b"synthetic-image-bytes")
    client = TestClient(app)
    source = source_identity(store.get(asset_id))
    document = {"version": "1.0", "source": source, "items": [
        {"id": uuid4().hex, "name": "ROI", "indices": {"C": 1, "Z": 2, "T": 1},
         "roi": {"kind": "rectangle", "x": 1, "y": 1, "width": 2, "height": 2}},
    ]}
    endpoint = f"/api/image/assets/{asset_id}/roi-collection/measure"
    assert client.post(endpoint, json={"collection": document, "extra_measurements": ["median", "median"]}).status_code == 422
    assert client.post(endpoint, json={"collection": {**document, "source": {**source, "sha256": "0" * 64}},
                                       "extra_measurements": []}).status_code == 422
    assert client.post(endpoint, content=b" " * (128 * 1024 + 1025)).status_code == 413
    store.close()

@pytest.mark.parametrize("cancel_request", [False, True])
def test_collection_measure_submission_keeps_validation_off_loop_and_owns_lease(tmp_path, monkeypatch, cancel_request):
    import asyncio
    from threading import Event, Lock, get_ident
    from starlette.requests import Request
    from fastapi import HTTPException

    store = ImageAssetStore(tmp_path / "assets")
    identifier = _inspected(store, b"synthetic-image-bytes")
    asset = store.get(identifier)
    document = {"version": "1.0", "source": source_identity(asset), "items": [
        {"id": uuid4().hex, "name": "ROI", "indices": {"C": 1, "Z": 2, "T": 1},
         "roi": {"kind": "rectangle", "x": 1, "y": 1, "width": 2, "height": 2}}]}
    manager = ImageJobManager()
    started, resume, completed = Event(), Event(), Event()
    gate = Lock()
    threads = []
    original = image_jobs.validate_collection

    def paused(*args):
        threads.append(get_ident())
        started.set()
        assert resume.wait(5)
        return original(*args)

    def engine(_asset, _id, cancel, _document, _extras):
        completed.set()
        if cancel.is_set():
            raise FijiCancelled()
        item = _document["items"][0]
        return {"source": _document["source"], "extra_measurements": [],
                "roi_manager_multi_measure_equivalent": False,
                "rows": [{**item, "sample_count": 4, "imagej1_analyzer": {
                    "area": 4, "area_unit": "pixel^2", "mean": 2, "min": 1, "max": 3}}]}

    monkeypatch.setattr(api, "store", store)
    monkeypatch.setattr(api, "manager", manager)
    monkeypatch.setattr(api, "_roi_collection_gate", gate)
    monkeypatch.setattr(image_jobs, "validate_collection", paused)
    monkeypatch.setattr(image_jobs, "measure_roi_collection", engine)

    async def run():
        raw = json.dumps({"collection": document, "extra_measurements": []}).encode()
        async def receive():
            return {"type": "http.request", "body": raw, "more_body": False}
        request = Request({"type": "http", "method": "POST", "path": "/test", "headers": []}, receive)
        task = asyncio.create_task(api.create_roi_collection_measure(identifier, request))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            assert threads == [threads[0]] and threads[0] != get_ident()
            await asyncio.wait_for(asyncio.sleep(0), .2)
            assert store._leases == {identifier: 1}
            with pytest.raises(HTTPException) as rejected:
                api.get_roi_collection_source(identifier)
            assert rejected.value.status_code == 429
            if cancel_request:
                task.cancel()
                await asyncio.sleep(0)
        finally:
            resume.set()
        if cancel_request:
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            assert (await task)["operation"] == "measure_roi_collection"
        job = manager.get(manager.all_public()[0]["id"])
        await asyncio.to_thread(job.future.result, timeout=3)
        await asyncio.to_thread(manager.close)
        result = manager.all_public()[0]
        assert result["state"] == ("cancelled" if cancel_request else "succeeded")
        assert (result["result"] is None) == cancel_request
        assert store._leases == {} and gate.acquire(blocking=False)
        gate.release()

    try:
        asyncio.run(run())
    finally:
        resume.set()
        manager.close()
        store.close()
