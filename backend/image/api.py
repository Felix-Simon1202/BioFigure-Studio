"""Read-only Fiji inventory endpoints for the image workspace."""

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from starlette.concurrency import run_in_threadpool
from contextlib import contextmanager
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from backend.image.assets import ImageAssetStore, store, MAX_SESSION_BYTES
from backend.image.catalog import load_inventory, runtime_status
from backend.image.jobs import manager
from backend.image.preview import source_plane_png
from backend.image.roi_collection import MAX_COLLECTION_BYTES, source_identity, validate_collection
from backend.image.roi_collection import MAX_NATIVE_ZIP_BYTES, bind_native_zip, inspect_native_zip
from backend.image.fiji_process import FijiCancelled, FijiUnavailable, run_roi_zip
from backend.image.results import batch_results, results
from backend.image.batch import MAX_BATCH_FILES
from backend.image.project_export import ProjectExportBusy, prepare_project_export, prepare_workspace_export
from backend.image.project import MAX_PROJECT_BYTES
from backend.image.workspace_project import MAX_WORKSPACE_MANIFEST_BYTES
from backend.image.measurement_export import measurement_record, measurement_json, measurement_csv
from backend.image.download import ManagedFileResponse
from backend.image.paths import image_work_dir
from pathlib import Path
import json
from threading import Lock
from threading import Event
from typing import Literal
from uuid import uuid4
import asyncio
import base64
import binascii


BATCH_INPUT_ROOT = image_work_dir("image-batch-inputs")
PROJECT_INPUT_ROOT = image_work_dir("image-project-inputs")
_plane_preview_gate = Lock()
_roi_collection_gate = Lock()

_roi_zip_gate = Lock()



router = APIRouter(prefix="/api/image", tags=["image"])


@router.get("/runtime")
def get_runtime() -> dict[str, object]:
    return runtime_status()


@router.get("/plugins")
def get_plugins() -> dict[str, object]:
    inventory = load_inventory()
    return {"items": inventory["items"], "counts": inventory["counts"]}


@router.get("/plugins/{plugin_id}")
def get_plugin(plugin_id: str) -> dict[str, object]:
    for item in load_inventory()["items"]:
        if item["id"] == plugin_id:
            return item
    raise HTTPException(status_code=404, detail="图像命令不在已固定的清单中。")


@router.get("/assets")
def get_assets() -> dict[str, object]:
    return {"items": store.all_public()}


@router.post("/assets", status_code=201)
async def add_asset(file: UploadFile = File(...)) -> dict[str, object]:
    try:
        return (await store.add(file)).public()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/assets/{asset_id}")
def get_asset(asset_id: str) -> dict[str, object]:
    try:
        return store.get(asset_id).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error


@router.get("/assets/{asset_id}/roi-collection/source")
def get_roi_collection_source(asset_id: str) -> dict[str, object]:
    with _roi_collection_asset(asset_id) as asset:
        try:
            return source_identity(asset)
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error


@contextmanager
def _roi_collection_asset(asset_id: str):
    # Keep the gate and lease inside the worker, even if its requester leaves.
    if not _roi_collection_gate.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="ROI 来源或集合正在核验，请稍后重试。")
    try:
        try:
            asset = store.acquire(asset_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error
        try:
            yield asset
        finally:
            store.release(asset_id)
    finally:
        _roi_collection_gate.release()


def _validate_roi_document(asset_id: str, document) -> dict[str, object]:
    with _roi_collection_asset(asset_id) as asset:
        try:
            return validate_collection(asset, document)
        except (ValueError, OSError, TypeError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/assets/{asset_id}/roi-collection/validate")
async def validate_roi_collection(asset_id: str, request: Request) -> dict[str, object]:
    chunks = bytearray()
    async for chunk in request.stream():
        if len(chunks) + len(chunk) > MAX_COLLECTION_BYTES:
            raise HTTPException(status_code=413, detail="ROI 集合超过 128 KiB。")
        chunks.extend(chunk)
    try:
        document = json.loads(chunks)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail="ROI 集合 JSON 无效。") from error
    return await run_in_threadpool(_validate_roi_document, asset_id, document)


def _native_roi_operation(asset_id: str, raw: bytes, operation: str, cancel: Event) -> dict[str, object]:
    if not _roi_zip_gate.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="原生 ROI ZIP 正在处理，请稍后重试。")
    try:
        with _roi_collection_asset(asset_id) as asset:
            if cancel.is_set():
                raise FijiCancelled()
            payload = json.loads(raw)
            if operation == "export":
                document = validate_collection(asset, payload)
                if not document["items"]:
                    raise ValueError("原生 ROI ZIP 至少需要一项。")
                result = run_roi_zip(asset, uuid4().hex, cancel, "export", {"collection": document})
                archive = bind_native_zip(base64.b64decode(result["archive_base64"], validate=True), asset)
                return {"archive_base64": base64.b64encode(archive).decode("ascii"),
                        "count": result["count"], "source_bound": True}
            if not isinstance(payload, dict) or set(payload) != {"archive_base64"} or not isinstance(payload["archive_base64"], str):
                raise ValueError("原生 ROI ZIP 请求格式无效。")
            archive = base64.b64decode(payload["archive_base64"], validate=True)
            entries, source_bound = inspect_native_zip(archive, asset)
            result = run_roi_zip(asset, uuid4().hex, cancel, "import", {
                "archive_base64": payload["archive_base64"], "roi_count": len(entries)})
            document = validate_collection(asset, {"version": "1.0", "source": source_identity(asset),
                                                  "items": result["items"]})
            return {"document": document, "measurements": result["measurements"], "source_bound": source_bound}
    except KeyError as error:
        raise HTTPException(status_code=422, detail="原生 ROI ZIP 结果缺少字段。") from error
    except (ValueError, OSError, TimeoutError, FijiUnavailable, binascii.Error) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        _roi_zip_gate.release()


async def _native_roi_request(asset_id: str, request: Request, operation: str) -> dict[str, object]:
    limit = MAX_COLLECTION_BYTES if operation == "export" else MAX_NATIVE_ZIP_BYTES * 2
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > limit:
            raise HTTPException(status_code=413, detail="原生 ROI ZIP 请求超过上限。")
        raw.extend(chunk)
    cancel = Event()
    try:
        return await run_in_threadpool(_native_roi_operation, asset_id, bytes(raw), operation, cancel)
    except asyncio.CancelledError:
        cancel.set()
        raise


@router.post("/assets/{asset_id}/roi-collection/native-export")
async def export_native_roi_zip(asset_id: str, request: Request) -> dict[str, object]:
    return await _native_roi_request(asset_id, request, "export")


@router.post("/assets/{asset_id}/roi-collection/native-import")
async def import_native_roi_zip(asset_id: str, request: Request) -> dict[str, object]:
    return await _native_roi_request(asset_id, request, "import")


@router.get("/assets/{asset_id}/plane-preview")
def get_source_plane_preview(asset_id: str, c: int | None = None, z: int | None = None,
                             t: int | None = None) -> Response:
    if not _plane_preview_gate.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="源图预览正在生成，请稍后重试。")
    try:
        try:
            asset = store.acquire(asset_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error
        try:
            indices = {key: value for key, value in (("C", c), ("Z", z), ("T", t)) if value is not None}
            data, headers = source_plane_png(asset, indices)
            return Response(content=data, media_type="image/png", headers=headers)
        except (ValueError, OSError) as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        finally:
            store.release(asset_id)
    finally:
        _plane_preview_gate.release()


@router.delete("/assets/{asset_id}", status_code=204)
def remove_asset(asset_id: str) -> None:
    try:
        store.remove(asset_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


class InspectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    asset_id: str


class GridRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    asset_ids: list[str]
    columns: int
    gap_px: int = 0


class AnnotationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    items: list[dict[str, object]]


class RectROIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: StrictInt
    y: StrictInt
    width: StrictInt
    height: StrictInt


class EllipseROIRequest(RectROIRequest):
    kind: Literal["ellipse"]


class PolygonPointRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: StrictInt
    y: StrictInt


class PolygonROIRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["polygon"]
    points: list[PolygonPointRequest]


class MeasureSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: str
    asset_id: str
    indices: dict[str, StrictInt] = Field(default_factory=dict)
    roi: PolygonROIRequest | EllipseROIRequest | RectROIRequest | None = None
    extra_measurements: list[Literal["std_dev", "median", "mode", "integrated_density"]] = Field(default_factory=list)


@router.get("/jobs")
def get_jobs(include_results: bool = True) -> dict[str, object]:
    return {"items": manager.all_public(include_results=include_results)}


@router.post("/jobs/inspect", status_code=202)
def inspect_image(request: InspectRequest) -> dict[str, object]:
    try:
        return manager.submit_inspection(store, request.asset_id).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error
    except ValueError as error:
        raise HTTPException(status_code=429, detail=str(error)) from error


@router.post("/jobs/invert-8bit", status_code=202)
def invert_8bit_image(request: InspectRequest) -> dict[str, object]:
    try:
        return manager.submit_invert(store, results, request.asset_id).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/jobs/measure-selection", status_code=202)
def create_measure_selection(request: MeasureSelectionRequest) -> dict[str, object]:
    if request.version != "1.0":
        raise HTTPException(status_code=422, detail="图像选择契约版本无效。")
    try:
        return manager.submit_measure(store, request.asset_id, request.indices,
                                      request.roi.model_dump() if request.roi else None,
                                      request.extra_measurements).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _submit_collection_measure(asset_id: str, payload: dict, cancel: Event) -> dict[str, object]:
    # The worker owns admission until source validation and dispatch finish.
    if not _roi_collection_gate.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="源图正在核验，请稍后重试。")
    try:
        return manager.submit_collection_measure(store, asset_id, payload["collection"],
            payload["extra_measurements"], cancel).public()
    finally:
        _roi_collection_gate.release()


@router.post("/assets/{asset_id}/roi-collection/measure", status_code=202)
async def create_roi_collection_measure(asset_id: str, request: Request) -> dict[str, object]:
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_COLLECTION_BYTES + 1024:
            raise HTTPException(status_code=413, detail="集合测量请求超过上限。")
        raw.extend(chunk)
    try:
        payload = json.loads(raw)
        if (not isinstance(payload, dict) or set(payload) != {"collection", "extra_measurements"}
                or not isinstance(payload["extra_measurements"], list)):
            raise ValueError("集合测量请求格式无效。")
        cancel = Event()
        try:
            return await run_in_threadpool(_submit_collection_measure, asset_id, payload, cancel)
        except asyncio.CancelledError:
            cancel.set()
            raise
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error
    except (ValueError, TypeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/assets/{asset_id}/multi-measure", status_code=202)
async def create_native_multi_measure(asset_id: str, request: Request) -> dict[str, object]:
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_COLLECTION_BYTES + 16384:
            raise HTTPException(status_code=413, detail="Multi Measure 请求超过容量上限。")
        raw.extend(chunk)
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict) or set(payload) != {
                "collection", "selected_roi_ids", "current_plane", "runs", "measurement_flags"}:
            raise ValueError("Multi Measure 请求字段无效。")
        # Source digest and scientific parameter validation run inside the
        # admitted worker, never while holding the HTTP loop or manager lock.
        return manager.submit_multi_measure(store, asset_id, payload).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error
    except (ValueError, TypeError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/measurement-settings")
def get_native_measurement_settings() -> dict[str, object]:
    from backend.image.set_measurements import MEASUREMENT_BITS
    from backend.image.non_area_measure import NATIVE_TYPE_CODES
    from backend.image.native_area_geometry import TYPE_CODES
    return {"version": "1.0", "operation": "native_set_measurements",
            "measurements": [{"id": name, "native_bit": bit} for name, bit in MEASUREMENT_BITS.items()],
            "roi_support": {"area_kinds": ["rectangle", "ellipse", "polygon"], "whole_plane_roi": None,
                            "non_area_native_types": NATIVE_TYPE_CODES, "non_area_version": "1.0",
                              "coordinate_storage": {"line": "double", "other_non_area": "float32"},
                              "native_area_version": "1.0", "native_area_types": TYPE_CODES,
                              "area_max_vertices": 64, "area_spline_points": {"min": 8, "max": 512},
                              "area_max_shape_operands": 8},
            "decimal_places": {"min": 0, "max": 9, "affects": "native_display_only"},
            "threshold": {"explicit_when": "limit_to_threshold", "applied_to": "sampled_source_or_redirect"},
            "redirect": {"identity": "asset_id", "same_xy_required": True,
                         "stack_alignment": "same_linear_index_or_single_plane"},
            "request_schema": NativeMeasureRequest.model_json_schema()}


class RoiExchangeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["2.0"]
    operation: Literal["export_zip", "export_roi", "import_zip", "import_roi"]
    collection: dict[str, object] | None = None
    file_base64: str | None = Field(default=None, max_length=2 * 1048576)


@router.post("/assets/{asset_id}/roi-exchange", status_code=202)
async def create_roi_exchange(asset_id: str, request: Request) -> dict[str, object]:
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 2 * 1048576:
            raise HTTPException(status_code=413, detail="ROI 交换请求超过 2 MiB。")
        raw.extend(chunk)
    try:
        payload = RoiExchangeRequest.model_validate_json(raw).model_dump()
        if payload["operation"].startswith("export"):
            if len(raw) > 256 * 1024 + 1024 or payload["collection"] is None or payload["file_base64"] is not None:
                raise ValueError("ROI 导出须提供至多 256 KiB 的集合，不得包含导入文件。")
        elif payload["collection"] is not None or payload["file_base64"] is None:
            raise ValueError("ROI 导入须提供原始文件编码，不得同时提供集合。")
        return manager.submit_roi_exchange(store, asset_id, payload).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像资源不存在或会话已结束。") from error
    except (ValueError, TypeError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


class NativeMeasureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal["1.0"]
    indices: dict[Literal["C", "Z", "T"], StrictInt]
    roi: dict[str, object] | None = None
    settings: dict[str, object]
    redirect_asset_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")
    redirect_plane: dict[Literal["C", "Z", "T"], StrictInt] | None = None


@router.post("/assets/{asset_id}/native-measure", status_code=202)
async def create_native_measure(asset_id: str, request: Request) -> dict[str, object]:
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 32 * 1024:
            raise HTTPException(status_code=413, detail="原生测量设置超过 32 KiB。")
        raw.extend(chunk)
    try:
        payload = NativeMeasureRequest.model_validate_json(raw)
        return manager.submit_native_measure(store, asset_id, payload.model_dump()).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="主图或重定向图像已移除。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/jobs/exact-grid", status_code=202)
def create_exact_grid(request: GridRequest) -> dict[str, object]:
    if request.version != "1.0":
        raise HTTPException(status_code=422, detail="网格请求版本无效。")
    try:
        return manager.submit_grid(store, results, request.asset_ids, request.columns, request.gap_px).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="源图像不存在或会话已结束。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.post("/jobs/batch-grid", status_code=202)
async def create_batch_grid(request: Request, files: list[UploadFile] = File(...),
                            group_size: int = Form(...), columns: int = Form(...),
                            gap_px: int = Form(0)) -> dict[str, object]:
    if (not 1 <= len(files) <= MAX_BATCH_FILES or not 1 <= group_size <= 8
            or len(files) % group_size or not 1 <= columns <= group_size
            or not 0 <= gap_px <= 1000):
        raise HTTPException(status_code=422, detail="批量输入需 1 至 64 张图像、完整分组与有效列数/间距。")
    batch_store = ImageAssetStore(BATCH_INPUT_ROOT, max_assets=64,
                                  max_session_bytes=4 * 1024 * 1024 * 1024)
    submitted = False
    try:
        ids = [(await batch_store.add(upload)).id for upload in files]
        job = manager.submit_batch(batch_store, batch_results, ids, group_size, columns, gap_px,
                                   admission_release=request.state.batch_admission_release)
        request.state.batch_admission_transferred = True
        submitted = True
        return job.public()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        for upload in files:
            await upload.close()
        if not submitted:
            batch_store.close()


@router.post("/jobs/open-project", status_code=202)
async def open_grid_project(request: Request, file: UploadFile = File(...)) -> dict[str, object]:
    return await _open_project_upload(request, file, workspace=False)


@router.post("/jobs/open-workspace", status_code=202)
async def open_workspace_project(request: Request, file: UploadFile = File(...)) -> dict[str, object]:
    return await _open_project_upload(request, file, workspace=True)


async def _open_project_upload(request: Request, file: UploadFile, *, workspace: bool) -> dict[str, object]:
    byte_limit = MAX_SESSION_BYTES + MAX_WORKSPACE_MANIFEST_BYTES if workspace else MAX_PROJECT_BYTES
    archive_store = ImageAssetStore(PROJECT_INPUT_ROOT, max_assets=1,
        max_image_bytes=byte_limit + 65536, max_session_bytes=byte_limit + 65536)
    submitted = False
    try:
        archive = await archive_store.add(file)
        job = manager.submit_project(archive_store, archive.id, store, results,
            admission_release=request.state.batch_admission_release, workspace=workspace)
        request.state.batch_admission_transferred = True
        submitted = True
        return job.public()
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        await file.close()
        if not submitted:
            archive_store.close()


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, object]:
    try:
        return manager.get(job_id).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像任务不存在或会话已结束。") from error


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, object]:
    try:
        return manager.cancel(job_id).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像任务不存在或会话已结束。") from error


@router.get("/jobs/{job_id}/measurement.{format}")
def download_measurement(job_id: str, format: Literal["json", "csv"]) -> Response:
    try:
        record = measurement_record(manager.measurement_snapshot(job_id))
    except KeyError as error:
        raise HTTPException(status_code=404, detail="测量记录不存在或已从近期任务中移除。") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    content = measurement_json(record) if format == "json" else measurement_csv(record)
    return Response(content, media_type="application/json" if format == "json" else "text/csv", headers={
        "Content-Disposition": f'attachment; filename="biofigure-measurement-{record["job_id"][:8]}.{format}"',
        "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})


@router.get("/results")
def get_results() -> dict[str, object]:
    return {"items": results.all_public()}


@router.get("/results/{result_id}")
def get_result(result_id: str) -> dict[str, object]:
    try:
        return results.get(result_id).public()
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像成品不存在或会话已结束。") from error


@router.get("/results/{result_id}/file")
def download_result(result_id: str) -> FileResponse:
    return _leased_result_response(results, result_id)


def _leased_result_response(result_store, result_id: str) -> FileResponse:
    try:
        result = result_store.acquire(result_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像成品不存在或会话已结束。") from error
    try:
        return ManagedFileResponse(result.path, media_type=result.mime_type,
            filename=result.public()["filename"], cleanup=lambda: result_store.release(result_id))
    except BaseException:
        result_store.release(result_id)
        raise


@router.get("/results/{result_id}/preview.png")
def preview_result(result_id: str) -> Response:
    try:
        content, headers = results.preview(result_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像成品不存在或会话已结束。") from error
    except (ValueError, OSError) as error:
        raise HTTPException(status_code=422, detail="此成品暂不能生成显示预览。") from error
    return Response(content, media_type="image/png", headers=headers)


@router.post("/workspace/project")
async def download_workspace_project(request: Request) -> FileResponse:
    # Native form navigation streams a potentially large archive to the browser
    # download manager, without materializing a 2 GiB JavaScript Blob.
    from urllib.parse import parse_qs
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > 4 * MAX_WORKSPACE_MANIFEST_BYTES:
            raise HTTPException(status_code=413, detail="工作台状态超过保存上限。")
        raw.extend(chunk)
    try:
        if request.headers.get("content-type", "").split(";")[0] != "application/x-www-form-urlencoded":
            raise ValueError("请使用工作台的保存入口。")
        form = parse_qs(raw.decode("utf-8"), strict_parsing=True, max_num_fields=1)
        if set(form) != {"state"} or len(form["state"]) != 1:
            raise ValueError("工作台保存状态格式无效。")
        state = json.loads(form["state"][0])
        cancel = Event()
        worker = asyncio.create_task(run_in_threadpool(prepare_workspace_export, store, state, cancel=cancel))
        try:
            exported = await asyncio.shield(worker)
        except asyncio.CancelledError:
            cancel.set()
            def cleanup_abandoned(done):
                try:
                    done.result().close()
                except BaseException:
                    pass  # The export helper has already rolled back its failure.
            worker.add_done_callback(cleanup_abandoned)
            raise
    except ProjectExportBusy as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="待保存的源图已移除。") from error
    except (ValueError, TypeError, OSError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        return ManagedFileResponse(exported.path, media_type="application/zip", cleanup=exported.close,
            filename="biofigure-workspace.bfswork", headers={"Cache-Control": "no-store"})
    except BaseException:
        exported.close()
        raise


@router.get("/results/{result_id}/project")
def download_grid_project(result_id: str) -> FileResponse:
    try:
        exported = prepare_project_export(result_id, store, results)
    except ProjectExportBusy as error:
        raise HTTPException(status_code=429, detail=str(error)) from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="成品或其原图已移除，无法保存完整项目。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    try:
        response = ManagedFileResponse(exported.path, media_type="application/zip", cleanup=exported.close,
            filename=f"biofigure-grid-{result_id[:8]}.bfsimg",
            headers={"Cache-Control": "no-store"})
        return response
    except BaseException:
        exported.close()
        raise


@router.get("/results/{result_id}/annotations-preview.svg")
def preview_annotations(result_id: str) -> Response:
    try:
        payload = results.get_annotations(result_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像成品不存在或会话已结束。") from error
    if payload["svg"] is None:
        raise HTTPException(status_code=404, detail="此成品尚无标注层。")
    return Response(payload["svg"], media_type="image/svg+xml", headers={
        "Cache-Control": "no-store", "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'",
        "X-Content-Type-Options": "nosniff"})


@router.delete("/results/{result_id}", status_code=204)
def delete_result(result_id: str) -> None:
    try:
        results.remove(result_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像成品不存在或会话已结束。") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/batch-results")
def list_batch_results() -> dict[str, object]:
    return {"items": batch_results.all_public()}


@router.get("/batch-results/{result_id}/file")
def download_batch_result(result_id: str) -> FileResponse:
    return _leased_result_response(batch_results, result_id)


@router.delete("/batch-results/{result_id}", status_code=204)
def delete_batch_result(result_id: str) -> None:
    try:
        batch_results.remove(result_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="批量成品不存在或会话已结束。") from error
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.put("/results/{result_id}/annotations")
def set_result_annotations(result_id: str, request: AnnotationRequest) -> dict[str, object]:
    if request.version != "1.0":
        raise HTTPException(status_code=422, detail="图像标注版本无效。")
    try:
        return results.set_annotations(result_id, request.items)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像成品不存在或会话已结束。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@router.get("/results/{result_id}/annotations")
def get_result_annotations(result_id: str) -> dict[str, object]:
    try:
        payload = results.get_annotations(result_id)
        return {key: value for key, value in payload.items() if key != "svg"}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像成品不存在或会话已结束。") from error


@router.get("/results/{result_id}/annotations.svg")
def download_result_annotations(result_id: str) -> Response:
    try:
        payload = results.get_annotations(result_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像成品不存在或会话已结束。") from error
    svg = payload["svg"]
    if svg is None:
        raise HTTPException(status_code=404, detail="此成品尚无标注层。")
    return Response(content=svg, media_type="image/svg+xml",
                    headers={"Content-Disposition": f'attachment; filename="biofigure-annotations-{result_id[:8]}.svg"'})


@router.get("/results/{result_id}/annotations.json")
def download_result_annotation_parameters(result_id: str) -> Response:
    try:
        payload = results.get_annotations(result_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="图像成品不存在或会话已结束。") from error
    return Response(json.dumps({key: value for key, value in payload.items() if key != "svg"}, ensure_ascii=False),
        media_type="application/json", headers={
            "Content-Disposition": f'attachment; filename="biofigure-annotations-{result_id[:8]}.json"',
            "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
