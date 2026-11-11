"""Reopen original stacks and their workspace state as one asset transaction."""

from contextlib import nullcontext
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock
from typing import Callable

from backend.image.assets import ImageAssetStore, ImageAssetImportCancelled
from backend.image.project_import import inspect_project_sources
from backend.image.storage import require_disk_space
from backend.image.paths import image_work_dir
from backend.image.workspace_project import read_workspace_project, normalize_workspace_state


ROOT = image_work_dir("image-workspace-imports")


def restore_workspace_project(archive: Path, assets: ImageAssetStore, job_id: str,
                              cancel: Event, *, commit_lock: Lock | None = None,
                              root: Path = ROOT, progress: Callable[[float], None] | None = None,
                              on_commit: Callable[[dict], None] | None = None) -> dict:
    """Publish checked sources and remapped state together, after fresh Fiji IO.

    The caller's commit lock must also protect job cancellation and readers of
    on_commit state. Callback checks must finish before publishing anything;
    it must not call the asset store while its transaction lock is held.
    """
    def check_cancel():
        if cancel.is_set():
            raise ImageAssetImportCancelled()

    check_cancel()
    root.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="import-", dir=root) as directory:
        def before_extract(manifest):
            total = sum(source.bytes for source in manifest.sources)
            require_disk_space([(Path(directory), total), (assets.session, total)])

        pending = read_workspace_project(archive, Path(directory) / "sources", cancel,
                                         before_extract=before_extract)
        manifest = pending.manifest
        inspected = inspect_project_sources(pending, job_id, cancel, progress=progress)
        states = {}
        sources = {source.id: source for source in inspected}
        for source in inspected:
            check_cancel()
            state = manifest.source_states.get(source.id)
            if state is not None:
                # Validate stored source identity, ROI geometry, C/Z/T and
                # options against fresh axes before copying or publishing.
                states[source.id] = normalize_workspace_state(source, state, sources).model_dump()
        with assets.stage_many(inspected, cancel) as staged:
            identities = {source.key: asset.id for source, asset in zip(manifest.sources, staged.assets, strict=True)}
            for state in states.values():
                native = state["native_measurement"]
                if native is not None and native["redirect_source"] is not None:
                    native["redirect_source"] = identities[native["redirect_source"]]
            payload = {
                "assets": [asset.public() for asset in staged.assets],
                "source_verification": "fresh_fiji_inspection",
                "workspace": {
                    "source_states": {identities[key]: state for key, state in states.items()},
                    "active_asset_id": identities[manifest.active_source_key] if manifest.active_source_key else None,
                    "selected_asset_ids": [identities[key] for key in manifest.selected_source_keys],
                    "grid": manifest.grid.model_dump(),
                },
            }
            with commit_lock if commit_lock is not None else nullcontext():
                check_cancel()
                staged.commit((lambda: on_commit(payload)) if on_commit is not None else None)
            return payload
