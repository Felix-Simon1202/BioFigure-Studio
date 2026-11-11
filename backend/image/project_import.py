"""Reinspect and rebuild a portable grid before publishing any new assets."""

from contextlib import nullcontext
from dataclasses import replace
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock
from typing import Callable

from backend.image.assets import ImageAsset, ImageAssetStore, ImageAssetImportCancelled
from backend.image.fiji_process import inspect_asset
from backend.image.montage import render_exact_grid, MAX_GRID_PIXELS
from backend.image.project import read_grid_project
from backend.image.results import ImageResultStore
from backend.image.storage import require_disk_space
from backend.image.paths import image_work_dir


ROOT = image_work_dir("image-project-imports")


def inspect_project_sources(pending, job_id: str, cancel: Event, *,
                            progress: Callable[[float], None] | None = None) -> list[ImageAsset]:
    """Inspect original bytes; package metadata never becomes live metadata."""
    inspected = []
    for index, (reference, path) in enumerate(zip(pending.manifest.sources, pending.source_paths, strict=True)):
        if cancel.is_set():
            raise ImageAssetImportCancelled()
        source = ImageAsset(reference.key, reference.original_name, reference.bytes, reference.sha256, path)
        inspection_id = sha256(f"{job_id}:{index}".encode("utf-8")).hexdigest()[:32]
        metadata = inspect_asset(source, inspection_id, cancel)
        if cancel.is_set():
            raise ImageAssetImportCancelled()
        inspected.append(replace(source, metadata={key: metadata.get(key)
            for key in ("axes", "pixel_type", "bit_depth", "channels")}))
        if progress is not None:
            progress((index + 1) / (len(pending.manifest.sources) + 1))
    return inspected


def restore_grid_project(archive: Path, assets: ImageAssetStore, results: ImageResultStore,
                         result_id: str, output: Path, job_id: str, cancel: Event, *,
                         commit_lock: Lock | None = None, root: Path = ROOT,
                         progress: Callable[[float], None] | None = None,
                         on_commit: Callable[[dict], None] | None = None) -> dict:
    """Caller owns the reserved result and discards it if this operation fails.

    commit_lock linearizes the short publication step against job cancellation.
    Lock order: job manager -> asset store -> result store.
    """
    def check_cancel():
        if cancel.is_set():
            raise ImageAssetImportCancelled()

    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="import-", dir=root) as directory:
        def before_extract(manifest):
            total = sum(source.bytes for source in manifest.sources)
            # The archive already occupies disk. Budget the additional extracted
            # sources, copied assets and worst supported 4-byte-per-pixel grid.
            require_disk_space([(Path(directory), total), (assets.session, total),
                                (output.parent, MAX_GRID_PIXELS * 4 + 1024 * 1024)])

        pending = read_grid_project(archive, Path(directory) / "sources", cancel,
                                    before_extract=before_extract)
        inspected = inspect_project_sources(pending, job_id, cancel, progress=progress)
        with assets.stage_many(inspected, cancel) as staged:
            recipe = pending.manifest.grid
            proof = render_exact_grid(staged.assets, recipe.columns, recipe.gap_px, output, cancel)
            identities = {source.key: asset.id for source, asset in zip(pending.manifest.sources, staged.assets, strict=True)}
            annotations = [{**item, "asset_id": identities[item["asset_id"]]} if "asset_id" in item else item
                           for item in pending.manifest.annotations]
            saved = None

            def publish():
                nonlocal saved
                saved = results.finish(result_id, proof, annotations=annotations)

            with commit_lock if commit_lock is not None else nullcontext():
                check_cancel()
                staged.commit(publish)
                payload = {"result": saved.public(), "assets": [asset.public() for asset in staged.assets],
                    "source_verification": "fresh_fiji_inspection",
                    "original_output_sha256": pending.manifest.original_output_sha256}
                if on_commit is not None:
                    on_commit(payload)
            return payload
