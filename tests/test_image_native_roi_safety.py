import asyncio
import base64
from hashlib import sha256
from io import BytesIO
import json
import struct
from threading import Event, Lock, get_ident
from uuid import uuid4
from zipfile import ZipFile, ZIP_STORED, ZIP_LZMA

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from backend.image import api
from backend.image.assets import ImageAsset, ImageAssetStore
from backend.image.roi_collection import _inspect_roi_header, inspect_native_zip, source_identity


def header(kind=1):
    data = bytearray(64)
    data[:4] = b"Iout"
    data[4:6] = (228).to_bytes(2, "big")
    data[6] = kind
    data[12:14] = (5).to_bytes(2, "big")
    data[14:16] = (7).to_bytes(2, "big")
    return data


def archive(data, compression=ZIP_STORED):
    output = BytesIO()
    with ZipFile(output, "w", compression=compression) as packed:
        packed.writestr("cell.roi", data)
    return output.getvalue()


@pytest.mark.parametrize("case", ["shape_allocation", "metadata_pointer", "negative_pointer",
    "polygon_count", "polygon_truncated", "fractional_ellipse", "rounded", "text_subtype"])
def test_allocation_fields_and_geometry_are_checked_before_java_decode(case):
    data = header()
    if case == "shape_allocation":
        data[36:40] = (2 ** 30).to_bytes(4, "big")
    elif case in ("metadata_pointer", "negative_pointer"):
        data[60:64] = (64).to_bytes(4, "big")
        data.extend(bytes(64))
        data[80:84] = ((2 ** 30) if case == "metadata_pointer" else -1).to_bytes(4, "big", signed=True)
        data[84:88] = (80).to_bytes(4, "big")
    elif case in ("polygon_count", "polygon_truncated"):
        data[6] = 0
        data[16:18] = (65535 if case == "polygon_count" else 3).to_bytes(2, "big")
    elif case == "fractional_ellipse":
        data[6] = 2
        data[50:52] = (128).to_bytes(2, "big")
        data[18:34] = struct.pack(">4f", 1.5, 1, 7, 5)
    elif case == "rounded":
        data[54:56] = (4).to_bytes(2, "big")
    else:
        data[48:50] = (1).to_bytes(2, "big")
    with pytest.raises(ValueError):
        _inspect_roi_header(data)


def test_integer_geometry_in_float_encoding_is_preserved():
    data = header(2)
    data[50:52] = (128).to_bytes(2, "big")
    data[18:34] = struct.pack(">4f", 1, 1, 7, 5)
    _inspect_roi_header(data)


def test_unbounded_zip_codec_is_rejected_before_decompression(tmp_path):
    path = tmp_path / "source.tif"
    path.write_bytes(b"test")
    asset = ImageAsset("source", path.name, 4, sha256(b"test").hexdigest(), path)
    with pytest.raises(ValueError):
        inspect_native_zip(archive(header(), ZIP_LZMA), asset)


@pytest.mark.parametrize("operation", ["export", "import"])
@pytest.mark.parametrize("cancel_request", [False, True])
def test_native_worker_keeps_lease_and_honors_request_cancellation(tmp_path, monkeypatch, operation, cancel_request):
    path = tmp_path / "source.tif"
    path.write_bytes(b"test")
    source = ImageAsset("source", path.name, 4, sha256(b"test").hexdigest(), path,
        {"axes": [{"name": "X", "length": 12}, {"name": "Y", "length": 9}]})
    store = ImageAssetStore(tmp_path / "assets")
    asset, = store.adopt_many([source])
    item = {"id": uuid4().hex, "name": "Cell A", "indices": {},
            "roi": {"kind": "ellipse", "x": 1, "y": 1, "width": 7, "height": 5}}
    packed = base64.b64encode(archive(header())).decode()
    document = {"version": "1.0", "source": source_identity(asset), "items": [item]}
    request_data = document if operation == "export" else {"archive_base64": packed}
    gate = Lock()
    monkeypatch.setattr(api, "store", store)
    monkeypatch.setattr(api, "_roi_zip_gate", gate)
    monkeypatch.setattr(api, "_roi_collection_gate", Lock())
    entered, resume = Event(), Event()
    tokens, threads = [], []

    def held_engine(source, job_id, cancel, op, payload):
        tokens.append(cancel)
        threads.append(get_ident())
        entered.set()
        assert resume.wait(5)
        if cancel.is_set():
            raise api.FijiCancelled()
        return {"archive_base64": packed, "count": 1} if op == "export" else {"items": [item], "measurements": []}

    monkeypatch.setattr(api, "run_roi_zip", held_engine)

    async def run():
        loop_thread = get_ident()

        async def receive():
            return {"type": "http.request", "body": json.dumps(request_data).encode(), "more_body": False}

        request = Request({"type": "http", "method": "POST", "path": "/test", "headers": []}, receive)
        task = asyncio.create_task(api._native_roi_request(asset.id, request, operation))
        try:
            assert await asyncio.to_thread(entered.wait, 2)
            assert threads[0] != loop_thread
            if cancel_request:
                task.cancel()
                await asyncio.sleep(0)
                assert tokens[0].is_set()
            assert store._leases == {asset.id: 1}
            with pytest.raises(ValueError):
                store.remove(asset.id)
            with pytest.raises(HTTPException) as refused:
                api.get_roi_collection_source(asset.id)
            assert refused.value.status_code == 429
        finally:
            resume.set()
            if cancel_request:
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                result = await task
                assert result.get("count", len(result.get("document", {}).get("items", []))) == 1
            assert await asyncio.to_thread(lambda: gate.acquire(timeout=2))
            gate.release()
        assert store._leases == {}

    try:
        asyncio.run(run())
    finally:
        resume.set()
        store.close()
