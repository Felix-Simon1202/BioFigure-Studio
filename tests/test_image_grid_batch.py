"""Batch grids use a separate bounded staging area, beyond the 8-image UI cache."""

from hashlib import sha256
from io import BytesIO
import asyncio
import json
import time
from threading import Event, Thread
from zipfile import ZipFile

from fastapi import UploadFile
from fastapi.testclient import TestClient
from PIL import Image

from backend.api.app import app
from backend.image import api
from backend.image import jobs as image_jobs
from backend.image.assets import ImageAssetStore
from backend.image.montage import MontageCancelled
from backend.image.results import ImageResultStore


def _rgba(seed: int) -> bytes:
    image = Image.new("RGBA", (7, 5))
    for y in range(5):
        for x in range(7):
            image.putpixel((x, y), ((x + seed) % 256, (y * 17) % 256,
                                    (seed * 31) % 256, (x * y + seed) % 256))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def test_batch_api_handles_ten_sources_without_interactive_asset_cap(tmp_path, monkeypatch):
    result_store = ImageResultStore(tmp_path / "results", max_results=2,
                                    max_bytes=512 * 1024 * 1024, extension=".zip",
                                    mime_type="application/zip", prefix="batch")
    monkeypatch.setattr(api, "batch_results", result_store)
    monkeypatch.setattr(api, "BATCH_INPUT_ROOT", tmp_path / "batch-inputs")
    client = TestClient(app)
    sources = [_rgba(index) for index in range(10)]
    files = [("files", (f"source-{index}.png", data, "image/png"))
             for index, data in enumerate(sources)]
    submitted = client.post("/api/image/jobs/batch-grid", files=files,
                            data={"group_size": "2", "columns": "2", "gap_px": "3"})
    assert submitted.status_code == 202, submitted.text
    job_id = submitted.json()["id"]
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        job = client.get(f"/api/image/jobs/{job_id}").json()
        if job["state"] not in ("queued", "running"):
            break
        time.sleep(0.02)
    assert job["state"] == "succeeded", job["error"]
    assert job["progress"] == 1.0
    assert job["result"]["proof"]["group_count"] == 5
    assert job["result"]["proof"]["source_count"] == 10
    downloaded = client.get(f"/api/image/batch-results/{job['result']['id']}/file")
    assert downloaded.status_code == 200
    assert sha256(downloaded.content).hexdigest() == job["result"]["sha256"]
    with ZipFile(BytesIO(downloaded.content)) as archive:
        assert archive.testzip() is None
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["group_count"] == 5
        for group_index in range(5):
            name = f"grid-{group_index + 1:03d}.tif"
            with Image.open(BytesIO(archive.read(name))) as grid:
                assert grid.mode == "RGBA" and grid.size == (17, 5)
                for position in (0, 1):
                    with Image.open(BytesIO(sources[group_index * 2 + position])) as source:
                        x = position * 10
                        assert grid.crop((x, 0, x + 7, 5)).tobytes() == source.tobytes()
    assert client.delete(f"/api/image/batch-results/{job['result']['id']}").status_code == 204
    assert list((tmp_path / "batch-inputs").iterdir()) == []
    result_store.close()


def test_running_batch_cancel_releases_staging_and_result(tmp_path, monkeypatch):
    inputs = ImageAssetStore(tmp_path / "inputs", max_assets=64, max_session_bytes=4 * 1024 ** 3)
    outputs = ImageResultStore(tmp_path / "outputs", extension=".zip",
                               mime_type="application/zip", prefix="batch")
    identifiers = []
    for index in range(2):
        uploaded = asyncio.run(inputs.add(UploadFile(file=BytesIO(_rgba(index)), filename=f"{index}.png")))
        identifiers.append(uploaded.id)
    started = Event()

    def held_batch(_groups, _columns, _gap, _output, cancel, _on_group_done):
        started.set()
        assert cancel.wait(5)
        raise MontageCancelled()

    monkeypatch.setattr(image_jobs, "run_grid_batch", held_batch)
    manager = image_jobs.ImageJobManager()
    job = manager.submit_batch(inputs, outputs, identifiers, 2, 2, 0)
    assert started.wait(5)
    manager.cancel(job.id)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and manager.get(job.id).state in ("queued", "running"):
        time.sleep(0.01)
    assert manager.get(job.id).state == "cancelled"
    assert manager.get(job.id).result is None
    assert not inputs.session.exists()
    assert outputs.all_public() == []
    manager.close()
    outputs.close()


def test_failed_batch_does_not_publish_partial_zip(tmp_path, monkeypatch):
    output_store = ImageResultStore(tmp_path / "results", extension=".zip",
                                    mime_type="application/zip", prefix="batch")
    monkeypatch.setattr(api, "batch_results", output_store)
    monkeypatch.setattr(api, "BATCH_INPUT_ROOT", tmp_path / "inputs")
    gray = Image.new("L", (2, 2), 3)
    buffer = BytesIO()
    gray.save(buffer, format="PNG")
    client = TestClient(app)
    submitted = client.post("/api/image/jobs/batch-grid", files=[
        ("files", ("gray.png", buffer.getvalue(), "image/png")),
        ("files", ("rgba.png", _rgba(1), "image/png")),
    ], data={"group_size": "2", "columns": "2", "gap_px": "0"})
    assert submitted.status_code == 202
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = client.get(f"/api/image/jobs/{submitted.json()['id']}").json()
        if job["state"] not in ("queued", "running"):
            break
        time.sleep(0.02)
    assert job["state"] == "failed"
    assert output_store.all_public() == []
    assert list((tmp_path / "inputs").iterdir()) == []
    output_store.close()


def test_second_batch_upload_is_rejected_before_it_stages_files(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "BATCH_INPUT_ROOT", tmp_path / "inputs")
    outputs = ImageResultStore(tmp_path / "outputs", extension=".zip",
                               mime_type="application/zip", prefix="batch")
    monkeypatch.setattr(api, "batch_results", outputs)
    entered = Event()
    resume = Event()
    original_add = ImageAssetStore.add

    async def paused_add(self, upload):
        entered.set()
        assert resume.wait(5)
        return await original_add(self, upload)

    monkeypatch.setattr(ImageAssetStore, "add", paused_add)
    first_response = []

    def submit_first():
        first_response.append(TestClient(app).post(
            "/api/image/jobs/batch-grid",
            files=[("files", ("first.png", _rgba(1), "image/png"))],
            data={"group_size": "1", "columns": "1"}))

    thread = Thread(target=submit_first)
    thread.start()
    try:
        assert entered.wait(5)
        denied = TestClient(app).post(
            "/api/image/jobs/batch-grid",
            files=[("files", ("second.png", _rgba(2), "image/png"))],
            data={"group_size": "1", "columns": "1"})
        assert denied.status_code == 429
        assert len(list((tmp_path / "inputs").iterdir())) == 1
    finally:
        resume.set()
        thread.join(10)
    assert len(first_response) == 1 and first_response[0].status_code == 202
    job_id = first_response[0].json()["id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if image_jobs.manager.get(job_id).state not in ("queued", "running"):
            break
        time.sleep(0.01)
    assert image_jobs.manager.get(job_id).state == "succeeded"
    assert list((tmp_path / "inputs").iterdir()) == []
    outputs.close()


def test_batch_submission_failure_releases_input_and_reservation(tmp_path, monkeypatch):
    inputs = ImageAssetStore(tmp_path / "inputs", max_assets=64)
    outputs = ImageResultStore(tmp_path / "outputs", extension=".zip",
                               mime_type="application/zip", prefix="batch")
    source = asyncio.run(inputs.add(UploadFile(file=BytesIO(_rgba(3)), filename="source.png")))
    manager = image_jobs.ImageJobManager()

    def reject_submit(*_args):
        raise RuntimeError("executor unavailable")

    monkeypatch.setattr(manager._executor, "submit", reject_submit)
    try:
        try:
            manager.submit_batch(inputs, outputs, [source.id], 1, 1, 0)
        except RuntimeError:
            pass
        else:
            assert False, "submission must fail"
        assert manager.all_public() == []
        assert outputs._reserved == set()
        inputs.remove(source.id)
    finally:
        manager.close()
        inputs.close()
        outputs.close()


def test_batch_admission_is_held_until_running_job_finishes(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "BATCH_INPUT_ROOT", tmp_path / "inputs")
    outputs = ImageResultStore(tmp_path / "outputs", extension=".zip",
                               mime_type="application/zip", prefix="batch")
    monkeypatch.setattr(api, "batch_results", outputs)
    started = Event()
    original_runner = image_jobs.run_grid_batch

    def held_batch(_groups, _columns, _gap, _output, cancel, _on_group_done):
        started.set()
        assert cancel.wait(5)
        raise MontageCancelled()

    monkeypatch.setattr(image_jobs, "run_grid_batch", held_batch)
    client = TestClient(app)
    upload = [("files", ("source.png", _rgba(4), "image/png"))]
    parameters = {"group_size": "1", "columns": "1"}
    first = client.post("/api/image/jobs/batch-grid", files=upload, data=parameters)
    try:
        assert first.status_code == 202
        assert started.wait(5)
        second = client.post("/api/image/jobs/batch-grid", files=upload, data=parameters)
        assert second.status_code == 429
        assert len(list((tmp_path / "inputs").iterdir())) == 1
    finally:
        if first.status_code == 202:
            client.post(f"/api/image/jobs/{first.json()['id']}/cancel")
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if image_jobs.manager.get(first.json()["id"]).state == "cancelled":
            break
        time.sleep(0.01)
    assert image_jobs.manager.get(first.json()["id"]).state == "cancelled"
    assert list((tmp_path / "inputs").iterdir()) == []
    monkeypatch.setattr(image_jobs, "run_grid_batch", original_runner)
    third = client.post("/api/image/jobs/batch-grid", files=upload, data=parameters)
    assert third.status_code == 202
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if image_jobs.manager.get(third.json()["id"]).state not in ("queued", "running"):
            break
        time.sleep(0.01)
    assert image_jobs.manager.get(third.json()["id"]).state == "succeeded"
    outputs.close()
