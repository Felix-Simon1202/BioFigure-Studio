"""Phase 6A acceptance checks using a synthetic anonymous AnnData fixture."""

import os
import tempfile

import anndata as ad
import numpy as np
import pandas as pd
from fastapi.testclient import TestClient

from backend.api.app import app


def _h5ad_bytes() -> bytes:
    matrix = np.array([[1, 0, 2], [2, 1, 0], [0, 2, 3], [4, 0, 1], [3, 1, 2], [1, 3, 0]], dtype=float)
    data = ad.AnnData(
        X=matrix,
        obs=pd.DataFrame({"cluster": ["A", "A", "B", "B", "C", "C"], "score": [.1, .4, .8, .2, .9, .5]}, index=[f"cell-{i}" for i in range(6)]),
        var=pd.DataFrame(index=["G1", "G2", "G3"]),
    )
    data.obsm["X_umap"] = np.array([[0, 0], [1, 0], [0, 1], [1, 1], [2, 0], [2, 1]], dtype=float)
    data.layers["counts"] = matrix
    handle = tempfile.NamedTemporaryFile(suffix=".h5ad", delete=False)
    path = handle.name
    handle.close()
    try:
        data.write_h5ad(path)
        with open(path, "rb") as source:
            return source.read()
    finally:
        os.unlink(path)


def _base(dataset_id: str) -> dict[str, object]:
    return {
        "spec_version": "1.1", "dataset_id": dataset_id, "coordinate_key": "X_umap",
        "theme_id": "scientific_clear", "palette_id": "viridis", "width_mm": 180,
        "height_mm": 120, "dpi": 120, "font_size": 9, "line_width": 1.0,
        "show_legend": True, "category_order": [], "x_column": "", "y_column": "",
        "group_column": None, "color_field": "cluster", "genes": [],
        "expression_source": "X", "expression_layer": None, "transform": "none",
        "point_size": 8, "title": "测试图",
    }


def test_h5ad_five_phase6a_charts_and_project_roundtrip() -> None:
    client = TestClient(app)
    uploaded = client.post("/api/datasets", files={"file": ("anonymous.h5ad", _h5ad_bytes(), "application/octet-stream")})
    assert uploaded.status_code == 201
    summary = uploaded.json()
    assert summary["kind"] == "single_cell"
    assert summary["coordinates"] == [{"key": "X_umap", "dimensions": 2}]
    base = _base(summary["dataset_id"])
    charts = [
        ("embedding_categorical", {}),
        ("embedding_continuous", {"color_field": "score"}),
        ("feature", {"genes": ["G1"]}),
        ("violin", {"group_column": "cluster", "genes": ["G1"]}),
        ("dotplot", {"group_column": "cluster", "genes": ["G1", "G2"]}),
    ]
    for chart_type, extra in charts:
        rendered = client.post("/api/renders", json={"chart": {**base, "chart_type": chart_type, **extra}})
        assert rendered.status_code == 201, rendered.text
        for export_format in ("png", "svg", "pdf"):
            artifact = client.get(f"/api/renders/{rendered.json()['render_id']}.{export_format}")
            assert artifact.status_code == 200 and artifact.content
    project = client.post("/api/projects", json={"name": "anonymous-demo", "chart": {**base, "chart_type": "feature", "genes": ["G1"]}})
    assert project.status_code == 200 and project.content.startswith(b"PK")
    opened = client.post("/api/projects/open", files={"file": ("anonymous-demo.bfsproj", project.content, "application/zip")})
    assert opened.status_code == 200
    assert opened.json()["preview"]["kind"] == "single_cell"


def test_missing_coordinate_is_explicitly_rejected() -> None:
    client = TestClient(app)
    uploaded = client.post("/api/datasets", files={"file": ("anonymous.h5ad", _h5ad_bytes(), "application/octet-stream")})
    base = _base(uploaded.json()["dataset_id"])
    rendered = client.post("/api/renders", json={"chart": {**base, "chart_type": "embedding_categorical", "coordinate_key": "X_tsne"}})
    assert rendered.status_code == 422
    assert "不会自动计算降维" in rendered.json()["detail"]


def test_builtin_synthetic_h5ad_preview_is_available() -> None:
    response = TestClient(app).get("/api/datasets/simulated-single-cell/preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["kind"] == "single_cell"
    assert payload["source"] == "built-in synthetic anonymous H5AD"
    assert payload["coordinates"][0]["key"] == "X_umap"
