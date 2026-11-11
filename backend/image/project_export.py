"""One bounded portable-project export at a time, with source leases."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event, Lock, Semaphore
from typing import Callable

from backend.image.assets import ImageAssetStore
from backend.image.project import save_grid_project, MAX_MANIFEST_BYTES
from backend.image.results import ImageResultStore
from backend.image.storage import require_disk_space
from backend.image.paths import image_work_dir


ROOT = image_work_dir("image-project-exports")
_admission = Semaphore(1)


class ProjectExportBusy(ValueError):
    pass


@dataclass
class ProjectExport:
    path: Path
    _temporary: TemporaryDirectory
    _gate: Semaphore
    _close_lock: Lock
    _closed: bool = False

    def close(self) -> None:
        with self._close_lock:
            if not self._closed:
                try:
                    self._temporary.cleanup()
                finally:
                    self._closed = True
                    self._gate.release()


def prepare_project_export(result_id: str, assets: ImageAssetStore,
                           results: ImageResultStore, *, root: Path = ROOT,
                           gate: Semaphore = _admission) -> ProjectExport:
    def plan():
        proof, annotations = results.grid_project_snapshot(result_id)
        return [placement.asset_id for placement in proof.placements], lambda sources, output: save_grid_project(sources, proof, annotations, output)
    return _prepare_source_export(assets, plan, MAX_MANIFEST_BYTES, ".bfsimg", root=root, gate=gate)


def prepare_workspace_export(assets: ImageAssetStore, request: dict, *, root: Path = ROOT,
                             gate: Semaphore = _admission, cancel: Event | None = None) -> ProjectExport:
    from backend.image.workspace_project import WorkspaceExportRequest, save_workspace_project, MAX_WORKSPACE_MANIFEST_BYTES
    checked = WorkspaceExportRequest.model_validate(request)
    def plan():
        return checked.asset_ids, lambda sources, output: save_workspace_project(sources,
            checked.source_states, output, active_asset_id=checked.active_asset_id,
            selected_asset_ids=checked.selected_asset_ids, grid=checked.grid, cancel=cancel)
    return _prepare_source_export(assets, plan, MAX_WORKSPACE_MANIFEST_BYTES, ".bfswork", root=root, gate=gate)


def _prepare_source_export(assets: ImageAssetStore, plan: Callable, manifest_budget: int, suffix: str,
                            *, root: Path, gate: Semaphore) -> ProjectExport:
    # Keep admission through response completion: slow downloads also occupy disk.
    if not gate.acquire(blocking=False):
        raise ProjectExportBusy("已有项目包正在保存或下载，请等待完成。")
    temporary = None
    leased_ids = []
    try:
        root.mkdir(parents=True, exist_ok=True)
        temporary = TemporaryDirectory(prefix="export-", dir=root)
        source_ids, write = plan()
        sources = assets.acquire_many(source_ids)
        leased_ids = source_ids
        require_disk_space([(Path(temporary.name), sum(source.bytes for source in sources) + manifest_budget + 65536)])
        output = Path(temporary.name) / ("project" + suffix)
        write(sources, output)
        return ProjectExport(output, temporary, gate, Lock())
    except BaseException:
        try:
            if temporary is not None:
                temporary.cleanup()
        finally:
            gate.release()
        raise
    finally:
        if leased_ids:
            assets.release_many(leased_ids)
