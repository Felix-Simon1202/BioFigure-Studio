"""Render the local palette catalog using synthetic charts; no network access."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd
from backend.adapters.matplotlib_charts import configure_fonts, draw_chart
from backend.core.specs import ChartSpec
from backend.themes.palettes import SCIENTIFIC_PALETTES, continuous_palette


def main():
    configure_fonts()
    frame = pd.DataFrame({'response': [1, 2, 3, 4] * 6,
        'viability': [2 + i * .55 + j * (.14 + i * .03) for i in range(6) for j in range(4)],
        'group': [f'Group {i + 1}' for i in range(6) for _ in range(4)]})
    correlation = pd.DataFrame({'A': [1, 2, 3, 4, 5, 6], 'B': [6, 5, 4, 3, 2, 1],
                                'C': [3, 1, 6, 2, 5, 4], 'D': [1, 3, 2, 5, 4, 6]})
    columns = 5
    rows = (len(SCIENTIFIC_PALETTES) + columns - 1) // columns
    figure, axes = plt.subplots(rows, columns, figsize=(16, rows * 2.6), layout='constrained', squeeze=False)
    try:
        for ax, (key, item) in zip(axes.flat, SCIENTIFIC_PALETTES.items()):
            categorical = item['kind'] == 'categorical'
            spec = ChartSpec(dataset_id='synthetic', chart_type='line' if categorical else 'heatmap',
                x_column='response' if categorical else 'A', y_column='viability' if categorical else 'B',
                group_column='group' if categorical else None, palette_id=key,
                title=item['name']['en'], font_size=8, show_legend=False)
            if item['kind'] == 'sequential':
                magnitude = [[0., .1, .2, .3], [.2, .4, .6, .8], [.1, .3, .7, .9], [.3, .5, .8, 1.]]
                image = ax.imshow(magnitude, vmin=0, vmax=1, cmap=continuous_palette(key))
                ax.set_title(item['name']['en'], loc='left', fontsize=10)
                ax.set_xticks([])
                ax.set_yticks([])
                figure.colorbar(image, ax=ax, label='Relative magnitude', shrink=.85)
            else:
                draw_chart(ax, spec, frame if categorical else correlation)
        for ax in list(axes.flat)[len(SCIENTIFIC_PALETTES):]:
            ax.set_visible(False)
        figure.suptitle('BioFigure Studio · 25 scientific palettes · synthetic data', fontsize=14)
        output = ROOT / 'docs/media/scientific-palette-catalog.png'
        figure.savefig(output, dpi=125, metadata={'Software': 'BioFigure Studio'})
        print(output.name)
    finally:
        plt.close(figure)


if __name__ == '__main__':
    main()
