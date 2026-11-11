"""Bounded, opaque local image asset references.

Image files remain untouched on disk. Only an internal asset ID can resolve to
their path; the HTTP contract never accepts a server filesystem path.
"""

from __future__ import annotations

import asyncio
import atexit
from contextlib import contextmanager
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path
import re
from threading import Event, Lock
from typing import Any, Callable
from uuid import uuid4

from fastapi import UploadFile
from backend.image.storage import require_disk_space
from backend.image.paths import image_work_dir


MAX_IMAGE_BYTES = 1024 * 1024 * 1024
MAX_SESSION_BYTES = 2 * 1024 * 1024 * 1024
MAX_SESSION_ASSETS = 8
CHUNK_BYTES = 4 * 1024 * 1024
WORK_ROOT = image_work_dir("image-assets")


class ImageAssetImportCancelled(RuntimeError):
    pass


def _asset_name(name: str) -> tuple[str, str]:
    name = name.replace("\\", "/").split("/")[-1].strip()
    if not name or len(name) > 200:
        raise ValueError("图像文件名无效或过长。")
    suffix = "".join(Path(name).suffixes[-2:]).lower()
    return name, suffix if re.fullmatch(r"(?:\.[a-z0-9]{1,12}){0,2}", suffix) else ""


def _copy_import_source(asset: ImageAsset, target: Path, cancel: Event | None) -> None:
    count = 0
    digest = sha256()
    created = False
    try:
        with asset.path.open("rb") as source, target.open("xb") as output:
            created = True
            while chunk := source.read(CHUNK_BYTES):
                if cancel is not None and cancel.is_set():
                    raise ImageAssetImportCancelled()
                count += len(chunk)
                if count > asset.bytes:
                    raise ValueError("导入源图字节超出声明。")
                digest.update(chunk)
                output.write(chunk)
        if count != asset.bytes or digest.hexdigest() != asset.sha256:
            raise ValueError("导入源图与已检查的字节摘要不符。")
    except BaseException:
        if created:
            target.unlink(missing_ok=True)
        raise


@dataclass(frozen=True)
class ImageAsset:
    id: str
    name: str
    bytes: int
    sha256: str
    path: Path
    metadata: dict[str, Any] | None = None

    def public(self) -> dict[str, object]:
        axes = self.metadata.get("axes") if self.metadata else None
        return {"id": self.id, "original_name": self.name, "bytes": self.bytes,
                "sha256": self.sha256,
                "pixel_type": self.metadata.get("pixel_type") if self.metadata else None,
                "bit_depth": self.metadata.get("bit_depth") if self.metadata else None,
                "axes": axes,
                "shape": [axis.get("length") for axis in axes] if isinstance(axes, list) else None,
                "channels": self.metadata.get("channels") if self.metadata else None,
                "metadata_status": "fiji_inspected" if self.metadata else "not_inspected"}


def verify_asset_bytes(asset: ImageAsset, cancel: Event | None = None) -> str:
    """Bounded provenance check for an already admitted, leased source."""
    digest = sha256()
    count = 0
    if cancel is not None and cancel.is_set():
        raise ImageAssetImportCancelled()
    with asset.path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(CHUNK_BYTES), b""):
            if cancel is not None and cancel.is_set():
                raise ImageAssetImportCancelled()
            count += len(chunk)
            if count > asset.bytes:
                raise ValueError("源图实际字节超过导入长度，摘要不符。")
            digest.update(chunk)
    if count != asset.bytes or digest.hexdigest() != asset.sha256:
        raise ValueError("源图字节与导入摘要不符。")
    if cancel is not None and cancel.is_set():
        raise ImageAssetImportCancelled()
    return digest.hexdigest()


class StagedImageAssets:
    """Internal transaction, owned by ImageAssetStore.stage_many's context."""

    def __init__(self, store, assets: list[ImageAsset], cancel: Event | None):
        self.store = store
        self.assets = assets
        self.cancel = cancel
        self.committed = False
        self.active = True

    def commit(self, publish: Callable[[], None] | None = None) -> None:
        # A companion result is published while asset readers remain blocked.
        # The callback must complete its own checks before publishing anything.
        with self.store._lock:
            if not self.active or self.committed:
                raise ValueError("导入事务已结束。")
            if self.cancel is not None and self.cancel.is_set():
                raise ImageAssetImportCancelled()
            if publish is not None:
                publish()
            self.store._assets.update({asset.id: asset for asset in self.assets})
            self.store._pending_count -= len(self.assets)
            self.store._pending_bytes -= sum(asset.bytes for asset in self.assets)
            self.committed = True


class ImageAssetStore:
    def __init__(self, root: Path = WORK_ROOT, *, max_assets: int | None = None,
                 max_session_bytes: int | None = None, max_image_bytes: int | None = None):
        self.root = root
        self.max_assets = max_assets if max_assets is not None else MAX_SESSION_ASSETS
        self.max_session_bytes = max_session_bytes if max_session_bytes is not None else MAX_SESSION_BYTES
        self.max_image_bytes = max_image_bytes if max_image_bytes is not None else MAX_IMAGE_BYTES
        self.root.mkdir(parents=True, exist_ok=True)
        self.session = self.root / uuid4().hex
        self.session.mkdir()
        self._assets: dict[str, ImageAsset] = {}
        self._leases: dict[str, int] = {}
        self._lock = Lock()
        self._upload_lock = asyncio.Lock()
        self._pending_count = 0
        self._pending_bytes = 0

    def _reserve_unlocked(self, count: int, size: int) -> None:
        if (len(self._assets) + self._pending_count + count > self.max_assets
                or sum(asset.bytes for asset in self._assets.values()) + self._pending_bytes + size > self.max_session_bytes):
            raise ValueError("图像超过本机会话剩余容量。")
        self._pending_count += count
        self._pending_bytes += size

    def adopt_many(self, sources: list[ImageAsset], cancel: Event | None = None) -> list[ImageAsset]:
        """Atomically publish copied sources; caller supplies fresh inspection metadata.

        This internal method checks source bytes, not the scientific truth of
        metadata. Project JSON claims must never be passed as live metadata.
        """
        with self.stage_many(sources, cancel) as staged:
            staged.commit()
            return staged.assets

    @contextmanager
    def stage_many(self, sources: list[ImageAsset], cancel: Event | None = None):
        """Reserve/copy sources but keep them invisible until explicit commit."""
        if not sources or any(not 1 <= asset.bytes <= self.max_image_bytes for asset in sources):
            raise ValueError("项目导入源数量或单文件容量无效。")
        names = [_asset_name(asset.name) for asset in sources]
        total = sum(asset.bytes for asset in sources)
        with self._lock:
            self._reserve_unlocked(len(sources), total)
        adopted: list[ImageAsset] = []
        staged = StagedImageAssets(self, adopted, cancel)
        try:
            require_disk_space([(self.session, total)])
            for asset, (name, suffix) in zip(sources, names, strict=True):
                if cancel is not None and cancel.is_set():
                    raise ImageAssetImportCancelled()
                identifier = uuid4().hex
                target = self.session / (identifier + suffix)
                _copy_import_source(asset, target, cancel)
                adopted.append(ImageAsset(identifier, name, asset.bytes, asset.sha256, target, asset.metadata))
            yield staged
        finally:
            staged.active = False
            if not staged.committed:
                for asset in adopted:
                    if asset.path.resolve().parent != self.session.resolve():
                        raise ValueError("拒绝清理导入会话之外的路径。")
                    asset.path.unlink(missing_ok=True)
                with self._lock:
                    self._pending_count -= len(sources)
                    self._pending_bytes -= total

    def all_public(self) -> list[dict[str, object]]:
        with self._lock:
            return [asset.public() for asset in self._assets.values()]

    def get(self, asset_id: str) -> ImageAsset:
        with self._lock:
            return self._assets[asset_id]

    def set_metadata(self, asset_id: str, metadata: dict[str, Any]) -> None:
        with self._lock:
            asset = self._assets[asset_id]
            if not self._leases.get(asset_id, 0):
                raise ValueError("Fiji 元数据只能在受保护的检查任务内写入。")
            self._assets[asset_id] = replace(asset, metadata={
                "axes": metadata.get("axes"), "pixel_type": metadata.get("pixel_type"),
                "bit_depth": metadata.get("bit_depth"), "channels": metadata.get("channels"),
            })

    def acquire(self, asset_id: str) -> ImageAsset:
        """Keep an asset alive throughout a job, atomically against removal."""
        with self._lock:
            asset = self._assets[asset_id]
            self._leases[asset_id] = self._leases.get(asset_id, 0) + 1
            return asset

    def acquire_many(self, asset_ids: list[str]) -> list[ImageAsset]:
        if len(set(asset_ids)) != len(asset_ids):
            raise ValueError("同一源图像不能在一张网格中重复引用。")
        with self._lock:
            assets = [self._assets[identifier] for identifier in asset_ids]
            for identifier in asset_ids:
                self._leases[identifier] = self._leases.get(identifier, 0) + 1
            return assets

    def release(self, asset_id: str) -> None:
        with self._lock:
            count = self._leases[asset_id]
            if count == 1:
                del self._leases[asset_id]
            else:
                self._leases[asset_id] = count - 1

    def release_many(self, asset_ids: list[str]) -> None:
        for identifier in asset_ids:
            self.release(identifier)

    def remove(self, asset_id: str) -> None:
        with self._lock:
            asset = self._assets[asset_id]
            if self._leases.get(asset_id, 0):
                raise ValueError("图像正在任务中使用，请先等待或取消任务。")
            # Delete only a path generated inside this session, never a supplied path.
            if asset.path.resolve().parent != self.session.resolve():
                raise ValueError("图像资源路径不属于当前会话。")
            asset.path.unlink(missing_ok=True)
            del self._assets[asset_id]

    async def add(self, upload: UploadFile) -> ImageAsset:
        try:
            original_name, suffix = _asset_name(upload.filename or "")
            async with self._upload_lock:
                if upload.size is not None and upload.size > self.max_image_bytes:
                    raise ValueError("图像超过单文件容量上限。")
                with self._lock:
                    self._reserve_unlocked(1, 0)
                asset_id = uuid4().hex
                target = self.session / (asset_id + suffix)
                digest = sha256()
                count = 0
                created = False
                committed = False
                try:
                    require_disk_space([(self.session, upload.size or 0)])
                    with target.open("xb") as stream:
                        created = True
                        while chunk := await upload.read(CHUNK_BYTES):
                            if count + len(chunk) > self.max_image_bytes:
                                raise ValueError("图像超过单文件容量上限。")
                            require_disk_space([(self.session, len(chunk))])
                            with self._lock:
                                self._reserve_unlocked(0, len(chunk))
                                count += len(chunk)
                            digest.update(chunk)
                            stream.write(chunk)
                    if count == 0:
                        raise ValueError("图像文件为空。")
                    asset = ImageAsset(asset_id, original_name, count, digest.hexdigest(), target)
                    with self._lock:
                        self._assets[asset_id] = asset
                        self._pending_count -= 1
                        self._pending_bytes -= count
                        committed = True
                    return asset
                finally:
                    if not committed:
                        if created:
                            target.unlink(missing_ok=True)
                        with self._lock:
                            self._pending_count -= 1
                            self._pending_bytes -= count
        finally:
            await upload.close()

    def close(self) -> None:
        """Remove only files belonging to this process's generated session."""
        if self.session.resolve().parent != self.root.resolve() or not re.fullmatch(r"[0-9a-f]{32}", self.session.name):
            raise ValueError("Refusing to clean a path outside the managed image session")
        with self._lock:
            if self._pending_count:
                raise ValueError("图像仍在导入，不能清理此会话。")
            self._assets.clear()
            self._leases.clear()
        if self.session.exists():
            for path in self.session.iterdir():
                if not path.is_file() or path.is_symlink():
                    raise ValueError("Unexpected entry in image session; manual review required")
                path.unlink()
            self.session.rmdir()


store = ImageAssetStore()
atexit.register(store.close)
