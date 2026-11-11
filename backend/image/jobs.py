"""Bounded Fiji jobs with truthful lifecycle and cancellation states."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import contextmanager
from copy import deepcopy
import atexit
import math
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock
from time import time
from typing import Any, Callable
from uuid import uuid4

from backend.image.assets import ImageAsset, ImageAssetStore, ImageAssetImportCancelled
from backend.image.fiji_process import (FijiCancelled, FijiUnavailable, inspect_asset,
    invert_8bit_asset, measure_selection, measure_roi_collection, EXPECTED_SHA256)
from backend.image.invert import validate_invert_input, verify_inversion
from backend.image.selection import EXTRA_MEASUREMENTS, ImageSelection, build_selection
from backend.image.roi_collection import validate_collection
from backend.image.multi_measure import run_native_multi_measure
from backend.image.set_measurements import run_native_set_measurements
from backend.image.non_area_measure import LINE_KINDS, POINT_KINDS, run_native_non_area_measure
from backend.image.native_area_geometry import run_native_area_geometry_measure
from backend.image.fiji_process import native_area_geometry_measure
from backend.image.fiji_process import native_roi_exchange
from backend.image.native_roi_exchange import run_roi_exchange
from backend.image.montage import MontageCancelled, render_exact_grid
from backend.image.results import ImageResultStore, ResultProof
from backend.image.batch import run_grid_batch
from backend.image.project_import import restore_grid_project
from backend.image.workspace_import import restore_workspace_project


MAX_JOBS = 4


@dataclass
class ImageJob:
    id: str
    asset_id: str
    operation: str = "inspect_metadata"
    source_label: str | None = None
    state: str = "queued"
    progress: float | None = None  # Fiji IOService exposes no reliable percentage here.
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time)
    finished_at: float | None = None
    cancel: Event = field(default_factory=Event, repr=False)
    future: Future | None = field(default=None, repr=False)
    lease_store: ImageAssetStore | None = field(default=None, repr=False)
    asset_ids: list[str] = field(default_factory=list)
    result_id: str | None = None
    result_store: ImageResultStore | None = field(default=None, repr=False)
    result_committed: bool = field(default=False, repr=False)
    close_lease_store_on_finish: bool = False
    admission_release: Callable[[], None] | None = field(default=None, repr=False)
    selection: ImageSelection | None = field(default=None, repr=False)

    def public(self, *, include_result: bool = True) -> dict[str, Any]:
        budget = ({"java_heap_mib": 2048, "wall_seconds": 180} if self.operation in ("inspect_metadata", "invert_8bit", "measure_selection")
                  else {"java_heap_mib": 2048, "wall_seconds": 180, "max_rois": 64,
                        "max_candidate_pixels": 4_000_000} if self.operation in ("measure_roi_collection", "native_multi_measure")
                  else {"max_grid_pixels": 16_000_000, "max_result_bytes": 512 * 1024 * 1024}
                  if self.operation == "exact_grid" else
                  {"max_sources": 8, "per_source_fiji_wall_seconds": 180,
                   "max_grid_pixels": 16_000_000, "max_source_bytes": 2 * 1024 ** 3}
                  if self.operation in ("open_grid_project", "open_workspace_project") else
                  {"max_files": 64, "max_groups": 64, "max_zip_bytes": 2 * 1024 * 1024 * 1024,
                   "wall_seconds": 1800})
        if self.operation == "native_multi_measure":
            budget = {"java_heap_mib": 2048, "wall_seconds": 180, "max_rois": 16,
                      "max_stack_planes": 64, "max_runs": 3, "max_table_values": 12288,
                      "max_candidate_pixels": 16_000_000, "max_report_bytes": 4 * 1024 * 1024}
        if self.operation == "native_set_measurements":
            budget = {"java_heap_mib": 2048, "wall_seconds": 180, "max_sources": 2,
                      "max_candidate_pixels": 1_000_000, "max_redirect_stack_planes": 64,
                      "max_report_bytes": 1048576, "non_area_max_points": 64, "non_area_max_planes": 64,
                      "area_max_outline_points": 4096, "area_max_shape_operands": 8}
        if self.operation == "native_roi_exchange":
            budget = {"java_heap_mib": 2048, "wall_seconds": 180, "max_rois": 64,
                      "max_stack_planes": 64, "max_file_bytes": 1048576,
                      "max_roi_bytes": 32768, "max_report_bytes": 2 * 1048576}
        return {"id": self.id, "asset_id": self.asset_id, "asset_ids": self.asset_ids,
                "operation": self.operation, "source_label": self.source_label,
                "selection": self.selection.public() if self.selection else None,
                "state": self.state, "progress": self.progress, "result": self.result if include_result else None,
                "error": self.error, "created_at": self.created_at,
                "finished_at": self.finished_at, "resource_budget": budget}


class ImageJobManager:
    def __init__(self):
        self._lock = Lock()
        self._closed = False
        self._jobs: dict[str, ImageJob] = {}
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="bfs-fiji")

    def _prune_finished(self) -> None:
        """Called while holding _lock; retain a bounded recent job history."""
        while len(self._jobs) >= 16:
            finished = next((identifier for identifier, old in self._jobs.items()
                             if old.state not in ("queued", "running")), None)
            if finished is None:
                break
            del self._jobs[finished]

    @contextmanager
    def _submission(self, asset_store: ImageAssetStore, asset_ids: list[str],
                    result_store: ImageResultStore | None = None):
        """One admission/lease/reservation boundary for every operation.

        The manager lock stays held through dispatch. On success the job owns
        the leases; before dispatch succeeds this context owns the rollback.
        Upload admission remains with the HTTP caller until submission returns.
        """
        with self._lock:
            if self._closed:
                raise ValueError("本地图像任务队列已关闭。")
            if sum(job.state in ("queued", "running") for job in self._jobs.values()) >= MAX_JOBS:
                raise ValueError("本地图像任务队列已满（4 项）。")
            self._prune_finished()
            assets = asset_store.acquire_many(asset_ids)
            result_id = None
            output = None
            try:
                if result_store is not None:
                    result_id, output = result_store.reserve()
                yield assets, result_id, output
            except BaseException:
                try:
                    if result_store is not None and result_id is not None:
                        result_store.discard(result_id)
                finally:
                    asset_store.release_many(asset_ids)
                raise

    def _dispatch(self, job: ImageJob, worker: Callable, *args) -> ImageJob:
        """Called only inside _submission; executor refusal is never visible."""
        self._jobs[job.id] = job
        try:
            job.future = self._executor.submit(worker, job, *args)
        except BaseException:
            self._jobs.pop(job.id, None)
            raise
        return job

    def submit_inspection(self, asset_store: ImageAssetStore, asset_id: str,
                          *, close_lease_store_on_finish: bool = False,
                          source_label: str | None = None) -> ImageJob:
        with self._submission(asset_store, [asset_id]) as (assets, _, _):
            job = ImageJob(id=uuid4().hex, asset_id=asset_id, lease_store=asset_store,
                           asset_ids=[asset_id], close_lease_store_on_finish=close_lease_store_on_finish,
                           source_label=source_label)
            return self._dispatch(job, self._work, assets[0])

    def submit_project(self, archive_store: ImageAssetStore, archive_id: str,
                       asset_store: ImageAssetStore, result_store: ImageResultStore,
                       admission_release: Callable[[], None] | None = None, *,
                       workspace: bool = False) -> ImageJob:
        with self._submission(archive_store, [archive_id], None if workspace else result_store) as (assets, result_id, output):
            job = ImageJob(id=uuid4().hex, asset_id=archive_id, asset_ids=[archive_id],
                operation="open_workspace_project" if workspace else "open_grid_project", lease_store=archive_store,
                result_store=None if workspace else result_store, result_id=result_id,
                close_lease_store_on_finish=True, admission_release=admission_release)
            return self._dispatch(job, self._work_project, assets[0], asset_store, output)

    def _work_project(self, job: ImageJob, archive: ImageAsset,
                      asset_store: ImageAssetStore, output: Path | None) -> None:
        with self._lock:
            if not job.cancel.is_set():
                job.state = "running"
        final_state = "failed"
        error = None

        def progress(value):
            with self._lock:
                job.progress = value

        def committed(payload):
            # Called under _lock. Cancellation after this point is a no-op.
            job.result = payload
            job.result_committed = True
            job.progress = 1.0

        try:
            if job.operation == "open_workspace_project":
                restore_workspace_project(archive.path, asset_store, job.id, job.cancel,
                    commit_lock=self._lock, progress=progress, on_commit=committed)
            else:
                restore_grid_project(archive.path, asset_store, job.result_store, job.result_id,
                    output, job.id, job.cancel, commit_lock=self._lock, progress=progress, on_commit=committed)
            final_state = "succeeded"
        except (ImageAssetImportCancelled, FijiCancelled, MontageCancelled):
            final_state = "cancelled"
        except (FijiUnavailable, ValueError, OSError, TimeoutError) as cause:
            error = str(cause)
        except Exception:
            error = "项目重开失败；原图、拼版和标注未能全部恢复。"
        finally:
            # Once committed, cleanup errors cannot turn a valid publication
            # into a reported rollback or cause its assets to be removed.
            if job.result is not None:
                final_state = "succeeded"
                error = None
            elif job.result_store is not None:
                job.result_store.discard(job.result_id)
            self._release_lease(job)
            with self._lock:
                job.state = final_state
                job.error = error
                job.finished_at = time()

    def submit_grid(self, asset_store: ImageAssetStore, result_store: ImageResultStore,
                    asset_ids: list[str], columns: int, gap_px: int) -> ImageJob:
        if not 1 <= len(asset_ids) <= 8 or not 1 <= columns <= len(asset_ids) or not 0 <= gap_px <= 1000:
            raise ValueError("网格需要 1 至 8 张图像、有效列数与 0 至 1000 像素间距。")
        with self._submission(asset_store, asset_ids, result_store) as (assets, result_id, output):
            job = ImageJob(id=uuid4().hex, asset_id=asset_ids[0], asset_ids=asset_ids.copy(),
                operation="exact_grid", lease_store=asset_store,
                result_store=result_store, result_id=result_id)
            return self._dispatch(job, self._work_grid, assets, columns, gap_px, output)

    def submit_invert(self, asset_store: ImageAssetStore, result_store: ImageResultStore,
                      asset_id: str) -> ImageJob:
        with self._submission(asset_store, [asset_id], result_store) as (assets, result_id, output):
            job = ImageJob(id=uuid4().hex, asset_id=asset_id, asset_ids=[asset_id],
                operation="invert_8bit", lease_store=asset_store,
                result_store=result_store, result_id=result_id)
            return self._dispatch(job, self._work_invert, assets[0], output)

    def submit_measure(self, asset_store: ImageAssetStore, asset_id: str,
                       indices: dict[str, int], roi: dict[str, Any] | None,
                       extra_measurements: list[str] | None = None) -> ImageJob:
        with self._submission(asset_store, [asset_id]) as (assets, _, _):
            selection = build_selection(assets[0], indices, roi, extra_measurements)
            job = ImageJob(id=uuid4().hex, asset_id=asset_id, asset_ids=[asset_id],
                operation="measure_selection", lease_store=asset_store, selection=selection)
            return self._dispatch(job, self._work_measure, assets[0], selection)

    def submit_collection_measure(self, asset_store: ImageAssetStore, asset_id: str,
                                  collection: dict[str, Any], extras: list[str],
                                  cancel: Event | None = None) -> ImageJob:
        with self._submission(asset_store, [asset_id]) as (assets, _, _):
            document = validate_collection(assets[0], collection)
            if not document["items"]:
                raise ValueError("集合测量至少需要一个 ROI。")
            if (not isinstance(extras, list) or any(not isinstance(value, str) for value in extras)
                    or len(extras) != len(set(extras))
                    or any(value not in EXTRA_MEASUREMENTS for value in extras)):
                raise ValueError("额外测量选项无效或重复。")
            extras = [value for value in EXTRA_MEASUREMENTS if value in extras]
            total = sum(item["roi"]["width"] * item["roi"]["height"] for item in document["items"])
            if total > 4_000_000:
                raise ValueError("集合测量候选像素总量不得超过 400 万。")
            job = ImageJob(id=uuid4().hex, asset_id=asset_id, asset_ids=[asset_id],
                operation="measure_roi_collection", lease_store=asset_store,
                cancel=cancel if cancel is not None else Event())
            return self._dispatch(job, self._work_collection_measure, assets[0], deepcopy(document), extras)

    def submit_multi_measure(self, asset_store: ImageAssetStore, asset_id: str, request: dict) -> ImageJob:
        with self._submission(asset_store, [asset_id]) as (assets, _, _):
            frozen = deepcopy(request)
            job = ImageJob(id=uuid4().hex, asset_id=asset_id, asset_ids=[asset_id],
                operation="native_multi_measure", lease_store=asset_store)
            def execute():
                return run_native_multi_measure(assets[0], frozen["collection"], frozen["selected_roi_ids"],
                    frozen["current_plane"], frozen["runs"], frozen["measurement_flags"], job.cancel)
            return self._dispatch(job, self._work_analysis, assets[0], execute)

    def submit_native_measure(self, asset_store: ImageAssetStore, asset_id: str, request: dict) -> ImageJob:
        redirect_id = request.get("redirect_asset_id")
        identities = [asset_id, redirect_id] if redirect_id is not None else [asset_id]
        with self._submission(asset_store, identities) as (assets, _, _):
            frozen = deepcopy(request)
            job = ImageJob(id=uuid4().hex, asset_id=asset_id, asset_ids=identities,
                operation="native_set_measurements", lease_store=asset_store)
            def execute():
                target = assets[1] if len(assets) > 1 else None
                roi = frozen["roi"]
                if isinstance(roi, dict) and isinstance(roi.get("kind"), str) and roi["kind"] in LINE_KINDS | POINT_KINDS | {"angle"}:
                    result = run_native_non_area_measure(assets[0], frozen["indices"], roi, frozen["settings"],
                        target, frozen["redirect_plane"], job.cancel)
                elif isinstance(roi, dict) and roi.get("version") == "1.0":
                    result = run_native_area_geometry_measure(assets[0], frozen["indices"], roi, frozen["settings"],
                        target, frozen["redirect_plane"], job.cancel, native_area_geometry_measure)
                else:
                    selection = build_selection(assets[0], frozen["indices"], roi)
                    result = run_native_set_measurements(assets[0], selection, frozen["settings"],
                        target, frozen["redirect_plane"], job.cancel)
                result["redirect_source"] = target.public() if target is not None else None
                return result
            return self._dispatch(job, self._work_analysis, assets[0], execute)

    def submit_roi_exchange(self, asset_store: ImageAssetStore, asset_id: str, request: dict) -> ImageJob:
        with self._submission(asset_store, [asset_id]) as (assets, _, _):
            frozen = deepcopy(request)
            job = ImageJob(id=uuid4().hex, asset_id=asset_id, asset_ids=[asset_id],
                           operation="native_roi_exchange", lease_store=asset_store)
            def execute():
                import base64
                from hashlib import sha256
                operation = frozen["operation"]
                encoded = frozen.get("file_base64")
                raw = base64.b64decode(encoded, validate=True) if encoded is not None else None
                result = run_roi_exchange(assets[0], operation, job.cancel, native_roi_exchange,
                                          collection=frozen.get("collection"), file_bytes=raw)
                if "bytes" in result:
                    content = result.pop("bytes")
                    result.update(bytes=len(content), sha256=sha256(content).hexdigest(),
                                  file_base64=base64.b64encode(content).decode("ascii"),
                                  filename="biofigure-rois.zip" if operation == "export_zip" else "biofigure-region.roi")
                return result
            return self._dispatch(job, self._work_analysis, assets[0], execute)

    def submit_batch(self, asset_store: ImageAssetStore, result_store: ImageResultStore,
                     asset_ids: list[str], group_size: int, columns: int, gap_px: int,
                     admission_release: Callable[[], None] | None = None) -> ImageJob:
        if (not 1 <= len(asset_ids) <= 64 or not 1 <= group_size <= 8
                or len(asset_ids) % group_size or not 1 <= columns <= group_size
                or not 0 <= gap_px <= 1000):
            raise ValueError("批量输入需 1 至 64 张图像、完整分组与有效列数/间距。")
        with self._submission(asset_store, asset_ids, result_store) as (assets, result_id, output):
            groups = [assets[index:index + group_size] for index in range(0, len(assets), group_size)]
            job = ImageJob(id=uuid4().hex, asset_id=asset_ids[0], asset_ids=asset_ids.copy(),
                operation="exact_grid_batch", lease_store=asset_store,
                close_lease_store_on_finish=True, result_store=result_store,
                result_id=result_id, progress=0.0, admission_release=admission_release)
            return self._dispatch(job, self._work_batch, groups, columns, gap_px, output)

    @staticmethod
    def _release_lease(job: ImageJob) -> None:
        try:
            if job.lease_store is not None:
                lease_store = job.lease_store
                lease_store.release_many(job.asset_ids)
                job.lease_store = None
                if job.close_lease_store_on_finish:
                    lease_store.close()
        finally:
            release = job.admission_release
            job.admission_release = None
            if release is not None:
                release()

    def _work(self, job: ImageJob, asset: ImageAsset) -> None:
        with self._lock:
            if not job.cancel.is_set():
                job.state = "running"
        final_state = "failed"
        result: dict[str, Any] | None = None
        error: str | None = None
        try:
            if job.cancel.is_set():
                raise FijiCancelled()
            result = inspect_asset(asset, job.id, job.cancel)
            result["source_name"] = asset.name
            final_state = "cancelled" if job.cancel.is_set() else "succeeded"
            if final_state == "succeeded" and job.lease_store is not None:
                job.lease_store.set_metadata(asset.id, result)
        except FijiCancelled:
            final_state = "cancelled"
        except (FijiUnavailable, FileNotFoundError) as cause:
            error = str(cause)
        except (ValueError, TimeoutError):
            error = "Fiji 无法完成图像元数据检查；请确认格式和资源限制。"
        except Exception:
            error = "Fiji 图像任务异常终止。"
        finally:
            self._release_lease(job)
            with self._lock:
                job.state = final_state
                job.result = result if final_state == "succeeded" else None
                job.error = error
                job.finished_at = time()

    def _publish_result(self, job: ImageJob, proof: ResultProof) -> dict[str, Any]:
        """Linearize cancellation against the moment a result becomes public."""
        with self._lock:
            if job.cancel.is_set():
                raise FijiCancelled()
            if job.result_store is None or job.result_id is None:
                raise RuntimeError("Result reservation missing")
            result = job.result_store.finish(job.result_id, proof).public()
            job.result = result
            job.result_committed = True
            return result

    def _work_grid(self, job: ImageJob, assets: list[ImageAsset], columns: int,
                   gap_px: int, output: Path) -> None:
        with self._lock:
            if not job.cancel.is_set():
                job.state = "running"
        final_state = "failed"
        result: dict[str, Any] | None = None
        error: str | None = None
        published = False
        try:
            if job.cancel.is_set():
                raise MontageCancelled()
            proof = render_exact_grid(assets, columns, gap_px, output, job.cancel)
            if job.cancel.is_set():
                raise MontageCancelled()
            result = self._publish_result(job, proof)
            published = True
            final_state = "succeeded"
        except (MontageCancelled, FijiCancelled):
            final_state = "cancelled"
        except (ValueError, FileNotFoundError) as cause:
            error = str(cause)
        except Exception:
            error = "原像素网格任务异常终止。"
        finally:
            if job.result_store is not None and job.result_id is not None and final_state != "succeeded":
                if published:
                    job.result_store.remove(job.result_id)
                else:
                    job.result_store.discard(job.result_id)
            self._release_lease(job)
            with self._lock:
                job.state = final_state
                job.result = result if final_state == "succeeded" else None
                job.error = error
                job.finished_at = time()

    def _work_invert(self, job: ImageJob, asset: ImageAsset, output: Path) -> None:
        with self._lock:
            if not job.cancel.is_set():
                job.state = "running"
        final_state = "failed"
        result: dict[str, Any] | None = None
        error: str | None = None
        published = False
        try:
            if job.cancel.is_set():
                raise FijiCancelled()
            validate_invert_input(asset)
            invert_8bit_asset(asset, job.id, job.cancel, output)
            if job.cancel.is_set():
                raise FijiCancelled()
            proof = verify_inversion(asset, output)
            result = self._publish_result(job, proof)
            published = True
            final_state = "succeeded"
        except FijiCancelled:
            final_state = "cancelled"
        except (FijiUnavailable, ValueError, FileNotFoundError, TimeoutError) as cause:
            error = str(cause)
        except Exception:
            error = "Fiji 反相任务异常终止。"
        finally:
            if job.result_store is not None and job.result_id is not None and final_state != "succeeded":
                if published:
                    job.result_store.remove(job.result_id)
                else:
                    job.result_store.discard(job.result_id)
            self._release_lease(job)
            with self._lock:
                job.state = final_state
                job.result = result if final_state == "succeeded" else None
                job.error = error
                job.finished_at = time()

    def _work_measure(self, job: ImageJob, asset: ImageAsset, selection: ImageSelection) -> None:
        with self._lock:
            if not job.cancel.is_set():
                job.state = "running"
        final_state = "failed"
        result: dict[str, Any] | None = None
        error: str | None = None
        try:
            if job.cancel.is_set():
                raise FijiCancelled()
            payload = measure_selection(asset, job.id, job.cancel, selection)
            if job.cancel.is_set():
                raise FijiCancelled()
            actual_count = payload.get("sample_count")
            if (payload.get("selection") != selection.public() or
                    not isinstance(actual_count, int) or actual_count < 1 or
                    (actual_count != selection.sample_count if selection.roi["kind"] in ("rectangle", "full")
                     else actual_count > selection.sample_count)):
                raise ValueError("Fiji 结果与提交的 ROI/C/Z/T 选择不一致。")
            result = {key: value for key, value in payload.items() if key != "ok"}
            result["source"] = asset.public()
            result["execution"] = {"command": "ij.plugin.filter.Analyzer",
                                   "runtime_archive_sha256": EXPECTED_SHA256}
            final_state = "succeeded"
        except FijiCancelled:
            final_state = "cancelled"
        except (FijiUnavailable, ValueError, FileNotFoundError, TimeoutError) as cause:
            error = str(cause)
        except Exception:
            error = "Fiji 区域测量任务异常终止。"
        finally:
            self._release_lease(job)
            with self._lock:
                job.state = final_state
                job.result = result if final_state == "succeeded" else None
                job.error = error
                job.finished_at = time()

    def _work_collection_measure(self, job: ImageJob, asset: ImageAsset,
                                 collection: dict[str, Any], extras: list[str]) -> None:
        self._work_analysis(job, asset, lambda: self._collection_measurement_result(job, asset, collection, extras))

    def _collection_measurement_result(self, job: ImageJob, asset: ImageAsset,
                                       collection: dict[str, Any], extras: list[str]) -> dict:
        payload = measure_roi_collection(asset, job.id, job.cancel, collection, extras)
        if job.cancel.is_set():
            raise FijiCancelled()
        rows = payload.get("rows")
        if (payload.get("source") != collection["source"] or
                payload.get("extra_measurements") != extras or
                not isinstance(rows, list) or len(rows) != len(collection["items"]) or
                payload.get("roi_manager_multi_measure_equivalent") is not False):
            raise ValueError("Fiji 集合测量结果与提交内容不一致。")
        for item, row in zip(collection["items"], rows):
            if (not isinstance(row, dict) or any(row.get(key) != item[key]
                                                 for key in ("id", "name", "indices", "roi"))
                    or type(row.get("sample_count")) is not int
                    or not 1 <= row["sample_count"] <= item["roi"]["width"] * item["roi"]["height"]):
                raise ValueError("Fiji 集合测量条目或像素数与提交内容不一致。")
            values = row.get("imagej1_analyzer")
            required = {"area", "mean", "min", "max"}
            required.update(value for value in extras if value != "integrated_density")
            if "integrated_density" in extras:
                required.update(("integrated_density", "raw_integrated_density"))
            if (not isinstance(values, dict) or set(values) != required | {"area_unit"}
                    or not isinstance(values.get("area_unit"), str)
                    or any(type(values.get(key)) not in (int, float) or not math.isfinite(values[key])
                           for key in required)):
                raise ValueError("Fiji 集合测量数值字段缺失或无效。")
        result = {key: value for key, value in payload.items() if key != "ok"}
        result["source_file"] = {"original_name": asset.name, "bytes": asset.bytes, "sha256": asset.sha256}
        result["execution"] = {"engine": "Fiji / ImageJ1 Analyzer", "runtime_sha256": EXPECTED_SHA256,
                               "script": "fiji_measure_roi_collection.groovy"}
        return result

    def _work_analysis(self, job: ImageJob, asset: ImageAsset, execute: Callable[[], dict]) -> None:
        """One lifecycle for bounded native records; publish after cleanup."""
        with self._lock:
            if not job.cancel.is_set():
                job.state = "running"
        final_state, result, error = "failed", None, None
        try:
            if job.cancel.is_set():
                raise FijiCancelled()
            result = execute()
            result.setdefault("source_file", {"original_name": asset.name, "bytes": asset.bytes, "sha256": asset.sha256})
            final_state = "succeeded"
        except FijiCancelled:
            final_state = "cancelled"
        except (FijiUnavailable, ValueError, OSError, TimeoutError) as cause:
            error = str(cause)
        except Exception:
            error = "Fiji 图像任务异常终止。"
        finally:
            self._release_lease(job)
            with self._lock:
                if job.cancel.is_set():
                    final_state, error = "cancelled", None
                job.state = final_state
                job.result = result if final_state == "succeeded" else None
                job.error = error
                job.finished_at = time()

    def _work_batch(self, job: ImageJob, groups: list[list[ImageAsset]], columns: int,
                    gap_px: int, output: Path) -> None:
        with self._lock:
            if not job.cancel.is_set():
                job.state = "running"
        final_state = "failed"
        result: dict[str, Any] | None = None
        error: str | None = None
        published = False

        def update_progress(done: int, total: int) -> None:
            with self._lock:
                job.progress = done / total

        try:
            if job.cancel.is_set():
                raise MontageCancelled()
            proof = run_grid_batch(groups, columns, gap_px, output, job.cancel, update_progress)
            if job.cancel.is_set():
                raise MontageCancelled()
            result = self._publish_result(job, proof)
            published = True
            final_state = "succeeded"
        except (MontageCancelled, FijiCancelled):
            final_state = "cancelled"
        except (ValueError, FileNotFoundError, TimeoutError) as cause:
            error = str(cause)
        except Exception:
            error = "批量原像素网格任务异常终止。"
        finally:
            if job.result_store is not None and job.result_id is not None and final_state != "succeeded":
                if published:
                    job.result_store.remove(job.result_id)
                else:
                    job.result_store.discard(job.result_id)
            self._release_lease(job)
            with self._lock:
                job.state = final_state
                job.result = result if final_state == "succeeded" else None
                job.error = error
                job.finished_at = time()

    def get(self, job_id: str) -> ImageJob:
        with self._lock:
            return self._jobs[job_id]

    def measurement_snapshot(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._jobs[job_id]
            if job.operation != "measure_selection" or job.state != "succeeded" or job.result is None:
                raise ValueError("只有已完成的区域测量可以下载记录。")
            if "source" not in job.result:
                raise ValueError("此旧测量缺少来源记录，请重新测量。")
            return deepcopy(job.public())

    def all_public(self, *, include_results: bool = True) -> list[dict[str, Any]]:
        with self._lock:
            return [job.public(include_result=include_results) for job in self._jobs.values()]

    def cancel(self, job_id: str) -> ImageJob:
        with self._lock:
            job = self._jobs[job_id]
            if job.state not in ("queued", "running") or job.result_committed:
                return job
            job.cancel.set()
            if job.future and job.future.cancel():
                job.state = "cancelled"
                job.finished_at = time()
                self._release_lease(job)
                if job.result_store is not None and job.result_id is not None:
                    job.result_store.discard(job.result_id)
            return job

    def close(self) -> None:
        with self._lock:
            self._closed = True
            for job in self._jobs.values():
                if job.state in ("queued", "running") and not job.result_committed:
                    job.cancel.set()
                    if job.future and job.future.cancel():
                        job.state = "cancelled"
                        job.finished_at = time()
                        self._release_lease(job)
                        if job.result_store is not None and job.result_id is not None:
                            job.result_store.discard(job.result_id)
        self._executor.shutdown(wait=True, cancel_futures=True)


manager = ImageJobManager()
atexit.register(manager.close)
