"""Local workbench discovery and draft proposal endpoints."""

from backend.core.workbench import MODEL_ADMISSION
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.core.ai_boundary import AiBoundaryError
from backend.core.biodot import assistant_profile
from backend.core.workbench_catalog import capability_catalog, integration_ready
from backend.core.workbench import (BranchWorkflowIntent, ChartIntent, LocalModelUnavailable,
                                    LOCAL_MODEL_NAME, SYNTHETIC_BRANCH_SOURCE,
                                    build_chart_draft, extract_synthetic_branch_workflow,
                                    suggest_operation)
from backend.core.external_drawing_model import ExternalDraftRequest, ExternalModelUnavailable, suggest_external_chart
from backend.core.specs import ChartSpec
from backend.image.workbench_sample import fiji_sample_available, submit_fiji_sample


router = APIRouter(prefix="/api/workbench/v1", tags=["workbench"])
_model_admission = MODEL_ADMISSION


class DraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, str_strip_whitespace=True)

    provider: Literal["demo", "local"]
    prompt: str = Field(default="", max_length=320)
    locale: Literal["en", "zh-CN"] = "en"


class DraftResponse(BaseModel):
    provider: Literal["demo", "local", "external"]
    action: Literal["chart", "fiji_sample"] = "chart"
    chart: ChartSpec | None = None


class IllustrationDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    sample_id: Literal["synthetic-branch-v1"]


class IllustrationDraftResponse(BaseModel):
    provider: Literal["local"] = "local"
    sample_id: Literal["synthetic-branch-v1"] = "synthetic-branch-v1"
    source_text: str
    fields: BranchWorkflowIntent


@router.get("/capabilities")
def workbench_capabilities() -> dict[str, object]:
    catalog = capability_catalog()
    return {**catalog, "assistant": assistant_profile(catalog), "fiji_sample_available": integration_ready(catalog, "fiji"),
        "drafts": {"method": "POST", "path": "/api/workbench/v1/drafts",
                   "dataset": "synthetic", "local_model": LOCAL_MODEL_NAME}}


@router.post("/drafts")
def create_draft(request: DraftRequest) -> DraftResponse:
    if request.provider == "demo":
        return DraftResponse(provider="demo", chart=build_chart_draft(ChartIntent(
            chart_type="scatter", title="合成细胞响应" if request.locale == "zh-CN" else "Synthetic cell response", theme_id="scientific_clear"
        )))
    if not request.prompt:
        raise HTTPException(status_code=422, detail="请输入一条针对合成样例的绘图指令。")
    if not _model_admission.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="本机模型正在生成草案，请稍后重试。")
    try:
        fiji_available = fiji_sample_available()
        proposal = suggest_operation(request.prompt)
        if proposal.chart is not None:
            return DraftResponse(provider="local", chart=build_chart_draft(proposal.chart))
        if not fiji_available:
            raise HTTPException(status_code=503, detail="本机尚未配置已固定的 Fiji 运行时。")
        return DraftResponse(provider="local", action="fiji_sample")
    except LocalModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except TimeoutError as error:
        raise HTTPException(status_code=504, detail="本机模型响应超时，请稍后重试或打开合成示例。") from error
    except (AiBoundaryError, ValidationError) as error:
        raise HTTPException(status_code=422, detail="本机模型返回的草案不符合已开放的操作参数，请简化指令。") from error
    finally:
        _model_admission.release()


@router.post("/illustration-draft")
def create_illustration_draft(request: IllustrationDraftRequest) -> IllustrationDraftResponse:
    del request
    if not _model_admission.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="本机模型正在生成草案，请稍后重试。")
    try:
        fields = extract_synthetic_branch_workflow()
        return IllustrationDraftResponse(source_text=SYNTHETIC_BRANCH_SOURCE, fields=fields)
    except LocalModelUnavailable as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except TimeoutError as error:
        raise HTTPException(status_code=504, detail="本机模型响应超时；可手动填写合成示例。") from error
    except (AiBoundaryError, ValidationError) as error:
        raise HTTPException(status_code=422, detail="本机模型未逐字提取合成流程；可手动填写合成示例。") from error
    finally:
        _model_admission.release()


def _create_external_draft(request: ExternalDraftRequest) -> DraftResponse:
    if not _model_admission.acquire(blocking=False):
        raise HTTPException(status_code=429, detail="绘图助手正在生成草案，请稍后重试。")
    try:
        return DraftResponse(provider="external", chart=build_chart_draft(suggest_external_chart(request)))
    except TimeoutError as error:
        raise HTTPException(status_code=504, detail="外部模型响应超时。") from error
    except ExternalModelUnavailable as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    except AiBoundaryError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    except ValidationError as error:
        raise HTTPException(status_code=422, detail="外部模型草案不符合已开放的绘图参数。") from error
    finally:
        _model_admission.release()


@router.post("/external-drafts")
async def create_external_draft(request: Request) -> DraftResponse:
    if not getattr(request.state, "workbench_origin", None):
        raise HTTPException(status_code=403, detail="请从 BioFigure Studio 的本机启动入口使用外部模型。")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > 4096:
            raise HTTPException(status_code=413, detail="模型配置超过长度限制。")
        body.extend(chunk)
    try:
        # Never include credentials from invalid submissions in response bodies.
        config = ExternalDraftRequest.model_validate_json(body)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail="请核对服务地址、模型、API Key 和本次发送确认。") from error
    return await run_in_threadpool(_create_external_draft, config)


@router.post("/fiji-sample", status_code=202)
async def inspect_fiji_sample() -> dict[str, object]:
    if not fiji_sample_available():
        raise HTTPException(status_code=503, detail="本机尚未配置已固定的 Fiji 运行时。")
    try:
        job = await submit_fiji_sample()
    except (OSError, ValueError) as error:
        raise HTTPException(status_code=429, detail="本地图像队列暂不可用，请稍后重试。") from error
    return {"job_id": job.id, "state": job.state}
