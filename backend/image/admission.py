"""Bound multipart staging before FastAPI parses batch uploads."""

from threading import Lock
from pathlib import Path
import tempfile

from backend.image.storage import require_disk_space

from starlette.datastructures import Headers
from starlette.formparsers import MultiPartException
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send


MAX_BATCH_REQUEST_BYTES = 4 * 1024 ** 3 + 64 * 1024 ** 2
MAX_PROJECT_REQUEST_BYTES = 2 * 1024 ** 3 + 64 * 1024 ** 2
_batch_gate = Lock()


class BatchUploadAdmissionMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send):
        if (scope["type"] != "http" or scope["method"] != "POST"
                or scope["path"] not in ("/api/image/jobs/batch-grid", "/api/image/jobs/open-project", "/api/image/jobs/open-workspace")):
            return await self.app(scope, receive, send)
        project = scope["path"] in ("/api/image/jobs/open-project", "/api/image/jobs/open-workspace")
        limit = MAX_PROJECT_REQUEST_BYTES if project else MAX_BATCH_REQUEST_BYTES
        length = Headers(scope=scope).get("content-length")
        if length is None or not length.isdecimal():
            return await JSONResponse({"detail": "批量上传需要明确的请求长度。"}, status_code=411)(scope, receive, send)
        if len(length) > 20 or int(length) > limit:
            return await JSONResponse({"detail": "项目上传超出 2 GiB 暂存预算。" if project else "批量上传超出 4 GiB 暂存预算。"}, status_code=413)(scope, receive, send)
        body_limit = int(length)
        if not _batch_gate.acquire(blocking=False):
            return await JSONResponse({"detail": "已有批量或项目上传/任务正在进行。"}, status_code=429)(scope, receive, send)
        state = scope.setdefault("state", {})
        state["batch_admission_release"] = _batch_gate.release
        received = 0
        exceeded = False
        started = False

        async def bounded_receive():
            nonlocal received, exceeded
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > body_limit:
                    exceeded = True
                    # Starlette's multipart parser closes its opened spool files
                    # for this exception before translating it into HTTP 400.
                    raise MultiPartException("批量上传实际数据超过声明长度或容量限制。")
            return message

        async def bounded_send(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                if exceeded:
                    message = {**message, "status": 413}
            await send(message)

        try:
            try:
                # Multipart spools live on the system temporary volume, which
                # may differ from the project asset volume.
                require_disk_space([(Path(tempfile.gettempdir()), body_limit)])
            except ValueError as error:
                return await JSONResponse({"detail": str(error)}, status_code=507)(scope, receive, send)
            try:
                await self.app(scope, bounded_receive, bounded_send)
            except MultiPartException:
                if not exceeded or started:
                    raise
                await JSONResponse({"detail": "批量上传实际数据超过声明长度或容量限制。"}, status_code=413)(scope, receive, send)
        finally:
            if not state.get("batch_admission_transferred", False):
                _batch_gate.release()
