from io import BytesIO

import pandas as pd
from fastapi.testclient import TestClient

from backend.api.app import app


client = TestClient(app)

PAYLOAD = {
    "chart": {
        "dataset_id": "simulated-cell-response-v1",
        "x_column": "response",
        "y_column": "viability",
        "group_column": "condition",
        "title": "Cell response",
        "theme_id": "scientific_clear",
    }
}


def test_simulated_csv_and_preview_are_available() -> None:
    csv_response = client.get("/api/datasets/simulated.csv")
    preview_response = client.get("/api/datasets/simulated/preview")

    assert csv_response.status_code == 200
    assert "response" in csv_response.text
    assert preview_response.json()["row_count"] == 9
    assert preview_response.json()["columns"][0]["name"] == "sample"


def test_local_web_origin_is_allowed() -> None:
    response = client.options("/api/renders", headers={"Origin": "http://127.0.0.1:5173", "Access-Control-Request-Method": "POST"})

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"


def test_scatter_exports_all_required_formats() -> None:
    render_response = client.post("/api/renders", json=PAYLOAD)
    render_id = render_response.json()["render_id"]

    assert render_response.status_code == 201
    for export_format, media_type in (("svg", "image/svg+xml"), ("pdf", "application/pdf"), ("png", "image/png")):
        response = client.get(f"/api/renders/{render_id}.{export_format}")
        assert response.status_code == 200
        assert response.headers["content-type"].startswith(media_type)
        assert len(response.content) > 100


def test_two_reviewed_themes_and_config_round_trip() -> None:
    for theme in ("scientific_clear", "modern_soft", "high_contrast"):
        response = client.post("/api/renders", json={"chart": {**PAYLOAD["chart"], "theme_id": theme}})
        assert response.status_code == 201

    config = {"name": "cell-response", "chart": PAYLOAD["chart"]}
    assert client.post("/api/configs", json=config).status_code == 201
    loaded = client.get("/api/configs/cell-response").json()
    assert loaded["config_version"] == "1.0"
    assert loaded["name"] == "cell-response"
    assert loaded["chart"]["spec_version"] == "1.0"
    assert loaded["chart"]["chart_type"] == "scatter"
    assert loaded["chart"]["x_column"] == "response"


def test_render_settings_are_versioned_and_validated() -> None:
    chart = {**PAYLOAD["chart"], "palette_id": "colorblind", "width_mm": 200, "height_mm": 120, "dpi": 300, "font_size": 12, "line_width": 2, "show_legend": False}
    saved = client.post("/api/configs", json={"name": "styled", "chart": chart})

    assert saved.status_code == 201
    assert client.get("/api/configs/styled").json()["chart"]["width_mm"] == 200
    assert client.post("/api/renders", json={"chart": {**chart, "dpi": 700}}).status_code == 422


def test_rejects_unknown_columns_and_versions() -> None:
    invalid_column = {"chart": {**PAYLOAD["chart"], "x_column": "missing"}}
    assert client.post("/api/renders", json=invalid_column).status_code == 422
    invalid_version = {"chart": {**PAYLOAD["chart"], "spec_version": "2.0"}}
    assert client.post("/api/renders", json=invalid_version).status_code == 422


def test_csv_upload_reports_types_and_missing_values() -> None:
    response = client.post(
        "/api/datasets",
        files={"file": ("cells.csv", "group,value\nA,1\nB,\n", "text/csv")},
    )

    assert response.status_code == 201
    assert response.json()["columns"][1]["missing_count"] == 1
    assert response.json()["dataset_id"].startswith("local-")


def test_rejects_unsupported_or_empty_uploads() -> None:
    unsupported = client.post("/api/datasets", files={"file": ("cells.txt", "a,b\n1,2\n", "text/plain")})
    empty = client.post("/api/datasets", files={"file": ("cells.csv", b"", "text/csv")})

    assert unsupported.status_code == 422
    assert empty.status_code == 422


def test_xlsx_upload_is_read_locally() -> None:
    workbook = BytesIO()
    pd.DataFrame({"time": [1, 2], "signal": [3.5, 4.5]}).to_excel(workbook, index=False, engine="openpyxl")

    response = client.post("/api/datasets", files={"file": ("signals.xlsx", workbook.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})

    assert response.status_code == 201
    assert response.json()["columns"][1]["name"] == "signal"


def test_all_phase_three_chart_types_export() -> None:
    for chart_type in ("scatter", "bar", "line", "box", "heatmap"):
        response = client.post("/api/renders", json={"chart": {**PAYLOAD["chart"], "chart_type": chart_type}})
        assert response.status_code == 201
        export = client.get(f"/api/renders/{response.json()['render_id']}.png")
        assert export.status_code == 200
        assert export.headers["content-type"].startswith("image/png")
