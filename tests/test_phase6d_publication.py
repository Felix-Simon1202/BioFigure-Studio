from io import BytesIO
import re

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend.api.app import app


client = TestClient(app)
BASE = {
    "dataset_id": "simulated-cell-response-v1",
    "chart_type": "scatter",
    "x_column": "response",
    "y_column": "viability",
    "group_column": "condition",
    "palette_id": "clay",
    "title": "Cell response",
    "dpi": 120,
}


def publication_figure(**patch):
    value = {
        "spec_version": "2.0",
        "panels": [BASE, BASE],
        "columns": 2,
        "labels": "upper",
        "label_position": "inside",
        "legend_mode": "shared",
        "legend_position": "bottom",
        "template_id": "double_column",
        "width_mm": 180,
        "height_mm": 120,
        "margin_top_mm": 10,
        "margin_right_mm": 10,
        "margin_bottom_mm": 16,
        "margin_left_mm": 16,
        "panel_gap_mm": 7,
        "dpi": 300,
    }
    value.update(patch)
    return value


def test_publication_figure_exports_four_formats_with_exact_raster_size():
    response = client.post("/api/figures", json=publication_figure())
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["formats"] == ["pdf", "png", "svg", "tiff"]
    identifier = payload["render_id"]
    expected = (round(180 / 25.4 * 300), round(120 / 25.4 * 300))
    png = Image.open(BytesIO(client.get(f"/api/figures/{identifier}.png").content))
    tiff_response = client.get(f"/api/figures/{identifier}.tiff")
    tiff = Image.open(BytesIO(tiff_response.content))
    assert all(abs(actual - target) <= 1 for actual, target in zip(png.size, expected))
    assert all(abs(actual - target) <= 1 for actual, target in zip(tiff.size, expected))
    assert tiff_response.headers["content-type"] == "image/tiff"
    assert tiff.info["dpi"][0] == pytest.approx(300, rel=0.01)
    pdf = client.get(f"/api/figures/{identifier}.pdf").content
    bounds = re.search(rb"/MediaBox\s*\[\s*0\s+0\s+([\d.]+)\s+([\d.]+)", pdf)
    assert bounds and float(bounds[1]) == pytest.approx(180 / 25.4 * 72)
    assert float(bounds[2]) == pytest.approx(120 / 25.4 * 72)


@pytest.mark.parametrize(
    "patch, message",
    [
        ({"width_mm": 60, "height_mm": 60, "margin_left_mm": 20, "margin_right_mm": 20}, "30 × 30"),
        ({"width_mm": 420, "height_mm": 420, "dpi": 1200}, "1 亿像素"),
    ],
)
def test_publication_layout_rejects_unsafe_geometry(patch, message):
    response = client.post("/api/figures", json=publication_figure(**patch))
    assert response.status_code == 422
    assert message in response.text


def test_shared_legend_rejects_incompatible_mappings():
    panels = [BASE, {**BASE, "group_column": "batch"}]
    response = client.post("/api/figures", json=publication_figure(panels=panels))
    assert response.status_code == 422
    assert "共享图例" in response.json()["detail"]


def test_project_manifest_records_publication_provenance():
    response = client.post(
        "/api/projects",
        json={"name": "publication", "chart": BASE, "figure": publication_figure()},
    )
    assert response.status_code == 200, response.text
    from zipfile import ZipFile

    with ZipFile(BytesIO(response.content)) as archive:
        import json

        manifest = json.loads(archive.read("project.json"))
    assert manifest["project_version"] == "1.1"
    assert manifest["figure"]["spec_version"] == "2.0"
    assert manifest["plugin_versions"]["figure-spec"] == "2.0"
    assert manifest["font_provenance"]["sha256"].upper() == "A3041811A78C361B1DE50F953C805E0244951C21C5BD412F7232EF0D899AF0DA"
    assert manifest["export_checks"]["formats"] == ["pdf", "png", "svg", "tiff"]


def test_mixed_figure_exports_and_reopens_with_original_image(monkeypatch):
    from hashlib import sha256
    from zipfile import ZipFile

    from matplotlib.figure import Figure

    save_figure = Figure.savefig
    def check_panel_separation(figure, *args, **kwargs):
        if len(figure.axes) == 2 and figure.axes[0].images:
            image, chart = figure.axes
            assert chart.get_tightbbox(figure.canvas.get_renderer()).x0 > image.bbox.x1
        return save_figure(figure, *args, **kwargs)
    monkeypatch.setattr(Figure, "savefig", check_panel_separation)

    original = BytesIO()
    Image.new("I;16", (240, 180), 32768).save(original, format="TIFF")
    image_bytes = original.getvalue()
    asset_response = client.post("/api/image/assets", files={"file": ("micrograph.tif", image_bytes, "image/tiff")})
    assert asset_response.status_code == 201, asset_response.text
    asset_id = asset_response.json()["id"]
    figure = publication_figure(spec_version="2.1", panels=[BASE], legend_mode="per_panel", image_panel={
        "asset_id": asset_id,
        "crop": {"x": 20, "y": 10, "width": 200, "height": 150},
        "x_um_per_pixel": 0.5,
        "scale_bar_um": 10,
    })
    response = client.post("/api/figures", json=figure)
    assert response.status_code == 201, response.text
    check = response.json()["image_check"]
    assert check["source_pixels"] == [240, 180]
    assert check["placed_pixels"] == [200, 150]
    assert check["effective_dpi"] == pytest.approx(200 / 73.5 * 25.4, abs=0.01)
    assert check["below_output_dpi"]
    render_id = response.json()["render_id"]
    pdf = client.get(f"/api/figures/{render_id}.pdf").content
    assert b"/Subtype /Image" in pdf and b"/FontFile2" in pdf
    tiff = client.get(f"/api/figures/{render_id}.tiff").content
    with Image.open(BytesIO(tiff)) as image:
        assert image.info["dpi"][0] == pytest.approx(300)

    invalid = publication_figure(**{**figure, "image_panel": {**figure["image_panel"], "scale_bar_um": 500}})
    assert client.post("/api/figures", json=invalid).status_code == 422

    saved = client.post("/api/projects", json={"name": "合成图版", "chart": BASE, "figure": figure})
    assert saved.status_code == 200, saved.text
    assert "filename*=UTF-8''%E5%90%88%E6%88%90%E5%9B%BE%E7%89%88.bfsproj" in saved.headers["content-disposition"]
    with ZipFile(BytesIO(saved.content)) as project:
        assert project.read("image/source") == image_bytes
    opened = client.post("/api/projects/open", files={"file": ("mixed.bfsproj", saved.content)})
    assert opened.status_code == 200, opened.text
    document = opened.json()["project"]
    assert document["project_version"] == "1.2"
    assert document["name"] == "合成图版"
    assert document["image_sha256"] == sha256(image_bytes).hexdigest()
    new_panel = document["figure"]["image_panel"]
    assert new_panel["asset_id"] != asset_id
    assert new_panel["crop"] == figure["image_panel"]["crop"]
    assert new_panel["x_um_per_pixel"] == 0.5
    rerendered = client.post("/api/figures", json=document["figure"])
    assert rerendered.status_code == 201, rerendered.text
    assert rerendered.json()["image_check"] == check
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    assert client.delete(f"/api/image/assets/{new_panel['asset_id']}").status_code == 204


def test_optional_editable_svg_preserves_text_and_legacy_paths():
    from xml.etree import ElementTree

    from backend.adapters.matplotlib_charts import render_chart
    from backend.core.specs import ChartSpec
    from backend.data.simulated import simulated_dataframe

    spec = ChartSpec.model_validate(BASE)
    namespace = "{http://www.w3.org/2000/svg}"
    for text_mode in ("editable", "outline"):
        chart_svg = ElementTree.fromstring(render_chart(spec.model_copy(update={"svg_text_mode": text_mode}),
                                                       simulated_dataframe(), "svg"))
        text_nodes = chart_svg.findall(".//" + namespace + "text")
        assert bool(text_nodes) == (text_mode == "editable")
        assert chart_svg.findall(".//" + namespace + "path")
        if text_nodes:
            assert any(node.text == "Cell response" for node in text_nodes)

    response = client.post("/api/figures", json=publication_figure(svg_text_mode="editable"))
    assert response.status_code == 201, response.text
    identifier = response.json()["render_id"]
    svg = ElementTree.fromstring(client.get(f"/api/figures/{identifier}.svg").content)
    assert {"A", "B"} <= {node.text for node in svg.findall(".//" + namespace + "text")}
