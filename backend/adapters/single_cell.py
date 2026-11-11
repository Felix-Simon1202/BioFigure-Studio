"""Rendering of existing AnnData results without recomputing analyses."""

from __future__ import annotations

from io import BytesIO

import anndata as ad
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import sparse

from backend.core.specs import ChartSpec
from backend.themes.palettes import ART_PALETTES, continuous_palette
from backend.themes.registry import get_theme


def render_single_cell(spec: ChartSpec, adata: ad.AnnData, export_format: str) -> bytes:
    from backend.adapters.matplotlib_charts import RENDER_LOCK, configure_fonts, finish_figure
    with RENDER_LOCK:
        configure_fonts()
        figure, axes = plt.subplots(figsize=(spec.width_mm / 25.4, spec.height_mm / 25.4), dpi=spec.dpi, layout="constrained")
        try:
            draw_single_cell(axes, spec, adata)
            return finish_figure(figure, export_format, spec.dpi, svg_text_mode=spec.svg_text_mode)
        finally:
            plt.close(figure)


def draw_single_cell(axes, spec: ChartSpec, adata: ad.AnnData) -> None:
    theme = get_theme(spec.theme_id)
    figure = axes.figure
    figure.patch.set_facecolor(theme.figure_facecolor)
    axes.set_facecolor(theme.axes_facecolor)
    axes.tick_params(colors=theme.text_color, labelsize=spec.font_size)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)
    for spine in ("left", "bottom"):
        axes.spines[spine].set_color(theme.text_color)
        axes.spines[spine].set_linewidth(spec.line_width)
    if spec.chart_type in {"embedding_categorical", "embedding_continuous", "feature"}:
        _embedding(axes, spec, adata)
    elif spec.chart_type == "violin":
        _violin(axes, spec, adata)
    elif spec.chart_type == "dotplot":
        _dotplot(axes, spec, adata)
    else:
        raise ValueError("未知的单细胞图类型。")
    if spec.title:
        axes.set_title(spec.title, loc="left", color=theme.text_color, fontsize=spec.font_size + 2, fontweight="bold")


def _embedding(axes, spec: ChartSpec, adata: ad.AnnData) -> None:
    if spec.coordinate_key not in adata.obsm:
        raise ValueError(f"H5AD 中没有坐标 {spec.coordinate_key}；本阶段不会自动计算降维。")
    coordinates = np.asarray(adata.obsm[spec.coordinate_key])
    if coordinates.ndim != 2 or coordinates.shape[0] != adata.n_obs or coordinates.shape[1] < 2:
        raise ValueError(f"坐标 {spec.coordinate_key} 必须包含每个细胞的至少两个维度。")
    if not np.isfinite(coordinates[:, :2]).all():
        raise ValueError(f"坐标 {spec.coordinate_key} 含有缺失或无限值，请先修复源文件。")
    axes.set_xlabel(f"{_coordinate_label(spec.coordinate_key)} 1", fontsize=spec.font_size)
    axes.set_ylabel(f"{_coordinate_label(spec.coordinate_key)} 2", fontsize=spec.font_size)
    axes.grid(False)
    if spec.chart_type == "embedding_categorical":
        if not spec.color_field or spec.color_field not in adata.obs:
            raise ValueError("请选择 H5AD obs 中的分类着色字段。")
        values = adata.obs[spec.color_field].astype(object).where(adata.obs[spec.color_field].notna(), "缺失").astype(str)
        categories = list(dict.fromkeys(spec.category_order + sorted(values.unique().tolist())))
        palette = _categorical_palette(spec)
        if len(categories) > len(palette):
            raise ValueError(f"分类字段包含 {len(categories)} 类，超过当前色板 {len(palette)} 色的上限。")
        for index, category in enumerate(categories):
            mask = values.to_numpy() == category
            if mask.any():
                axes.scatter(coordinates[mask, 0], coordinates[mask, 1], s=spec.point_size, color=palette[index], alpha=.85, linewidths=0, label=category, rasterized=False)
        if spec.show_legend:
            axes.legend(frameon=False, title=spec.color_field, fontsize=max(7, spec.font_size - 1), markerscale=1.8)
        return
    if spec.chart_type == "embedding_continuous":
        if not spec.color_field or spec.color_field not in adata.obs:
            raise ValueError("请选择 H5AD obs 中的连续数值字段。")
        values = pd.to_numeric(adata.obs[spec.color_field], errors="coerce").to_numpy(dtype=float)
        label = spec.color_field
    else:
        if len(spec.genes) != 1:
            raise ValueError("Feature Plot 每次请选择一个基因。")
        values = _gene_vector(adata, spec, spec.genes[0])
        label = spec.genes[0]
    if not np.isfinite(values).all():
        raise ValueError(f"{label} 含有缺失或无限值；本阶段不会静默丢弃细胞。")
    order = np.argsort(values, kind="stable")
    points = axes.scatter(coordinates[order, 0], coordinates[order, 1], c=values[order], s=spec.point_size, cmap=_continuous_palette(spec), linewidths=0, rasterized=False)
    colorbar = axes.figure.colorbar(points, ax=axes, label=label)
    colorbar.ax.tick_params(labelsize=max(7, spec.font_size - 1))


def _violin(axes, spec: ChartSpec, adata: ad.AnnData) -> None:
    groups, categories = _groups(adata, spec)
    if not spec.genes or len(spec.genes) > 8:
        raise ValueError("小提琴图请选择 1–8 个基因。")
    if len(spec.genes) > 1 and len(categories) > 1:
        raise ValueError("当前小提琴图一次支持多个基因或多个分组；请缩小选择以保持可读。")
    series: list[np.ndarray] = []
    labels: list[str] = []
    if len(spec.genes) == 1:
        vector = _gene_vector(adata, spec, spec.genes[0])
        for category in categories:
            series.append(vector[groups == category])
            labels.append(category)
        axes.set_ylabel(f"{spec.genes[0]} expression", fontsize=spec.font_size)
    else:
        for gene in spec.genes:
            series.append(_gene_vector(adata, spec, gene))
            labels.append(gene)
        axes.set_ylabel("expression", fontsize=spec.font_size)
    parts = axes.violinplot(series, showmeans=False, showmedians=True, showextrema=False)
    colors = _categorical_palette(spec)
    for index, body in enumerate(parts["bodies"]):
        body.set_facecolor(colors[index % len(colors)])
        body.set_edgecolor("none")
        body.set_alpha(.82)
    parts["cmedians"].set_color("#202124")
    parts["cmedians"].set_linewidth(spec.line_width)
    axes.set_xticks(range(1, len(labels) + 1), labels, rotation=25 if len(labels) > 4 else 0, ha="right" if len(labels) > 4 else "center")
    axes.grid(axis="y", alpha=.2)


def _dotplot(axes, spec: ChartSpec, adata: ad.AnnData) -> None:
    groups, categories = _groups(adata, spec)
    if not spec.genes or len(spec.genes) > 20:
        raise ValueError("Dot Plot 请选择 1–20 个基因。")
    means = np.zeros((len(categories), len(spec.genes)))
    fractions = np.zeros_like(means)
    for column, gene in enumerate(spec.genes):
        vector = _gene_vector(adata, spec, gene)
        for row, category in enumerate(categories):
            selected = vector[groups == category]
            means[row, column] = float(np.mean(selected)) if len(selected) else np.nan
            fractions[row, column] = float(np.mean(selected > 0)) if len(selected) else 0
    x, y = np.meshgrid(np.arange(len(spec.genes)), np.arange(len(categories)))
    points = axes.scatter(x.ravel(), y.ravel(), s=18 + fractions.ravel() * 180, c=means.ravel(), cmap=_continuous_palette(spec), edgecolors="#ffffff", linewidths=.4)
    axes.set_xticks(range(len(spec.genes)), spec.genes, rotation=35, ha="right")
    axes.set_yticks(range(len(categories)), categories)
    axes.invert_yaxis()
    axes.grid(False)
    axes.figure.colorbar(points, ax=axes, label="mean expression")
    axes.text(1, 1.02, "点大小：表达细胞比例", transform=axes.transAxes, ha="right", va="bottom", fontsize=max(7, spec.font_size - 1))


def _groups(adata: ad.AnnData, spec: ChartSpec) -> tuple[np.ndarray, list[str]]:
    if not spec.group_column or spec.group_column not in adata.obs:
        raise ValueError("请选择 H5AD obs 中的分组字段。")
    values = adata.obs[spec.group_column].astype(object).where(adata.obs[spec.group_column].notna(), "缺失").astype(str).to_numpy()
    categories = list(dict.fromkeys(spec.category_order + sorted(np.unique(values).tolist())))
    if len(categories) > 30:
        raise ValueError("分组超过 30 类，请缩小分组后再绘图。")
    return values, categories


def _gene_vector(adata: ad.AnnData, spec: ChartSpec, gene: str) -> np.ndarray:
    if spec.expression_source == "raw":
        if adata.raw is None:
            raise ValueError("该 H5AD 没有 raw 表达矩阵。")
        matrix, names = adata.raw.X, adata.raw.var_names
    elif spec.expression_source == "layer":
        if not spec.expression_layer or spec.expression_layer not in adata.layers:
            raise ValueError("所选表达 layer 不存在。")
        matrix, names = adata.layers[spec.expression_layer], adata.var_names
    else:
        matrix, names = adata.X, adata.var_names
    matches = np.flatnonzero(np.asarray(names.astype(str)) == gene)
    if len(matches) != 1:
        raise ValueError(f"表达矩阵中找不到唯一基因：{gene}")
    selected = matrix[:, int(matches[0])]
    vector = selected.toarray().ravel() if sparse.issparse(selected) else np.asarray(selected).ravel()
    vector = vector.astype(float, copy=False)
    if not np.isfinite(vector).all():
        raise ValueError(f"基因 {gene} 含有缺失或无限值。")
    if spec.transform == "log1p":
        if np.any(vector < 0):
            raise ValueError("表达值含负数，不能应用 log1p。")
        vector = np.log1p(vector)
    return vector


def _categorical_palette(spec: ChartSpec) -> tuple[str, ...]:
    if spec.palette_id in ART_PALETTES:
        return ART_PALETTES[spec.palette_id]
    if spec.palette_id == "colorblind":
        return ("#0072B2", "#E69F00", "#009E73", "#CC79A7", "#D55E00", "#56B4E9", "#F0E442", "#000000")
    return get_theme(spec.theme_id).palette


def _continuous_palette(spec: ChartSpec):
    return continuous_palette(spec.palette_id)


def _coordinate_label(key: str) -> str:
    return key[2:].upper() if key.startswith("X_") else key
