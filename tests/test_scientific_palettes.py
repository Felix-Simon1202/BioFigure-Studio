"""New colors must reach real exports and the bounded Biodot proposal path."""
import json
import re

import matplotlib.pyplot as plt
from matplotlib.colors import to_hex
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.adapters.matplotlib_charts import draw_chart, render_chart
from backend.adapters.single_cell import _categorical_palette, _continuous_palette
from backend.core.ai_boundary import validate_draft
from backend.core.specs import ChartSpec, SavedChartConfig
from backend.core.workbench import ChartIntent, build_chart_draft
from backend.themes.palettes import ART_PALETTES, SCIENTIFIC_PALETTES, continuous_palette


FRAME = pd.DataFrame({'response': [1, 2, 3, 1, 2, 3], 'viability': [2, 3, 4, 4, 3, 2],
                      'group': ['control'] * 3 + ['treatment'] * 3})


@pytest.mark.parametrize('palette', list(SCIENTIFIC_PALETTES))
def test_palette_roundtrip_real_svg_and_unchanged_data(palette):
    kind = SCIENTIFIC_PALETTES[palette]['kind']
    chart = ChartSpec(dataset_id='synthetic', chart_type='scatter' if kind == 'categorical' else 'heatmap',
                      palette_id=palette, x_column='response', y_column='viability', group_column='group',
                      title='Original 科学标签', svg_text_mode='editable')
    saved = SavedChartConfig(name='Synthetic colors', chart=chart)
    assert SavedChartConfig.model_validate_json(saved.model_dump_json()) == saved
    before = FRAME.copy(deep=True)
    svg = render_chart(chart, FRAME, 'svg').decode()
    assert '<svg' in svg and 'Original 科学标签' in svg
    pd.testing.assert_frame_equal(FRAME, before)
    if kind == 'categorical':
        for color in SCIENTIFIC_PALETTES[palette]['colors'][:2]:
            assert color.lower() in svg.lower()
        assert _categorical_palette(chart) == ART_PALETTES[palette]
    else:
        assert _continuous_palette(chart).name == palette


def test_signed_heatmap_ramp_and_sequential_lightness():
    chart = ChartSpec(dataset_id='synthetic', chart_type='heatmap', palette_id='oc_balance',
                      x_column='response', y_column='viability')
    figure, axes = plt.subplots()
    try:
        draw_chart(axes, chart, FRAME)
        image = axes.images[0]
        assert image.get_clim() == (-1, 1)
        assert to_hex(image.cmap(0.0)) == SCIENTIFIC_PALETTES['oc_balance']['colors'][0]
        assert to_hex(image.cmap(1.0)) == SCIENTIFIC_PALETTES['oc_balance']['colors'][-1]
    finally:
        plt.close(figure)
    ramp = continuous_palette('oc_blues')
    # sRGB channel order is strictly darker for this reviewed monochromatic ramp.
    brightness = [sum(ramp(value)[:3]) for value in (0., .25, .5, .75, 1.)]
    assert brightness == sorted(brightness, reverse=True)


def test_biodot_catalog_schema_and_reviewed_style_proposal():
    with TestClient(app) as client:
        profile = client.get('/api/workbench/v1/capabilities').json()['assistant']
    assert {item['id'] for item in profile['chart_palettes']} == set(SCIENTIFIC_PALETTES)
    for item in profile['chart_palettes']:
        assert all(re.fullmatch(r'#[0-9a-fA-F]{6}', color) for color in item['colors'])
        assert set(item['name']) == {'en', 'zh-CN'}
    intent = ChartIntent(chart_type='scatter', title='Synthetic groups', theme_id='scientific_clear', palette_id='oc_clear')
    chart = build_chart_draft(intent)
    assert chart.palette_id == 'oc_clear'
    draft = validate_draft('theme', json.dumps({'theme_id': 'scientific_clear', 'palette_id': 'oc_soft'}))
    assert draft.palette_id == 'oc_soft'
    assert ChartIntent(chart_type='line', title='Existing', theme_id='modern_soft').palette_id == 'theme'
    with pytest.raises(ValueError):
        ChartIntent(chart_type='scatter', title='Reject', theme_id='scientific_clear', palette_id='unreviewed')


def test_genome_tracks_use_selected_colors_and_preserve_explicit_source():
    from backend.adapters.omics import _draw_genome_tracks
    from backend.data.store import DatasetRecord
    frame = pd.DataFrame({'start': [10], 'end': [20]})
    record = DatasetRecord(kind='genome', filename='synthetic.bed', payload=b'', digest='synthetic', dataframe=frame)
    spec = ChartSpec(dataset_id='synthetic', chart_type='genome_tracks', palette_id='oc_clear')
    figure, axes = plt.subplots()
    try:
        _draw_genome_tracks(axes, spec, record)
        assert to_hex(axes.patches[0].get_facecolor()) == ART_PALETTES['oc_clear'][0]
        assert axes.patches[0].get_x() == 10
        assert axes.patches[0].get_width() == 10
    finally:
        plt.close(figure)


def test_environment_gradient_uses_requested_ramp():
    frame = pd.DataFrame({'sample': ['s1', 's2', 's3'], 'x': [1., 2., 3.],
                          'y': [3., 1., 2.], 'expression': [0., 5., 10.]})
    spec = ChartSpec(dataset_id='synthetic', chart_type='ecology_environment_gradient',
        palette_id='oc_blues', x_column='x', y_column='y', ecology_environment_column='expression')
    figure, axes = plt.subplots()
    try:
        draw_chart(axes, spec, frame)
        assert axes.collections[0].cmap.name == 'oc_blues'
        assert axes.collections[0].get_clim() == (0., 10.)
    finally:
        plt.close(figure)
