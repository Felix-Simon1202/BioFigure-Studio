"""Exercise resource limits with tiny stand-ins instead of large allocations."""

from hashlib import sha256
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
import h5py
from fastapi.testclient import TestClient

from backend.api import app as api
from backend.data import store


def _record(payload: bytes) -> store.DatasetRecord:
    return store.DatasetRecord("table", "sample.csv", payload, sha256(payload).hexdigest())


def test_dataset_session_evicts_old_records_by_count_and_bytes(monkeypatch):
    monkeypatch.setattr(store, "_datasets", {})
    monkeypatch.setattr(store, "MAX_SESSION_DATASETS", 3)
    monkeypatch.setattr(store, "MAX_SESSION_DATASET_BYTES", 12)
    first = store.store_record(_record(b"aaaa"))
    second = store.store_record(_record(b"bbbb"))
    third = store.store_record(_record(b"cccc"))
    fourth = store.store_record(_record(b"dddd"))
    assert first not in store._datasets
    assert list(store._datasets) == [second, third, fourth]
    fifth = store.store_record(_record(b"12345678"))
    assert list(store._datasets) == [fourth, fifth]
    with pytest.raises(ValueError, match="内存上限"):
        store.store_record(_record(b"x" * 13))
    assert list(store._datasets) == [fourth, fifth]


def test_artifact_session_evicts_by_total_bytes_and_rejects_oversize(monkeypatch):
    monkeypatch.setattr(api, "MAX_ARTIFACT_CACHE_BYTES", 10)
    cache: dict[str, dict[str, bytes]] = {}
    api._retain_artifacts(cache, "one", {"png": b"123456"})
    api._retain_artifacts(cache, "two", {"png": b"123456"})
    assert list(cache) == ["two"]
    with pytest.raises(api.HTTPException) as error:
        api._retain_artifacts(cache, "large", {"png": b"x" * 11})
    assert error.value.status_code == 422
    assert list(cache) == ["two"]


def test_heavy_render_is_serialized_and_lock_is_released():
    client = TestClient(api.app)
    chart = {"dataset_id": "simulated-cell-response-v1", "x_column": "response", "y_column": "viability", "dpi": 72}
    assert api._render_lock.acquire(blocking=False)
    try:
        response = client.post("/api/renders", json={"chart": chart})
        assert response.status_code == 429
    finally:
        api._render_lock.release()
    assert client.post("/api/renders", json={"chart": chart}).status_code == 201


def test_large_legacy_and_chart_rasters_fail_before_rendering():
    client = TestClient(api.app)
    chart = {"dataset_id": "simulated-cell-response-v1", "x_column": "response", "y_column": "viability", "width_mm": 300, "height_mm": 300, "dpi": 600}
    assert client.post("/api/renders", json={"chart": chart}).status_code == 422
    figure = {"spec_version": "1.0", "panels": [{"dataset_id": "simulated-cell-response-v1", "x_column": "response", "y_column": "viability"}], "width_mm": 420, "height_mm": 420, "dpi": 1200}
    assert client.post("/api/figures", json=figure).status_code == 422


def test_project_rejects_large_uncompressed_entry_before_read(monkeypatch):
    monkeypatch.setattr(api, "MAX_H5AD_BYTES", 5)
    content = BytesIO()
    with ZipFile(content, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("project.json", "{}")
        archive.writestr("data/source.csv", "1234567890")
    response = TestClient(api.app).post(
        "/api/projects/open",
        files={"file": ("sample.bfsproj", content.getvalue(), "application/zip")},
    )
    assert response.status_code == 422
    assert "解压后" in response.json()["detail"]


def test_named_configuration_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(api, "MAX_SAVED_CONFIGS", 2)
    cache: dict[str, int] = {}
    api._retain_config(cache, "first", 1)
    api._retain_config(cache, "second", 2)
    api._retain_config(cache, "second", 3)
    api._retain_config(cache, "third", 4)
    assert cache == {"second": 3, "third": 4}


def test_h5ad_large_declared_array_is_rejected_before_allocation(tmp_path):
    path = tmp_path / "compressed.h5ad"
    with h5py.File(path, "w") as source:
        source.create_dataset("X", shape=(100_000, 100_000), dtype="float64", chunks=(100, 100))
    assert path.stat().st_size < 10_000
    with pytest.raises(store.DatasetCapacityError, match="解压后的数组"):
        store.parse_dataset(path.name, path.read_bytes())
