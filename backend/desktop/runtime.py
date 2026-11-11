"""Single-process loopback server for the built web application."""

import secrets
import socket
import threading
from http.cookies import SimpleCookie
from pathlib import Path

import uvicorn
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse, RedirectResponse
from starlette.routing import Mount
from starlette.staticfiles import StaticFiles

from backend.core.workbench_connector import CONNECTOR_PATHS, LocalConnector


class SessionGate:
    """Separate desktop authentication from the existing development API."""

    def __init__(self, app, origin, secret):
        self.app, self.origin, self.secret = app, origin, secret
        self.cookie = "biofigure_" + secrets.token_hex(8)
        self.workbench_connector = LocalConnector()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            if scope["type"] == "websocket":
                await send({"type": "websocket.close", "code": 1008})
                return
            return await self.app(scope, receive, send)
        headers = dict(scope["headers"])
        host = headers.get(b"host", b"").decode("latin1")
        origin = headers.get(b"origin", b"").decode("latin1")
        cross_site = headers.get(b"sec-fetch-site") == b"cross-site"
        if host != self.origin.removeprefix("http://") or cross_site or (origin and origin != self.origin):
            response = PlainTextResponse("请求来源不受支持。", status_code=403)
        elif scope["path"] == "/_launch/" + self.secret and scope["method"] == "GET":
            response = RedirectResponse("/", status_code=303)
            response.set_cookie(self.cookie, self.secret, httponly=True, samesite="strict")
        else:
            # Only these exact routes delegate authentication to a paired bearer token.
            if scope["path"] in CONNECTOR_PATHS:
                return await self._protected(scope, receive, send)
            cookies = SimpleCookie()
            try:
                cookies.load(headers.get(b"cookie", b"").decode("latin1"))
                value = cookies[self.cookie].value if self.cookie in cookies else ""
            except Exception:
                value = ""
            if not secrets.compare_digest(value, self.secret):
                response = PlainTextResponse("请从 BioFigure Studio 启动窗口打开网页。", status_code=401)
            else:
                return await self._protected(scope, receive, send)
        for key, value in self.security_headers():
            response.headers[key.decode()] = value.decode()
        await response(scope, receive, send)

    async def _protected(self, scope, receive, send):
        state = {**scope.get("state", {}), "workbench_connector": self.workbench_connector,
                 "workbench_origin": self.origin}

        async def protected_send(message):
            if message["type"] == "http.response.start":
                message["headers"] = list(message["headers"]) + self.security_headers()
            await send(message)

        return await self.app({**scope, "state": state}, receive, protected_send)

    @staticmethod
    def security_headers():
        return [(b"cache-control", b"no-store"), (b"referrer-policy", b"no-referrer"),
                (b"x-content-type-options", b"nosniff"),
                (b"content-security-policy", b"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")]


class LocalRuntime:
    def __init__(self, web_root: Path):
        if not (web_root / "index.html").is_file():
            raise RuntimeError("缺少已构建的网页，请先按说明构建本地验证版。")
        # Import the plotting engine only after checking the required web asset.
        from backend.api.app import app
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            self.socket.bind(("127.0.0.1", 0))
            self.socket.listen(128)
            self.origin = f"http://127.0.0.1:{self.socket.getsockname()[1]}"
            self.secret = secrets.token_urlsafe(32)
            self.launch_url = self.origin + "/_launch/" + self.secret
            static_app = Starlette(routes=[Mount("/", app=StaticFiles(directory=web_root, html=True))])

            async def local_app(scope, receive, send):
                # Keep FastAPI's own middleware/exception handling intact.
                target = app if scope.get("path", "").startswith("/api/") else static_app
                await target(scope, receive, send)
            self.app = SessionGate(local_app, self.origin, self.secret)
            self.server = uvicorn.Server(uvicorn.Config(self.app, host="127.0.0.1", log_config=None,
                access_log=False, log_level="critical", lifespan="off", loop="asyncio", http="h11",
                ws="none", timeout_graceful_shutdown=3))
            self.failed = False
            self.thread = threading.Thread(target=self._serve, name="biofigure-local", daemon=True)
        except BaseException:
            self.socket.close()
            raise

    def _serve(self):
        try:
            self.server.run(sockets=[self.socket])
        except BaseException:
            self.failed = True
        finally:
            self.socket.close()

    def start(self):
        self.thread.start()

    def request_stop(self):
        self.server.should_exit = True

    def stop(self, timeout=5):
        self.request_stop()
        if self.thread.ident is not None:
            self.thread.join(timeout)
        self.socket.close()
        return not self.thread.is_alive()
