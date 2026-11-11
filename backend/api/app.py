"""Local-only API for table and existing single-cell visualization."""

from hashlib import sha256
from functools import wraps
from io import BytesIO
from importlib.metadata import version as package_version
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Lock
from typing import Callable, TypeVar
from urllib.parse import quote
from uuid import uuid4
from zipfile import ZIP_DEFLATED, BadZipFile, ZipFile

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel

from backend.adapters.matplotlib_charts import FONT_FILENAME, FONT_SHA256, render_chart, render_figure, resolve_figure
from backend.adapters.single_cell import render_single_cell
from backend.adapters.omics import render_omics
from backend.api.workbench import router as workbench_router
from backend.api.workbench_connector import connector_router
from backend.core.specs import ChartSpec, SavedChartConfig, FigureSpec, SavedFigureConfig, ProjectDocument
from backend.data.simulated import (
    SIMULATED_CSV, SIMULATED_DATASET_ID, SIMULATED_ECOLOGY_CSV, SIMULATED_ECOLOGY_DATASET_ID,
    SIMULATED_ECOLOGY_ALPHA_DATASET_ID, SIMULATED_ECOLOGY_BETA_DATASET_ID, SIMULATED_ECOLOGY_ORDINATION_DATASET_ID, SIMULATED_ECOLOGY_ENVIRONMENT_DATASET_ID, SIMULATED_ECOLOGY_TIME_DATASET_ID, SIMULATED_ECOLOGY_SPATIAL_DATASET_ID, SIMULATED_ECOLOGY_ALPHA_CSV, SIMULATED_ECOLOGY_BETA_CSV, SIMULATED_ECOLOGY_ORDINATION_CSV, SIMULATED_ECOLOGY_ENVIRONMENT_CSV, SIMULATED_ECOLOGY_TIME_CSV, SIMULATED_ECOLOGY_SPATIAL_CSV,
    ecology_alpha_preview_payload, ecology_beta_preview_payload, ecology_ordination_preview_payload, ecology_environment_preview_payload, ecology_preview_payload, preview_payload,
    simulated_dataframe, simulated_ecology_alpha_dataframe, simulated_ecology_beta_dataframe, simulated_ecology_ordination_dataframe, simulated_ecology_environment_dataframe, simulated_ecology_time_dataframe, simulated_ecology_spatial_dataframe, simulated_ecology_dataframe, ecology_time_preview_payload, ecology_spatial_preview_payload,
)
from backend.data.simulated_single_cell import simulated_single_cell_record
from backend.data.store import (
    MAX_H5AD_BYTES, MAX_OMICS_BYTES, MAX_PROJECT_BYTES, MAX_TABLE_BYTES, DatasetRecord, dataset_summary,
    get_record, parse_dataset, search_genes, store_record,
)
from backend.registry.charts import get_chart_adapter, register_chart
from backend.image.api import router as image_router
from backend.image.assets import ImageAsset, ImageAssetStore, store as image_store
from backend.image.publication import MAX_FIGURE_IMAGE_BYTES, prepare_publication_image
from backend.image.admission import BatchUploadAdmissionMiddleware


APP_VERSION = "0.1.0"
RENDER_FORMATS = {"svg": "image/svg+xml", "pdf": "application/pdf", "png": "image/png"}
FIGURE_FORMATS = {**RENDER_FORMATS, "tiff": "image/tiff"}
MAX_ARTIFACT_CACHE_BYTES = 128 * 1024 * 1024
MAX_SAVED_CONFIGS = 64
_renders: dict[str, dict[str, bytes]] = {}
_configs: dict[str, SavedChartConfig] = {}
_render_lock = Lock()
_artifact_lock = Lock()
T = TypeVar("T")


def _serialized_render(operation: Callable[..., T]) -> Callable[..., T]:
    """Matplotlib uses shared process state; reject overlapping heavy jobs."""
    @wraps(operation)
    def guarded(*args, **kwargs):
        if not _render_lock.acquire(blocking=False):
            raise HTTPException(status_code=429, detail="本机正在生成图表，请稍后重试。")
        try:
            return operation(*args, **kwargs)
        finally:
            _render_lock.release()
    return guarded


def _retain_artifacts(cache: dict[str, dict[str, bytes]], identifier: str, outputs: dict[str, bytes]) -> None:
    size = sum(len(value) for value in outputs.values())
    if size > MAX_ARTIFACT_CACHE_BYTES:
        raise HTTPException(status_code=422, detail="生成结果超过本机会话内存上限（128 MB）；请降低 DPI 或画布尺寸。")
    with _artifact_lock:
        while cache and (len(cache) >= 8 or sum(len(value) for entry in cache.values() for value in entry.values()) + size > MAX_ARTIFACT_CACHE_BYTES):
            del cache[next(iter(cache))]
        cache[identifier] = outputs


def _retain_config(cache: dict[str, T], name: str, config: T) -> None:
    with _artifact_lock:
        if name not in cache and len(cache) >= MAX_SAVED_CONFIGS:
            del cache[next(iter(cache))]
        cache[name] = config
for _chart_type in ("scatter", "bar", "line", "box", "heatmap"):
    register_chart(_chart_type, render_chart)
for _chart_type in ("embedding_categorical", "embedding_continuous", "feature", "violin", "dotplot"):
    register_chart(_chart_type, render_single_cell)
for _chart_type in ("spatial_categorical", "spatial_continuous", "spatial_feature", "genome_tracks", "circos", "dna_features", "r_ggplot"):
    register_chart(_chart_type, render_omics)
register_chart("ecology_composition", render_chart)
register_chart("ecology_alpha_diversity", render_chart)
register_chart("ecology_beta_ordination", render_chart)
register_chart("ecology_ordination_biplot", render_chart)
register_chart("ecology_environment_gradient", render_chart)
register_chart("ecology_time_series", render_chart)
register_chart("ecology_spatial_points", render_chart)


class HealthResponse(BaseModel):
    """Deliberately small health response that reveals no local paths or data."""

    status: str
    version: str
    mode: str


app = FastAPI(
    title="BioFigure Studio API",
    version=APP_VERSION,
    description="Local-only API for reproducible scientific figures.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
app.add_middleware(BatchUploadAdmissionMiddleware)
app.include_router(image_router)
app.include_router(workbench_router)


@app.get("/api/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    """Report that the local API is ready without exposing host details."""
    return HealthResponse(status="ok", version=APP_VERSION, mode="local")


@app.get("/api/datasets/simulated.csv", tags=["datasets"])
def get_simulated_csv() -> Response:
    """Serve the built-in simulated CSV; no user data is accepted or stored."""
    return Response(SIMULATED_CSV, media_type="text/csv", headers={"Content-Disposition": "attachment; filename=simulated-cell-response.csv"})


@app.get("/api/datasets/simulated/preview", tags=["datasets"])
def get_simulated_preview() -> dict[str, object]:
    """Return a bounded preview of the built-in simulated dataset."""
    return preview_payload()


@app.get("/api/datasets/simulated-ecology/preview", tags=["datasets"])
def get_simulated_ecology_preview() -> dict[str, object]:
    """Return a deterministic anonymous ecology composition sample."""
    return ecology_preview_payload()


@app.get("/api/datasets/simulated-ecology-alpha/preview", tags=["datasets"])
def get_simulated_ecology_alpha_preview() -> dict[str, object]:
    return ecology_alpha_preview_payload()


@app.get("/api/datasets/simulated-ecology-beta/preview", tags=["datasets"])
def get_simulated_ecology_beta_preview() -> dict[str, object]:
    return ecology_beta_preview_payload()

@app.get("/api/datasets/simulated-ecology-ordination/preview", tags=["datasets"])
def get_simulated_ecology_ordination_preview() -> dict[str, object]:
    return ecology_ordination_preview_payload()


@app.get("/api/datasets/simulated-ecology-environment/preview", tags=["datasets"])
def get_simulated_ecology_environment_preview() -> dict[str, object]:
    return ecology_environment_preview_payload()

@app.get("/api/datasets/simulated-ecology-time/preview", tags=["datasets"])
def get_simulated_ecology_time_preview() -> dict[str, object]:
    return ecology_time_preview_payload()


@app.get("/api/datasets/simulated-ecology-spatial/preview", tags=["datasets"])
def get_simulated_ecology_spatial_preview() -> dict[str, object]:
    return ecology_spatial_preview_payload()


@app.get("/api/datasets/simulated-single-cell/preview", tags=["datasets"])
def get_simulated_single_cell_preview() -> dict[str, object]:
    """Load a deterministic anonymous H5AD fixture into this local session."""
    record = simulated_single_cell_record()
    dataset_id = store_record(record)
    return dataset_summary(dataset_id, record, "built-in synthetic anonymous H5AD")


@app.post("/api/datasets", status_code=201, tags=["datasets"])
async def upload_dataset(file: UploadFile = File(...)) -> dict[str, object]:
    """Accept one bounded CSV/XLSX/H5AD file into local process memory only."""
    filename = file.filename or ""
    try:
        lower_name = filename.lower()
        limit = MAX_H5AD_BYTES if lower_name.endswith(".h5ad") else MAX_OMICS_BYTES if lower_name.endswith((".gb", ".gbk", ".genbank", ".bed", ".bedgraph", ".gff", ".gff3", ".gtf", ".chrom.sizes", ".json")) else MAX_TABLE_BYTES
        record = parse_dataset(filename, await file.read(limit + 1))
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    finally:
        await file.close()
    if record.dataframe is not None and record.dataframe.empty:
        raise HTTPException(status_code=422, detail="文件没有可用数据行。")
    if record.dataframe is not None and len(record.dataframe.columns) < 2:
        raise HTTPException(status_code=422, detail="至少需要两列数据。")
    try:
        dataset_id = store_record(record)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    return dataset_summary(dataset_id, record, "local upload")


class RenderRequest(BaseModel):
    chart: ChartSpec


@app.get("/api/datasets/{dataset_id}/preview", tags=["datasets"])
def dataset_preview(dataset_id: str) -> dict[str, object]:
    try:
        value = simulated_dataframe() if dataset_id == SIMULATED_DATASET_ID else simulated_ecology_dataframe() if dataset_id == SIMULATED_ECOLOGY_DATASET_ID else simulated_ecology_alpha_dataframe() if dataset_id == SIMULATED_ECOLOGY_ALPHA_DATASET_ID else simulated_ecology_beta_dataframe() if dataset_id == SIMULATED_ECOLOGY_BETA_DATASET_ID else simulated_ecology_ordination_dataframe() if dataset_id == SIMULATED_ECOLOGY_ORDINATION_DATASET_ID else simulated_ecology_environment_dataframe() if dataset_id == SIMULATED_ECOLOGY_ENVIRONMENT_DATASET_ID else simulated_ecology_time_dataframe() if dataset_id == SIMULATED_ECOLOGY_TIME_DATASET_ID else simulated_ecology_spatial_dataframe() if dataset_id == SIMULATED_ECOLOGY_SPATIAL_DATASET_ID else get_record(dataset_id)
        return dataset_summary(dataset_id, value, "local session")
    except KeyError as error:
        raise HTTPException(status_code=404, detail="数据集不存在或会话已结束，请重新提交数据。") from error


@app.get("/api/datasets/{dataset_id}/genes", tags=["datasets"])
def dataset_genes(dataset_id: str, q: str = Query(default="", max_length=128)) -> dict[str, object]:
    try:
        return {"genes": search_genes(dataset_id, q)}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="数据集不存在或会话已结束，请重新提交数据。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/renders", status_code=201, tags=["renders"])
@_serialized_render
def create_render(request: RenderRequest) -> dict[str, object]:
    """Return success only after all three local artifacts have rendered."""
    try:
        adapter = get_chart_adapter(request.chart.chart_type)
        spec = request.chart
        value = _resolve_chart_data(spec)
        outputs = {fmt: adapter(spec, value, fmt) for fmt in RENDER_FORMATS}
    except KeyError as error:
        raise HTTPException(status_code=404, detail="数据集不存在或会话已结束，请重新提交数据。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    render_id = uuid4().hex
    _retain_artifacts(_renders, render_id, outputs)
    return {"render_id": render_id, "formats": sorted(RENDER_FORMATS), "spec_version": request.chart.spec_version}


@app.get("/api/renders/{render_id}.{export_format}", tags=["renders"])
def export_render(render_id: str, export_format: str) -> Response:
    """Export one in-memory render as a browser-downloadable artifact."""
    outputs = _renders.get(render_id)
    if outputs is None:
        raise HTTPException(status_code=404, detail="图示不存在或已清除，请重新生成。")
    media_type = RENDER_FORMATS.get(export_format)
    if media_type is None:
        raise HTTPException(status_code=404, detail="unsupported export format")
    output = outputs[export_format]
    return Response(output, media_type=media_type, headers={"Content-Disposition": f"attachment; filename=biofigure-{render_id}.{export_format}"})


@app.post("/api/configs", status_code=201, tags=["configs"])
def save_config(config: SavedChartConfig) -> SavedChartConfig:
    """Save a validated configuration for the current local process only."""
    _retain_config(_configs, config.name, config)
    return config


@app.get("/api/configs/{name}", tags=["configs"])
def load_config(name: str) -> SavedChartConfig:
    """Load a named configuration without exposing arbitrary local paths."""
    config = _configs.get(name)
    if config is None:
        raise HTTPException(status_code=404, detail="本次会话尚未保存该单图配置，或服务重启后已清除。")
    return config


_figures: dict[str, dict[str, bytes]] = {}
_figure_configs: dict[str, SavedFigureConfig] = {}


@app.post("/api/figures", status_code=201)
def create_figure(spec: FigureSpec) -> dict[str, object]:
    return _create_figure(spec, image_store)


@_serialized_render
def _create_figure(spec: FigureSpec, asset_store: ImageAssetStore) -> dict[str, object]:
    try:
        frames = [_resolve_chart_data(panel) for panel in spec.panels]
        spec = resolve_figure(spec, frames)
        publication_image = None
        if spec.image_panel:
            asset_id = spec.image_panel.asset_id
            try:
                asset = asset_store.acquire(asset_id)
            except KeyError as error:
                raise HTTPException(status_code=404, detail="图版图像不存在或会话已结束，请重新导入。") from error
            try:
                publication_image = prepare_publication_image(asset, spec.image_panel, spec)
            finally:
                asset_store.release(asset_id)
        outputs = {}
        for fmt in FIGURE_FORMATS:
            try:
                outputs[fmt] = render_figure(spec, frames, fmt, publication_image)
            except ValueError as error:
                raise ValueError(f"{fmt.upper()} 导出失败：{error}") from error
    except KeyError as error:
        raise HTTPException(status_code=404, detail="数据集不存在或会话已结束。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    identifier = uuid4().hex
    _retain_artifacts(_figures, identifier, outputs)
    result = {"render_id": identifier, "formats": sorted(FIGURE_FORMATS), "spec_version": spec.spec_version}
    if publication_image is not None:
        result["image_check"] = publication_image.check(spec)
    return result


@app.get("/api/figures/{identifier}.{export_format}")
def export_figure(identifier: str, export_format: str) -> Response:
    output = _figures.get(identifier, {}).get(export_format)
    if output is None:
        raise HTTPException(status_code=404, detail="拼版不存在或已清除，请重新生成。")
    media_type = FIGURE_FORMATS.get(export_format)
    if media_type is None:
        raise HTTPException(status_code=404, detail="unsupported export format")
    return Response(output, media_type=media_type, headers={"Content-Disposition": f"attachment; filename=biofigure-{identifier}.{export_format}"})


@app.post("/api/figure-configs", status_code=201)
def save_figure_config(config: SavedFigureConfig) -> SavedFigureConfig:
    try:
        frames = [_resolve_chart_data(panel) for panel in config.figure.panels]
        config = config.model_copy(update={"figure": resolve_figure(config.figure, frames)})
    except (KeyError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    _retain_config(_figure_configs, config.name, config)
    return config


@app.get("/api/figure-configs/{name}")
def load_figure_config(name: str) -> SavedFigureConfig:
    if name not in _figure_configs:
        raise HTTPException(status_code=404, detail="本次会话尚未保存该拼版。")
    return _figure_configs[name]


class ProjectSaveRequest(BaseModel):
    name: str
    chart: ChartSpec
    figure: FigureSpec | None = None


@app.post("/api/projects", tags=["projects"])
def export_project(request: ProjectSaveRequest) -> Response:
    """Create a self-contained local project archive with source data and provenance."""
    return _export_project(request, image_store)


def _export_project(request: ProjectSaveRequest, asset_store: ImageAssetStore) -> Response:
    try:
        if request.chart.dataset_id == SIMULATED_DATASET_ID:
            record = _simulated_table_record()
        elif request.chart.dataset_id == SIMULATED_ECOLOGY_DATASET_ID:
            payload = SIMULATED_ECOLOGY_CSV.encode("utf-8")
            record = DatasetRecord("table", "simulated-ecology-composition.csv", payload, sha256(payload).hexdigest(), dataframe=simulated_ecology_dataframe())
        elif request.chart.dataset_id == SIMULATED_ECOLOGY_ALPHA_DATASET_ID:
            payload = SIMULATED_ECOLOGY_ALPHA_CSV.encode("utf-8")
            record = DatasetRecord("table", "simulated-ecology-alpha.csv", payload, sha256(payload).hexdigest(), dataframe=simulated_ecology_alpha_dataframe())
        elif request.chart.dataset_id == SIMULATED_ECOLOGY_BETA_DATASET_ID:
            payload = SIMULATED_ECOLOGY_BETA_CSV.encode("utf-8")
            record = DatasetRecord("table", "simulated-ecology-beta.csv", payload, sha256(payload).hexdigest(), dataframe=simulated_ecology_beta_dataframe())
        elif request.chart.dataset_id == SIMULATED_ECOLOGY_ORDINATION_DATASET_ID:
            payload = SIMULATED_ECOLOGY_ORDINATION_CSV.encode("utf-8")
            record = DatasetRecord("table", "simulated-ecology-ordination.csv", payload, sha256(payload).hexdigest(), dataframe=simulated_ecology_ordination_dataframe())
        elif request.chart.dataset_id == SIMULATED_ECOLOGY_ENVIRONMENT_DATASET_ID:
            payload = SIMULATED_ECOLOGY_ENVIRONMENT_CSV.encode("utf-8")
            record = DatasetRecord("table", "simulated-ecology-environment.csv", payload, sha256(payload).hexdigest(), dataframe=simulated_ecology_environment_dataframe())
        elif request.chart.dataset_id == SIMULATED_ECOLOGY_TIME_DATASET_ID:
            payload = SIMULATED_ECOLOGY_TIME_CSV.encode("utf-8")
            record = DatasetRecord("table", "simulated-ecology-time.csv", payload, sha256(payload).hexdigest(), dataframe=simulated_ecology_time_dataframe())
        elif request.chart.dataset_id == SIMULATED_ECOLOGY_SPATIAL_DATASET_ID:
            payload = SIMULATED_ECOLOGY_SPATIAL_CSV.encode("utf-8")
            record = DatasetRecord("table", "simulated-ecology-spatial.csv", payload, sha256(payload).hexdigest(), dataframe=simulated_ecology_spatial_dataframe())
        else:
            record = get_record(request.chart.dataset_id)
        figure = request.figure
        if figure and any(panel.dataset_id != request.chart.dataset_id for panel in figure.panels):
            raise ValueError("项目包当前只保存同一数据集生成的单图与拼图。")
        if figure:
            figure = resolve_figure(figure, [_resolve_chart_data(panel) for panel in figure.panels])
        image_name = image_digest = None
        image_payload = None
        if figure and figure.image_panel:
            asset_id = figure.image_panel.asset_id
            try:
                asset = asset_store.acquire(asset_id)
            except KeyError as error:
                raise HTTPException(status_code=404, detail="图版图像不存在或会话已结束，请重新导入。") from error
            try:
                prepare_publication_image(asset, figure.image_panel, figure)
                if len(record.payload) + asset.bytes > MAX_PROJECT_BYTES - 1024 * 1024:
                    raise ValueError("混合图版的源文件超过项目容量。")
                with asset.path.open("rb") as image_file:
                    image_payload = image_file.read(asset.bytes + 1)
                if len(image_payload) != asset.bytes or sha256(image_payload).hexdigest() != asset.sha256:
                    raise ValueError("图版源图与导入摘要不符。")
                image_name, image_digest = asset.name, asset.sha256
            finally:
                asset_store.release(asset_id)
        document = ProjectDocument(
            project_version="1.2" if image_payload is not None else "1.1",
            image_filename=image_name,
            image_sha256=image_digest,
            name=request.name,
            chart=request.chart,
            figure=figure,
            data_filename=record.filename,
            data_sha256=record.digest,
            data_kind=record.kind,
            transformations=([] if request.chart.transform == "none" else [request.chart.transform]) + (["ecology_count_to_fraction"] if request.chart.chart_type == "ecology_composition" and request.chart.ecology_value_mode == "count" else []),
            plugin_versions={
                "biofigure-studio": APP_VERSION,
                "chart-spec": request.chart.spec_version,
                "figure-spec": figure.spec_version if figure else "not-used",
                "matplotlib": package_version("matplotlib"),
                "pandas": package_version("pandas"),
                "numpy": package_version("numpy"),
                "anndata": package_version("anndata"),
                "adapter": "matplotlib-reviewed-v1",
            },
            font_provenance={
                "family": "Noto Sans SC",
                "file": f"assets/fonts/{FONT_FILENAME}",
                "sha256": FONT_SHA256,
                "license": "OFL-1.1",
                "svg": "editable-text" if request.chart.svg_text_mode == "editable" else "glyph-paths",
                **({"figure_svg": "editable-text" if figure.svg_text_mode == "editable" else "glyph-paths"} if figure else {}),
                "pdf": "embedded-TrueType",
                "raster": "rendered-pixels",
            },
            export_checks={} if figure is None else {
                "formats": sorted(FIGURE_FORMATS),
                "width_mm": figure.width_mm,
                "height_mm": figure.height_mm,
                "dpi": figure.dpi,
                "pixel_width": round(figure.width_mm / 25.4 * figure.dpi),
                "pixel_height": round(figure.height_mm / 25.4 * figure.dpi),
                "font_embedding": figure.font_embedding,
                "palette_version": figure.palette_version,
                "status": "configuration-validated",
            },
        )
        output = BytesIO()
        with ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=6) as archive:
            archive.writestr("project.json", document.model_dump_json(indent=2, exclude_none=True))
            archive.writestr(f"data/{Path(record.filename).name}", record.payload)
            if image_payload is not None:
                archive.writestr("image/source", image_payload)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="数据集不存在或会话已结束，请重新导入。") from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    safe_name = "".join(character for character in request.name if character.isalnum() or character in "-_ ").strip() or "biofigure-project"
    filename = f"{safe_name}.bfsproj"
    disposition = f'attachment; filename="{filename}"'
    if not filename.isascii():
        disposition = f"attachment; filename=biofigure-project.bfsproj; filename*=UTF-8''{quote(filename, safe='')}"
    return Response(output.getvalue(), media_type="application/vnd.biofigure.project+zip",
                    headers={"Content-Disposition": disposition})


def _export_connector_sample(chart: ChartSpec, figure: FigureSpec | None,
                             asset_store: ImageAssetStore | None) -> Response:
    return _export_project(ProjectSaveRequest(name="biofigure-sample", chart=chart, figure=figure),
                           asset_store or image_store)


app.include_router(connector_router(
    lambda chart: create_render(RenderRequest(chart=chart)),
    export_render, _create_figure, export_figure, _export_connector_sample,
))


@app.post("/api/projects/open", tags=["projects"])
async def open_project(file: UploadFile = File(...)) -> dict[str, object]:
    filename = file.filename or ""
    try:
        payload = await file.read(MAX_PROJECT_BYTES + 1)
    finally:
        await file.close()
    if not filename.lower().endswith(".bfsproj") or len(payload) > MAX_PROJECT_BYTES:
        raise HTTPException(status_code=422, detail="请选择不超过 220 MB 的 .bfsproj 项目文件。")
    return await run_in_threadpool(_restore_project, payload)


def _restore_project(payload: bytes) -> dict[str, object]:
    try:
        with ZipFile(BytesIO(payload)) as archive:
            names = archive.namelist()
            data_names = [name for name in names if name.startswith("data/")]
            if ("project.json" not in names or len(data_names) != 1
                    or any(name.startswith(("/", "\\")) or ".." in Path(name).parts for name in names)):
                raise ValueError("项目包结构无效。")
            data_name = data_names[0]
            if archive.getinfo("project.json").file_size > 1024 * 1024 or archive.getinfo(data_name).file_size > MAX_H5AD_BYTES:
                raise ValueError("项目包解压后超过安全上限；请减小项目或数据文件。")
            document = ProjectDocument.model_validate_json(archive.read("project.json"))
            expected_names = {"project.json", data_name}
            if document.image_sha256:
                expected_names.add("image/source")
            if len(names) != len(expected_names) or set(names) != expected_names:
                raise ValueError("项目包成员与清单不一致。")
            image_payload = None
            if document.image_sha256:
                image_size = archive.getinfo("image/source").file_size
                if not 1 <= image_size <= MAX_FIGURE_IMAGE_BYTES:
                    raise ValueError("项目源图解压后超过安全上限。")
                image_payload = archive.read("image/source")
                if sha256(image_payload).hexdigest() != document.image_sha256:
                    raise ValueError("项目源图摘要不匹配，文件可能已损坏。")
            data = archive.read(data_name)
        if sha256(data).hexdigest() != document.data_sha256:
            raise ValueError("项目数据摘要不匹配，文件可能已损坏。")
        record = parse_dataset(document.data_filename, data)
        figure = document.figure
        if image_payload is not None:
            with TemporaryDirectory(dir=image_store.session) as directory:
                path = Path(directory) / "source"
                path.write_bytes(image_payload)
                source_asset = ImageAsset(figure.image_panel.asset_id, document.image_filename,
                                          len(image_payload), document.image_sha256, path)
                with image_store.stage_many([source_asset]) as staged:
                    asset = staged.assets[0]
                    prepare_publication_image(asset, figure.image_panel, figure)
                    figure = figure.model_copy(update={"image_panel": figure.image_panel.model_copy(update={"asset_id": asset.id})})
                    dataset_id = store_record(record)
                    staged.commit()
        else:
            dataset_id = store_record(record)
        chart = document.chart.model_copy(update={"dataset_id": dataset_id})
        if figure:
            figure = figure.model_copy(update={"panels": [panel.model_copy(update={"dataset_id": dataset_id}) for panel in figure.panels]})
        restored = document.model_copy(update={"chart": chart, "figure": figure})
    except (BadZipFile, KeyError, json.JSONDecodeError, ValueError) as error:
        raise HTTPException(status_code=422, detail=str(error) or "无法打开项目文件。") from error
    return {"project": restored.model_dump(mode="json"), "preview": dataset_summary(dataset_id, record, "embedded project")}


def _simulated_table_record() -> DatasetRecord:
    payload = SIMULATED_CSV.encode("utf-8")
    return DatasetRecord("table", "simulated-cell-response.csv", payload, sha256(payload).hexdigest(),
                         dataframe=simulated_dataframe())


def _resolve_chart_data(panel: ChartSpec):
    if panel.dataset_id == SIMULATED_DATASET_ID:
        return _simulated_table_record() if panel.chart_type == "r_ggplot" else simulated_dataframe()
    if panel.dataset_id == SIMULATED_ECOLOGY_DATASET_ID:
        return simulated_ecology_dataframe()
    if panel.dataset_id == SIMULATED_ECOLOGY_ALPHA_DATASET_ID:
        return simulated_ecology_alpha_dataframe()
    if panel.dataset_id == SIMULATED_ECOLOGY_BETA_DATASET_ID:
        return simulated_ecology_beta_dataframe()
    if panel.dataset_id == SIMULATED_ECOLOGY_ORDINATION_DATASET_ID:
        return simulated_ecology_ordination_dataframe()
    if panel.dataset_id == SIMULATED_ECOLOGY_ENVIRONMENT_DATASET_ID:
        return simulated_ecology_environment_dataframe()
    if panel.dataset_id == SIMULATED_ECOLOGY_TIME_DATASET_ID:
        return simulated_ecology_time_dataframe()
    if panel.dataset_id == SIMULATED_ECOLOGY_SPATIAL_DATASET_ID:
        return simulated_ecology_spatial_dataframe()
    record = get_record(panel.dataset_id)
    if panel.chart_type in {"embedding_categorical", "embedding_continuous", "feature", "violin", "dotplot"}:
        if record.adata is None:
            raise ValueError("单细胞图需要 H5AD 数据。")
        return record.adata
    if panel.chart_type in {"spatial_categorical", "spatial_continuous", "spatial_feature", "genome_tracks", "circos", "dna_features", "r_ggplot"}:
        return record
    if record.dataframe is None:
        raise ValueError("基础图表需要 CSV 或 XLSX 表格。")
    return record.dataframe
