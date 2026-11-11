"""Export contract tests use a controlled result, not evidence of Fiji parity."""

import asyncio
import csv
from io import BytesIO, StringIO

from fastapi import UploadFile
from fastapi.testclient import TestClient
from PIL import Image
import pytest

from backend.api.app import app
from backend.image import api, jobs
from backend.image.assets import ImageAssetStore


@pytest.fixture
def completed(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    manager = jobs.ImageJobManager()
    encoded = BytesIO()
    Image.new("I;16", (8, 6), 1023).save(encoded, format="TIFF")
    asset = asyncio.run(store.add(UploadFile(BytesIO(encoded.getvalue()), filename='=科研,"测量".tif')))
    store.acquire(asset.id)
    store.set_metadata(asset.id, {"axes": [
        {"name": "X", "length": 8, "unit": "um", "scale": .25},
        {"name": "Y", "length": 6, "unit": "um", "scale": .5}], "bit_depth": 16})
    store.release(asset.id)

    def measured(source, job_id, cancel, selection):
        return {"ok": True, "selection": selection.public(), "sample_count": 31,
                "sum": -38.75, "mean": -1.25, "min": -2.0, "max": 0.0,
                "pixel_type": "test-only", "bit_depth": 16,
                "imagej1_analyzer": {"area": 3.875, "area_unit": "=1+1",
                    "mean": -1.25, "min": -2.0, "max": 0.0, "std_dev": .99}}

    monkeypatch.setattr(jobs, "measure_selection", measured)
    monkeypatch.setattr(api, "manager", manager)
    job = manager.submit_measure(store, asset.id, {},
        {"kind": "ellipse", "x": 0, "y": 0, "width": 7, "height": 5}, ["std_dev"])
    job.future.result(timeout=5)
    assert job.state == "succeeded", job.error
    try:
        yield TestClient(app), manager, store, asset, job
    finally:
        manager.close()
        store.close()


def test_json_and_csv_preserve_result_and_provenance_after_source_removal(completed):
    client, manager, store, asset, job = completed
    store.remove(asset.id)
    response = client.get(f"/api/image/jobs/{job.id}/measurement.json")
    assert response.status_code == 200
    assert "attachment;" in response.headers["content-disposition"]
    assert response.headers["x-content-type-options"] == "nosniff"
    record = response.json()
    assert record["source"]["sha256"] == asset.sha256 and "path" not in record["source"]
    assert record["source"]["original_name"] == '=科研,"测量".tif'
    assert record["selection"]["roi"]["kind"] == "ellipse"
    assert record["selection"]["sample_count"] == 35 and record["result"]["sample_count"] == 31
    assert record["result"]["execution"]["command"] == "ij.plugin.filter.Analyzer"
    response = client.get(f"/api/image/jobs/{job.id}/measurement.csv")
    assert response.status_code == 200 and response.content.startswith(b"\xef\xbb\xbf")
    row, = csv.DictReader(StringIO(response.content.decode("utf-8-sig")))
    assert row["source_name"] == '\'=科研,"测量".tif'
    assert row["area_unit"] == "'=1+1" and record["result"]["imagej1_analyzer"]["area_unit"] == "=1+1"
    assert float(row["mean"]) == -1.25 and float(row["sum"]) == -38.75
    assert row["candidate_pixels"] == "35" and row["sample_count"] == "31"
    assert row["median"] == "" and row["std_dev"] == "0.99"
    assert row["runtime_archive_sha256"] == jobs.EXPECTED_SHA256
    snapshot = manager.measurement_snapshot(job.id)
    snapshot["selection"]["roi"]["width"] = 999
    assert manager.measurement_snapshot(job.id)["selection"]["roi"]["width"] == 7


@pytest.mark.parametrize("state", ["queued", "running", "failed", "cancelled"])
def test_incomplete_measurements_cannot_be_exported(completed, state):
    client, manager, _, _, _ = completed
    fake = jobs.ImageJob(id="a" * 32, asset_id="none", operation="measure_selection", state=state)
    manager._jobs[fake.id] = fake
    assert client.get(f"/api/image/jobs/{fake.id}/measurement.json").status_code == 409


def test_missing_wrong_operation_or_format_are_rejected(completed):
    client, manager, _, _, job = completed
    assert client.get("/api/image/jobs/missing/measurement.json").status_code == 404
    assert client.get(f"/api/image/jobs/{job.id}/measurement.exe").status_code == 422
    job.operation = "inspect_metadata"
    assert client.get(f"/api/image/jobs/{job.id}/measurement.csv").status_code == 409
