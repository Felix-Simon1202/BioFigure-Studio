"""Opt-in verification against the pinned, locally audited Fiji process."""

import os
import csv
import ctypes
from io import BytesIO, StringIO
import base64
import struct
from zipfile import ZipFile, ZIP_DEFLATED

from pathlib import Path
import time
from threading import Event
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image, TiffImagePlugin
import pytest
import numpy as np

from backend.api.app import app
from backend.image import api
from backend.image.assets import ImageAssetStore
from backend.image.fiji_process import JOBS_ROOT, RUNTIME, verify_roi_collection_native
from backend.image.roi_collection import source_identity, validate_collection
from backend.image.multi_measure import run_native_multi_measure
from backend.image.set_measurements import MEASUREMENT_OPTIONS, run_native_set_measurements
from backend.image.non_area_measure import run_native_non_area_measure
from backend.image.selection import build_selection
from backend.image.results import ImageResultStore
from scripts.generate_image_acceptance_fixtures import generate


pytestmark = pytest.mark.skipif(
    os.environ.get("BFS_RUN_FIJI_INTEGRATION") != "1" or not RUNTIME.is_dir(),
    reason="Run explicitly against the audited local Fiji runtime",
)


def _uploaded_tiff(client: TestClient, tmp_path: Path) -> str:
    source = tmp_path / "synthetic-16bit.tif"
    Image.new("I;16", (7, 6), 1023).save(source)
    response = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    assert response.status_code == 201
    return response.json()["id"]


def _combined_czt_tiff(path: Path) -> np.ndarray:
    """ImageJ pages in explicit T/Z/C order, C varying fastest."""
    t, z, c, y, x = np.indices((2, 3, 2, 8, 9), dtype=np.uint32)
    values = (t * 10000 + z * 2000 + c * 500 + y * 20 + x).astype(np.uint16)
    pages = [Image.fromarray(plane) for plane in values.reshape(12, 8, 9)]
    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[270] = "ImageJ=1.54\nimages=12\nchannels=2\nslices=3\nframes=2\nhyperstack=true\nmode=grayscale\nunit=um\n"
    pages[0].save(path, save_all=True, append_images=pages[1:], tiffinfo=info,
                  compression="tiff_deflate")
    for page in pages:
        page.close()
    return values


def _settled(client: TestClient, job_id: str) -> dict:
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        response = client.get(f"/api/image/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["state"] not in ("queued", "running"):
            return job
        time.sleep(0.2)
    raise AssertionError("Fiji job did not settle within integration test limit")


def test_fiji_reads_synthetic_tiff_metadata(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    client = TestClient(app)
    asset_id = _uploaded_tiff(client, tmp_path)
    response = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert response.status_code == 202
    job = _settled(client, response.json()["id"])
    assert job["state"] == "succeeded", job["error"]
    assert job["result"]["pixel_type"] == "net.imglib2.type.numeric.integer.UnsignedShortType"
    assert job["result"]["bit_depth"] == 16
    axes = {axis["name"]: axis["length"] for axis in job["result"]["axes"]}
    assert axes["X"] == 7 and axes["Y"] == 6
    inspected = client.get(f"/api/image/assets/{asset_id}").json()
    assert inspected["metadata_status"] == "fiji_inspected"
    assert inspected["bit_depth"] == 16
    temporary_store.close()


def test_fiji_records_calibrated_synthetic_axes(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    temporary_results = ImageResultStore(tmp_path / "results")
    monkeypatch.setattr(api, "store", temporary_store)
    monkeypatch.setattr(api, "results", temporary_results)
    client = TestClient(app)
    fixture_root = tmp_path / "fixtures"
    generate(fixture_root)
    source = fixture_root / "灰度16_非等距标定.tif"
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    assert uploaded.status_code == 201
    asset_id = uploaded.json()["id"]
    submitted = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert submitted.status_code == 202
    job = _settled(client, submitted.json()["id"])
    assert job["state"] == "succeeded", job["error"]
    axes = {axis["name"]: axis for axis in job["result"]["axes"]}
    assert axes["X"]["scale"] == 0.25
    assert axes["Y"]["scale"] == 0.5
    assert axes["X"]["unit"] in ("um", "µm")
    assert axes["Y"]["unit"] in ("um", "µm")
    grid = client.post("/api/image/jobs/exact-grid", json={
        "version": "1.0", "asset_ids": [asset_id], "columns": 1, "gap_px": 0,
    })
    assert grid.status_code == 202
    assembled = _settled(client, grid.json()["id"])
    assert assembled["state"] == "succeeded", assembled["error"]
    placement = assembled["result"]["proof"]["placements"][0]
    assert placement["source_axes"] == job["result"]["axes"]
    assert assembled["result"]["proof"]["metadata_preserved"] is False
    temporary_results.close()
    temporary_store.close()


def test_fiji_inspection_can_be_cancelled(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    client = TestClient(app)
    asset_id = _uploaded_tiff(client, tmp_path)
    submitted = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert submitted.status_code == 202
    job_id = submitted.json()["id"]
    pid_file = JOBS_ROOT / job_id / "engine.pid"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and not pid_file.is_file():
        assert client.get(f"/api/image/jobs/{job_id}").json()["state"] in ("queued", "running")
        time.sleep(0.02)
    assert pid_file.is_file(), "Expected a launched Fiji process before cancellation"
    pid = int(pid_file.read_text(encoding="ascii"))
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 409
    assert client.post(f"/api/image/jobs/{job_id}/cancel").status_code == 200
    job = _settled(client, job_id)
    assert job["state"] == "cancelled"
    assert job["result"] is None
    assert not (JOBS_ROOT / job_id).exists()
    if os.name == "nt":
        kernel = ctypes.windll.kernel32
        kernel.OpenProcess.restype = ctypes.c_void_p
        handle = kernel.OpenProcess(0x1000, False, pid)
        if handle:
            code = ctypes.c_ulong()
            assert kernel.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
            kernel.CloseHandle(ctypes.c_void_p(handle))
            assert code.value != 259, "Launched Fiji process still running after cancellation"
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


def test_fiji_invert_8bit_command_roundtrip(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    temporary_results = ImageResultStore(tmp_path / "results")
    monkeypatch.setattr(api, "store", temporary_store)
    monkeypatch.setattr(api, "results", temporary_results)
    source = Image.frombytes("L", (4, 2), bytes([10, 20, 30, 40, 50, 60, 70, 80]))
    buffer = BytesIO()
    source.save(buffer, format="TIFF")
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": ("gray.tif", buffer.getvalue(), "image/tiff")})
    assert uploaded.status_code == 201
    submitted = client.post("/api/image/jobs/invert-8bit", json={"asset_id": uploaded.json()["id"]})
    assert submitted.status_code == 202
    job = _settled(client, submitted.json()["id"])
    assert job["state"] == "succeeded", job["error"]
    assert job["result"]["proof"]["command"] == "net.imagej.plugins.commands.assign.InvertDataValues"
    assert job["result"]["proof"]["verified_pixels"] == 8
    assert job["result"]["proof"]["metadata_preserved"] is False
    downloaded = client.get(f"/api/image/results/{job['result']['id']}/file")
    assert downloaded.status_code == 200
    with Image.open(BytesIO(downloaded.content)) as output:
        assert output.mode == "L" and output.size == (4, 2)
        assert output.tobytes() == bytes([245, 235, 225, 215, 205, 195, 185, 175])
    temporary_results.close()
    temporary_store.close()


def test_fiji_invert_rejects_16bit_without_publishing(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    temporary_results = ImageResultStore(tmp_path / "results")
    monkeypatch.setattr(api, "store", temporary_store)
    monkeypatch.setattr(api, "results", temporary_results)
    client = TestClient(app)
    asset_id = _uploaded_tiff(client, tmp_path)
    submitted = client.post("/api/image/jobs/invert-8bit", json={"asset_id": asset_id})
    assert submitted.status_code == 202
    job = _settled(client, submitted.json()["id"])
    assert job["state"] == "failed"
    assert job["result"] is None
    assert temporary_results.all_public() == []
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_results.close()
    temporary_store.close()


def test_fiji_measures_explicit_z_plane_and_rectangle(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    fixtures = tmp_path / "fixtures"
    generate(fixtures)
    source = fixtures / "zstack16.tif"
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    assert uploaded.status_code == 201
    asset_id = uploaded.json()["id"]
    inspected = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert inspected.status_code == 202
    assert _settled(client, inspected.json()["id"])["state"] == "succeeded"
    missing = client.post("/api/image/jobs/measure-selection", json={
        "version": "1.0", "asset_id": asset_id, "indices": {},
        "roi": {"x": 3, "y": 4, "width": 5, "height": 6},
    })
    assert missing.status_code == 422
    submitted = client.post("/api/image/jobs/measure-selection", json={
        "version": "1.0", "asset_id": asset_id, "indices": {"Z": 1},
        "roi": {"x": 3, "y": 4, "width": 5, "height": 6},
        "extra_measurements": ["std_dev", "median", "integrated_density"],
    })
    assert submitted.status_code == 202, submitted.text
    assert submitted.json()["selection"]["indices"] == {"Z": 1}
    measured = _settled(client, submitted.json()["id"])
    assert measured["state"] == "succeeded", measured["error"]
    expected = np.load(fixtures / "zstack16.tif.expected.npy", allow_pickle=False)[1, 4:10, 3:8]
    assert measured["result"]["sample_count"] == 30
    assert measured["result"]["sum"] == float(expected.sum())
    assert measured["result"]["mean"] == float(expected.mean())
    assert measured["result"]["min"] == float(expected.min())
    assert measured["result"]["max"] == float(expected.max())
    assert measured["result"]["imagej1_analyzer"]["mean"] == float(expected.mean())
    assert measured["result"]["imagej1_analyzer"]["area"] == pytest.approx(3.75)
    assert measured["result"]["imagej1_analyzer"]["area_unit"] in ("um^2", "µm^2")
    assert measured["result"]["imagej1_analyzer"]["std_dev"] == pytest.approx(float(expected.std(ddof=1)), rel=1e-5)
    # ImageJ1 selects the first histogram bin whose cumulative count exceeds n/2.
    # For an even number of pixels this is the upper middle value, not NumPy's average.
    assert measured["result"]["imagej1_analyzer"]["median"] == float(np.sort(expected, axis=None)[expected.size // 2])
    assert measured["result"]["imagej1_analyzer"]["raw_integrated_density"] == float(expected.sum())
    assert measured["result"]["imagej1_analyzer"]["integrated_density"] == pytest.approx(float(expected.mean()) * 3.75)
    assert measured["result"]["selection"]["roi"]["kind"] == "rectangle"
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


def test_fiji_measure_mode_uses_smallest_tied_16bit_value(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    values = np.array([1000] * 4 + [2000] * 4 + [3000] * 3 + [4000], dtype=np.uint16).reshape(3, 4)
    buffer = BytesIO()
    Image.fromarray(values).save(buffer, format="TIFF")
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": ("mode16.tif", buffer.getvalue(), "image/tiff")})
    assert uploaded.status_code == 201
    asset_id = uploaded.json()["id"]
    inspected = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert inspected.status_code == 202
    assert _settled(client, inspected.json()["id"])["state"] == "succeeded"
    submitted = client.post("/api/image/jobs/measure-selection", json={
        "version": "1.0", "asset_id": asset_id, "indices": {}, "extra_measurements": ["mode"],
    })
    assert submitted.status_code == 202, submitted.text
    measured = _settled(client, submitted.json()["id"])
    assert measured["state"] == "succeeded", measured["error"]
    assert measured["result"]["sample_count"] == 12
    assert measured["result"]["imagej1_analyzer"]["mode"] == 1000.0
    assert "median" not in measured["result"]["imagej1_analyzer"]
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


@pytest.mark.parametrize("filename,axis,index", [
    ("channels16.tif", "c", 1),
    ("zstack16.tif", "z", 1),
    ("time16.tif", "t", 2),
])
def test_fiji_inspected_plane_preview_is_display_only(tmp_path, monkeypatch, filename, axis, index):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    fixtures = tmp_path / "fixtures"
    generate(fixtures)
    source = fixtures / filename
    source_digest = source.read_bytes()
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source_digest, "image/tiff")})
    assert uploaded.status_code == 201
    asset_id = uploaded.json()["id"]
    endpoint = f"/api/image/assets/{asset_id}/plane-preview"
    assert client.get(endpoint, params={axis: index}).status_code == 422
    inspected = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert inspected.status_code == 202
    assert _settled(client, inspected.json()["id"])["state"] == "succeeded"
    assert client.get(endpoint).status_code == 422
    assert client.get(endpoint, params={axis: 99}).status_code == 422
    expected = np.load(fixtures / (filename + ".expected.npy"), allow_pickle=False)
    for plane_index in (0, index):
        response = client.get(endpoint, params={axis: plane_index})
        assert response.status_code == 200, response.text
        assert response.headers["x-preview-only"] == "true"
        assert response.headers["x-source-plane"] == str(plane_index)
        with Image.open(BytesIO(response.content)) as shown:
            observed = np.array(shown)
        plane = expected[plane_index].astype(np.float64)
        reference = ((plane - plane.min()) / (plane.max() - plane.min()) * 255).astype(np.uint8)
        assert np.array_equal(observed, reference)
    assert temporary_store.get(asset_id).path.read_bytes() == source_digest
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


def test_fiji_combined_czt_plane_selection_matches_imagej_pages(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    source = tmp_path / "combined-czt16.tif"
    expected = _combined_czt_tiff(source)
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    assert uploaded.status_code == 201
    asset_id = uploaded.json()["id"]
    inspected = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert inspected.status_code == 202
    job = _settled(client, inspected.json()["id"])
    assert job["state"] == "succeeded", job["error"]
    axes = {axis["name"]: axis["length"] for axis in job["result"]["axes"]}
    assert axes == {"X": 9, "Y": 8, "Channel": 2, "Z": 3, "Time": 2}
    endpoint = f"/api/image/assets/{asset_id}/plane-preview"
    assert client.get(endpoint, params={"c": 0, "z": 0}).status_code == 422
    for t in range(2):
        for z in range(3):
            for c in range(2):
                preview = client.get(endpoint, params={"c": c, "z": z, "t": t})
                assert preview.status_code == 200, preview.text
                assert preview.headers["x-source-plane"] == str((t * 3 + z) * 2 + c)
                assert preview.headers["x-source-indices"] == f"C={c},Z={z},T={t}"
                with Image.open(BytesIO(preview.content)) as shown:
                    observed = np.array(shown)
                plane = expected[t, z, c].astype(np.float64)
                reference = ((plane - plane.min()) / (plane.max() - plane.min()) * 255).astype(np.uint8)
                assert np.array_equal(observed, reference)
    for t, z, c in ((0, 0, 0), (0, 0, 1), (0, 1, 0), (1, 0, 0), (1, 2, 1)):
        indices = {"C": c, "Z": z, "T": t}
        submitted = client.post("/api/image/jobs/measure-selection", json={
            "version": "1.0", "asset_id": asset_id, "indices": indices,
            "roi": {"x": 2, "y": 1, "width": 3, "height": 4},
        })
        assert submitted.status_code == 202, submitted.text
        measured = _settled(client, submitted.json()["id"])
        assert measured["state"] == "succeeded", measured["error"]
        reference = expected[t, z, c, 1:5, 2:5]
        assert measured["result"]["sample_count"] == 12
        assert measured["result"]["sum"] == float(reference.sum())
        assert measured["result"]["imagej1_analyzer"]["mean"] == float(reference.mean())
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


def _verify_measurement_downloads(client, job_id, source_sha256, pixels, selection):
    record = client.get(f"/api/image/jobs/{job_id}/measurement.json")
    assert record.status_code == 200 and "attachment" in record.headers["content-disposition"]
    payload = record.json()
    assert payload["source"]["sha256"] == source_sha256
    assert payload["selection"] == selection
    assert payload["result"]["sample_count"] == len(pixels)
    assert payload["result"]["sum"] == float(pixels.sum())
    exported = client.get(f"/api/image/jobs/{job_id}/measurement.csv")
    assert exported.status_code == 200
    row, = csv.DictReader(StringIO(exported.content.decode("utf-8-sig")))
    assert int(row["sample_count"]) == len(pixels)
    assert int(row["candidate_pixels"]) == selection["sample_count"]
    assert float(row["mean"]) == float(pixels.mean())
    assert row["source_sha256"] == source_sha256


def test_fiji_native_ellipse_roi_uses_masked_pixels(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    source = tmp_path / "ellipse-czt16.tif"
    expected = _combined_czt_tiff(source)
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    asset_id = uploaded.json()["id"]
    inspection = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert _settled(client, inspection.json()["id"])["state"] == "succeeded"
    roi = {"kind": "ellipse", "x": 1, "y": 1, "width": 7, "height": 5}
    selection = client.post("/api/image/jobs/measure-selection", json={
        "version": "1.0", "asset_id": asset_id, "indices": {"C": 1, "Z": 2, "T": 1}, "roi": roi,
    })
    assert selection.status_code == 202, selection.text
    result = _settled(client, selection.json()["id"])
    assert result["state"] == "succeeded", result["error"]
    yy, xx = np.indices((8, 9))
    inside = (((xx + 0.5 - 4.5) / 3.5) ** 2 + ((yy + 0.5 - 3.5) / 2.5) ** 2 <= 1)
    pixels = expected[1, 2, 1][inside]
    assert result["result"]["sample_count"] == len(pixels) < 35
    assert result["result"]["sum"] == float(pixels.sum())
    assert result["result"]["imagej1_analyzer"]["mean"] == float(pixels.mean())
    assert result["result"]["imagej1_analyzer"]["area"] == float(len(pixels))
    assert result["result"]["selection"]["roi"] == roi
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    _verify_measurement_downloads(client, result["id"], uploaded.json()["sha256"], pixels, result["selection"])
    temporary_store.close()


def test_fiji_native_polygon_roi_uses_masked_pixels(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    source = tmp_path / "polygon-czt16.tif"
    expected = _combined_czt_tiff(source)
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    asset_id = uploaded.json()["id"]
    inspection = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert _settled(client, inspection.json()["id"])["state"] == "succeeded"
    points = [{"x": 1, "y": 1}, {"x": 7, "y": 1}, {"x": 1, "y": 6}]
    selection = client.post("/api/image/jobs/measure-selection", json={
        "version": "1.0", "asset_id": asset_id, "indices": {"C": 1, "Z": 2, "T": 1},
        "roi": {"kind": "polygon", "points": points},
    })
    assert selection.status_code == 202, selection.text
    result = _settled(client, selection.json()["id"])
    assert result["state"] == "succeeded", result["error"]
    yy, xx = np.indices((8, 9))
    inside = ((xx + 0.5 >= 1) & (yy + 0.5 >= 1)
              & ((xx + 0.5 - 1) / 6 + (yy + 0.5 - 1) / 5 <= 1))
    pixels = expected[1, 2, 1][inside]
    assert result["result"]["sample_count"] == len(pixels)
    assert result["result"]["sum"] == float(pixels.sum())
    assert result["result"]["imagej1_analyzer"]["mean"] == float(pixels.mean())
    assert result["result"]["imagej1_analyzer"]["area"] == float(len(pixels))
    assert result["result"]["selection"]["roi"]["points"] == points
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    _verify_measurement_downloads(client, result["id"], uploaded.json()["sha256"], pixels, result["selection"])
    temporary_store.close()


def test_fiji_roi_manager_collection_zip_roundtrip_and_measure(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    source = tmp_path / "roi-manager-czt16.tif"
    _combined_czt_tiff(source)
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    asset_id = uploaded.json()["id"]
    inspection = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert _settled(client, inspection.json()["id"])["state"] == "succeeded"
    asset = temporary_store.get(asset_id)
    document = validate_collection(asset, {"version": "1.0", "source": source_identity(asset), "items": [
        {"id": uuid4().hex, "name": "Nucleus A", "indices": {"C": 1, "Z": 2, "T": 1},
         "roi": {"kind": "ellipse", "x": 1, "y": 1, "width": 7, "height": 5}},
        {"id": uuid4().hex, "name": "Boundary B", "indices": {"C": 0, "Z": 1, "T": 0},
         "roi": {"kind": "polygon", "points": [
             {"x": 1, "y": 1}, {"x": 7, "y": 1}, {"x": 1, "y": 6}]}},
    ]})
    result = verify_roi_collection_native(asset, uuid4().hex, Event(), document)
    assert result["count"] == 2
    assert [(item["name"], item["kind"], item["area"], item["mean"])
            for item in result["measurements"]] == [
        ("Nucleus A", "ellipse", 31.0, 14564.0),
        ("Boundary B", "polygon", 15.0, 2049.0),
    ]
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


def test_fiji_native_roi_zip_export_import_preserves_shapes_and_planes(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    source = tmp_path / "native-rois-czt16.tif"
    _combined_czt_tiff(source)
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    asset_id = uploaded.json()["id"]
    inspection = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert _settled(client, inspection.json()["id"])["state"] == "succeeded"
    asset = temporary_store.get(asset_id)
    document = validate_collection(asset, {"version": "1.0", "source": source_identity(asset), "items": [
        {"id": uuid4().hex, "name": "Nucleus A", "indices": {"C": 1, "Z": 2, "T": 1},
         "roi": {"kind": "ellipse", "x": 1, "y": 1, "width": 7, "height": 5}},
        {"id": uuid4().hex, "name": "Boundary B", "indices": {"C": 0, "Z": 1, "T": 0},
         "roi": {"kind": "polygon", "points": [
             {"x": 1, "y": 1}, {"x": 7, "y": 1}, {"x": 1, "y": 6}]}},
    ]})
    exported = client.post(f"/api/image/assets/{asset_id}/roi-collection/native-export", json=document)
    assert exported.status_code == 200, exported.text
    archive = base64.b64decode(exported.json()["archive_base64"])
    with ZipFile(BytesIO(archive)) as saved:
        names = saved.namelist()
        assert len([name for name in names if name.endswith(".roi")]) == 2
        assert all(saved.read(name).startswith(b"Iout") for name in names if name.endswith(".roi"))
        assert "biofigure-source.json" in names
    imported = client.post(f"/api/image/assets/{asset_id}/roi-collection/native-import",
                           json={"archive_base64": exported.json()["archive_base64"]})
    assert imported.status_code == 200, imported.text
    assert imported.json()["source_bound"] is True
    assert [(item["name"], item["roi"]["kind"], item["indices"])
            for item in imported.json()["document"]["items"]] == [
        ("Nucleus A", "ellipse", {"C": 1, "Z": 2, "T": 1}),
        ("Boundary B", "polygon", {"C": 0, "Z": 1, "T": 0}),
    ]
    assert [(item["area"], item["mean"]) for item in imported.json()["measurements"]] == [
        (31.0, 14564.0), (15.0, 2049.0)]
    plain = BytesIO()
    with ZipFile(BytesIO(archive)) as source_zip, ZipFile(plain, "w", ZIP_DEFLATED) as target_zip:
        for name in source_zip.namelist():
            if name.endswith(".roi"):
                target_zip.writestr(name, source_zip.read(name))
    plain_import = client.post(f"/api/image/assets/{asset_id}/roi-collection/native-import",
                               json={"archive_base64": base64.b64encode(plain.getvalue()).decode()})
    assert plain_import.status_code == 200, plain_import.text
    assert plain_import.json()["source_bound"] is False
    fractional = BytesIO()
    changed = False
    with ZipFile(BytesIO(archive)) as source_zip, ZipFile(fractional, "w", ZIP_DEFLATED) as target_zip:
        for name in source_zip.namelist():
            data = bytearray(source_zip.read(name))
            if name.endswith(".roi") and data[6] == 2 and not changed:
                data[4:6] = (228).to_bytes(2, "big")
                options = int.from_bytes(data[50:52], "big") | 128
                data[50:52] = options.to_bytes(2, "big")
                data[18:34] = struct.pack(">4f", 1.5, 1, 7, 5)
                changed = True
            target_zip.writestr(name, data)
    assert changed
    refused = client.post(f"/api/image/assets/{asset_id}/roi-collection/native-import",
        json={"archive_base64": base64.b64encode(fractional.getvalue()).decode()})
    assert refused.status_code == 422
    assert "亚像素" in refused.json()["detail"]
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


def test_fiji_named_roi_collection_measures_each_explicit_plane(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    source = tmp_path / "collection-czt16.tif"
    _combined_czt_tiff(source)
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    asset_id = uploaded.json()["id"]
    inspection = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert _settled(client, inspection.json()["id"])["state"] == "succeeded"
    asset = temporary_store.get(asset_id)
    document = validate_collection(asset, {"version": "1.0", "source": source_identity(asset), "items": [
        {"id": uuid4().hex, "name": "Nucleus A", "indices": {"C": 1, "Z": 2, "T": 1},
         "roi": {"kind": "ellipse", "x": 1, "y": 1, "width": 7, "height": 5}},
        {"id": uuid4().hex, "name": "Boundary B", "indices": {"C": 0, "Z": 1, "T": 0},
         "roi": {"kind": "polygon", "points": [
             {"x": 1, "y": 1}, {"x": 7, "y": 1}, {"x": 1, "y": 6}]}},
    ]})
    submitted = client.post(f"/api/image/assets/{asset_id}/roi-collection/measure", json={
        "collection": document, "extra_measurements": ["std_dev", "median", "integrated_density"]})
    assert submitted.status_code == 202, submitted.text
    completed = _settled(client, submitted.json()["id"])
    assert completed["state"] == "succeeded", completed["error"]
    result = completed["result"]
    assert result["roi_manager_multi_measure_equivalent"] is False
    assert result["source"] == document["source"]
    assert [(row["id"], row["name"], row["indices"], row["roi"])
            for row in result["rows"]] == [
        (item["id"], item["name"], item["indices"], item["roi"]) for item in document["items"]]
    assert [(row["sample_count"], row["imagej1_analyzer"]["area"],
             row["imagej1_analyzer"]["mean"]) for row in result["rows"]] == [
        (31, 31.0, 14564.0), (15, 15.0, 2049.0)]
    assert [row["imagej1_analyzer"]["raw_integrated_density"] for row in result["rows"]] == [
        31 * 14564.0, 15 * 2049.0]
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


def test_fiji_roi_manager_multi_measure_stack_layout_and_append(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    source = tmp_path / "multi-measure-czt16.tif"
    _combined_czt_tiff(source)
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    asset_id = uploaded.json()["id"]
    inspection = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert _settled(client, inspection.json()["id"])["state"] == "succeeded"
    asset = temporary_store.get(asset_id)
    document = validate_collection(asset, {"version": "1.0", "source": source_identity(asset), "items": [
        {"id": uuid4().hex, "name": "Region A", "indices": {"C": 1, "Z": 2, "T": 1},
         "roi": {"kind": "rectangle", "x": 1, "y": 1, "width": 2, "height": 2}},
        {"id": uuid4().hex, "name": "Region B", "indices": {"C": 0, "Z": 1, "T": 0},
         "roi": {"kind": "rectangle", "x": 4, "y": 2, "width": 3, "height": 2}},
    ]})
    submitted = client.post(f"/api/image/assets/{asset_id}/multi-measure", json={
        "collection": document, "selected_roi_ids": [item["id"] for item in document["items"]],
        "current_plane": {"C": 1, "Z": 2, "T": 1}, "runs": [
            {"measure_all": True, "one_row_per_slice": True, "append_results": False},
            {"measure_all": True, "one_row_per_slice": True, "append_results": True},
            {"measure_all": False, "one_row_per_slice": False, "append_results": False},
        ], "measurement_flags": []})
    assert submitted.status_code == 202, submitted.text
    completed = _settled(client, submitted.json()["id"])
    assert completed["state"] == "succeeded", completed["error"]
    result = completed["result"]
    assert result["source_file"]["sha256"] == asset.sha256
    assert [run["row_count"] for run in result["runs"]] == [12, 24, 2]
    assert [(run["new_row_start"], run["new_row_count"]) for run in result["runs"]] == [
        (0, 12), (12, 12), (0, 2),
    ]
    assert result["current_stack_index"] == 12
    assert result["stack_planes"][0] == {"stack_index": 1, "C": 0, "Z": 0, "T": 0}
    assert result["stack_planes"][-1] == {"stack_index": 12, "C": 1, "Z": 2, "T": 1}
    first = result["runs"][0]
    assert "Area(Region A)" in first["headings"] and "Mean(Region B)" in first["headings"]
    assert first["rows"][0]["Mean(Region A)"] == pytest.approx(31.5)
    assert first["rows"][0]["Mean(Region B)"] == pytest.approx(55.0)
    assert first["rows"][1]["Mean(Region A)"] == pytest.approx(531.5)
    assert result["runs"][1]["rows"][:12] == first["rows"]
    assert result["runs"][1]["rows"][12:] == first["rows"]
    last = result["runs"][2]
    assert last["layout"] == "one_row_per_measurement"
    assert [row["Mean"] for row in last["rows"]] == pytest.approx([14531.5, 14555.0])
    row_layout = run_native_multi_measure(asset, document, [item["id"] for item in document["items"]],
        {"C": 1, "Z": 2, "T": 1}, [
            {"measure_all": False, "one_row_per_slice": False, "append_results": False},
            {"measure_all": False, "one_row_per_slice": False, "append_results": True},
        ], ["std_dev"], Event())
    assert [run["row_count"] for run in row_layout["runs"]] == [2, 4]
    assert [(run["new_row_start"], run["new_row_count"]) for run in row_layout["runs"]] == [
        (0, 2), (2, 2),
    ]
    assert row_layout["runs"][1]["rows"][:2] == row_layout["runs"][0]["rows"]
    assert row_layout["runs"][1]["rows"][2:] == row_layout["runs"][0]["rows"]
    assert "StdDev" in row_layout["runs"][0]["headings"]
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


def test_fiji_set_measurements_all_area_options_redirect_threshold_and_calibration(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    client = TestClient(app)
    yy, xx = np.indices((6, 8), dtype=np.uint16)
    source_pixels = (10 + yy * 2 + xx).astype(np.uint16)
    target_pixels = (100 + yy * 10 + xx).astype(np.uint16)
    ids = []
    for name, pixels, calibrated in (("source.tif", source_pixels, False),
                                     ("target.tif", target_pixels, True)):
        path = tmp_path / name
        info = TiffImagePlugin.ImageFileDirectory_v2()
        if calibrated:
            info[282], info[283], info[296] = 4.0, 2.0, 1
            info[270] = "ImageJ=1.54\nimages=1\nunit=um\nhyperstack=false\nmode=grayscale\n"
        Image.fromarray(pixels).save(path, tiffinfo=info)
        response = client.post("/api/image/assets", files={"file": (name, path.read_bytes(), "image/tiff")})
        assert response.status_code == 201
        ids.append(response.json()["id"])
        job = client.post("/api/image/jobs/inspect", json={"asset_id": ids[-1]})
        assert _settled(client, job.json()["id"])["state"] == "succeeded"
    source_asset, target_asset = [temporary_store.get(identifier) for identifier in ids]
    selection = build_selection(source_asset, {}, {"kind": "rectangle", "x": 1, "y": 1, "width": 4, "height": 3})
    submitted = client.post(f"/api/image/assets/{source_asset.id}/native-measure", json={
        "version": "1.0", "indices": {}, "roi": selection.roi,
        "settings": {"measurements": list(MEASUREMENT_OPTIONS), "decimal_places": 2,
                     "threshold": {"min": 120, "max": 135}},
        "redirect_asset_id": target_asset.id, "redirect_plane": {}})
    assert submitted.status_code == 202, submitted.text
    completed = _settled(client, submitted.json()["id"])
    assert completed["state"] == "succeeded", completed["error"]
    result = completed["result"]
    assert result["redirect_source"]["sha256"] == target_asset.sha256
    assert result["row_count"] == 1
    assert result["source_sha256"] == source_asset.sha256
    assert result["redirect_sha256"] == target_asset.sha256
    assert result["measurement_bits"] > 0
    assert result["sampled_calibration"]["pixel_width"] == pytest.approx(0.25)
    assert result["sampled_calibration"]["pixel_height"] == pytest.approx(0.5)
    assert result["roi_source_calibration"]["pixel_width"] == pytest.approx(1.0)
    assert result["roi_source_calibration"]["pixel_height"] == pytest.approx(1.0)
    assert result["row"]["Area"] == pytest.approx(1.0)
    assert result["row"]["Mean"] == pytest.approx(127.5)
    assert result["row"]["Min"] == pytest.approx(121)
    assert result["row"]["Max"] == pytest.approx(134)
    assert result["overlay_count"] == 1
    assert result["label"].endswith(".tif")
    assert result["label"] in result["displayed_row"]
    assert result["headings"] == [
        "Area", "Mean", "StdDev", "Mode", "Min", "Max", "X", "Y", "XM", "YM",
        "Perim.", "BX", "BY", "Width", "Height", "Major", "Minor", "Angle",
        "Circ.", "Feret", "IntDen", "Median", "Skew", "Kurt", "%Area",
        "RawIntDen", "Slice", "FeretX", "FeretY", "FeretAngle", "MinFeret",
        "AR", "Round", "Solidity", "MinThr", "MaxThr",
    ]
    assert result["row"]["%Area"] == pytest.approx(100 * 8 / 12)
    assert result["row"]["RawIntDen"] == pytest.approx(1020)
    assert result["row"]["IntDen"] == pytest.approx(127.5)
    assert result["row"]["Perim."] == pytest.approx(14.0)
    assert result["row"]["Feret"] == pytest.approx(5.0)
    assert result["row"]["MinThr"] == 120 and result["row"]["MaxThr"] == 135
    assert result["non_finite_headings"] == ["AR", "Round"]
    assert result["row"]["AR"] is None and result["row"]["Round"] is None
    assert "1.28E2" in result["displayed_row"]
    local = run_native_set_measurements(source_asset, selection,
        {"measurements": ["area", "mean", "limit_to_threshold"], "decimal_places": 6,
         "threshold": {"min": 14, "max": 18}}, None, None, Event())
    assert local["redirect_sha256"] is None
    assert local["row"]["Area"] == 9
    assert local["row"]["Mean"] == pytest.approx(146 / 9)
    assert local["row"]["Mean"] != result["row"]["Mean"]
    assert "16.222222" in local["displayed_row"]
    for identifier in ids:
        assert client.delete(f"/api/image/assets/{identifier}").status_code == 204
    temporary_store.close()


def test_fiji_set_measurements_redirects_matching_linear_stack_plane(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    client = TestClient(app)
    primary = tmp_path / "primary-czt.tif"
    pixels = _combined_czt_tiff(primary)
    shifted = tmp_path / "shifted-czt.tif"
    pages = [Image.fromarray(plane) for plane in (pixels + 1000).reshape(12, 8, 9)]
    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[270] = "ImageJ=1.54\nimages=12\nchannels=2\nslices=3\nframes=2\nhyperstack=true\nmode=grayscale\nunit=um\n"
    pages[0].save(shifted, save_all=True, append_images=pages[1:], tiffinfo=info,
                  compression="tiff_deflate")
    for page in pages:
        page.close()
    ids = []
    for path in (primary, shifted):
        uploaded = client.post("/api/image/assets", files={"file": (path.name, path.read_bytes(), "image/tiff")})
        assert uploaded.status_code == 201
        ids.append(uploaded.json()["id"])
        job = client.post("/api/image/jobs/inspect", json={"asset_id": ids[-1]})
        assert _settled(client, job.json()["id"])["state"] == "succeeded"
    source, target = [temporary_store.get(identifier) for identifier in ids]
    selection = build_selection(source, {"C": 1, "Z": 2, "T": 1},
        {"kind": "rectangle", "x": 1, "y": 1, "width": 2, "height": 2})
    settings = {"measurements": ["mean", "stack_position"], "decimal_places": 3, "threshold": None}
    with pytest.raises(ValueError, match="线性平面"):
        run_native_set_measurements(source, selection, settings, target,
                                    {"C": 0, "Z": 2, "T": 1}, Event())
    result = run_native_set_measurements(source, selection, settings, target,
                                         {"C": 1, "Z": 2, "T": 1}, Event())
    assert result["source_stack_index"] == result["sampled_stack_index"] == 12
    assert result["row"]["Mean"] == pytest.approx(15531.5)
    assert [result["row"][name] for name in ("Ch", "Slice", "Frame")] == [2, 3, 2]
    for identifier in ids:
        assert client.delete(f"/api/image/assets/{identifier}").status_code == 204
    temporary_store.close()


def test_fiji_non_area_roi_native_types_and_rows(tmp_path, monkeypatch):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    client = TestClient(app)
    source = tmp_path / "non-area-czt.tif"
    pixels = _combined_czt_tiff(source)
    uploaded = client.post("/api/image/assets", files={"file": (source.name, source.read_bytes(), "image/tiff")})
    assert uploaded.status_code == 201
    asset_id = uploaded.json()["id"]
    submitted = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert _settled(client, submitted.json()["id"])["state"] == "succeeded"
    asset = temporary_store.get(asset_id)
    plane = {"C": 1, "Z": 2, "T": 1}
    settings = {"measurements": ["mean", "min_max", "std_dev", "centroid", "display_label", "stack_position"],
                "decimal_places": 3, "threshold": None}
    cases = [
        {"version": "1.0", "kind": "line", "points": [{"x": 1.25, "y": 1.5}, {"x": 5.25, "y": 1.5}], "stroke_width": 1.0},
        {"version": "1.0", "kind": "line", "points": [{"x": 1.25, "y": 1.5}, {"x": 5.25, "y": 1.5}], "stroke_width": 3.0},
        {"version": "1.0", "kind": "polyline", "points": [{"x": 1.25, "y": 1.5}, {"x": 4.25, "y": 1.5}, {"x": 4.25, "y": 4.5}], "stroke_width": 1.0},
        {"version": "1.0", "kind": "freeline", "points": [{"x": 1.25, "y": 1.5}, {"x": 4.25, "y": 1.5}, {"x": 4.25, "y": 4.5}], "stroke_width": 1.0},
        {"version": "1.0", "kind": "angle", "points": [{"x": 1.25, "y": 1.5}, {"x": 4.25, "y": 1.5}, {"x": 4.25, "y": 4.5}]},
        {"version": "1.0", "kind": "point", "points": [{"x": 2.25, "y": 3.5}],
         "point_positions": [12], "point_counters": [4]},
        {"version": "1.0", "kind": "multipoint", "points": [{"x": 2.25, "y": 3.5}, {"x": 4.25, "y": 2.5}],
         "point_positions": [1, 12], "point_counters": [1, 2]},
    ]
    outputs = []
    for roi in cases:
        submitted = client.post(f"/api/image/assets/{asset.id}/native-measure", json={
            "version": "1.0", "indices": plane, "roi": roi, "settings": settings})
        assert submitted.status_code == 202, submitted.text
        completed = _settled(client, submitted.json()["id"])
        assert completed["state"] == "succeeded", completed["error"]
        outputs.append(completed["result"])
    assert [output["row_count"] for output in outputs] == [1, 1, 1, 1, 1, 1, 2]
    assert outputs[0]["native_roi"]["class_name"] == "ij.gui.Line"
    assert outputs[0]["native_roi"]["subpixel"] is True
    assert outputs[0]["native_roi"]["stroke_width"] == 1.0
    assert outputs[1]["native_roi"]["stroke_width"] == 3.0
    assert outputs[0]["rows"][0]["Length"] == pytest.approx(4.0)
    assert outputs[0]["rows"][0]["Mean"] == pytest.approx(14533.25)
    assert outputs[1]["rows"][0]["Mean"] == pytest.approx(14522.5)
    assert outputs[2]["rows"][0]["Length"] == pytest.approx(6.0)
    assert outputs[3]["rows"][0]["Length"] == pytest.approx(4.47213595499958)
    assert "Angle" not in outputs[2]["headings"] and "Angle" not in outputs[3]["headings"]
    assert outputs[4]["rows"][0]["Angle"] == pytest.approx(90.0)
    assert "Length" not in outputs[4]["headings"]
    assert outputs[5]["rows"][0]["Mean"] == pytest.approx(14582.0)
    assert outputs[6]["native_roi"]["point_positions"] == [1, 12]
    assert outputs[6]["native_roi"]["point_counters"] == [1, 2]
    assert [row["Mean"] for row in outputs[6]["rows"]] == pytest.approx([82.0, 14564.0])
    assert [row["Counter"] for row in outputs[6]["rows"]] == [1, 2]
    assert [row["Slice"] for row in outputs[6]["rows"]] == [1, 3]
    assert all(output["source_stack_index"] == 12 for output in outputs)

    redirect = tmp_path / "non-area-target.tif"
    pages = [Image.fromarray(page) for page in (pixels + 1000).reshape(12, 8, 9)]
    info = TiffImagePlugin.ImageFileDirectory_v2()
    info[270] = "ImageJ=1.54\nimages=12\nchannels=2\nslices=3\nframes=2\nhyperstack=true\nmode=grayscale\nunit=um\n"
    pages[0].save(redirect, save_all=True, append_images=pages[1:], tiffinfo=info,
                  compression="tiff_deflate")
    for page in pages:
        page.close()
    target_upload = client.post("/api/image/assets", files={"file": (redirect.name, redirect.read_bytes(), "image/tiff")})
    assert target_upload.status_code == 201
    target_id = target_upload.json()["id"]
    target_inspect = client.post("/api/image/jobs/inspect", json={"asset_id": target_id})
    assert _settled(client, target_inspect.json()["id"])["state"] == "succeeded"
    target = temporary_store.get(target_id)
    submitted = client.post(f"/api/image/assets/{asset.id}/native-measure", json={
        "version": "1.0", "indices": plane, "roi": cases[0],
        "settings": {"measurements": ["mean", "min_max", "limit_to_threshold", "add_to_overlay"],
                     "decimal_places": 3, "threshold": {"min": 15531, "max": 15536}},
        "redirect_asset_id": target.id, "redirect_plane": plane})
    assert submitted.status_code == 202, submitted.text
    completed = _settled(client, submitted.json()["id"])
    assert completed["state"] == "succeeded", completed["error"]
    redirected = completed["result"]
    assert redirected["redirect_sha256"] == target.sha256
    assert redirected["sampled_stack_index"] == 12
    # The native thresholded line branch converts its interpolated profile back to 16-bit.
    assert redirected["rows"][0]["Mean"] == pytest.approx(15533.0)
    assert redirected["overlay_count"] == 1
    assert redirected["rows"][0]["MinThr"] == 15531
    assert client.delete(f"/api/image/assets/{target_id}").status_code == 204
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


@pytest.mark.parametrize("filename,axis,index", [
    ("channels16.tif", "C", 1),
    ("time16.tif", "T", 2),
])
def test_fiji_measurement_uses_selected_channel_or_time(tmp_path, monkeypatch, filename, axis, index):
    temporary_store = ImageAssetStore(tmp_path / "assets")
    monkeypatch.setattr(api, "store", temporary_store)
    fixtures = tmp_path / "fixtures"
    generate(fixtures)
    source = fixtures / filename
    client = TestClient(app)
    uploaded = client.post("/api/image/assets", files={"file": (filename, source.read_bytes(), "image/tiff")})
    assert uploaded.status_code == 201
    asset_id = uploaded.json()["id"]
    inspected = client.post("/api/image/jobs/inspect", json={"asset_id": asset_id})
    assert _settled(client, inspected.json()["id"])["state"] == "succeeded"
    submitted = client.post("/api/image/jobs/measure-selection", json={
        "version": "1.0", "asset_id": asset_id, "indices": {axis: index},
        "roi": {"x": 2, "y": 3, "width": 4, "height": 5},
    })
    assert submitted.status_code == 202, submitted.text
    job = _settled(client, submitted.json()["id"])
    assert job["state"] == "succeeded", job["error"]
    expected = np.load(fixtures / f"{filename}.expected.npy", allow_pickle=False)[index, 3:8, 2:6]
    assert job["result"]["selection"]["indices"] == {axis: index}
    assert job["result"]["sum"] == float(expected.sum())
    assert job["result"]["mean"] == float(expected.mean())
    assert job["result"]["imagej1_analyzer"]["mean"] == float(expected.mean())
    assert job["result"]["imagej1_analyzer"]["area"] == pytest.approx(2.5)
    assert job["result"]["imagej1_analyzer"]["area_unit"] in ("um^2", "µm^2")
    assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    temporary_store.close()


def test_fiji_native_area_geometries_through_shared_http_task(tmp_path, monkeypatch):
    from test_native_area_geometry_runtime import CASES
    from backend.image.jobs import ImageJobManager
    temporary_store = ImageAssetStore(tmp_path / 'assets')
    manager = ImageJobManager()
    monkeypatch.setattr(api, 'store', temporary_store)
    monkeypatch.setattr(api, 'manager', manager)
    client = TestClient(app)
    ids = []
    try:
        for name, value in [('area-source.tif', 1000), ('area-target.tif', 2000)]:
            buffer = BytesIO(); Image.new('I;16', (5, 4), value).save(buffer, format='TIFF')
            uploaded = client.post('/api/image/assets', files={'file': (name, buffer.getvalue(), 'image/tiff')})
            assert uploaded.status_code == 201
            ids.append(uploaded.json()['id'])
            inspected = client.post('/api/image/jobs/inspect', json={'asset_id': ids[-1]})
            assert _settled(client, inspected.json()['id'])['state'] == 'succeeded'
        settings = {'measurements': ['area', 'mean', 'add_to_overlay'], 'decimal_places': 3, 'threshold': None}
        cases = [*CASES,
            ({'version': '1.0', 'kind': 'rotated_rectangle', 'x1': 0, 'y1': 2, 'x2': 4, 'y2': 2, 'rect_width': 2}, 'ij.gui.RotatedRectRoi', 2),
            ({'version': '1.0', 'kind': 'rotated_ellipse', 'x1': 0, 'y1': 2, 'x2': 4, 'y2': 2, 'aspect_ratio': .5}, 'ij.gui.EllipseRoi', 3)]
        for roi, class_name, type_code in cases:
            submitted = client.post(f'/api/image/assets/{ids[0]}/native-measure', json={
                'version': '1.0', 'indices': {}, 'roi': roi, 'settings': settings})
            assert submitted.status_code == 202
            job = _settled(client, submitted.json()['id'])
            assert job['state'] == 'succeeded', (roi, job['error'])
            result = job['result']; native = result['native_roi']
            assert native['class_name'] == class_name and native['type_code'] == type_code
            assert result['row']['Mean'] == 1000 and result['row']['Area'] > 0
            assert result['overlay_count_before'] == 0 and result['overlay_count'] == 1
            assert result['roi'] == roi and result['source_file']['original_name'] == 'area-source.tif'
            if roi['kind'] == 'spline_polygon': assert len(native['float_outline']) == 32
            if roi['kind'] == 'rotated_ellipse': assert len(native['float_outline']) == 72
            if roi['kind'] == 'shape':
                assert native['shape_path']
                expected = {'union': 15, 'intersection': 3, 'xor': 12}.get(roi['operation'])
                if expected is not None: assert result['row']['Area'] == expected
        submitted = client.post(f'/api/image/assets/{ids[0]}/native-measure', json={
            'version': '1.0', 'indices': {}, 'roi': cases[-1][0],
            'settings': {**settings, 'measurements': ['area', 'mean', 'limit_to_threshold'], 'threshold': {'min': 1999, 'max': 2001}},
            'redirect_asset_id': ids[1], 'redirect_plane': {}})
        job = _settled(client, submitted.json()['id'])
        assert job['state'] == 'succeeded', job['error']
        assert job['result']['row']['Mean'] == 2000
        assert job['result']['redirect_source']['sha256'] == temporary_store.get(ids[1]).sha256
        assert temporary_store._leases == {}
    finally:
        manager.close(); temporary_store.close()


def test_fiji_native_roi_exchange_through_shared_tasks(tmp_path, monkeypatch):
    from test_native_roi_exchange_runtime import collection
    from backend.image.jobs import ImageJobManager
    temporary_store = ImageAssetStore(tmp_path / 'assets'); manager = ImageJobManager()
    monkeypatch.setattr(api, 'store', temporary_store); monkeypatch.setattr(api, 'manager', manager)
    client = TestClient(app)
    try:
        buffer = BytesIO(); Image.new('I;16', (5, 4), 1000).save(buffer, format='TIFF')
        source = client.post('/api/image/assets', files={'file': ('exchange.tif', buffer.getvalue(), 'image/tiff')}).json()
        identifier = source['id']; inspected = client.post('/api/image/jobs/inspect', json={'asset_id': identifier})
        assert _settled(client, inspected.json()['id'])['state'] == 'succeeded'
        document = collection(temporary_store.get(identifier))
        endpoint = f'/api/image/assets/{identifier}/roi-exchange'
        def exchange(operation, **fields):
            response = client.post(endpoint, json={'version': '2.0', 'operation': operation, **fields})
            assert response.status_code == 202, response.text
            job = _settled(client, response.json()['id'])
            assert job['state'] == 'succeeded', job['error']
            assert job['resource_budget']['max_report_bytes'] == 2 * 1048576
            assert temporary_store._leases == {}
            return job['result']
        exported = exchange('export_zip', collection=document)
        raw = base64.b64decode(exported['file_base64'], validate=True)
        from hashlib import sha256
        assert exported['sha256'] == sha256(raw).hexdigest() and exported['bytes'] == len(raw)
        assert len(exported['proofs']) == 14 and exported['filename'].endswith('.zip')
        imported = exchange('import_zip', file_base64=exported['file_base64'])
        assert imported['manifest_matches_source'] is True
        assert len(imported['collection']['items']) == 14
        assert any(item['roi']['kind'] == 'shape_path' for item in imported['collection']['items'])
        assert any(item['roi']['kind'] == 'rotated_rectangle' for item in imported['collection']['items'])
        second = exchange('export_zip', collection=imported['collection'])
        assert len(second['proofs']) == 14
        one = {**document, 'items': [document['items'][9]]}
        single = exchange('export_roi', collection=one)
        reimported = exchange('import_roi', file_base64=single['file_base64'])
        assert reimported['manifest_matches_source'] is False
        line = reimported['collection']['items'][0]['roi']
        assert line['kind'] == 'line' and line['stroke_width'] == 2.5
        assert line['points'] == one['items'][0]['roi']['points']
    finally:
        manager.close(); temporary_store.close()
