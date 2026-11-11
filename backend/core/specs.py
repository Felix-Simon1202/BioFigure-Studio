"""Stable, validated specifications for the phase 2 figure workflow."""

import math

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.themes.palettes import PaletteId


CHART_SPEC_VERSION = "1.0"
SvgTextMode = Literal["outline", "editable"]


class ChartSpec(BaseModel):
    """A portable scatter-plot instruction with no executable user input."""

    spec_version: Literal["1.0", "1.1", "1.2"] = CHART_SPEC_VERSION
    chart_type: Literal[
        "scatter", "bar", "line", "box", "heatmap",
        "embedding_categorical", "embedding_continuous", "feature", "violin", "dotplot",
        "spatial_categorical", "spatial_continuous", "spatial_feature",
        "genome_tracks", "circos", "dna_features", "r_ggplot", "ecology_composition", "ecology_alpha_diversity", "ecology_beta_ordination", "ecology_ordination_biplot", "ecology_environment_gradient", "ecology_time_series", "ecology_spatial_points",
    ] = "scatter"
    dataset_id: str = Field(min_length=1, max_length=80)
    x_column: str = Field(default="", max_length=128)
    y_column: str = Field(default="", max_length=128)
    group_column: str | None = Field(default=None, max_length=128)
    coordinate_key: str = Field(default="X_umap", max_length=128)
    color_field: str | None = Field(default=None, max_length=128)
    genes: list[str] = Field(default_factory=list, max_length=20)
    expression_source: Literal["X", "raw", "layer"] = "X"
    expression_layer: str | None = Field(default=None, max_length=128)
    transform: Literal["none", "log1p"] = "none"
    ecology_value_mode: Literal["relative_fraction", "count"] = "relative_fraction"
    ecology_sample_column: str = Field(default="sample", max_length=128)
    ecology_metric_column: str = Field(default="metric", max_length=128)
    ecology_metric: str = Field(default="", max_length=128)
    ecology_entity_type_column: str = Field(default="entity_type", max_length=128)
    ecology_environment_mode: Literal["continuous_value", "existing_vector"] = "continuous_value"
    ecology_environment_column: str = Field(default="", max_length=128)
    ecology_time_column: str = Field(default="time", max_length=128)
    ecology_value_column: str = Field(default="value", max_length=128)
    ecology_replicate_column: str = Field(default="", max_length=128)
    ecology_error_column: str = Field(default="", max_length=128)
    ecology_spatial_coordinate_mode: Literal["geographic_wgs84", "planar"] = "geographic_wgs84"
    ecology_spatial_reference: str = Field(default="EPSG:4326", max_length=128)
    ecology_spatial_unit: Literal["degrees", "m", "km", "arbitrary"] = "degrees"
    point_size: float = Field(default=8, ge=1, le=100)
    title: str = Field(default="", max_length=160)
    theme_id: Literal["scientific_clear", "modern_soft", "high_contrast"] = "scientific_clear"
    palette_id: PaletteId = "theme"
    category_order: list[str] = Field(default_factory=list, max_length=100)
    palette_version: Literal["1.0"] = "1.0"
    width_mm: float = Field(default=160, ge=60, le=300)
    height_mm: float = Field(default=105, ge=60, le=300)
    dpi: int = Field(default=300, ge=72, le=600)
    font_size: float = Field(default=10, ge=7, le=24)
    line_width: float = Field(default=1.2, ge=0.5, le=5)
    show_legend: bool = True
    svg_text_mode: SvgTextMode = "outline"

    @field_validator(
        "dataset_id", "x_column", "y_column", "group_column", "coordinate_key",
        "color_field", "expression_layer", "ecology_sample_column", "ecology_metric_column", "ecology_metric", "ecology_entity_type_column", "ecology_environment_column", "ecology_time_column", "ecology_value_column", "ecology_replicate_column", "ecology_error_column", "ecology_spatial_reference",
    )
    @classmethod
    def reject_control_characters(cls, value: str | None) -> str | None:
        if value is not None and any(character in value for character in "\r\n\x00"):
            raise ValueError("field names must not contain control characters")
        return value

    @field_validator("genes")
    @classmethod
    def reject_invalid_genes(cls, values: list[str]) -> list[str]:
        if any(not value or len(value) > 128 or any(character in value for character in "\r\n\x00") for value in values):
            raise ValueError("gene names must be non-empty and contain no control characters")
        return values

    @model_validator(mode="after")
    def validate_raster_budget(self):
        pixels_w = round(self.width_mm / 25.4 * self.dpi)
        pixels_h = round(self.height_mm / 25.4 * self.dpi)
        if pixels_w * pixels_h > 16_000_000:
            raise ValueError("图表栅格尺寸超过本机交互上限（1,600 万像素）；请降低 DPI 或毫米尺寸。")
        return self


class SavedChartConfig(BaseModel):
    """Named, versioned configuration that can be regenerated locally."""

    config_version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=1, max_length=80)
    chart: ChartSpec


class FigureImageCrop(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class FigureImagePanel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_id: str = Field(pattern=r"^[0-9a-f]{32}$")
    crop: FigureImageCrop | None = None
    x_um_per_pixel: float = Field(gt=0, allow_inf_nan=False)
    scale_bar_um: float = Field(gt=0, allow_inf_nan=False)
    scale_bar_color: Literal["white", "black"] = "white"


class FigureSpec(BaseModel):
    spec_version: Literal["1.0", "2.0", "2.1"] = "1.0"
    panels: list[ChartSpec] = Field(min_length=1, max_length=4)
    image_panel: FigureImagePanel | None = None
    columns: int = Field(default=2, ge=1, le=2)
    labels: Literal["upper", "lower", "none"] = "upper"
    theme_id: Literal["scientific_clear", "modern_soft", "high_contrast"] = "scientific_clear"
    template_id: Literal["custom", "single_column", "double_column", "square_grid"] = "custom"
    width_mm: float = Field(default=280, ge=60, le=420)
    height_mm: float = Field(default=210, ge=60, le=420)
    margin_top_mm: float = Field(default=12, ge=2, le=50)
    margin_right_mm: float = Field(default=12, ge=2, le=50)
    margin_bottom_mm: float = Field(default=14, ge=2, le=50)
    margin_left_mm: float = Field(default=16, ge=2, le=50)
    panel_gap_mm: float = Field(default=8, ge=2, le=30)
    label_position: Literal["inside", "outside"] = "inside"
    label_font_size: float = Field(default=11, ge=7, le=24)
    legend_mode: Literal["per_panel", "shared", "none"] = "per_panel"
    legend_position: Literal["right", "bottom"] = "right"
    font_family: Literal["noto_sans_sc"] = "noto_sans_sc"
    font_embedding: Literal["required"] = "required"
    svg_text_mode: SvgTextMode = "outline"
    palette_version: Literal["1.0"] = "1.0"
    dpi: int = Field(default=150, ge=72, le=1200)

    @property
    def panel_count(self) -> int:
        return len(self.panels) + (self.image_panel is not None)

    @model_validator(mode="after")
    def validate_publication_layout(self):
        if self.spec_version == "2.1":
            if self.image_panel is None or len(self.panels) != 1:
                raise ValueError("混合图版需要恰好一张科研图像和一张统计图。")
            if self.panels[0].chart_type not in {"scatter", "bar", "line", "box", "heatmap"}:
                raise ValueError("混合图版首版支持散点、柱状、折线、箱线和热图。")
        elif self.image_panel is not None:
            raise ValueError("混合图版需要 FigureSpec 2.1。")
        pixels_w = round(self.width_mm / 25.4 * self.dpi)
        pixels_h = round(self.height_mm / 25.4 * self.dpi)
        if pixels_w > 20_000 or pixels_h > 20_000 or pixels_w * pixels_h > 100_000_000:
            raise ValueError("图版栅格尺寸超过安全上限（单边 20,000 像素、总计 1 亿像素），请降低 DPI 或毫米尺寸。")
        if pixels_w * pixels_h > 16_000_000:
            raise ValueError("图版栅格尺寸超过本机交互上限（1,600 万像素），请降低 DPI 或毫米尺寸。")
        if self.spec_version == "1.0":
            return self
        usable_width = self.width_mm - self.margin_left_mm - self.margin_right_mm - self.panel_gap_mm * (self.columns - 1)
        rows = (self.panel_count + self.columns - 1) // self.columns
        usable_height = self.height_mm - self.margin_top_mm - self.margin_bottom_mm - self.panel_gap_mm * (rows - 1)
        if usable_width <= 0 or usable_height <= 0 or usable_width / self.columns < 30 or usable_height / rows < 30:
            raise ValueError("图版边距或面板间距过大，每个子图至少需要 30 × 30 mm；请减小边距/间距或增大画布。")
        if any(panel.palette_version != self.palette_version for panel in self.panels):
            raise ValueError("子图色板版本与图版色板版本不一致，请统一后再导出。")
        return self


class SavedFigureConfig(BaseModel):
    config_version: Literal["1.0"] = "1.0"
    name: str = Field(min_length=1, max_length=80)
    figure: FigureSpec


class ProjectDocument(BaseModel):
    """Portable project manifest stored inside a local .bfsproj archive."""

    project_version: Literal["1.0", "1.1", "1.2"] = "1.1"
    name: str = Field(min_length=1, max_length=80)
    chart: ChartSpec
    figure: FigureSpec | None = None
    image_filename: str | None = Field(default=None, min_length=1, max_length=200)
    image_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    data_mode: Literal["embedded"] = "embedded"
    data_filename: str = Field(min_length=1, max_length=180)
    data_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    data_kind: Literal["table", "single_cell", "dna", "genome_track", "omics_manifest"]
    palette_mapping: dict[str, str] = Field(default_factory=dict)
    transformations: list[str] = Field(default_factory=list, max_length=20)
    plugin_versions: dict[str, str] = Field(default_factory=dict)
    font_provenance: dict[str, str] = Field(default_factory=dict)
    export_checks: dict[str, object] = Field(default_factory=dict)


    @model_validator(mode="after")
    def validate_mixed_figure_source(self):
        has_image_panel = bool(self.figure and self.figure.image_panel)
        if self.project_version == "1.2":
            if not (has_image_panel and self.image_filename and self.image_sha256):
                raise ValueError("混合图版项目缺少源图或摘要。")
        elif has_image_panel or self.image_filename or self.image_sha256:
            raise ValueError("混合图版项目需要项目版本 1.2。")
        return self


class IllustrationBase(BaseModel):
    model_config = ConfigDict(extra="forbid")


class IllustrationCanvas(IllustrationBase):
    width: int = Field(default=960, ge=320, le=2400)
    height: int = Field(default=640, ge=240, le=1800)
    background: str = Field(default="#ffffff", pattern=r"^#[0-9a-fA-F]{6}$")
    grid_size: int = Field(default=20, ge=4, le=100)
    show_grid: bool = True
    snap_to_grid: bool = True


class IllustrationNode(IllustrationBase):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    component_id: Literal[
        "cell_generic", "nucleus_generic", "dna_helix", "rna_single",
        "protein_generic", "receptor_membrane", "ligand_generic", "drug_tablet",
    ]
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(ge=24, le=800)
    height: float = Field(ge=24, le=800)
    rotation: float = Field(default=0, ge=-180, le=180)
    z_index: int = Field(default=0, ge=0, le=999)
    label: str = Field(default="", max_length=200)
    fill: str = Field(default="#d7ece7", pattern=r"^#[0-9a-fA-F]{6}$")
    text_color: str = Field(default="#26332f", pattern=r"^#[0-9a-fA-F]{6}$")
    scientific_status: Literal["illustrative", "verified", "needs_review"] = "illustrative"
    entity_type: Literal["context", "molecule", "ligand", "receptor", "protein", "gene", "transcript", "drug"] = "context"
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)
    section_id: str | None = None

    @field_validator("label")
    @classmethod
    def reject_node_control_characters(cls, value: str) -> str:
        if any(character in value for character in "\r\n\x00"):
            raise ValueError("illustration text must not contain control characters")
        return value


class IllustrationEdgeEndpoint(IllustrationBase):
    node_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    anchor_id: Literal["top", "right", "bottom", "left"]


class IllustrationEdge(IllustrationBase):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    source: IllustrationEdgeEndpoint
    target: IllustrationEdgeEndpoint
    relation: Literal["normal", "association", "activation", "inhibition", "binding", "translocation", "expression"] = "association"
    routing: Literal["orthogonal"] = "orthogonal"
    label: str = Field(default="", max_length=200)
    scientific_status: Literal["illustrative", "verified", "needs_review"] = "needs_review"
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class IllustrationEvidence(IllustrationBase):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    evidence_type: Literal["literature", "experiment", "database_record", "user_note"]
    citation: str = Field(min_length=1, max_length=500)
    locator: str = Field(default="", max_length=200)
    note: str = Field(default="", max_length=200)
    added_by: str = Field(min_length=1, max_length=200)
    date: str = Field(pattern=r"^\d{4}-\d{2}-\d{2}$")

    @field_validator("citation", "locator", "note", "added_by")
    @classmethod
    def reject_evidence_control_characters(cls, value: str) -> str:
        if any(character in value for character in "\r\n\x00"):
            raise ValueError("illustration evidence must not contain control characters")
        return value


class IllustrationGroup(IllustrationBase):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    name: str = Field(min_length=1, max_length=80)
    node_ids: list[str] = Field(min_length=1, max_length=200)
    edge_ids: list[str] = Field(default_factory=list, max_length=400)


class IllustrationProvenance(IllustrationBase):
    registry_version: Literal["1.0"] = "1.0"
    component_ids: list[str] = Field(default_factory=list, max_length=8)
    note: str = Field(default="BioFigure Studio 原创组件；科学关系需由用户核实。", max_length=300)
    mechanism_schema_version: Literal["1.0"] | None = None
    composition_schema_version: Literal["1.0"] | None = None


class IllustrationSection(IllustrationBase):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    kind: Literal["panel", "step"]
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    x: float = Field(ge=0)
    y: float = Field(ge=0)
    width: float = Field(ge=100)
    height: float = Field(ge=100)
    scientific_status: Literal["illustrative", "verified", "needs_review"] = "illustrative"
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("title", "description")
    @classmethod
    def reject_section_control_characters(cls, value: str) -> str:
        if any(character in value for character in "\r\n\x00"):
            raise ValueError("illustration section text must not contain control characters")
        return value


class IllustrationFlowLink(IllustrationBase):
    id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    source_section_id: str
    target_section_id: str
    label: str = Field(default="", max_length=120)

    @field_validator("label")
    @classmethod
    def reject_flow_control_characters(cls, value: str) -> str:
        if any(character in value for character in "\r\n\x00"):
            raise ValueError("illustration flow text must not contain control characters")
        return value


class IllustrationSpec(IllustrationBase):
    """Portable, non-executable phase 7A illustration document."""

    spec_version: Literal["1.0", "1.1", "1.2", "1.3"] = "1.3"
    document_kind: Literal["mechanism", "graphical_abstract", "experimental_workflow"] = "mechanism"
    title: str = Field(default="未命名生物图示", min_length=1, max_length=120)
    canvas: IllustrationCanvas = Field(default_factory=IllustrationCanvas)
    nodes: list[IllustrationNode] = Field(default_factory=list, max_length=200)
    edges: list[IllustrationEdge] = Field(default_factory=list, max_length=400)
    groups: list[IllustrationGroup] = Field(default_factory=list, max_length=100)
    sections: list[IllustrationSection] = Field(default_factory=list, max_length=8)
    flow_links: list[IllustrationFlowLink] = Field(default_factory=list, max_length=16)
    evidence_records: list[IllustrationEvidence] = Field(default_factory=list, max_length=300)
    provenance: IllustrationProvenance = Field(default_factory=IllustrationProvenance)

    @model_validator(mode="after")
    def validate_illustration_references(self):
        node_ids = [node.id for node in self.nodes]
        edge_ids = [edge.id for edge in self.edges]
        group_ids = [group.id for group in self.groups]
        if len(node_ids) != len(set(node_ids)) or len(edge_ids) != len(set(edge_ids)) or len(group_ids) != len(set(group_ids)):
            raise ValueError("图示中的节点、连线或分组 ID 重复。")
        known_nodes = set(node_ids)
        known_edges = set(edge_ids)
        evidence_ids = [evidence.id for evidence in self.evidence_records]
        if len(evidence_ids) != len(set(evidence_ids)):
            raise ValueError("证据记录 ID 重复。")
        known_evidence = set(evidence_ids)
        for node in self.nodes:
            radians = node.rotation * math.pi / 180
            rotated_width = abs(node.width * math.cos(radians)) + abs(node.height * math.sin(radians))
            rotated_height = abs(node.width * math.sin(radians)) + abs(node.height * math.cos(radians))
            left = node.x + (node.width - rotated_width) / 2
            top = node.y + (node.height - rotated_height) / 2
            if left < -0.001 or top < -0.001 or left + rotated_width > self.canvas.width + 0.001 or top + rotated_height > self.canvas.height + 0.001:
                raise ValueError("旋转后的图示节点超出画布边界。")
        for edge in self.edges:
            if edge.source.node_id not in known_nodes or edge.target.node_id not in known_nodes:
                raise ValueError("图示连线引用了不存在的节点。")
        if self.spec_version in ("1.2", "1.3"):
            if self.provenance.mechanism_schema_version != "1.0":
                raise ValueError("机制图必须声明 mechanism_schema_version 1.0。")
            for node in self.nodes:
                if not set(node.evidence_ids).issubset(known_evidence):
                    raise ValueError("节点引用了不存在的证据记录。")
                if node.scientific_status == "verified" and not node.evidence_ids:
                    raise ValueError("用户已核实的节点必须引用至少一条证据。")
            for edge in self.edges:
                if edge.relation == "normal":
                    raise ValueError("IllustrationSpec 1.2 必须使用受控机制关系。")
                if not set(edge.evidence_ids).issubset(known_evidence):
                    raise ValueError("关系引用了不存在的证据记录。")
                if edge.scientific_status == "verified" and not edge.evidence_ids:
                    raise ValueError("用户已核实的关系必须引用至少一条证据。")
        if self.spec_version == "1.3":
            if self.provenance.composition_schema_version != "1.0":
                raise ValueError("图形摘要/流程项目必须声明 composition_schema_version 1.0。")
            if self.document_kind == "mechanism" and (self.sections or self.flow_links):
                raise ValueError("机制图不能包含面板、步骤或流程箭头。")
            if self.document_kind == "graphical_abstract" and len(self.sections) > 6:
                raise ValueError("图形摘要最多六个面板。")
            if self.document_kind != "mechanism" and len(self.sections) == 1:
                raise ValueError("摘要或流程至少需要两个分区。")
            section_ids: set[str] = set()
            for section in self.sections:
                if section.id in section_ids or section.kind != ("panel" if self.document_kind == "graphical_abstract" else "step"):
                    raise ValueError("面板/步骤 ID 重复或模式不匹配。")
                if section.x + section.width > self.canvas.width or section.y + section.height > self.canvas.height:
                    raise ValueError("面板/步骤超出画布。")
                if not set(section.evidence_ids).issubset(known_evidence):
                    raise ValueError("面板/步骤引用了不存在的证据。")
                if section.scientific_status == "verified" and not section.evidence_ids:
                    raise ValueError("用户已核实的面板/步骤必须引用证据。")
                chars = max(8, int((section.width - 32) // 14))
                if (len(section.title) + (3 if section.kind == "step" else 0)) * 18 > section.width - 36 or math.ceil(len(section.description) / chars) > math.floor((section.height - 85) / 20):
                    raise ValueError("面板/步骤文字超出固定版式。")
                for other in self.sections:
                    if other.id == section.id:
                        continue
                    if section.x < other.x + other.width and section.x + section.width > other.x and section.y < other.y + other.height and section.y + section.height > other.y:
                        raise ValueError("面板/步骤不能重叠。")
                section_ids.add(section.id)
            for node in self.nodes:
                if node.section_id is not None:
                    section = next((item for item in self.sections if item.id == node.section_id), None)
                    if section is None:
                        raise ValueError("节点引用了不存在的面板/步骤。")
                    radians = node.rotation * math.pi / 180
                    width = abs(node.width * math.cos(radians)) + abs(node.height * math.sin(radians))
                    height = abs(node.width * math.sin(radians)) + abs(node.height * math.cos(radians))
                    left = node.x + (node.width - width) / 2
                    top = node.y + (node.height - height) / 2
                    if left < section.x or top < section.y or left + width > section.x + section.width or top + height > section.y + section.height:
                        raise ValueError("节点必须完整位于所属面板/步骤内。")
            if self.document_kind != "experimental_workflow" and self.flow_links:
                raise ValueError("流程箭头只能用于实验流程图。")
            order = {section.id: index for index, section in enumerate(self.sections)}
            flow_ids: set[str] = set()
            flow_pairs: set[tuple[str, str]] = set()
            for link in self.flow_links:
                pair = (link.source_section_id, link.target_section_id)
                if link.id in flow_ids or pair in flow_pairs or pair[0] not in order or pair[1] not in order or order[pair[0]] >= order[pair[1]]:
                    raise ValueError("流程箭头 ID 重复、引用无效或方向违反步骤顺序。")
                flow_ids.add(link.id)
                flow_pairs.add(pair)
        grouped_nodes: set[str] = set()
        for group in self.groups:
            if not set(group.node_ids).issubset(known_nodes) or not set(group.edge_ids).issubset(known_edges):
                raise ValueError("图示分组包含不存在的对象。")
            if grouped_nodes.intersection(group.node_ids):
                raise ValueError("首版中一个节点最多属于一个分组。")
            grouped_nodes.update(group.node_ids)
        registered = set(self.provenance.component_ids)
        used = {node.component_id for node in self.nodes}
        if registered != used:
            raise ValueError("组件来源清单必须与实际使用的组件一致。")
        return self
