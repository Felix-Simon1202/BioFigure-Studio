"""Presentation-only figure proposals; existing data and rendering stay authoritative."""
from hashlib import sha256
import json
from typing import Callable

from pydantic import BaseModel, ConfigDict, Field
from backend.core.ai_boundary import ThemeDraft
from backend.core.specs import FigureSpec
from backend.data.store import get_record
from backend.themes.palettes import ART_PALETTES
from backend.themes.registry import get_theme


class FigureStyleRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    figure: FigureSpec
    style: ThemeDraft
    category_order: list[str] = Field(default_factory=list, max_length=64)


def fingerprint(value: dict) -> str:
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def preview_figure_style(request: FigureStyleRequest, resolve: Callable = get_record) -> dict:
    before = request.figure.model_dump(mode='json')
    after = json.loads(json.dumps(before))
    discovered: set[str] = set()
    for chart in request.figure.panels:
        if chart.chart_type not in {'scatter', 'bar', 'line', 'box', 'heatmap'}:
            raise ValueError('Use the five standard plot types for linked figure styling.')
        column = chart.group_column if chart.chart_type in {'scatter', 'line'} else chart.x_column if chart.chart_type in {'bar', 'box'} else None
        if column:
            frame = resolve(chart.dataset_id).dataframe
            if frame is None or column not in frame:
                raise ValueError('A category field is unavailable; reload the source dataset.')
            if frame[column].isna().any():
                raise ValueError('Name missing categories explicitly before linking group colors.')
            discovered.update(frame[column].astype(str).unique())
    order = request.category_order or sorted(discovered)
    if len(set(order)) != len(order) or set(order) != discovered:
        raise ValueError('Category order must contain every displayed group exactly once, with original names.')
    palette_id = request.style.palette_id
    if palette_id in {'viridis', 'cividis', 'magma', 'coolwarm', 'oc_blues', 'oc_balance'} or palette_id.startswith(('oc_seq_', 'oc_div_')):
        raise ValueError('Choose a categorical palette for consistent experimental groups.')
    palette = ART_PALETTES.get(palette_id, ('#0072b2', '#e69f00', '#009e73', '#cc79a7', '#d55e00', '#56b4e9') if palette_id == 'colorblind' else get_theme(request.style.theme_id).palette)
    if len(order) > len(palette):
        raise ValueError('The category count exceeds the palette capacity; choose fewer groups or another palette.')
    changes = []
    for index, panel in enumerate(after['panels']):
        patch = request.style.model_dump()
        if panel['chart_type'] == 'heatmap':
            patch.pop('palette_id') # Signed/continuous scales retain their existing meaning.
        else:
            patch['category_order'] = order
        for key, value in patch.items():
            if panel.get(key) != value:
                changes.append({'target': f'panel:{index+1}', 'field': key, 'before': panel.get(key), 'after': value})
                panel[key] = value
    for key, value in {'theme_id': request.style.theme_id, 'label_font_size': request.style.font_size}.items():
        if after[key] != value:
            changes.append({'target': 'figure', 'field': key, 'before': after[key], 'after': value})
            after[key] = value
    result = FigureSpec.model_validate(after)
    return {'figure': result.model_dump(mode='json'), 'before_fingerprint': fingerprint(before),
            'changes': changes, 'group_colors': dict(zip(order, palette)), 'source_data_changed': False}
