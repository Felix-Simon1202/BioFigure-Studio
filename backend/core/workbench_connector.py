"""Per-process pairing state for a synthetic-data-only workbench connection."""

from collections import deque
from hashlib import sha256
from hmac import compare_digest
import re
from secrets import token_urlsafe
from threading import Lock
from time import monotonic
from typing import Literal


CONNECTOR_PREFIX = "/api/workbench/v1/connector"
CONNECTOR_PATHS = frozenset({CONNECTOR_PREFIX, CONNECTOR_PREFIX + "/render", CONNECTOR_PREFIX + "/artifact", CONNECTOR_PREFIX + "/fiji", CONNECTOR_PREFIX + "/figure", CONNECTOR_PREFIX + "/r-chart", CONNECTOR_PREFIX + "/project", CONNECTOR_PREFIX + "/vector"})
TOKEN_SECONDS = 600
OutputKind = Literal["chart", "fiji", "figure"]
_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_-]{43}")


class LocalConnector:
    def __init__(self):
        self._lock = Lock()
        self._digest: bytes | None = None
        self._expires = 0.0
        self._outputs: dict[OutputKind, deque[str]] = {
            "chart": deque(maxlen=4), "fiji": deque(maxlen=4), "figure": deque(maxlen=4),
        }

    def pair(self) -> str:
        token = token_urlsafe(32)
        with self._lock:
            self._digest = sha256(token.encode("ascii")).digest()
            self._expires = monotonic() + TOKEN_SECONDS
            for outputs in self._outputs.values():
                outputs.clear()
        return token

    def revoke(self) -> None:
        with self._lock:
            self._digest = None
            self._expires = 0.0
            for outputs in self._outputs.values():
                outputs.clear()

    def _is_active(self, digest: bytes) -> bool:
        return self._digest is not None and monotonic() < self._expires and compare_digest(digest, self._digest)

    def authenticate(self, authorization: str) -> bytes | None:
        kind, separator, token = authorization.partition(" ")
        if not separator or kind.lower() != "bearer" or not _TOKEN_PATTERN.fullmatch(token):
            return None
        digest = sha256(token.encode("ascii")).digest()
        with self._lock:
            return digest if self._is_active(digest) else None

    def record(self, digest: bytes, artifact_id: str, kind: OutputKind = "chart") -> bool:
        with self._lock:
            if not self._is_active(digest):
                return False
            self._outputs[kind].append(artifact_id)
            return True

    def owns(self, digest: bytes, artifact_id: str, kind: OutputKind = "chart") -> bool:
        with self._lock:
            return self._is_active(digest) and artifact_id in self._outputs[kind]
