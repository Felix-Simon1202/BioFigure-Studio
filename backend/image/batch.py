"""Sequential, bounded multi-group exact-pixel montage export."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from threading import Event
import tempfile
import time
from typing import Callable
import zipfile

from backend.image.assets import ImageAsset
from backend.image.montage import MontageCancelled, render_exact_grid, MAX_GRID_PIXELS
from backend.image.storage import require_disk_space


MAX_BATCH_FILES = 64
MAX_BATCH_GROUPS = 64
MAX_BATCH_ZIP_BYTES = 2 * 1024 * 1024 * 1024
MAX_BATCH_SECONDS = 1800


@dataclass(frozen=True)
class BatchProof:
    output_sha256: str
    groups: tuple[dict[str, object], ...]
    source_count: int

    def public(self) -> dict[str, object]:
        return {"group_count": len(self.groups), "source_count": self.source_count,
                "groups": list(self.groups), "output_sha256": self.output_sha256,
                "scope": "per-group exact pixels; source calibration remains per placement"}


def _hash_stream(stream, check: Callable[[], None]) -> str:
    digest = sha256()
    while True:
        check()
        chunk = stream.read(4 * 1024 * 1024)
        if not chunk:
            break
        digest.update(chunk)
    return digest.hexdigest()


def run_grid_batch(groups: list[list[ImageAsset]], columns: int, gap_px: int,
                   output: Path, cancel: Event,
                   on_group_done: Callable[[int, int], None] | None = None) -> BatchProof:
    if not 1 <= len(groups) <= MAX_BATCH_GROUPS:
        raise ValueError("批量任务需要 1 至 64 组图像。")
    if not 1 <= sum(map(len, groups)) <= MAX_BATCH_FILES:
        raise ValueError("批量任务最多接受 64 张图像。")
    if any(not 1 <= len(group) <= 8 for group in groups):
        raise ValueError("每组需 1 至 8 张图像。")
    if not 1 <= columns <= min(map(len, groups)) or not 0 <= gap_px <= 1000:
        raise ValueError("批量任务列数或间距无效。")
    if output.exists():
        raise ValueError("批量成品目标已存在。")
    output.parent.mkdir(parents=True, exist_ok=True)
    partial = output.with_name(output.name + ".partial")
    deadline = time.monotonic() + MAX_BATCH_SECONDS
    summaries: list[dict[str, object]] = []
    created = False

    def check():
        if cancel.is_set():
            raise MontageCancelled()
        if time.monotonic() > deadline:
            raise TimeoutError("批量拼版超过 30 分钟时限。")

    try:
        check()
        with tempfile.TemporaryDirectory(prefix="grid-batch-", dir=output.parent) as directory:
            temporary = Path(directory)
            with partial.open("xb") as raw:
                created = True
                with zipfile.ZipFile(raw, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                    for index, group in enumerate(groups, start=1):
                        check()
                        # Current ZIP already consumes disk. Budget one bounded
                        # TIFF plus its additional uncompressed ZIP member.
                        require_disk_space([(output.parent, 2 * (MAX_GRID_PIXELS * 4 + 1024 * 1024))])
                        image_path = temporary / f"grid-{index:03d}.tif"
                        proof = render_exact_grid(group, columns, gap_px, image_path, cancel)
                        check()
                        with image_path.open("rb") as source, archive.open(image_path.name, "w", force_zip64=True) as target:
                            while True:
                                check()
                                chunk = source.read(4 * 1024 * 1024)
                                if not chunk:
                                    break
                                if archive.fp.tell() + len(chunk) > MAX_BATCH_ZIP_BYTES:
                                    raise ValueError("批量成品超过 2 GiB 上限。")
                                target.write(chunk)
                        image_path.unlink()
                        summaries.append({"index": index, "filename": image_path.name,
                                          "source_names": [asset.name for asset in group],
                                          "source_sha256": [asset.sha256 for asset in group],
                                          "proof": proof.public()})
                        if on_group_done is not None:
                            on_group_done(index, len(groups))
                    manifest = {"schema_version": "1.0", "operation": "exact_grid_batch",
                                "group_count": len(groups), "source_count": sum(map(len, groups)),
                                "groups": summaries}
                    archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
            check()
            # Include manifest, ZIP64 records and the final central directory.
            if partial.stat().st_size > MAX_BATCH_ZIP_BYTES:
                raise ValueError("批量成品超过 2 GiB 上限。")
            with zipfile.ZipFile(partial) as archive:
                for summary in summaries:
                    with archive.open(summary["filename"]) as member:
                        if _hash_stream(member, check) != summary["proof"]["output_sha256"]:
                            raise ValueError("批量 ZIP 中的 TIFF 摘要不一致。")
                check()
                if json.loads(archive.read("manifest.json")) != manifest:
                    raise ValueError("批量 ZIP 清单不一致。")
            with partial.open("rb") as source:
                digest = _hash_stream(source, check)
            check()
            # Same-volume exclusive publication: never replace a raced-in file.
            os.link(partial, output)
        return BatchProof(digest, tuple(summaries), sum(map(len, groups)))
    finally:
        if created:
            partial.unlink(missing_ok=True)
