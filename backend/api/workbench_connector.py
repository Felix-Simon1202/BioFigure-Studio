"""Scoped loopback API for an explicitly paired external workbench client."""

from contextlib import asynccontextmanager
from threading import Lock
from typing import Callable, Literal

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import ValidationError

from backend.core.ai_boundary import AiBoundaryError, parse_draft_object
from backend.core.specs import ChartSpec, FigureImagePanel, FigureSpec
from backend.core.workbench import ChartIntent, build_chart_draft
from backend.core.workbench_catalog import (JOB_ID_PATTERN, RChartIntent,
                                            SampleProjectIntent, capability_catalog, integration_ready)
from backend.core.workbench_connector import CONNECTOR_PREFIX, TOKEN_SECONDS, LocalConnector
from backend.image.assets import ImageAssetStore
from backend.image.jobs import ImageJob, manager as image_jobs
from backend.image.workbench_sample import fiji_sample_available, publication_sample, submit_fiji_sample


MAX_CONNECTOR_REQUEST = 8192
FIJI_ROUTE = CONNECTOR_PREFIX + "/fiji"
R_ROUTE = CONNECTOR_PREFIX + "/r-chart"
_sample_admission = Lock()


def _public_fiji_job(job: ImageJob) -> dict[str, object]:
    view = job.public()
    result = view["result"] if view["state"] == "succeeded" else None
    return {
        "job_id": job.id,
        "state": view["state"],
        "metadata": {key: result.get(key) for key in ("axes", "pixel_type", "bit_depth", "channels")} if result else None,
        "error": "本机 Fiji 检查未完成，请检查工作台的固定运行时。" if view["state"] == "failed" else None,
    }


def _connection(request: Request) -> LocalConnector:
    connection = getattr(request.state, "workbench_connector", None)
    if not isinstance(connection, LocalConnector):
        raise HTTPException(status_code=403, detail="连接仅在本机桌面试用会话中可用。")
    return connection


def _require_token(request: Request) -> tuple[LocalConnector, bytes]:
    connection = _connection(request)
    digest = connection.authenticate(request.headers.get("authorization", ""))
    if digest is None:
        raise HTTPException(status_code=401, detail="连接码无效、已过期或已撤销。",
                            headers={"WWW-Authenticate": "Bearer"})
    return connection, digest


@asynccontextmanager
async def _sample_figure(chart: ChartSpec):
    if not _sample_admission.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="本机正在生成合成图版或项目。")
    try:
        store, asset = await publication_sample()
        try:
            figure = FigureSpec(
                spec_version="2.1", panels=[chart], width_mm=180, height_mm=120,
                template_id="double_column", dpi=300, svg_text_mode="editable",
                image_panel=FigureImagePanel(asset_id=asset.id, x_um_per_pixel=0.5, scale_bar_um=40),
            )
            yield figure, store
        finally:
            store.close()
    finally:
        _sample_admission.release()


async def _read_parameters(request: Request) -> dict[str, object]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="连接请求必须使用 JSON。")
    body = bytearray()
    async for chunk in request.stream():
        if len(chunk) > MAX_CONNECTOR_REQUEST - len(body):
            raise HTTPException(status_code=413, detail="连接请求超过 8 KiB。")
        body.extend(chunk)
    try:
        return parse_draft_object(body.decode("utf-8"))
    except (AiBoundaryError, UnicodeError) as error:
        raise HTTPException(status_code=422, detail="连接请求不是受支持的参数对象。") from error


async def _read_chart(request: Request) -> ChartSpec:
    try:
        return build_chart_draft(ChartIntent.model_validate(await _read_parameters(request)))
    except (AiBoundaryError, ValidationError) as error:
        raise HTTPException(status_code=422, detail="连接只接受合成图的图种、标题和主题。") from error


def connector_router(render_chart: Callable[[ChartSpec], dict[str, object]],
                     export_chart: Callable[[str, str], Response],
                     render_figure: Callable[[FigureSpec, ImageAssetStore], dict[str, object]],
                     export_figure: Callable[[str, str], Response],
                     export_project: Callable[[ChartSpec, FigureSpec | None, ImageAssetStore | None], Response]) -> APIRouter:
    router = APIRouter(tags=["workbench-connector"])

    @router.post("/api/workbench/v1/connection")
    def pair(request: Request) -> dict[str, object]:
        token = _connection(request).pair()
        return {
            "url": request.state.workbench_origin + CONNECTOR_PREFIX,
            "token": token,
            "expires_in": TOKEN_SECONDS,
        }

    @router.delete("/api/workbench/v1/connection", status_code=204)
    def revoke(request: Request) -> Response:
        _connection(request).revoke()
        return Response(status_code=204)

    @router.get(CONNECTOR_PREFIX)
    def discover(request: Request) -> dict[str, object]:
        _require_token(request)
        catalog = capability_catalog()
        return {"version": catalog["version"], "scope": catalog["scope"],
                "actions": [{key: value for key, value in tool.items() if key not in ("ready", "integration")}
                            for tool in catalog["tools"] if tool["ready"]]}

    @router.post("/api/workbench/v1/r-sample")
    async def local_r_sample(intent: RChartIntent) -> Response:
        if not integration_ready(capability_catalog(), "r"):
            raise HTTPException(status_code=503, detail="本机已审核的 R 和 ggplot2 尚不可用。")
        result = await run_in_threadpool(render_chart, _r_chart(intent))
        response = await run_in_threadpool(export_chart, str(result["render_id"]), "pdf")
        response.headers["Content-Disposition"] = 'attachment; filename="biofigure-r-sample.pdf"'
        return response

    async def _vector_sample() -> Response:
        chart = build_chart_draft(ChartIntent(chart_type="scatter", theme_id="scientific_clear",
                                               title="Synthetic cell response"))
        chart = chart.model_copy(update={"svg_text_mode": "editable"})
        result = await run_in_threadpool(render_chart, chart)
        response = await run_in_threadpool(export_chart, str(result["render_id"]), "svg")
        response.headers["Content-Disposition"] = 'attachment; filename="biofigure-editable-sample.svg"'
        return response

    def _r_chart(intent: RChartIntent) -> ChartSpec:
        chart = build_chart_draft(ChartIntent(chart_type="scatter", theme_id="scientific_clear", title=intent.title))
        return chart.model_copy(update={"chart_type": "r_ggplot"})

    @router.post("/api/workbench/v1/vector-sample")
    async def local_vector_sample() -> Response:
        return await _vector_sample()

    @router.post(CONNECTOR_PREFIX + "/vector")
    async def paired_vector_sample(request: Request) -> Response:
        connection, digest = _require_token(request)
        if await _read_parameters(request):
            raise HTTPException(status_code=422, detail="SVG 合成样例不接受外部参数。")
        response = await _vector_sample()
        if connection.authenticate(request.headers.get("authorization", "")) != digest:
            raise HTTPException(status_code=401, detail="生成期间连接已失效。")
        return response


    @router.post(CONNECTOR_PREFIX + "/render", status_code=201)
    async def render(request: Request) -> dict[str, object]:
        connection, digest = _require_token(request)
        chart = await _read_chart(request)
        if connection.authenticate(request.headers.get("authorization", "")) != digest:
            raise HTTPException(status_code=401, detail="连接已失效。")
        result = await run_in_threadpool(render_chart, chart)
        if not connection.record(digest, str(result["render_id"])):
            raise HTTPException(status_code=401, detail="生成期间连接已失效。")
        return {**result, "chart": chart.model_dump(mode="json")}

    @router.post(R_ROUTE, status_code=201)
    async def render_r_sample(request: Request) -> dict[str, object]:
        connection, digest = _require_token(request)
        if not integration_ready(capability_catalog(), "r"):
            raise HTTPException(status_code=503, detail="本机已审核的 R 和 ggplot2 尚不可用。")
        try:
            intent = RChartIntent.model_validate(await _read_parameters(request))
        except ValidationError as error:
            raise HTTPException(status_code=422, detail="R 合成散点图只接受标题。") from error
        if connection.authenticate(request.headers.get("authorization", "")) != digest:
            raise HTTPException(status_code=401, detail="连接已失效。")
        chart = _r_chart(intent)
        result = await run_in_threadpool(render_chart, chart)
        if not connection.record(digest, str(result["render_id"])):
            raise HTTPException(status_code=401, detail="生成期间连接已失效。")
        return {**result, "engine": "r_ggplot", "chart": chart.model_dump(mode="json")}

    @router.post(CONNECTOR_PREFIX + "/figure", status_code=201)
    async def render_sample_figure(request: Request) -> dict[str, object]:
        connection, digest = _require_token(request)
        chart = await _read_chart(request)
        if connection.authenticate(request.headers.get("authorization", "")) != digest:
            raise HTTPException(status_code=401, detail="连接已失效。")
        async with _sample_figure(chart) as (spec, store):
            result = await run_in_threadpool(render_figure, spec, store)
        if not connection.record(digest, str(result["render_id"]), "figure"):
            raise HTTPException(status_code=401, detail="生成期间连接已失效。")
        return result

    @router.post(CONNECTOR_PREFIX + "/project")
    async def create_sample_project(request: Request) -> Response:
        connection, digest = _require_token(request)
        try:
            intent = SampleProjectIntent.model_validate(await _read_parameters(request))
            chart_intent = ChartIntent.model_validate(intent.model_dump(exclude={"include_image"}))
            chart = build_chart_draft(chart_intent)
        except (AiBoundaryError, ValidationError) as error:
            raise HTTPException(status_code=422, detail="合成项目只接受图种、标题、主题和是否加入合成图像。") from error
        if connection.authenticate(request.headers.get("authorization", "")) != digest:
            raise HTTPException(status_code=401, detail="连接已失效。")
        if intent.include_image:
            async with _sample_figure(chart) as (spec, store):
                response = await run_in_threadpool(export_project, chart, spec, store)
        else:
            response = await run_in_threadpool(export_project, chart, None, None)
        if connection.authenticate(request.headers.get("authorization", "")) != digest:
            raise HTTPException(status_code=401, detail="生成期间连接已失效。")
        return response

    @router.get(CONNECTOR_PREFIX + "/artifact")
    def artifact(request: Request, render_id: str = Query(pattern=JOB_ID_PATTERN),
                 format: Literal["pdf", "png", "svg", "tiff"] = "pdf") -> Response:
        connection, digest = _require_token(request)
        if connection.owns(digest, render_id):
            return export_chart(render_id, format)
        if connection.owns(digest, render_id, "figure"):
            return export_figure(render_id, format)
        raise HTTPException(status_code=404, detail="此连接没有该成品。")

    @router.post(FIJI_ROUTE, status_code=202)
    async def inspect_sample(request: Request) -> dict[str, object]:
        connection, digest = _require_token(request)
        if not fiji_sample_available():
            raise HTTPException(status_code=503, detail="未找到已固定的 Fiji 运行时。")
        try:
            job = await submit_fiji_sample()
        except (OSError, ValueError) as error:
            raise HTTPException(status_code=429, detail="本地图像队列暂不可用，请稍后重试。") from error
        if not connection.record(digest, job.id, "fiji"):
            image_jobs.cancel(job.id)
            raise HTTPException(status_code=401, detail="提交期间连接已失效。")
        return _public_fiji_job(job)

    @router.get(FIJI_ROUTE)
    @router.delete(FIJI_ROUTE)
    def sample_job(request: Request, job_id: str = Query(pattern=JOB_ID_PATTERN)) -> dict[str, object]:
        connection, digest = _require_token(request)
        if not connection.owns(digest, job_id, "fiji"):
            raise HTTPException(status_code=404, detail="此连接没有该 Fiji 任务。")
        try:
            job = image_jobs.cancel(job_id) if request.method == "DELETE" else image_jobs.get(job_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail="Fiji 任务已过期。") from error
        return _public_fiji_job(job)

    return router
