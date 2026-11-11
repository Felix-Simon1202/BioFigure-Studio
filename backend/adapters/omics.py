"""Local adapters for phase 6B omics slices."""

from __future__ import annotations

import csv
import os
from pathlib import Path
import shutil
import subprocess
from tempfile import TemporaryDirectory

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from backend.core.specs import ChartSpec
from backend.data.store import DatasetRecord
from backend.themes.registry import get_theme


def render_omics(spec: ChartSpec, record: DatasetRecord, export_format: str) -> bytes:
    from backend.adapters.matplotlib_charts import RENDER_LOCK, configure_fonts, finish_figure

    if spec.chart_type == "r_ggplot":
        return _render_r_ggplot(spec, record, export_format)
    with RENDER_LOCK:
        configure_fonts()
        figure, axes = plt.subplots(figsize=(spec.width_mm / 25.4, spec.height_mm / 25.4), dpi=spec.dpi, layout="constrained")
        try:
            if spec.chart_type.startswith("spatial_"):
                from backend.adapters.single_cell import draw_single_cell
                spatial_kind = {"spatial_categorical": "embedding_categorical", "spatial_continuous": "embedding_continuous", "spatial_feature": "feature"}[spec.chart_type]
                draw_single_cell(axes, spec.model_copy(update={"chart_type": spatial_kind}), _require_adata(record))
            elif spec.chart_type == "genome_tracks":
                _draw_genome_tracks(axes, spec, record)
            elif spec.chart_type == "circos":
                plt.close(figure)
                figure = _draw_circos(spec, record)
            elif spec.chart_type == "dna_features":
                _draw_dna_features(axes, spec, record)
            else:
                raise ValueError("未知的组学图表类型。")
            return finish_figure(figure, export_format, spec.dpi, svg_text_mode=spec.svg_text_mode)
        finally:
            plt.close(figure)


def _require_adata(record: DatasetRecord):
    if record.adata is None:
        raise ValueError("空间组学图需要 H5AD 数据。")
    return record.adata


def _draw_genome_tracks(axes, spec: ChartSpec, record: DatasetRecord) -> None:
    theme = get_theme(spec.theme_id)
    if record.manifest is not None:
        manifest = record.manifest
        tracks = manifest.get("tracks")
        if not isinstance(tracks, list) or not tracks:
            raise ValueError("genome_tracks manifest 至少需要一个 tracks 项。")
        track_rows = [(str(track.get("name", f"track-{i + 1}")), pd.DataFrame(track.get("records", [])), str(track.get("type", "interval"))) for i, track in enumerate(tracks) if isinstance(track, dict)]
        region = manifest.get("region")
    elif record.dataframe is not None:
        manifest = {}
        track_rows = [(record.filename, record.dataframe, "signal" if "value" in record.dataframe else "interval")]
        region = None
    else:
        raise ValueError("基因组轨道需要 BED、bedGraph、GFF3/GTF 或 JSON manifest。")
    xmin, xmax = _region_bounds(region, track_rows)
    axes.set_xlim(xmin, xmax)
    axes.set_ylim(-0.5, len(track_rows) - 0.5)
    axes.set_yticks(range(len(track_rows)), [name for name, _, _ in track_rows])
    axes.set_xlabel(f"{manifest.get('assembly', '') + ' · ' if manifest.get('assembly') else ''}genomic position", fontsize=spec.font_size)
    axes.tick_params(labelsize=spec.font_size)
    for row_index, (_, frame, track_type) in enumerate(track_rows):
        if frame.empty or not {"start", "end"}.issubset(frame.columns):
            raise ValueError("每条基因组轨道都需要 start 和 end 列。")
        for _, row in frame.iterrows():
            start, end = float(row["start"]), float(row["end"])
            if start < xmin or end > xmax or end <= start:
                raise ValueError("基因组轨道坐标超出展示区间或不是递增区间。")
            if track_type in {"signal", "bedgraph"} or "value" in row:
                value = float(row.get("value", 0))
                axes.plot([start, end], [row_index + value * 0.25, row_index + value * 0.25], color=theme.palette[row_index % len(theme.palette)], linewidth=max(1, spec.line_width * 2))
            else:
                axes.add_patch(plt.Rectangle((start, row_index - 0.25), end - start, 0.5, facecolor=theme.palette[row_index % len(theme.palette)], alpha=.78, linewidth=0))
    axes.grid(axis="x", alpha=.18)
    axes.set_title(spec.title or "Genome tracks", loc="left", color=theme.text_color, fontsize=spec.font_size + 2, fontweight="bold")


def _region_bounds(region: object, track_rows: list[tuple[str, pd.DataFrame, str]]) -> tuple[float, float]:
    if isinstance(region, dict):
        start, end = float(region.get("start", 0)), float(region.get("end", 0))
        if end <= start:
            raise ValueError("展示区间 end 必须大于 start。")
        return start, end
    starts = [float(frame["start"].min()) for _, frame, _ in track_rows if not frame.empty]
    ends = [float(frame["end"].max()) for _, frame, _ in track_rows if not frame.empty]
    if not starts or not ends:
        raise ValueError("轨道没有可用坐标。")
    return min(starts), max(ends)


def _draw_circos(spec: ChartSpec, record: DatasetRecord):
    from pycirclize import Circos
    if record.manifest is None:
        raise ValueError("Circos 图需要 JSON manifest。")
    manifest = record.manifest
    sectors_raw = manifest.get("sectors")
    if not isinstance(sectors_raw, dict) or not sectors_raw:
        raise ValueError("Circos manifest 需要非空 sectors 对象。")
    sectors = {str(key): float(value) for key, value in sectors_raw.items()}
    if any(value <= 0 for value in sectors.values()):
        raise ValueError("Circos sectors 长度必须为正数。")
    circos = Circos(sectors, space=float(manifest.get("space", 3)))
    theme = get_theme(spec.theme_id)
    for index, sector in enumerate(circos.sectors):
        sector.text(sector.name, r=108, size=max(8, spec.font_size), color=theme.text_color)
        track = sector.add_track((78, 98), r_pad_ratio=.08)
        track.axis(fc="#ffffff00", ec=theme.text_color, lw=spec.line_width)
        values = next((item for item in manifest.get("tracks", []) if isinstance(item, dict) and item.get("sector") == sector.name), None)
        if values:
            x = np.asarray(values.get("x", []), dtype=float)
            y = np.asarray(values.get("y", []), dtype=float)
            if len(x) != len(y) or np.any(x < sector.start) or np.any(x > sector.end):
                raise ValueError(f"Circos 轨道 {sector.name} 的 x/y 长度或范围无效。")
            track.line(x, y, color=theme.palette[index % len(theme.palette)], lw=spec.line_width)
    for link in manifest.get("links", []):
        if not isinstance(link, dict):
            continue
        source, target = link.get("source"), link.get("target")
        if not (isinstance(source, list) and len(source) == 3 and isinstance(target, list) and len(target) == 3):
            raise ValueError("Circos link 必须是 [sector, start, end]。")
        circos.link((str(source[0]), float(source[1]), float(source[2])), (str(target[0]), float(target[1]), float(target[2])), color=str(link.get("color", theme.palette[0])), alpha=.55)
    figure = circos.plotfig(dpi=spec.dpi, figsize=(spec.width_mm / 25.4, spec.height_mm / 25.4))
    if spec.title:
        figure.text(.5, .98, spec.title, ha="center", va="top", fontsize=spec.font_size + 2, color=theme.text_color, fontweight="bold")
    return figure


def _draw_dna_features(axes, spec: ChartSpec, record: DatasetRecord) -> None:
    from dna_features_viewer import GraphicFeature, GraphicRecord
    if record.sequence_record is None:
        raise ValueError("DNA 图需要 GenBank 文件。")
    sequence = record.sequence_record
    features = []
    palette = get_theme(spec.theme_id).palette
    for index, feature in enumerate(sequence.features):
        if feature.location is None:
            continue
        start, end = int(feature.location.start), int(feature.location.end)
        if end <= start or start < 0 or end > len(sequence.seq):
            raise ValueError("GenBank feature 坐标超出序列范围。")
        qualifiers = feature.qualifiers or {}
        label = next((str(qualifiers[key][0]) for key in ("label", "gene", "locus_tag", "product") if qualifiers.get(key)), str(feature.type))
        features.append(GraphicFeature(start=start, end=end, strand=feature.location.strand or 0, label=label[:48], color=palette[index % len(palette)]))
    if not features:
        raise ValueError("GenBank 没有可绘制的 feature。")
    graphic = GraphicRecord(sequence_length=len(sequence.seq), features=features)
    graphic.plot(ax=axes, figure_width=spec.width_mm / 25.4, figure_height=spec.height_mm / 25.4, with_ruler=True, annotate_inline=True, max_label_length=48)
    if spec.title:
        axes.set_title(spec.title, loc="left", fontsize=spec.font_size + 2, fontweight="bold")


def _reviewed_r_root() -> Path | None:
    local = os.environ.get("LOCALAPPDATA")
    return Path(local) / "BioFigureStudio" / "R-4.6.1" if local else None


def _rscript_path() -> str | None:
    configured = os.environ.get("BIOFIGURE_RSCRIPT")
    root = _reviewed_r_root()
    candidates = [configured, shutil.which("Rscript"), str(root / "bin" / "Rscript.exe") if root else None]
    return next((candidate for candidate in candidates if candidate and Path(candidate).is_file()), None)


def reviewed_r_available() -> bool:
    root, executable = _reviewed_r_root(), _rscript_path()
    if not root or not executable or Path(executable).resolve() != (root / "bin" / "Rscript.exe").resolve():
        return False
    try:
        metadata = (root / "library" / "ggplot2" / "DESCRIPTION").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False
    return "Version: 4.0.3" in metadata.splitlines()


def _render_r_ggplot(spec: ChartSpec, record: DatasetRecord, export_format: str) -> bytes:
    if record.dataframe is None:
        raise ValueError("R ggplot 插件当前需要 CSV 或 XLSX 表格。")
    rscript = _rscript_path()
    if rscript is None:
        raise ValueError("未找到 Rscript；请在插件设置中安装 R 4.6 或配置 BIOFIGURE_RSCRIPT。")
    if not spec.x_column or not spec.y_column or spec.x_column not in record.dataframe or spec.y_column not in record.dataframe:
        raise ValueError("R ggplot 需要有效的 X、Y 字段。")
    with TemporaryDirectory(prefix="biofigure-r-") as directory:
        root = Path(directory)
        data_path = root / "data.csv"
        parameters_path = root / "parameters.csv"
        script_path = root / "render.R"
        output_path = root / f"plot.{export_format}"
        record.dataframe.to_csv(data_path, index=False)
        with parameters_path.open("w", encoding="utf-8", newline="") as parameters:
            writer = csv.writer(parameters)
            writer.writerow(("x", "y", "group", "title"))
            writer.writerow((spec.x_column, spec.y_column, spec.group_column or "", spec.title))
        script_path.write_text(_R_GGPLOT_SCRIPT, encoding="utf-8")
        args = [rscript, "--vanilla", str(script_path), str(data_path), str(output_path), str(parameters_path),
                export_format, str(spec.width_mm), str(spec.height_mm), str(spec.dpi)]
        runtime_variables = {
            "SYSTEMROOT", "WINDIR", "SYSTEMDRIVE", "COMSPEC", "PATH", "TEMP", "TMP",
            "USERPROFILE", "HOMEDRIVE", "HOMEPATH", "USERNAME", "APPDATA", "LOCALAPPDATA", "PROGRAMDATA",
            "NUMBER_OF_PROCESSORS", "PROCESSOR_ARCHITECTURE", "LANG", "LC_ALL",
        }
        environment = {key: value for key, value in os.environ.items() if key.upper() in runtime_variables}
        reviewed_root = _reviewed_r_root()
        if reviewed_root:
            library = str(reviewed_root / "library")
            environment.update(R_LIBS_USER=library, BIOFIGURE_R_LIB=library)
        try:
            completed = subprocess.run(args, capture_output=True, text=True, encoding="utf-8",
                                       errors="replace", timeout=45, env=environment, check=False)
        except subprocess.TimeoutExpired as error:
            raise ValueError("R 绘图超过 45 秒，请缩小输入或稍后重试。") from error
        if completed.returncode != 0 or not output_path.exists():
            detail = (completed.stderr or completed.stdout).strip().splitlines()[-4:]
            raise ValueError(f"R 绘图失败：{' '.join(detail) or 'Rscript 没有生成输出。'}")
        return output_path.read_bytes()


_R_GGPLOT_SCRIPT = r'''args <- commandArgs(trailingOnly=TRUE)
lib <- Sys.getenv("BIOFIGURE_R_LIB")
if (nzchar(lib)) .libPaths(c(lib, .libPaths()))
data <- read.csv(args[[1]], check.names=FALSE, stringsAsFactors=FALSE, encoding="UTF-8")
parameters <- read.csv(args[[3]], colClasses="character", na.strings=NULL, encoding="UTF-8")
out <- args[[2]]; fmt <- args[[4]]
x <- parameters$x[[1]]; y <- parameters$y[[1]]; group <- parameters$group[[1]]; title <- parameters$title[[1]]
if (!requireNamespace("ggplot2", quietly=TRUE)) stop("ggplot2 未安装")
library(ggplot2)
mapping <- aes(x=.data[[x]], y=.data[[y]])
if (nzchar(group) && group %in% names(data)) mapping <- aes(x=.data[[x]], y=.data[[y]], colour=.data[[group]])
plot <- ggplot(data, mapping) + geom_point(size=2.2, alpha=.82) + theme_minimal(base_size=11) + labs(title=title, x=x, y=y, colour=if (nzchar(group)) group else NULL)
width <- as.numeric(args[[5]]) / 25.4; height <- as.numeric(args[[6]]) / 25.4; dpi <- as.numeric(args[[7]])
if (fmt == "svg") {
  grDevices::svg(out, width=width, height=height)
  print(plot)
  grDevices::dev.off()
} else if (fmt == "pdf" && capabilities("cairo")) {
  ggsave(out, plot, width=width, height=height, units="in", device=grDevices::cairo_pdf)
} else {
  ggsave(out, plot, width=width, height=height, units="in", dpi=dpi, device=fmt)
}
'''
