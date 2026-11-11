"""Matplotlib adapters for reviewed phase 3 chart types."""

from io import BytesIO
from pathlib import Path
from hashlib import sha256
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager
from matplotlib.colors import Normalize
from matplotlib.ticker import PercentFormatter
from matplotlib.transforms import Bbox, BboxTransform

from backend.core.specs import ChartSpec, FigureImagePanel, FigureSpec, SvgTextMode
from backend.image.publication import PublicationImage
from backend.themes.palettes import ART_PALETTES, SCIENTIFIC_PALETTES, continuous_palette
from threading import RLock

RENDER_LOCK = RLock()
from backend.themes.registry import get_theme

_FONT_READY = False
FONT_SHA256 = "a3041811a78c361b1de50f953c805e0244951c21c5bd412f7232ef0d899af0da"
FONT_FILENAME = "NotoSansSC-Regular.ttf"


def configure_fonts() -> None:
    """Register the reviewed bundled CJK font for screen and all exports."""
    global _FONT_READY
    if _FONT_READY:
        return
    roots = [Path(__file__).resolve().parents[2]]
    if getattr(sys, "_MEIPASS", None):
        roots.insert(0, Path(sys._MEIPASS))
    for root in roots:
        candidate = root / "assets" / "fonts" / FONT_FILENAME
        if candidate.is_file():
            if sha256(candidate.read_bytes()).hexdigest() != FONT_SHA256:
                raise ValueError("审核字体摘要不匹配，已停止导出；请恢复项目随附的 Noto Sans SC 字体文件。")
            font_manager.fontManager.addfont(candidate)
            family = font_manager.FontProperties(fname=candidate).get_name()
            matplotlib.rcParams["font.family"] = [family, "DejaVu Sans"]
            matplotlib.rcParams["axes.unicode_minus"] = False
            matplotlib.rcParams["svg.fonttype"] = "path"
            matplotlib.rcParams["pdf.fonttype"] = 42
            break
    else:
        raise ValueError("缺少审核字体 Noto Sans SC，无法保证论文图字体一致与嵌入；请恢复项目字体文件。")
    _FONT_READY = True


def render_chart(spec: ChartSpec, dataframe: pd.DataFrame, export_format: str) -> bytes:
    """Render one validated chart with theme parameters, without filesystem writes."""
    with RENDER_LOCK:
        configure_fonts()
        figure, axes = plt.subplots(figsize=(spec.width_mm / 25.4, spec.height_mm / 25.4), dpi=spec.dpi, layout="constrained")
        try:
            draw_chart(axes, spec, dataframe)
            return finish_figure(figure, export_format, spec.dpi, svg_text_mode=spec.svg_text_mode)
        finally:
            plt.close(figure)


def draw_chart(axes, spec, dataframe):
    ecology_chart = spec.chart_type in {"ecology_alpha_diversity", "ecology_beta_ordination", "ecology_ordination_biplot", "ecology_environment_gradient", "ecology_time_series", "ecology_spatial_points"}
    required = [] if ecology_chart else [spec.x_column, spec.y_column] + ([spec.group_column] if spec.group_column else [])
    for column in required:
        if column not in dataframe.columns:
            raise ValueError(f"未知字段：{column}")
    theme = get_theme(spec.theme_id)
    palette = _palette(spec, theme.palette)
    category_column = spec.group_column if spec.chart_type in ("scatter", "line") else None
    if category_column and dataframe[category_column].nunique(dropna=False) > len(palette):
        raise ValueError("类别数量超过色板容量，请减少类别或拆分图表。")
    figure = axes.figure
    figure.patch.set_facecolor(theme.figure_facecolor)
    axes.set_facecolor(theme.axes_facecolor)
    axes.tick_params(colors=theme.text_color, labelsize=spec.font_size)
    for spine in ("top", "right"):
        axes.spines[spine].set_visible(False)
    axes.spines["left"].set_color(theme.text_color); axes.spines["left"].set_linewidth(spec.line_width)
    axes.spines["bottom"].set_color(theme.text_color); axes.spines["bottom"].set_linewidth(spec.line_width)
    axes.grid(axis="y", color=theme.grid_color, linewidth=spec.line_width * .6)
    axes.set_axisbelow(True)

    if spec.chart_type == "ecology_composition":
        _ecology_composition(axes, dataframe, spec, palette)
    elif spec.chart_type == "ecology_alpha_diversity":
        _ecology_alpha_diversity(axes, dataframe, spec, palette)
    elif spec.chart_type == "ecology_beta_ordination":
        _ecology_beta_ordination(axes, dataframe, spec, palette)
    elif spec.chart_type == "ecology_ordination_biplot":
        _ecology_ordination_biplot(axes, dataframe, spec, palette)
    elif spec.chart_type == "ecology_environment_gradient":
        _ecology_environment_gradient(axes, dataframe, spec, palette)
    elif spec.chart_type == "ecology_time_series":
        _ecology_time_series(axes, dataframe, spec, palette)
    elif spec.chart_type == "ecology_spatial_points":
        _ecology_spatial_points(axes, dataframe, spec, palette)
    elif spec.chart_type == "scatter":
        _scatter(axes, dataframe, spec, palette)
    elif spec.chart_type == "bar":
        _bar(axes, dataframe, spec, palette[0])
    elif spec.chart_type == "line":
        _line(axes, dataframe, spec, palette)
    elif spec.chart_type == "box":
        _box(axes, dataframe, spec, palette)
    elif spec.chart_type == "heatmap":
        _heatmap(axes, dataframe, spec)
    if spec.chart_type not in {"ecology_alpha_diversity", "ecology_beta_ordination", "ecology_ordination_biplot", "ecology_environment_gradient", "ecology_spatial_points"}:
        axes.set_xlabel("" if spec.chart_type == "heatmap" else spec.x_column, color=theme.text_color, fontsize=spec.font_size)
        axes.set_ylabel("" if spec.chart_type == "heatmap" else spec.y_column, color=theme.text_color, fontsize=spec.font_size)
    if spec.title:
        axes.set_title(spec.title, color=theme.text_color, loc="left", fontweight="bold", fontsize=spec.font_size + 2)


def _fit_chart_panel(figure, axes, cell):
    """Keep plot labels and colorbars inside the physical chart panel."""
    to_figure = figure.transFigure.inverted()
    padding_x = 1 / figure.bbox.width
    padding_y = 1 / figure.bbox.height
    for attempt in range(5):
        renderer = figure.canvas.get_renderer()
        boxes = [axis.get_tightbbox(renderer) for axis in axes if axis.get_visible()]
        painted = Bbox.union([box for box in boxes if box is not None]).transformed(to_figure)
        left = max(0, cell.x0 - painted.x0)
        bottom = max(0, cell.y0 - painted.y0)
        right = max(0, painted.x1 - cell.x1)
        top = max(0, painted.y1 - cell.y1)
        if left <= padding_x and right <= padding_x and bottom <= padding_y and top <= padding_y:
            return
        if attempt == 4:
            break
        positions = [axis.get_position(original=True).frozen() for axis in axes]
        region = Bbox.union(positions)
        target = Bbox.from_extents(region.x0 + left, region.y0 + bottom, region.x1 - right, region.y1 - top)
        if target.width < cell.width / 3 or target.height < cell.height / 3:
            break
        transform = BboxTransform(region, target)
        for axis, position in zip(axes, positions, strict=True):
            axis.set_position(position.transformed(transform))
        figure.canvas.draw()
    raise ValueError("统计图文字或图例放不进面板，请增大画布、缩短标签或减小字体。")


def finish_figure(figure, export_format, dpi, *, svg_text_mode: SvgTextMode = "outline",
                  image_scale_label=None, chart_panel=None):
    figure.canvas.draw()
    if chart_panel is not None:
        _fit_chart_panel(figure, *chart_panel)
    renderer = figure.canvas.get_renderer()
    frame = figure.bbox
    if image_scale_label is not None:
        bounds = image_scale_label.get_window_extent(renderer)
        image_bounds = image_scale_label.axes.bbox
        if not (image_bounds.contains(bounds.x0, bounds.y0) and image_bounds.contains(bounds.x1, bounds.y1)):
            raise ValueError("比例尺文字超出图像面板，请减少裁切或增大面板。")
    for axis in figure.axes:
        if not axis.get_visible():
            continue
        box = axis.get_tightbbox(renderer)
        if box is not None and (box.x0 < -1 or box.y0 < -1 or box.x1 > frame.x1 + 1 or box.y1 > frame.y1 + 1):
            overflow = []
            if box.x0 < -1: overflow.append("左侧")
            if box.y0 < -1: overflow.append("底部")
            if box.x1 > frame.x1 + 1: overflow.append("右侧")
            if box.y1 > frame.y1 + 1: overflow.append("顶部")
            raise ValueError(f"文字或图例超出画布（{'、'.join(overflow)}），请增大对应边距/画布、减小字体或缩短标签。")
    for legend in figure.legends:
        box = legend.get_window_extent(renderer)
        if box.x0 < -1 or box.y0 < -1 or box.x1 > frame.x1 + 1 or box.y1 > frame.y1 + 1:
            raise ValueError("共享图例超出画布，请增大边距/画布、减小字体或改用逐图图例。")
    figure.set_layout_engine("none")
    output = BytesIO()
    svg_font = "none" if svg_text_mode == "editable" else "path"
    with matplotlib.rc_context({"savefig.bbox": None, "svg.fonttype": svg_font}):
        kwargs = {"pil_kwargs": {"compression": "tiff_lzw"}} if export_format == "tiff" else {}
        figure.savefig(output, format=export_format, dpi=dpi, facecolor=figure.get_facecolor(), bbox_inches=None, **kwargs)
    return output.getvalue()


def _draw_figure_image(axis, image: PublicationImage, panel: FigureImagePanel, font_size: float):
    pixels = image.pixels
    grayscale = {"cmap": "gray", "vmin": 0, "vmax": np.iinfo(pixels.dtype).max} if pixels.ndim == 2 else {}
    axis.imshow(pixels, interpolation="none", **grayscale)
    axis.set_axis_off()
    bar_width = image.scale_bar_pixels / pixels.shape[1]
    axis.plot([0.07, 0.07 + bar_width], [0.08, 0.08], transform=axis.transAxes,
              color=panel.scale_bar_color, linewidth=1.5, solid_capstyle="butt")
    return axis.text(0.07 + bar_width / 2, 0.11, f"{panel.scale_bar_um:g} µm",
                     transform=axis.transAxes, color=panel.scale_bar_color, fontsize=font_size,
                     ha="center", va="bottom")


def render_figure(spec: FigureSpec, dataframes: list[object], export_format: str,
                  publication_image: PublicationImage | None = None) -> bytes:
    with RENDER_LOCK:
        configure_fonts()
        rows = (spec.panel_count + spec.columns - 1) // spec.columns
        publication = spec.spec_version != "1.0"
        figure, axes = plt.subplots(rows, spec.columns, squeeze=False, figsize=(spec.width_mm / 25.4, spec.height_mm / 25.4), dpi=spec.dpi, layout=None if publication else "constrained")
        try:
            if publication:
                left = spec.margin_left_mm / spec.width_mm
                right = 1 - spec.margin_right_mm / spec.width_mm
                bottom = spec.margin_bottom_mm / spec.height_mm
                top = 1 - spec.margin_top_mm / spec.height_mm
                panel_width = (spec.width_mm - spec.margin_left_mm - spec.margin_right_mm - spec.panel_gap_mm * (spec.columns - 1)) / spec.columns
                panel_height = (spec.height_mm - spec.margin_top_mm - spec.margin_bottom_mm - spec.panel_gap_mm * (rows - 1)) / rows
                figure.subplots_adjust(left=left, right=right, bottom=bottom, top=top, wspace=spec.panel_gap_mm / panel_width, hspace=spec.panel_gap_mm / panel_height)
            shared_handles, shared_labels = [], []
            image_scale_label = None
            chart_panel = None
            image_offset = int(spec.image_panel is not None)
            for index, axis in enumerate(axes.flat):
                if index >= spec.panel_count:
                    axis.set_visible(False)
                    continue
                panel = None
                if index < image_offset:
                    if publication_image is None:
                        raise ValueError("混合图版缺少图像来源。")
                    image_scale_label = _draw_figure_image(axis, publication_image, spec.image_panel, spec.label_font_size)
                else:
                    chart_index = index - image_offset
                    original = spec.panels[chart_index]
                    if image_offset:
                        cell = axis.get_position(original=True).frozen()
                        previous_axes = set(figure.axes)
                    panel = original.model_copy(update={
                        "theme_id": spec.theme_id,
                        "show_legend": spec.legend_mode == "per_panel" and original.show_legend,
                    })
                    if panel.chart_type in {"embedding_categorical", "embedding_continuous", "feature", "violin", "dotplot"}:
                        from backend.adapters.single_cell import draw_single_cell
                        draw_single_cell(axis, panel, dataframes[chart_index])
                    else:
                        draw_chart(axis, panel, dataframes[chart_index])
                    if image_offset:
                        chart_panel = ([axis, *(extra for extra in figure.axes if extra not in previous_axes)], cell)
                    if spec.legend_mode == "shared" and original.show_legend:
                        handles, labels = axis.get_legend_handles_labels()
                        if handles and image_offset:
                            position = "center right" if spec.legend_position == "right" else "lower center"
                            axis.legend(handles, labels, loc=position, frameon=False)
                        elif handles and not shared_handles:
                            shared_handles, shared_labels = handles, labels
                if spec.labels != "none":
                    label = chr((65 if spec.labels == "upper" else 97) + index)
                    if publication:
                        position = (-0.08, 1.04) if spec.label_position == "outside" else (0.02, 0.98)
                        image_label = {"bbox": {"facecolor": "white", "edgecolor": "none", "pad": 1}} if panel is None else {}
                        axis.text(*position, label, transform=axis.transAxes, ha="left", va="bottom" if spec.label_position == "outside" else "top", fontsize=spec.label_font_size, fontweight="bold", clip_on=False, **image_label)
                    else:
                        axis.set_title(label + (" · " + panel.title if panel.title else ""), loc="left", fontsize=panel.font_size + 2, fontweight="bold")
            if spec.legend_mode == "shared" and shared_handles:
                if spec.legend_position == "right":
                    figure.legend(shared_handles, shared_labels, loc="center right", frameon=False)
                else:
                    figure.legend(shared_handles, shared_labels, loc="lower center", ncol=max(1, len(shared_labels)), frameon=False)
            return finish_figure(figure, export_format, spec.dpi,
                                 svg_text_mode=spec.svg_text_mode, image_scale_label=image_scale_label, chart_panel=chart_panel)
        finally:
            plt.close(figure)


def _palette(spec: ChartSpec, fallback: tuple[str, ...]) -> tuple[str, ...]:
    if spec.palette_id in ART_PALETTES:
        return ART_PALETTES[spec.palette_id]
    if spec.palette_id in SCIENTIFIC_PALETTES:
        return tuple(matplotlib.colors.to_hex(continuous_palette(spec.palette_id)(i / 5)) for i in range(6))
    if spec.palette_id in ("viridis", "cividis", "magma", "coolwarm"):
        return tuple(matplotlib.colors.to_hex(matplotlib.colormaps[spec.palette_id](i / 5)) for i in range(6))
    if spec.palette_id == "colorblind":
        return ("#0072b2", "#e69f00", "#009e73", "#cc79a7", "#d55e00", "#56b4e9")
    return fallback


def _numeric(dataframe: pd.DataFrame, *columns: str) -> None:
    if any(not pd.api.types.is_numeric_dtype(dataframe[column]) for column in columns):
        raise ValueError("所选数值轴必须为数值列。")


def _scatter(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    _numeric(dataframe, spec.x_column, spec.y_column)
    if spec.group_column:
        for index, (group, subset) in enumerate(dataframe.groupby(spec.group_column, sort=True, dropna=False)):
            axes.scatter(subset[spec.x_column], subset[spec.y_column], s=54, alpha=.9, color=palette[(spec.category_order.index(str(group)) if str(group) in spec.category_order else index) % len(palette)], label=str(group), edgecolors="white", linewidths=.7)
        if spec.show_legend:
            axes.legend(frameon=False, title=spec.group_column, fontsize=spec.font_size)
    else:
        axes.scatter(dataframe[spec.x_column], dataframe[spec.y_column], s=54, color=palette[0], edgecolors="white", linewidths=.7)


def _bar(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, color: str) -> None:
    _numeric(dataframe, spec.y_column)
    summary = dataframe.groupby(spec.x_column, dropna=False)[spec.y_column].mean()
    axes.bar(summary.index.astype(str), summary.values, color=color)


def _line(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    _numeric(dataframe, spec.x_column, spec.y_column)
    if spec.group_column:
        for index, (group, subset) in enumerate(dataframe.groupby(spec.group_column, sort=True, dropna=False)):
            subset = subset.sort_values(spec.x_column)
            axes.plot(subset[spec.x_column], subset[spec.y_column], linewidth=spec.line_width, marker="o", color=palette[(spec.category_order.index(str(group)) if str(group) in spec.category_order else index) % len(palette)], label=str(group))
        if spec.show_legend:
            axes.legend(frameon=False, title=spec.group_column, fontsize=spec.font_size)
    else:
        subset = dataframe.sort_values(spec.x_column)
        axes.plot(subset[spec.x_column], subset[spec.y_column], linewidth=spec.line_width, marker="o", color=palette[0])


def _box(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    _numeric(dataframe, spec.y_column)
    groups = dataframe.groupby(spec.x_column, sort=True, dropna=False)[spec.y_column]
    labels, values = zip(*((str(label), group.dropna().tolist()) for label, group in groups))
    box = axes.boxplot(values, tick_labels=labels, patch_artist=True)
    for index, patch in enumerate(box["boxes"]):
        patch.set_facecolor(palette[index % len(palette)])
        patch.set_alpha(.75)


def _heatmap(axes: object, dataframe: pd.DataFrame, spec: ChartSpec) -> None:
    numeric = dataframe.select_dtypes(include="number")
    if numeric.shape[1] < 2:
        raise ValueError("热图至少需要两列数值数据。")
    if spec.palette_id in ART_PALETTES:
        raise ValueError("相关性热图请选择 Viridis 或 Coolwarm，艺术分类色仅用于类别。")
    cmap = continuous_palette(spec.palette_id) if spec.palette_id in {"viridis", "cividis", "magma", "coolwarm", "oc_blues", "oc_balance"} else "coolwarm"
    image = axes.imshow(numeric.corr(), vmin=-1, vmax=1, cmap=cmap)
    axes.set_xticks(range(len(numeric.columns)), numeric.columns, rotation=35, ha="right")
    axes.set_yticks(range(len(numeric.columns)), numeric.columns)
    axes.figure.colorbar(image, ax=axes, label="correlation")


def _ecology_composition(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    """Draw a bounded stacked composition chart from an explicit long table."""
    required = [spec.x_column, spec.y_column, spec.color_field]
    if any(not column or column not in dataframe.columns for column in required):
        raise ValueError("群落组成图需要有效的样品、丰度和分类单元字段。")
    frame = dataframe[[spec.x_column, spec.y_column, spec.color_field]].copy()
    if frame.isna().any().any():
        raise ValueError("群落组成图的样品、分类单元和丰度字段不能包含缺失值。")
    if not pd.api.types.is_numeric_dtype(frame[spec.y_column]):
        raise ValueError("群落组成图的丰度字段必须为数值列。")
    if not np.isfinite(frame[spec.y_column].to_numpy(dtype=float)).all() or (frame[spec.y_column] < 0).any():
        raise ValueError("群落组成图的丰度必须是有限的非负数。")
    if frame.duplicated([spec.x_column, spec.color_field]).any():
        raise ValueError("同一样品与分类单元只能出现一行；请先在本地整理重复记录。")
    sample_count = frame[spec.x_column].astype(str).nunique()
    taxa = frame[spec.color_field].astype(str).unique().tolist()
    if sample_count > 60:
        raise ValueError("群落组成图最多支持 60 个样品，请先拆分图表。")
    if len(taxa) > len(palette):
        raise ValueError(f"分类单元数量超过当前色板容量（{len(palette)}），请先筛选或拆分图表。")
    frame[spec.x_column] = frame[spec.x_column].astype(str)
    frame[spec.color_field] = frame[spec.color_field].astype(str)
    if spec.ecology_value_mode == "relative_fraction":
        if (frame[spec.y_column] > 1 + 1e-8).any():
            raise ValueError("相对丰度必须使用 0 到 1 之间的分数；如数据是计数，请切换为原始计数模式。")
        totals = frame.groupby(spec.x_column, sort=False)[spec.y_column].sum()
        if ((totals <= 0) | ((totals - 1).abs() > 0.02)).any():
            raise ValueError("相对丰度模式要求每个样品的丰度总和接近 1。")
        matrix = frame.pivot(index=spec.x_column, columns=spec.color_field, values=spec.y_column).fillna(0)
        ylabel = "相对丰度"
    else:
        totals = frame.groupby(spec.x_column, sort=False)[spec.y_column].sum()
        if (totals <= 0).any():
            raise ValueError("原始计数模式要求每个样品至少有一个正丰度记录。")
        matrix = frame.pivot(index=spec.x_column, columns=spec.color_field, values=spec.y_column).fillna(0)
        matrix = matrix.div(matrix.sum(axis=1), axis=0)
        ylabel = "相对丰度（由计数归一化）"
    order = [str(value) for value in spec.category_order if str(value) in matrix.columns]
    order.extend(column for column in matrix.columns if column not in order)
    matrix = matrix[order]
    matrix.plot.bar(ax=axes, stacked=True, width=.82, color=[palette[index % len(palette)] for index in range(len(order))], legend=spec.show_legend)
    axes.set_ylim(0, 1)
    axes.yaxis.set_major_formatter(PercentFormatter(1.0))
    axes.set_ylabel(ylabel)
    axes.set_xlabel(spec.x_column)
    axes.tick_params(axis="x", rotation=35, labelsize=spec.font_size)
    if spec.show_legend:
        axes.legend(title=spec.color_field, frameon=False, fontsize=spec.font_size, bbox_to_anchor=(1.02, 1), loc="upper left")


def _ecology_alpha_diversity(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    required = [spec.ecology_sample_column, spec.ecology_metric_column, spec.y_column]
    if any(not column or column not in dataframe.columns for column in required):
        raise ValueError("α 多样性图需要样品、指标和值字段。")
    if spec.group_column and spec.group_column not in dataframe.columns:
        raise ValueError(f"α 多样性图的分组字段不存在：{spec.group_column}")
    columns = required + ([spec.group_column] if spec.group_column and spec.group_column not in required else [])
    frame = dataframe[columns].copy()
    if frame.isna().any().any():
        raise ValueError("α 多样性图的样品、指标、值和分组字段不能包含缺失值。")
    if not spec.ecology_metric:
        raise ValueError("请选择一个已有的 α 多样性指标。")
    frame = frame[frame[spec.ecology_metric_column].astype(str) == spec.ecology_metric]
    if frame.empty:
        raise ValueError("所选 α 多样性指标没有可用记录。")
    if not pd.api.types.is_numeric_dtype(frame[spec.y_column]):
        raise ValueError("α 多样性值字段必须为数值列。")
    values = frame[spec.y_column].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("α 多样性值必须是有限数值。")
    sample_names = frame[spec.ecology_sample_column].astype(str).str.strip()
    if sample_names.eq("").any():
        raise ValueError("α 多样性样品名称不能为空。")
    if sample_names.duplicated().any():
        raise ValueError("同一个样品在所选 α 多样性指标中只能出现一行。")
    grouping = spec.group_column if spec.group_column and spec.group_column in frame.columns else None
    frame["__plot_group"] = frame[grouping].astype(str) if grouping else "全部样品"
    groups = list(dict.fromkeys(frame["__plot_group"].tolist()))
    if len(groups) > len(palette):
        raise ValueError(f"α 多样性分组数量超过当前色板容量（{len(palette)}）。")
    positions = np.arange(1, len(groups) + 1, dtype=float)
    series = [frame.loc[frame["__plot_group"] == group, spec.y_column].to_numpy(dtype=float) for group in groups]
    box = axes.boxplot(series, positions=positions, widths=.56, patch_artist=True, showfliers=False)
    for index, patch in enumerate(box["boxes"]):
        patch.set_facecolor(palette[index % len(palette)])
        patch.set_alpha(.72)
    rng = np.random.default_rng(0)
    for index, (group, group_values) in enumerate(zip(groups, series)):
        jitter = rng.uniform(-.12, .12, size=len(group_values))
        axes.scatter(np.full(len(group_values), positions[index]) + jitter, group_values, s=30, color=palette[index % len(palette)], label=group if grouping else None, edgecolors="white", linewidths=.7, zorder=3)
    axes.set_xticks(positions, groups)
    axes.set_xlabel(grouping or "样品组")
    axes.set_ylabel(spec.ecology_metric)
    if grouping and spec.show_legend:
        axes.legend(title=grouping, frameon=False, fontsize=spec.font_size, bbox_to_anchor=(1.02, 1), loc="upper left")
    axes.set_title(spec.title or f"{spec.ecology_metric} diversity", loc="left", fontweight="bold")


def _ecology_beta_ordination(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    required = [spec.ecology_sample_column, spec.x_column, spec.y_column]
    if any(not column or column not in dataframe.columns for column in required):
        raise ValueError("β 多样性图需要样品、第一轴和第二轴字段。")
    if spec.group_column and spec.group_column not in dataframe.columns:
        raise ValueError(f"β 多样性图的分组字段不存在：{spec.group_column}")
    columns = required + ([spec.group_column] if spec.group_column and spec.group_column not in required else [])
    frame = dataframe[columns].copy()
    if frame.isna().any().any():
        raise ValueError("β 多样性图的样品、坐标和分组字段不能包含缺失值。")
    if not pd.api.types.is_numeric_dtype(frame[spec.x_column]) or not pd.api.types.is_numeric_dtype(frame[spec.y_column]):
        raise ValueError("β 多样性坐标字段必须为数值列。")
    coordinates = frame[[spec.x_column, spec.y_column]].to_numpy(dtype=float)
    if not np.isfinite(coordinates).all():
        raise ValueError("β 多样性坐标必须是有限数值。")
    sample_names = frame[spec.ecology_sample_column].astype(str).str.strip()
    if sample_names.eq("").any():
        raise ValueError("β 多样性样品名称不能为空。")
    if sample_names.duplicated().any():
        raise ValueError("β 多样性排序结果中样品名称必须唯一。")
    grouping = spec.group_column if spec.group_column and spec.group_column in frame.columns else None
    frame["__plot_group"] = frame[grouping].astype(str) if grouping else "全部样品"
    groups = list(dict.fromkeys(frame["__plot_group"].tolist()))
    if len(groups) > len(palette):
        raise ValueError(f"β 多样性分组数量超过当前色板容量（{len(palette)}）。")
    for index, group in enumerate(groups):
        subset = frame[frame["__plot_group"] == group]
        axes.scatter(subset[spec.x_column], subset[spec.y_column], s=54, color=palette[index % len(palette)], label=group, edgecolors="white", linewidths=.7)
        for _, row in subset.iterrows():
            axes.annotate(str(row[spec.ecology_sample_column]), (row[spec.x_column], row[spec.y_column]), xytext=(4, 4), textcoords="offset points", fontsize=max(7, spec.font_size - 2), color="#6d7771")
    if spec.show_legend:
        axes.legend(title=grouping, frameon=False, fontsize=spec.font_size, bbox_to_anchor=(1.02, 1), loc="upper left")
    axes.set_xlabel(spec.x_column)
    axes.set_ylabel(spec.y_column)
    axes.set_title(spec.title or "β diversity ordination", loc="left", fontweight="bold")

def _ecology_ordination_biplot(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    if len(dataframe) > 500:
        raise ValueError("排序双图最多支持 500 行。")
    required = [spec.ecology_sample_column, spec.ecology_entity_type_column, spec.x_column, spec.y_column]
    if any(not column or column not in dataframe.columns for column in required):
        raise ValueError("排序双图需要 entity、entity_type、axis_1 和 axis_2 字段。")
    if spec.group_column and spec.group_column not in dataframe.columns:
        raise ValueError(f"排序双图的分组字段不存在：{spec.group_column}")
    grouping = spec.group_column if spec.group_column and spec.group_column in dataframe.columns else None
    columns = required + ([grouping] if grouping and grouping not in required else [])
    frame = dataframe[columns].copy()
    if frame[[spec.ecology_sample_column, spec.ecology_entity_type_column, spec.x_column, spec.y_column]].isna().any().any():
        raise ValueError("排序双图的实体、类型和坐标字段不能包含缺失值。")
    types = frame[spec.ecology_entity_type_column].astype(str).str.strip()
    if not types.isin(["sample", "taxon"]).all():
        raise ValueError("entity_type 只能是 sample 或 taxon。")
    if not pd.api.types.is_numeric_dtype(frame[spec.x_column]) or not pd.api.types.is_numeric_dtype(frame[spec.y_column]):
        raise ValueError("排序坐标字段必须为数值列。")
    if not np.isfinite(frame[[spec.x_column, spec.y_column]].to_numpy(dtype=float)).all():
        raise ValueError("排序坐标必须是有限数值。")
    frame["__entity"] = frame[spec.ecology_sample_column].astype(str).str.strip()
    if frame["__entity"].eq("").any() or frame.duplicated([spec.ecology_entity_type_column, "__entity"]).any():
        raise ValueError("同一实体类型内的名称必须非空且唯一。")
    samples = frame[types == "sample"].copy()
    taxa = frame[types == "taxon"].copy()
    if len(samples) > 300 or len(taxa) > 200:
        raise ValueError("排序双图最多支持 300 个样品和 200 个 taxon 向量。")
    if len(samples) < 2 or taxa.empty:
        raise ValueError("排序双图至少需要 2 个 sample 和 1 个 taxon 向量。")
    groups = list(dict.fromkeys(samples[grouping].astype(str).tolist())) if grouping else ["全部样品"]
    if len(groups) > len(palette):
        raise ValueError(f"样品分组数量超过当前色板容量（{len(palette)}）。")
    if grouping:
        samples["__group"] = samples[grouping].astype(str)
    else:
        samples["__group"] = "全部样品"
    for index, group in enumerate(groups):
        subset = samples[samples["__group"] == group]
        axes.scatter(subset[spec.x_column], subset[spec.y_column], s=58, color=palette[index % len(palette)], label=group, edgecolors="white", linewidths=.7, zorder=3)
        for _, row in subset.iterrows():
            axes.annotate(row["__entity"], (row[spec.x_column], row[spec.y_column]), xytext=(4, 4), textcoords="offset points", fontsize=max(7, spec.font_size - 2), color="#6d7771")
    for _, row in taxa.iterrows():
        axes.annotate("", xy=(row[spec.x_column], row[spec.y_column]), xytext=(0, 0), arrowprops={"arrowstyle": "->", "color": "#b48a4a", "lw": spec.line_width, "alpha": .82})
        axes.annotate(row["__entity"], (row[spec.x_column], row[spec.y_column]), xytext=(4, 3), textcoords="offset points", fontsize=max(7, spec.font_size - 2), color="#8d6b35")
    if spec.show_legend and grouping:
        axes.legend(title=grouping, frameon=False, fontsize=spec.font_size, bbox_to_anchor=(1.02, 1), loc="upper left")
    axes.axhline(0, color="#c8c0b2", lw=.7, zorder=0); axes.axvline(0, color="#c8c0b2", lw=.7, zorder=0)
    axes.set_xlabel(spec.x_column); axes.set_ylabel(spec.y_column)
    axes.set_title(spec.title or "Ordination biplot", loc="left", fontweight="bold")


def _ecology_environment_gradient(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    """Render existing environmental values/vectors without fitting or inference."""
    if len(dataframe) > 500:
        raise ValueError("环境关联图最多支持 500 行。")
    required = [spec.ecology_sample_column, spec.x_column, spec.y_column]
    if spec.ecology_environment_mode == "continuous_value":
        required.append(spec.ecology_environment_column)
    else:
        required.append(spec.ecology_entity_type_column)
    if any(not column or column not in dataframe.columns for column in required):
        raise ValueError("环境关联图需要样品/实体、二维坐标和环境字段。")
    if spec.group_column and spec.group_column not in dataframe.columns:
        raise ValueError(f"环境关联图的分组字段不存在：{spec.group_column}")
    columns = list(dict.fromkeys(required + ([spec.group_column] if spec.group_column else [])))
    frame = dataframe[columns].copy()
    if frame[required].isna().any().any():
        raise ValueError("环境关联图的字段不能包含缺失值。")
    if not pd.api.types.is_numeric_dtype(frame[spec.x_column]) or not pd.api.types.is_numeric_dtype(frame[spec.y_column]):
        raise ValueError("环境关联图的二维坐标必须为数值列。")
    if not np.isfinite(frame[[spec.x_column, spec.y_column]].to_numpy(dtype=float)).all():
        raise ValueError("环境关联图的二维坐标必须是有限数值。")
    frame["__entity"] = frame[spec.ecology_sample_column].astype(str).str.strip()
    if frame["__entity"].eq("").any():
        raise ValueError("环境关联图的样品/实体名称不能为空。")
    if frame.duplicated([spec.ecology_sample_column]).any():
        raise ValueError("环境关联图的样品/实体名称必须唯一。")
    if spec.ecology_environment_mode == "continuous_value":
        if not pd.api.types.is_numeric_dtype(frame[spec.ecology_environment_column]):
            raise ValueError("环境值字段必须为数值列。")
        values = frame[spec.ecology_environment_column].to_numpy(dtype=float)
        if not np.isfinite(values).all():
            raise ValueError("环境值必须是有限数值。")
        samples = frame
        if len(samples) > 300:
            raise ValueError("连续环境值模式最多支持 300 个样品。")
        cmap_name = continuous_palette(spec.palette_id)
        norm = Normalize(vmin=float(values.min()), vmax=float(values.max())) if values.min() != values.max() else Normalize(vmin=float(values.min()) - 1, vmax=float(values.max()) + 1)
        scatter = axes.scatter(samples[spec.x_column], samples[spec.y_column], c=values, cmap=cmap_name, norm=norm, s=58, edgecolors="white", linewidths=.7, zorder=3)
        axes.figure.colorbar(scatter, ax=axes, label=spec.ecology_environment_column)
        if spec.group_column:
            groups = samples[spec.group_column].astype(str)
            if groups.nunique() > len(palette):
                raise ValueError(f"样品分组数量超过当前色板容量（{len(palette)}）。")
        axes.set_xlabel(spec.x_column); axes.set_ylabel(spec.y_column)
        axes.set_title(spec.title or "Environment gradient", loc="left", fontweight="bold")
        return
    types = frame[spec.ecology_entity_type_column].astype(str).str.strip()
    if not types.isin(["sample", "environment"]).all():
        raise ValueError("环境向量模式的实体类型只能是 sample 或 environment。")
    samples = frame[types == "sample"].copy()
    vectors = frame[types == "environment"].copy()
    if spec.group_column and samples[spec.group_column].isna().any():
        raise ValueError("环境关联图的样品分组字段不能包含缺失值。")
    if len(samples) < 2 or vectors.empty:
        raise ValueError("环境向量模式至少需要 2 个样品和 1 个环境向量。")
    if len(samples) > 300 or len(vectors) > 100:
        raise ValueError("环境向量模式最多支持 300 个样品和 100 个环境向量。")
    if spec.group_column:
        groups = list(dict.fromkeys(samples[spec.group_column].astype(str).tolist()))
        if len(groups) > len(palette):
            raise ValueError(f"样品分组数量超过当前色板容量（{len(palette)}）。")
        for index, group in enumerate(groups):
            subset = samples[samples[spec.group_column].astype(str) == group]
            axes.scatter(subset[spec.x_column], subset[spec.y_column], s=58, color=palette[index], label=group, edgecolors="white", linewidths=.7, zorder=3)
        if spec.show_legend:
            axes.legend(title=spec.group_column, frameon=False, fontsize=spec.font_size, bbox_to_anchor=(1.02, 1), loc="upper left")
    else:
        axes.scatter(samples[spec.x_column], samples[spec.y_column], s=58, color=palette[0], edgecolors="white", linewidths=.7, zorder=3)
    for _, row in samples.iterrows():
        axes.annotate(row["__entity"], (row[spec.x_column], row[spec.y_column]), xytext=(4, 4), textcoords="offset points", fontsize=max(7, spec.font_size - 2), color="#6d7771")
    for _, row in vectors.iterrows():
        axes.annotate("", xy=(row[spec.x_column], row[spec.y_column]), xytext=(0, 0), arrowprops={"arrowstyle": "->", "color": "#b48a4a", "lw": spec.line_width, "alpha": .85})
        axes.annotate(row["__entity"], (row[spec.x_column], row[spec.y_column]), xytext=(4, 3), textcoords="offset points", fontsize=max(7, spec.font_size - 2), color="#8d6b35")
    axes.axhline(0, color="#c8c0b2", lw=.7, zorder=0); axes.axvline(0, color="#c8c0b2", lw=.7, zorder=0)
    axes.set_xlabel(spec.x_column); axes.set_ylabel(spec.y_column)
    axes.set_title(spec.title or "Existing environmental vectors", loc="left", fontweight="bold")

def _ecology_time_series(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    if len(dataframe) > 5000:
        raise ValueError("生态时间序列最多支持 5000 行。")
    required = [spec.ecology_sample_column, spec.ecology_time_column, spec.ecology_value_column]
    optional = [column for column in (spec.group_column, spec.ecology_replicate_column, spec.ecology_error_column) if column]
    for col in required + optional:
        if not col or col not in dataframe.columns:
            raise ValueError(f"时间序列字段不存在：{col}。")
    frame = dataframe[list(dict.fromkeys(required + optional))].copy()
    if frame.isna().any().any():
        raise ValueError("时间序列已选字段不能包含缺失值。")
    text_columns = [spec.ecology_sample_column] + ([spec.group_column] if spec.group_column else []) + ([spec.ecology_replicate_column] if spec.ecology_replicate_column else [])
    if any(frame[column].astype(str).str.strip().eq("").any() for column in text_columns):
        raise ValueError("样品、分组和重复测量标识不能为空。")
    if not pd.api.types.is_numeric_dtype(frame[spec.ecology_time_column]) or not pd.api.types.is_numeric_dtype(frame[spec.ecology_value_column]):
        raise ValueError("时间和值字段必须为数值列。")
    numeric = [spec.ecology_time_column, spec.ecology_value_column] + ([spec.ecology_error_column] if spec.ecology_error_column else [])
    if not np.isfinite(frame[numeric].to_numpy(dtype=float)).all():
        raise ValueError("时间、数值和误差必须是有限数值。")
    if spec.ecology_error_column and (frame[spec.ecology_error_column] < 0).any():
        raise ValueError("对称误差值不能为负数。")
    groups = frame[spec.group_column].astype(str) if spec.group_column else pd.Series(["全部"] * len(frame), index=frame.index)
    names = list(dict.fromkeys(groups.tolist()))
    if len(names) > len(palette):
        raise ValueError(f"分组数量超过当前色板容量（{len(palette)}）。")
    track_column = spec.ecology_replicate_column or spec.ecology_sample_column
    duplicate_key = ([spec.group_column] if spec.group_column else []) + [track_column, spec.ecology_time_column]
    if frame.duplicated(duplicate_key).any():
        raise ValueError("同一轨迹在同一时间点存在重复观测，不会自动聚合。")
    for idx, group in enumerate(names):
        group_frame = frame[groups == group]
        tracks = list(dict.fromkeys(group_frame[track_column].astype(str).tolist()))
        for track_index, track in enumerate(tracks):
            subset = group_frame[group_frame[track_column].astype(str) == track].sort_values(spec.ecology_time_column)
            axes.plot(subset[spec.ecology_time_column], subset[spec.ecology_value_column], marker="o", lw=spec.line_width, color=palette[idx], alpha=.9, label=group if track_index == 0 else None)
            if spec.ecology_error_column:
                err = subset[spec.ecology_error_column].to_numpy(dtype=float)
                axes.fill_between(subset[spec.ecology_time_column], subset[spec.ecology_value_column]-err, subset[spec.ecology_value_column]+err, color=palette[idx], alpha=.14, linewidth=0)
    if spec.show_legend and spec.group_column: axes.legend(frameon=False, title=spec.group_column)
    axes.set_xlabel(spec.ecology_time_column); axes.set_ylabel(spec.ecology_value_column)
    axes.set_title(spec.title or "Ecology time series (raw observations)", loc="left", fontweight="bold")


def _ecology_spatial_points(axes: object, dataframe: pd.DataFrame, spec: ChartSpec, palette: tuple[str, ...]) -> None:
    """Plot user-supplied point coordinates without basemaps, reprojection, or spatial inference."""
    if len(dataframe) > 5000:
        raise ValueError("空间生态点位图最多支持 5000 行。")
    required = [spec.ecology_sample_column, spec.x_column, spec.y_column]
    optional = [spec.group_column] if spec.group_column else []
    for column in required + optional:
        if not column or column not in dataframe.columns:
            raise ValueError(f"空间生态字段不存在：{column}。")
    frame = dataframe[list(dict.fromkeys(required + optional))].copy()
    if frame.isna().any().any():
        raise ValueError("空间生态已选字段不能包含缺失值。")
    identifiers = frame[spec.ecology_sample_column].astype(str).str.strip()
    if identifiers.eq("").any():
        raise ValueError("空间生态样品/点位标识不能为空。")
    if identifiers.duplicated().any():
        raise ValueError("空间生态样品/点位标识必须唯一；不会自动合并重复记录。")
    if not pd.api.types.is_numeric_dtype(frame[spec.x_column]) or not pd.api.types.is_numeric_dtype(frame[spec.y_column]):
        raise ValueError("空间生态 X/Y 坐标必须为数值列。")
    coordinates = frame[[spec.x_column, spec.y_column]].to_numpy(dtype=float)
    if not np.isfinite(coordinates).all():
        raise ValueError("空间生态坐标必须是有限数值。")

    if spec.ecology_spatial_coordinate_mode == "geographic_wgs84":
        if spec.ecology_spatial_unit != "degrees" or spec.ecology_spatial_reference.strip().upper() != "EPSG:4326":
            raise ValueError("WGS84 经纬度模式必须使用 EPSG:4326 和 degrees 单位。")
        if ((coordinates[:, 0] < -180) | (coordinates[:, 0] > 180)).any():
            raise ValueError("经度必须位于 -180 到 180 之间；不会自动交换经纬度。")
        if ((coordinates[:, 1] < -90) | (coordinates[:, 1] > 90)).any():
            raise ValueError("纬度必须位于 -90 到 90 之间；不会自动交换经纬度。")
        x_label, y_label = "经度 (°)", "纬度 (°)"
        subtitle = "WGS84 points (no basemap or reprojection)"
    else:
        reference = spec.ecology_spatial_reference.strip()
        if not reference:
            raise ValueError("平面坐标模式必须填写坐标参考说明。")
        if spec.ecology_spatial_unit == "degrees":
            raise ValueError("平面坐标模式请选择米、千米或任意单位。")
        unit_label = {"m": "m", "km": "km", "arbitrary": "任意单位"}[spec.ecology_spatial_unit]
        x_label, y_label = f"{spec.x_column} ({unit_label})", f"{spec.y_column} ({unit_label})"
        subtitle = f"Planar points · {reference}"

    if spec.group_column:
        groups = frame[spec.group_column].astype(str).str.strip()
        if groups.eq("").any():
            raise ValueError("空间生态分组字段不能为空。")
        observed = list(dict.fromkeys(groups.tolist()))
        names = [name for name in spec.category_order if name in observed]
        names.extend(name for name in observed if name not in names)
        if len(names) > len(palette):
            raise ValueError(f"空间生态分组数量超过当前色板容量（{len(palette)}）。")
        for index, group in enumerate(names):
            subset = frame[groups == group]
            axes.scatter(subset[spec.x_column], subset[spec.y_column], s=max(28, spec.point_size * 4), color=palette[index], label=group, edgecolors="white", linewidths=.7, zorder=3)
        if spec.show_legend:
            axes.legend(title=spec.group_column, frameon=False, fontsize=spec.font_size, bbox_to_anchor=(1.02, 1), loc="upper left")
    else:
        axes.scatter(frame[spec.x_column], frame[spec.y_column], s=max(28, spec.point_size * 4), color=palette[0], edgecolors="white", linewidths=.7, zorder=3)
    axes.grid(axis="x", color=get_theme(spec.theme_id).grid_color, linewidth=spec.line_width * .6)
    axes.set_aspect("equal", adjustable="datalim")
    axes.set_xlabel(x_label)
    axes.set_ylabel(y_label)
    axes.set_title(spec.title or subtitle, loc="left", fontweight="bold")


def resolve_figure(spec: FigureSpec, frames: list[object]) -> FigureSpec:
    """Freeze shared categorical domains so subsets keep the same group colors."""
    domains = {}
    for panel, frame in zip(spec.panels, frames):
        field = panel.group_column if panel.chart_type in ("scatter", "line", "violin", "dotplot", "ecology_spatial_points") else panel.color_field if panel.chart_type == "embedding_categorical" else None
        if not field:
            continue
        if panel.chart_type in ("violin", "dotplot", "embedding_categorical"):
            if not hasattr(frame, "obs") or field not in frame.obs:
                raise ValueError("单细胞分组或着色字段不存在。")
            values = frame.obs[field].astype(object).where(frame.obs[field].notna(), "缺失").astype(str).unique()
        else:
            if panel.chart_type not in ("scatter", "line", "ecology_spatial_points") or field not in frame:
                continue
            values = frame[field].astype(object).where(frame[field].notna(), "缺失").astype(str).unique()
        key = (field, panel.palette_id)
        domain = domains.setdefault(key, set())
        domain.update(panel.category_order)
        domain.update(str(value) for value in values)
    panels = []
    for panel in spec.panels:
        field = panel.group_column if panel.chart_type in ("scatter", "line", "violin", "dotplot", "ecology_spatial_points") else panel.color_field if panel.chart_type == "embedding_categorical" else None
        key = (field, panel.palette_id)
        order = sorted(domains.get(key, []))
        if len(order) > len(_palette(panel, get_theme(spec.theme_id).palette)):
            raise ValueError("拼版类别数量超过色板容量，请减少类别或拆分图表。")
        panels.append(panel.model_copy(update={"category_order": order}))
    resolved = spec.model_copy(update={"panels": panels})
    if resolved.spec_version != "1.0" and resolved.legend_mode == "shared":
        signatures = set()
        for panel in resolved.panels:
            if not panel.show_legend:
                continue
            field = panel.group_column if panel.chart_type in ("scatter", "line", "violin", "dotplot", "ecology_spatial_points") else panel.color_field if panel.chart_type == "embedding_categorical" else None
            if field:
                signatures.add((field, tuple(panel.category_order), panel.palette_id, panel.palette_version))
        if len(signatures) > 1:
            raise ValueError("共享图例要求所有子图使用相同分组字段、类别顺序、色板和色板版本；请改用逐图图例或统一设置。")
    return resolved
