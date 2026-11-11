"""File responses whose resource ownership lasts through body transmission."""

from typing import Callable

from fastapi.responses import FileResponse


class ManagedFileResponse(FileResponse):
    def __init__(self, *args, cleanup: Callable[[], None], **kwargs):
        super().__init__(*args, **kwargs)
        self._cleanup = cleanup

    async def __call__(self, scope, receive, send):
        try:
            # A path handoff can finish before the server reads the file. Keep
            # our lease until the actual body has passed to the ASGI server.
            scope = {**scope, "extensions": {key: value for key, value in scope.get("extensions", {}).items()
                                           if key != "http.response.pathsend"}}
            await super().__call__(scope, receive, send)
        finally:
            self._cleanup()
