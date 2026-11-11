"""Exercise the real ASGI receive boundary before multipart parsing."""

import asyncio
from threading import Lock

import pytest

from backend.image import admission
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette import formparsers


def scope(headers, path="/api/image/jobs/batch-grid"):
    return {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
            "method": "POST", "scheme": "http", "path": path,
            "raw_path": path.encode(), "root_path": "", "query_string": b"",
            "headers": headers, "server": ("127.0.0.1", 8000), "client": ("127.0.0.1", 1)}


@pytest.mark.parametrize("case,expected", [("missing", 411), ("oversize", 413), ("busy", 429)])
@pytest.mark.parametrize("path", ["/api/image/jobs/batch-grid", "/api/image/jobs/open-project"])
def test_rejected_upload_never_reads_request_body(monkeypatch, case, expected, path):
    gate = Lock()
    monkeypatch.setattr(admission, "_batch_gate", gate)
    limit = admission.MAX_PROJECT_REQUEST_BYTES if path.endswith("open-project") else admission.MAX_BATCH_REQUEST_BYTES
    headers = [] if case == "missing" else [(b"content-length", str(
        limit + 1 if case == "oversize" else 1).encode())]
    if case == "busy":
        gate.acquire()
    reads, entered, statuses = [], [], []

    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": b"x", "more_body": False}

    async def downstream(_scope, _receive, _send):
        entered.append(True)

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    try:
        asyncio.run(admission.BatchUploadAdmissionMiddleware(downstream)(scope(headers, path), receive, send))
        assert statuses == [expected]
        assert reads == entered == []
    finally:
        if case == "busy":
            gate.release()


def test_cancel_during_body_read_releases_admission(monkeypatch):
    gate = Lock()
    monkeypatch.setattr(admission, "_batch_gate", gate)

    async def run():
        entered = asyncio.Event()
        waiting = asyncio.Event()

        async def receive():
            entered.set()
            await waiting.wait()
            return {"type": "http.disconnect"}

        async def downstream(_scope, receive_body, _send):
            await receive_body()

        async def send(_message):
            pass

        task = asyncio.create_task(admission.BatchUploadAdmissionMiddleware(downstream)(
            scope([(b"content-length", b"100")]), receive, send))
        await asyncio.wait_for(entered.wait(), 2)
        assert not gate.acquire(blocking=False)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert gate.acquire(blocking=False)
        gate.release()

    asyncio.run(run())


def test_actual_body_overrun_closes_already_opened_multipart_files(monkeypatch):
    gate = Lock()
    monkeypatch.setattr(admission, "_batch_gate", gate)
    opened = []
    original = formparsers.SpooledTemporaryFile

    def tracked_file(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(formparsers, "SpooledTemporaryFile", tracked_file)
    head = (b'--test\r\nContent-Disposition: form-data; name="files"; filename="synthetic.tif"\r\n'
            b'Content-Type: image/tiff\r\n\r\nx')
    chunks = [head, b"x" * 20, b"\r\n--test--\r\n"]
    reads, statuses = [], []

    async def endpoint(request):
        async with request.form():
            return JSONResponse({"ok": True})

    async def receive():
        reads.append(True)
        return {"type": "http.request", "body": chunks.pop(0), "more_body": bool(chunks)}

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    app = admission.BatchUploadAdmissionMiddleware(Starlette(routes=[
        Route("/api/image/jobs/batch-grid", endpoint, methods=["POST"])]))
    asyncio.run(app(scope([(b"content-length", str(len(head) + 5).encode()),
                          (b"content-type", b"multipart/form-data; boundary=test")]), receive, send))
    assert statuses == [413] and len(reads) == 2
    assert opened and all(file.closed for file in opened)
    assert gate.acquire(blocking=False)
    gate.release()


@pytest.mark.parametrize("path", ["/api/image/jobs/batch-grid", "/api/image/jobs/open-project"])
def test_insufficient_spool_space_rejects_before_reading_and_releases_gate(monkeypatch, path):
    gate = Lock()
    monkeypatch.setattr(admission, "_batch_gate", gate)
    checked = []

    def low_space(writes):
        checked.extend(writes)
        raise ValueError("synthetic low disk space")

    monkeypatch.setattr(admission, "require_disk_space", low_space)
    statuses, reads, entered = [], [], []

    async def receive():
        reads.append(True)

    async def downstream(*args):
        entered.append(True)

    async def send(message):
        if message["type"] == "http.response.start":
            statuses.append(message["status"])

    asyncio.run(admission.BatchUploadAdmissionMiddleware(downstream)(
        scope([(b"content-length", b"100")], path), receive, send))
    assert statuses == [507] and reads == entered == []
    assert len(checked) == 1 and checked[0][1] == 100
    assert gate.acquire(blocking=False)
    gate.release()
