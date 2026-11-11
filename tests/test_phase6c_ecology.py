import pandas as pd
import matplotlib.pyplot as plt
from fastapi.testclient import TestClient

from backend.api.app import app
from backend.adapters.matplotlib_charts import draw_chart
from backend.core.specs import ChartSpec
from backend.data.simulated import simulated_ecology_time_dataframe


client = TestClient(app)


def _chart(dataset_id: str, **extra: object) -> dict[str, object]:
    return {
        "spec_version": "1.1", "dataset_id": dataset_id, "chart_type": "ecology_composition",
        "x_column": "sample", "y_column": "abundance", "color_field": "taxon",
        "title": "Community composition", "theme_id": "scientific_clear", "palette_id": "theme",
        "width_mm": 180, "height_mm": 120, "dpi": 120, "font_size": 10, "line_width": 1.2,
        **extra,
    }


def test_simulated_ecology_preview_and_render() -> None:
    preview = client.get("/api/datasets/simulated-ecology/preview")
    assert preview.status_code == 200
    assert preview.json()["kind"] == "ecology_composition"
    assert {column["name"] for column in preview.json()["columns"]} >= {"sample", "taxon", "abundance"}
    rendered = client.post("/api/renders", json={"chart": _chart(preview.json()["dataset_id"])})
    assert rendered.status_code == 201, rendered.text
    assert client.get(f"/api/renders/{rendered.json()['render_id']}.png").headers["content-type"].startswith("image/png")


def test_count_mode_is_explicitly_normalized() -> None:
    frame = pd.DataFrame({"sample": ["A", "A", "B", "B"], "taxon": ["Oak", "Fern", "Oak", "Fern"], "abundance": [3, 1, 1, 3]})
    uploaded = client.post("/api/datasets", files={"file": ("counts.csv", frame.to_csv(index=False).encode(), "text/csv")})
    assert uploaded.status_code == 201
    rendered = client.post("/api/renders", json={"chart": _chart(uploaded.json()["dataset_id"], ecology_value_mode="count")})
    assert rendered.status_code == 201, rendered.text
    project = client.post("/api/projects", json={"name": "count-demo", "chart": _chart(uploaded.json()["dataset_id"], ecology_value_mode="count")})
    assert project.status_code == 200
    reopened = client.post("/api/projects/open", files={"file": ("count-demo.bfsproj", project.content, "application/octet-stream")})
    assert reopened.status_code == 200
    assert reopened.json()["project"]["transformations"] == ["ecology_count_to_fraction"]


def test_duplicate_sample_taxon_pairs_are_rejected() -> None:
    payload = "sample,taxon,abundance\nA,Oak,0.5\nA,Oak,0.5\n"
    uploaded = client.post("/api/datasets", files={"file": ("duplicate.csv", payload.encode(), "text/csv")})
    assert uploaded.status_code == 201
    rendered = client.post("/api/renders", json={"chart": _chart(uploaded.json()["dataset_id"])})
    assert rendered.status_code == 422
    assert "重复" in rendered.json()["detail"]


def test_alpha_and_beta_diversity_use_existing_results() -> None:
    alpha = client.get("/api/datasets/simulated-ecology-alpha/preview")
    assert alpha.status_code == 200
    alpha_chart = _chart(alpha.json()["dataset_id"], chart_type="ecology_alpha_diversity", ecology_sample_column="sample", ecology_metric_column="metric", ecology_metric="Shannon", y_column="value", group_column="group")
    alpha_render = client.post("/api/renders", json={"chart": alpha_chart})
    assert alpha_render.status_code == 201, alpha_render.text

    beta = client.get("/api/datasets/simulated-ecology-beta/preview")
    assert beta.status_code == 200
    beta_chart = _chart(beta.json()["dataset_id"], chart_type="ecology_beta_ordination", ecology_sample_column="sample", x_column="PCoA1", y_column="PCoA2", group_column="group")
    beta_render = client.post("/api/renders", json={"chart": beta_chart})
    assert beta_render.status_code == 201, beta_render.text


def test_ordination_biplot_uses_existing_sample_and_taxon_coordinates() -> None:
    preview = client.get("/api/datasets/simulated-ecology-ordination/preview")
    assert preview.status_code == 200
    chart = _chart(preview.json()["dataset_id"], chart_type="ecology_ordination_biplot", ecology_sample_column="entity", ecology_entity_type_column="entity_type", x_column="axis_1", y_column="axis_2", group_column="group")
    rendered = client.post("/api/renders", json={"chart": chart})
    assert rendered.status_code == 201, rendered.text


def test_environment_gradient_existing_value_and_vector_exports() -> None:
    preview = client.get("/api/datasets/simulated-ecology-environment/preview")
    assert preview.status_code == 200
    assert preview.json()["kind"] == "ecology_environment_gradient"
    dataset_id = preview.json()["dataset_id"]
    base = _chart(
        dataset_id,
        chart_type="ecology_environment_gradient",
        ecology_sample_column="entity",
        ecology_entity_type_column="entity_type",
        x_column="axis_1",
        y_column="axis_2",
        ecology_environment_column="nitrate",
        group_column="group",
    )
    value_render = client.post("/api/renders", json={"chart": base})
    assert value_render.status_code == 201, value_render.text
    for fmt in ("png", "svg", "pdf"):
        assert client.get(f"/api/renders/{value_render.json()['render_id']}.{fmt}").status_code == 200

    vector_data = "entity,entity_type,group,axis_1,axis_2\nS01,sample,Forest,-0.4,0.2\nS02,sample,Meadow,0.3,-0.2\nmoisture,environment,,0.6,0.4\n"
    uploaded = client.post("/api/datasets", files={"file": ("env-vector.csv", vector_data.encode(), "text/csv")})
    assert uploaded.status_code == 201
    vector = {**base, "dataset_id": uploaded.json()["dataset_id"], "ecology_environment_mode": "existing_vector"}
    vector_render = client.post("/api/renders", json={"chart": vector})
    assert vector_render.status_code == 201, vector_render.text
    assert client.get(f"/api/renders/{vector_render.json()['render_id']}.png").content.startswith(b"\x89PNG")


def test_environment_gradient_rejects_missing_and_nonfinite_values() -> None:
    payload = "entity,entity_type,axis_1,axis_2,nitrate\nS01,sample,0.1,0.2,\n"
    uploaded = client.post("/api/datasets", files={"file": ("missing-env.csv", payload.encode(), "text/csv")})
    assert uploaded.status_code == 201
    chart = _chart(uploaded.json()["dataset_id"], chart_type="ecology_environment_gradient", ecology_sample_column="entity", ecology_entity_type_column="entity_type", x_column="axis_1", y_column="axis_2", ecology_environment_column="nitrate")
    rendered = client.post("/api/renders", json={"chart": chart})
    assert rendered.status_code == 422
    assert "缺失" in rendered.json()["detail"]


def test_time_series_keeps_independent_replicates_as_separate_tracks() -> None:
    preview = client.get("/api/datasets/simulated-ecology-time/preview")
    assert preview.status_code == 200
    chart = _chart(
        preview.json()["dataset_id"],
        chart_type="ecology_time_series",
        ecology_sample_column="sample",
        ecology_time_column="time",
        ecology_value_column="value",
        ecology_replicate_column="replicate",
        ecology_error_column="error",
        group_column="group",
    )
    rendered = client.post("/api/renders", json={"chart": chart})
    assert rendered.status_code == 201, rendered.text
    for fmt in ("png", "svg", "pdf"):
        assert client.get(f"/api/renders/{rendered.json()['render_id']}.{fmt}").status_code == 200

    figure, axes = plt.subplots()
    try:
        draw_chart(axes, ChartSpec.model_validate(chart), simulated_ecology_time_dataframe())
        assert len(axes.lines) == 3  # Forest R1, Forest R2, Meadow R1; never one line per group.
    finally:
        plt.close(figure)

    project = client.post("/api/projects", json={"name": "time-series", "chart": chart})
    assert project.status_code == 200
    reopened = client.post("/api/projects/open", files={"file": ("time-series.bfsproj", project.content, "application/octet-stream")})
    assert reopened.status_code == 200
    assert reopened.json()["project"]["chart"]["ecology_replicate_column"] == "replicate"


def test_time_series_rejects_duplicate_track_time_and_negative_error() -> None:
    duplicate = "sample,time,value,group,replicate,error\nS01,1,4.2,Forest,R1,0.3\nS02,1,5.2,Forest,R1,0.2\n"
    uploaded = client.post("/api/datasets", files={"file": ("duplicate-time.csv", duplicate.encode(), "text/csv")})
    chart = _chart(uploaded.json()["dataset_id"], chart_type="ecology_time_series", ecology_sample_column="sample", ecology_time_column="time", ecology_value_column="value", ecology_replicate_column="replicate", ecology_error_column="error", group_column="group")
    rejected = client.post("/api/renders", json={"chart": chart})
    assert rejected.status_code == 422
    assert "重复观测" in rejected.json()["detail"]

    negative = "sample,time,value,error\nS01,1,4.2,-0.3\n"
    uploaded = client.post("/api/datasets", files={"file": ("negative-error.csv", negative.encode(), "text/csv")})
    rejected = client.post("/api/renders", json={"chart": {**chart, "dataset_id": uploaded.json()["dataset_id"], "group_column": None, "ecology_replicate_column": ""}})
    assert rejected.status_code == 422
    assert "负数" in rejected.json()["detail"]


def test_spatial_points_export_and_project_roundtrip() -> None:
    preview = client.get("/api/datasets/simulated-ecology-spatial/preview")
    assert preview.status_code == 200
    assert preview.json()["kind"] == "ecology_spatial_points"
    chart = _chart(
        preview.json()["dataset_id"],
        spec_version="1.2",
        chart_type="ecology_spatial_points",
        ecology_sample_column="sample",
        x_column="longitude",
        y_column="latitude",
        group_column="group",
        ecology_spatial_coordinate_mode="geographic_wgs84",
        ecology_spatial_reference="EPSG:4326",
        ecology_spatial_unit="degrees",
        title="Synthetic spatial points",
    )
    rendered = client.post("/api/renders", json={"chart": chart})
    assert rendered.status_code == 201, rendered.text
    for fmt in ("png", "svg", "pdf"):
        assert client.get(f"/api/renders/{rendered.json()['render_id']}.{fmt}").status_code == 200

    project = client.post("/api/projects", json={"name": "spatial-points", "chart": chart})
    assert project.status_code == 200, project.text
    reopened = client.post("/api/projects/open", files={"file": ("spatial-points.bfsproj", project.content, "application/octet-stream")})
    assert reopened.status_code == 200, reopened.text
    restored = reopened.json()["project"]["chart"]
    assert restored["spec_version"] == "1.2"
    assert restored["ecology_spatial_coordinate_mode"] == "geographic_wgs84"
    assert restored["ecology_spatial_reference"] == "EPSG:4326"
    assert restored["ecology_spatial_unit"] == "degrees"


def test_spatial_planar_mode_requires_reference_and_preserves_unit() -> None:
    payload = "sample,group,x_m,y_m\nP01,A,0,0\nP02,B,10,20\n"
    uploaded = client.post("/api/datasets", files={"file": ("planar.csv", payload.encode(), "text/csv")})
    chart = _chart(
        uploaded.json()["dataset_id"],
        spec_version="1.2",
        chart_type="ecology_spatial_points",
        ecology_sample_column="sample",
        x_column="x_m",
        y_column="y_m",
        group_column="group",
        ecology_spatial_coordinate_mode="planar",
        ecology_spatial_reference="local plot grid",
        ecology_spatial_unit="m",
    )
    rendered = client.post("/api/renders", json={"chart": chart})
    assert rendered.status_code == 201, rendered.text
    no_reference = client.post("/api/renders", json={"chart": {**chart, "ecology_spatial_reference": ""}})
    assert no_reference.status_code == 422
    assert "坐标参考" in no_reference.json()["detail"]


def test_spatial_points_reject_invalid_coordinates_duplicates_and_capacity() -> None:
    invalid = "sample,group,longitude,latitude\nP01,A,181,20\n"
    uploaded = client.post("/api/datasets", files={"file": ("invalid-longitude.csv", invalid.encode(), "text/csv")})
    base = _chart(
        uploaded.json()["dataset_id"],
        spec_version="1.2",
        chart_type="ecology_spatial_points",
        ecology_sample_column="sample",
        x_column="longitude",
        y_column="latitude",
        group_column="group",
        ecology_spatial_coordinate_mode="geographic_wgs84",
        ecology_spatial_reference="EPSG:4326",
        ecology_spatial_unit="degrees",
    )
    rejected = client.post("/api/renders", json={"chart": base})
    assert rejected.status_code == 422
    assert "经度" in rejected.json()["detail"]

    duplicate = "sample,group,longitude,latitude\nP01,A,1,1\nP01,A,2,2\n"
    uploaded = client.post("/api/datasets", files={"file": ("duplicate-spatial.csv", duplicate.encode(), "text/csv")})
    rejected = client.post("/api/renders", json={"chart": {**base, "dataset_id": uploaded.json()["dataset_id"]}})
    assert rejected.status_code == 422
    assert "必须唯一" in rejected.json()["detail"]

    capacity = "sample,group,longitude,latitude\nP01,A,1,1\nP02,B,2,2\nP03,C,3,3\nP04,D,4,4\nP05,E,5,5\n"
    uploaded = client.post("/api/datasets", files={"file": ("capacity-spatial.csv", capacity.encode(), "text/csv")})
    rejected = client.post("/api/renders", json={"chart": {**base, "dataset_id": uploaded.json()["dataset_id"]}})
    assert rejected.status_code == 422
    assert "色板容量" in rejected.json()["detail"]


def test_spatial_points_reject_more_than_five_thousand_rows() -> None:
    frame = pd.DataFrame(
        {
            "sample": [f"P{index:04d}" for index in range(5001)],
            "longitude": [float(index % 180) for index in range(5001)],
            "latitude": [float(index % 90) for index in range(5001)],
        }
    )
    uploaded = client.post("/api/datasets", files={"file": ("too-many-spatial.csv", frame.to_csv(index=False).encode(), "text/csv")})
    chart = _chart(
        uploaded.json()["dataset_id"],
        spec_version="1.2",
        chart_type="ecology_spatial_points",
        ecology_sample_column="sample",
        x_column="longitude",
        y_column="latitude",
        group_column=None,
        ecology_spatial_coordinate_mode="geographic_wgs84",
        ecology_spatial_reference="EPSG:4326",
        ecology_spatial_unit="degrees",
    )
    rejected = client.post("/api/renders", json={"chart": chart})
    assert rejected.status_code == 422
    assert "5000" in rejected.json()["detail"]
