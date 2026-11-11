"""Offline product-AI boundary. No model, transport, or side effects live here."""

import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.core.specs import ChartSpec, IllustrationSpec
from backend.themes.palettes import PaletteId


AI_MODE: Literal["off"] = "off"
MAX_DRAFT_BYTES = 64 * 1024


class AiBoundaryError(ValueError):
    """A proposed AI action or draft is outside the frozen contract."""


class ThemeDraft(BaseModel):
    """A style suggestion; it cannot change data or scientific meaning."""

    model_config = ConfigDict(extra="forbid", strict=True)

    theme_id: Literal["scientific_clear", "modern_soft", "high_contrast"]
    palette_id: PaletteId
    palette_version: Literal["1.0"] = "1.0"
    font_size: float = Field(default=10, ge=7, le=24)
    line_width: float = Field(default=1.2, ge=0.5, le=5)
    show_legend: bool = True


def request_model(*, mode: str, payload: object, consent: bool = False) -> None:
    """Fail closed for every mode, including forged consent or project settings."""

    del mode, payload, consent
    raise AiBoundaryError("产品 AI 目前关闭；本地和云端模型尚未启用，无法发送或执行请求。")


def _object_without_duplicates(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise AiBoundaryError("草案包含重复字段。")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise AiBoundaryError(f"草案包含无效数字 {value}。")


_UNSAFE_TEXT = re.compile(r"<|>|(?:https?://|javascript:|file://|\\\\|[A-Za-z]:[\\/])", re.IGNORECASE)


def _check_text(value: object) -> None:
    if isinstance(value, str):
        if any(ord(char) < 32 or ord(char) == 127 for char in value) or _UNSAFE_TEXT.search(value):
            raise AiBoundaryError("草案包含控制字符、标记、外链或本机路径。")
    elif isinstance(value, list):
        for item in value:
            _check_text(item)
    elif isinstance(value, dict):
        for key, item in value.items():
            _check_text(key)
            _check_text(item)


def parse_draft_object(raw: str) -> dict[str, object]:
    """Read one bounded JSON proposal using the shared draft safety checks."""

    if len(raw.encode("utf-8")) > MAX_DRAFT_BYTES:
        raise AiBoundaryError("草案超过 64 KiB 上限。")
    try:
        parsed = json.loads(raw, object_pairs_hook=_object_without_duplicates, parse_constant=_reject_constant)
    except (json.JSONDecodeError, UnicodeError, RecursionError) as error:
        raise AiBoundaryError("草案必须是单个 JSON 对象。") from error
    if not isinstance(parsed, dict):
        raise AiBoundaryError("草案必须是单个 JSON 对象。")
    try:
        _check_text(parsed)
    except RecursionError as error:
        raise AiBoundaryError("草案嵌套层级过深。") from error
    return parsed


def validate_draft(kind: Literal["chart", "theme", "illustration"], raw: str, *, current_dataset_id: str | None = None) -> ChartSpec | ThemeDraft | IllustrationSpec:
    """Validate a static JSON draft without applying, rendering, or saving it."""
    parsed = parse_draft_object(raw)
    if kind == "chart":
        if current_dataset_id is None or parsed.get("dataset_id") != current_dataset_id:
            raise AiBoundaryError("图表草案只能引用当前用户已选的本机数据。")
        model: type[BaseModel] = ChartSpec
        if parsed.get("spec_version") not in ("1.0", "1.1", "1.2"):
            raise AiBoundaryError("图表草案版本不受支持。")
    elif kind == "theme":
        model = ThemeDraft
    elif kind == "illustration":
        if parsed.get("spec_version") != "1.3":
            raise AiBoundaryError("图示草案必须使用 IllustrationSpec 1.3。")
        model = IllustrationSpec
    else:
        raise AiBoundaryError("未知草案类型。")
    if set(parsed) - set(model.model_fields):
        raise AiBoundaryError("草案包含未审核字段。")
    try:
        draft = model.model_validate(parsed, strict=True)
    except ValidationError as error:
        raise AiBoundaryError("草案结构或数值不符合已冻结规范。") from error
    if isinstance(draft, IllustrationSpec) and any(
        item.scientific_status == "verified" for item in (*draft.nodes, *draft.edges, *draft.sections)
    ):
        raise AiBoundaryError("AI 图示草案不能标记为用户已核实。")
    if isinstance(draft, IllustrationSpec) and any(edge.scientific_status != "needs_review" for edge in draft.edges):
        raise AiBoundaryError("AI 新建的机制关系必须标记为待核实。")
    return draft
