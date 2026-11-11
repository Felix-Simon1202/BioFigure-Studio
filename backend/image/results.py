"""Bounded local result files for the interactive image session."""

from __future__ import annotations

import atexit
from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import re
from threading import Lock
from typing import Protocol
from uuid import uuid4

from backend.image.montage import GridProof
from backend.image.invert import InvertProof
from backend.image.annotations import create_overlay
from backend.image.preview import display_png
from backend.image.paths import image_work_dir


ROOT = image_work_dir("image-results")
BATCH_ROOT = image_work_dir("image-batch-results")
MAX_RESULTS = 8
MAX_RESULT_BYTES = 512 * 1024 * 1024


class ResultProof(Protocol):
    output_sha256: str

    def public(self) -> dict[str, object]: ...


@dataclass(frozen=True)
class ImageResult:
    id: str
    path: Path
    bytes: int
    proof: ResultProof
    extension: str = ".tif"
    mime_type: str = "image/tiff"
    prefix: str = "biofigure-grid"

    def public(self) -> dict[str, object]:
        return {"id": self.id, "filename": f"{self.prefix}-{self.id[:8]}{self.extension}",
                "mime_type": self.mime_type, "bytes": self.bytes,
                "sha256": self.proof.output_sha256, "proof": self.proof.public()}


class ImageResultStore:
    def __init__(self, root: Path = ROOT, *, max_results: int = MAX_RESULTS,
                 max_bytes: int = MAX_RESULT_BYTES, extension: str = ".tif",
                 mime_type: str = "image/tiff", prefix: str = "biofigure-grid"):
        self.root = root
        if extension not in (".tif", ".zip"):
            raise ValueError("Unsupported result extension")
        self.max_results = max_results
        self.max_bytes = max_bytes
        self.extension = extension
        self.mime_type = mime_type
        self.prefix = prefix
        self.root.mkdir(parents=True, exist_ok=True)
        self.session = self.root / uuid4().hex
        self.session.mkdir()
        self._lock = Lock()
        self._results: dict[str, ImageResult] = {}
        self._reserved: set[str] = set()
        self._leases: dict[str, int] = {}

    def reserve(self) -> tuple[str, Path]:
        with self._lock:
            if len(self._results) + len(self._reserved) >= self.max_results:
                raise ValueError(f"本机会话成品已满（{self.max_results} 份）；请移除旧成品。")
            identifier = uuid4().hex
            self._reserved.add(identifier)
            return identifier, self.session / f"{identifier}{self.extension}"

    def finish(self, identifier: str, proof: ResultProof, *, annotations: list[dict] | None = None) -> ImageResult:
        with self._lock:
            if identifier not in self._reserved:
                raise KeyError(identifier)
            path = self.session / f"{identifier}{self.extension}"
            if path.resolve().parent != self.session.resolve() or not path.is_file():
                raise ValueError("成品文件不存在或路径失控。")
            size = path.stat().st_size
            if sum(item.bytes for item in self._results.values()) + size > self.max_bytes:
                raise ValueError("本机会话成品超过存储上限。")
            result = ImageResult(identifier, path, size, proof, self.extension,
                                 self.mime_type,
                                 "biofigure-invert" if isinstance(proof, InvertProof) else self.prefix)
            if annotations is not None:
                if not isinstance(proof, GridProof):
                    raise ValueError("只有网格可恢复独立标注。")
                self._write_annotations_unlocked(identifier, proof, annotations)
            self._results[identifier] = result
            self._reserved.remove(identifier)
            return result

    def discard(self, identifier: str) -> None:
        with self._lock:
            if self._leases.get(identifier, 0):
                raise ValueError("成品正在下载，请等待传输结束。")
            self._reserved.discard(identifier)
            path = self.session / f"{identifier}{self.extension}"
            if path.resolve().parent != self.session.resolve():
                raise ValueError("拒绝清理会话之外的成品路径。")
            path.unlink(missing_ok=True)
            (self.session / f"{identifier}.annotations.json").unlink(missing_ok=True)

    def get(self, identifier: str) -> ImageResult:
        with self._lock:
            return self._results[identifier]

    def acquire(self, identifier: str) -> ImageResult:
        with self._lock:
            result = self._results[identifier]
            self._leases[identifier] = self._leases.get(identifier, 0) + 1
            return result

    def release(self, identifier: str) -> None:
        with self._lock:
            count = self._leases[identifier]
            if count == 1:
                del self._leases[identifier]
            else:
                self._leases[identifier] = count - 1

    def all_public(self) -> list[dict[str, object]]:
        with self._lock:
            return [result.public() for result in self._results.values()]

    def preview(self, identifier: str) -> tuple[bytes, dict[str, str]]:
        # Keep removal from racing the reader; previews are bounded and serial.
        with self._lock:
            return display_png(self._results[identifier].path)

    def remove(self, identifier: str) -> None:
        with self._lock:
            result = self._results[identifier]
            if self._leases.get(identifier, 0):
                raise ValueError("成品正在下载，请等待传输结束。")
            if result.path.resolve().parent != self.session.resolve():
                raise ValueError("拒绝删除会话之外的成品路径。")
            result.path.unlink(missing_ok=True)
            (self.session / f"{identifier}.annotations.json").unlink(missing_ok=True)
            del self._results[identifier]

    def set_annotations(self, identifier: str, items: list[dict[str, object]]) -> dict[str, object]:
        with self._lock:
            result = self._results[identifier]
            if not isinstance(result.proof, GridProof):
                raise ValueError("只有单张网格成品支持独立标注。")
            return self._write_annotations_unlocked(identifier, result.proof, items)

    def _write_annotations_unlocked(self, identifier: str, proof: GridProof, items: list[dict]) -> dict:
        normalized, svg = create_overlay(proof, items)
        payload = {"schema_version": "1.0", "result_id": identifier,
                   "source_sha256": proof.output_sha256,
                   "items": normalized, "svg_sha256": sha256(svg).hexdigest(),
                   "svg": svg.decode("utf-8")}
        target = self.session / f"{identifier}.annotations.json"
        temporary = self.session / f"{identifier}.annotations.json.partial"
        try:
            temporary.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)
        return {key: value for key, value in payload.items() if key != "svg"}

    def get_annotations(self, identifier: str) -> dict[str, object]:
        with self._lock:
            return self._annotations_unlocked(identifier)

    def _annotations_unlocked(self, identifier: str) -> dict[str, object]:
        result = self._results[identifier]
        target = self.session / f"{identifier}.annotations.json"
        if not target.is_file():
            return {"schema_version": "1.0", "result_id": identifier,
                    "source_sha256": result.proof.output_sha256,
                    "items": [], "svg_sha256": None, "svg": None}
        payload = json.loads(target.read_text(encoding="utf-8"))
        if payload.get("source_sha256") != result.proof.output_sha256:
            raise ValueError("标注层绑定的像素成品摘要不匹配。")
        return payload

    def grid_project_snapshot(self, identifier: str) -> tuple[GridProof, list[dict]]:
        """Snapshot the recipe and annotations under the same removal/edit lock."""
        with self._lock:
            proof = self._results[identifier].proof
            if not isinstance(proof, GridProof) or proof.grid_recipe is None:
                raise ValueError("此成品没有可保存的原像素网格配方。")
            return proof, self._annotations_unlocked(identifier)["items"]

    def close(self) -> None:
        if self.session.resolve().parent != self.root.resolve() or not re.fullmatch(r"[0-9a-f]{32}", self.session.name):
            raise ValueError("拒绝清理会话之外的成品路径。")
        with self._lock:
            if self._leases:
                raise ValueError("成品仍在下载，不能清理此会话。")
            self._results.clear()
            self._reserved.clear()
        if self.session.exists():
            for path in self.session.iterdir():
                if not path.is_file() or path.is_symlink():
                    raise ValueError("成品会话发现意外文件，需人工审查。")
                path.unlink()
            self.session.rmdir()


results = ImageResultStore()
atexit.register(results.close)
batch_results = ImageResultStore(BATCH_ROOT, max_results=2,
                                 max_bytes=2 * 1024 * 1024 * 1024,
                                 extension=".zip", mime_type="application/zip",
                                 prefix="biofigure-batch")
atexit.register(batch_results.close)
