from copy import deepcopy
from types import SimpleNamespace
import pandas as pd
import pytest
import matplotlib.pyplot as plt
from matplotlib.colors import to_hex
from backend.core.figure_consistency import FigureStyleRequest, preview_figure_style
from backend.core.specs import ChartSpec, FigureSpec
from backend.adapters.matplotlib_charts import draw_chart, render_figure
from backend.themes.palettes import ART_PALETTES


def test_four_panel_linked_style_preserves_data_and_labels_and_roundtrips():
    frame = pd.DataFrame({'x':[1,2,3,4], 'y':[4,3,2,1], 'group':['B','A','B','A']})
    panels = [ChartSpec(dataset_id='synthetic', chart_type=kind,
        x_column='group' if kind in {'bar','box'} else 'x', y_column='y',
        group_column='group' if kind in {'scatter','line'} else None,
        title=f'Original 科学标签 {kind}') for kind in ('scatter','line','bar','box')]
    figure = FigureSpec(spec_version='2.0',panels=panels)
    before = deepcopy(figure.model_dump()); source = frame.copy(deep=True)
    proposal = preview_figure_style(FigureStyleRequest(figure=figure,
        style={'theme_id':'scientific_clear','palette_id':'oc_clear','font_size':12,'line_width':1.8},
        category_order=['B','A']),resolve=lambda _:SimpleNamespace(dataframe=frame))
    after = FigureSpec.model_validate(proposal['figure'])
    assert figure.model_dump()==before
    pd.testing.assert_frame_equal(frame,source)
    assert FigureSpec.model_validate_json(after.model_dump_json())==after
    assert proposal['group_colors']=={'B':ART_PALETTES['oc_clear'][0],'A':ART_PALETTES['oc_clear'][1]}
    for index,panel in enumerate(after.panels):
        assert panel.title==panels[index].title
        assert panel.dataset_id=='synthetic' and panel.y_column=='y'
        assert panel.font_size==12 and panel.line_width==1.8 and panel.category_order==['B','A']
        axes_figure,axes=plt.subplots()
        try:
            draw_chart(axes,panel,frame)
            if panel.chart_type=='bar':
                assert to_hex(axes.patches[0].get_facecolor())==ART_PALETTES['oc_clear'][1]
        finally: plt.close(axes_figure)
    # Use the production render entry point for all four updated panels.
    from backend.adapters.matplotlib_charts import render_chart
    for panel in after.panels:
        assert render_chart(panel,frame,'pdf').startswith(b'%PDF-')
    assert render_figure(after,[frame]*4,'pdf').startswith(b'%PDF-')
    from backend.core.specs import ProjectDocument
    project=ProjectDocument(name='Original',chart=after.panels[0],figure=after,data_filename='source.csv',
        data_sha256='0'*64,data_kind='table')
    assert ProjectDocument.model_validate_json(project.model_dump_json()).figure==after


def test_heatmap_retains_scale_and_invalid_group_mapping_is_rejected():
    frame=pd.DataFrame({'x':[1,2], 'y':[2,1], 'group':['A','B']})
    figure=FigureSpec(panels=[ChartSpec(dataset_id='synthetic',chart_type='heatmap',x_column='x',y_column='y',palette_id='oc_balance')])
    request=FigureStyleRequest(figure=figure,style={'theme_id':'scientific_clear','palette_id':'oc_clear'})
    result=preview_figure_style(request,resolve=lambda _:SimpleNamespace(dataframe=frame))
    assert result['figure']['panels'][0]['palette_id']=='oc_balance'
    figure.panels=[ChartSpec(dataset_id='synthetic',x_column='x',y_column='y',group_column='group')]
    with pytest.raises(ValueError):
        preview_figure_style(FigureStyleRequest(figure=figure,style=request.style,category_order=['A']),resolve=lambda _:SimpleNamespace(dataframe=frame))
