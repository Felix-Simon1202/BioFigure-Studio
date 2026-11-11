import re
import struct
import pytest
from fastapi.testclient import TestClient
from backend.api.app import app
from backend.core.specs import ChartSpec
from backend.adapters.matplotlib_charts import render_chart, _palette
from backend.data.simulated import simulated_dataframe

client = TestClient(app)
BASE = dict(dataset_id="simulated-cell-response-v1", x_column="response", y_column="viability", group_column="condition", title="Cell response", dpi=100)


def test_layout_exports_and_config_roundtrip():
    panels = [{**BASE, "chart_type": kind, "palette_id": "coolwarm" if kind == "heatmap" else "clay"} for kind in ("scatter", "line", "heatmap")]
    figure = dict(panels=panels, columns=2, labels="lower", width_mm=280, height_mm=210, dpi=100, theme_id="modern_soft")
    saved = client.post("/api/figure-configs", json={"name": "layout-test", "figure": figure})
    assert saved.status_code == 201
    loaded = client.get("/api/figure-configs/layout-test").json()["figure"]
    assert loaded["panels"][0]["palette_version"] == "1.0"
    result = client.post("/api/figures", json=loaded)
    assert result.status_code == 201, result.text
    identifier = result.json()["render_id"]
    png = client.get(f"/api/figures/{identifier}.png").content
    assert struct.unpack(">II", png[16:24]) == (int(280 / 25.4 * 100), int(210 / 25.4 * 100))
    assert png == client.get(f"/api/figures/{identifier}.png").content
    svg = client.get(f"/api/figures/{identifier}.svg").text
    assert "a · Cell response" in svg and "c · Cell response" in svg
    assert "#f8f5ef" in svg
    pdf = client.get(f"/api/figures/{identifier}.pdf").content
    assert pdf.startswith(b"%PDF")
    bounds = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", pdf)
    assert bounds and float(bounds[1]) == pytest.approx(280 / 25.4 * 72)
    assert float(bounds[2]) == pytest.approx(210 / 25.4 * 72)
    dimensions = re.search(r'width="([\d.]+)pt" height="([\d.]+)pt"', svg)
    assert dimensions and float(dimensions[1]) == pytest.approx(280 / 25.4 * 72)
    regenerated = client.post("/api/figures", json=loaded).json()["render_id"]
    assert png == client.get(f"/api/figures/{regenerated}.png").content


@pytest.mark.parametrize("patch", [{"panels": []}, {"panels": [BASE] * 5}, {"columns": 3}, {"labels": "custom"}, {"panels": [{**BASE, "palette_version": "2.0"}]}])
def test_invalid_layout(patch):
    assert client.post("/api/figures", json={"panels": [BASE], **patch}).status_code == 422


def test_long_text_is_rejected_instead_of_clipped():
    result = client.post("/api/figures", json={"panels": [{**BASE, "title": "W" * 160, "font_size": 24}], "width_mm": 120, "height_mm": 120})
    assert result.status_code == 422
    assert "画布" in result.json()["detail"]


def test_palette_selection_changes_pixels_and_version_is_fixed():
    data = simulated_dataframe()
    clay = ChartSpec(**BASE, palette_id="clay")
    lagoon = ChartSpec(**BASE, palette_id="lagoon")
    assert _palette(clay, ()) == ("#A34F3E", "#D3A45B", "#527C78", "#73617F", "#7B854B", "#B86D86")
    assert render_chart(clay, data, "png") != render_chart(lagoon, data, "png")
    assert render_chart(clay, data, "png") == render_chart(clay, data.iloc[::-1], "png")


def test_shared_category_mapping_survives_subsets():
    from backend.core.specs import FigureSpec
    from backend.adapters.matplotlib_charts import resolve_figure
    data = simulated_dataframe()
    spec = FigureSpec(panels=[ChartSpec(**BASE), ChartSpec(**BASE)])
    resolved = resolve_figure(spec, [data, data.iloc[-3:]])
    assert resolved.panels[0].category_order == resolved.panels[1].category_order
    assert len(resolved.panels[0].category_order) == data.condition.nunique()


def test_oversized_legend_rejected():
    from backend.data.store import store_dataframe
    data = simulated_dataframe()
    data["condition"] = "W" * 150
    identifier = store_dataframe(data)
    response = client.post("/api/figures", json={"panels": [{**BASE, "dataset_id": identifier}], "width_mm": 120, "height_mm": 120})
    assert response.status_code == 422
    assert "画布" in response.json()["detail"]
