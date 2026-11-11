"""Every public operation must obey the same queue/resource ownership rules."""

import asyncio
from io import BytesIO
from threading import Event

from fastapi import UploadFile
from PIL import Image
import pytest

from backend.image.assets import ImageAssetStore
from backend.image.jobs import ImageJobManager, MAX_JOBS
from backend.image.results import ImageResultStore


OPERATIONS = ("inspect", "grid", "invert", "measure", "batch", "project", "collection", "workspace", "multi", "native_measure")


@pytest.fixture
def resources(tmp_path):
    assets = ImageAssetStore(tmp_path / "assets")
    results = ImageResultStore(tmp_path / "results")
    encoded = BytesIO()
    Image.new("I;16", (8, 6), 1023).save(encoded, format="TIFF")
    asset = asyncio.run(assets.add(UploadFile(BytesIO(encoded.getvalue()), filename="test.tif")))
    # Controlled metadata for unit dispatch tests; these tests run no engine.
    assets.acquire(asset.id)
    assets.set_metadata(asset.id, {"axes": [{"name": "X", "length": 8}, {"name": "Y", "length": 6}],
                                  "bit_depth": 16, "pixel_type": "test-type"})
    assets.release(asset.id)
    manager = ImageJobManager()
    try:
        yield manager, assets, results, asset.id
    finally:
        manager.close()
        assets.close()
        results.close()


def submit(operation, manager, assets, results, identifier, release=None):
    if operation == "inspect":
        return manager.submit_inspection(assets, identifier)
    if operation == "grid":
        return manager.submit_grid(assets, results, [identifier], 1, 0)
    if operation == "invert":
        return manager.submit_invert(assets, results, identifier)
    if operation == "measure":
        return manager.submit_measure(assets, identifier, {}, None)
    if operation == "native_measure":
        return manager.submit_native_measure(assets, identifier, {})
    if operation == "multi":
        return manager.submit_multi_measure(assets, identifier, {})
    if operation == "collection":
        from backend.image.roi_collection import source_identity
        document = {"version": "1.0", "source": source_identity(assets.get(identifier)), "items": [
            {"id": "1" * 32, "name": "test ROI", "indices": {},
             "roi": {"kind": "rectangle", "x": 0, "y": 0, "width": 2, "height": 2}}]}
        return manager.submit_collection_measure(assets, identifier, document, [])
    if operation == "batch":
        return manager.submit_batch(assets, results, [identifier], 1, 1, 0, admission_release=release)
    return manager.submit_project(assets, identifier, assets, results, admission_release=release,
                                  workspace=operation == "workspace")


@pytest.mark.parametrize("operation", OPERATIONS)
def test_executor_refusal_leaves_no_job_lease_or_result_reservation(resources, operation):
    manager, assets, results, identifier = resources
    manager._executor.shutdown()
    released = []
    with pytest.raises(RuntimeError):
        submit(operation, manager, assets, results, identifier, lambda: released.append(True))
    assert manager.all_public() == [] and assets._leases == {}
    assert results._reserved == set() and results.all_public() == []
    assert list(results.session.iterdir()) == []
    assert assets.get(identifier).path.is_file()
    assert released == []  # HTTP caller still owns admission on submission failure.


@pytest.mark.parametrize("operation", ("grid", "invert", "batch", "project"))
def test_result_capacity_failure_releases_acquired_assets(resources, operation):
    manager, assets, results, identifier = resources
    results.max_results = 0
    with pytest.raises(ValueError, match="成品已满"):
        submit(operation, manager, assets, results, identifier)
    assert manager.all_public() == [] and assets._leases == {} and results._reserved == set()


@pytest.mark.parametrize("operation", OPERATIONS)
def test_closed_manager_refuses_before_acquiring_any_resources(resources, operation):
    manager, assets, results, identifier = resources
    manager.close()
    with pytest.raises(ValueError, match="队列已关闭"):
        submit(operation, manager, assets, results, identifier)
    assert manager.all_public() == [] and assets._leases == {} and results._reserved == set()


def test_full_queue_refuses_without_leaks_and_queued_jobs_cancel_cleanly(resources):
    manager, assets, results, identifier = resources
    entered, unblock = Event(), Event()

    def hold_executor():
        entered.set()
        unblock.wait(5)

    manager._executor.submit(hold_executor)
    assert entered.wait(2)
    queued = []
    try:
        queued = [manager.submit_inspection(assets, identifier) for _ in range(MAX_JOBS)]
        with pytest.raises(ValueError, match="队列已满"):
            manager.submit_grid(assets, results, [identifier], 1, 0)
        assert len(manager.all_public()) == MAX_JOBS
        assert assets._leases == {identifier: MAX_JOBS} and results._reserved == set()
        # Cancel first, then let the untracked executor sentinel exit.
        for job in queued:
            assert manager.cancel(job.id).state == "cancelled"
        assert assets._leases == {}
    finally:
        unblock.set()
    manager.close()
    assert all(job.finished_at is not None for job in queued)


def test_close_cancels_queued_work_before_waiting_for_executor(resources, monkeypatch):
    manager, assets, results, identifier = resources
    entered, unblock = Event(), Event()

    def hold_executor():
        entered.set()
        unblock.wait(5)

    manager._executor.submit(hold_executor)
    assert entered.wait(2)
    queued = [manager.submit_inspection(assets, identifier) for _ in range(MAX_JOBS)]
    original_shutdown = manager._executor.shutdown

    def checked_shutdown(*args, **kwargs):
        assert all(job.state == "cancelled" and job.finished_at is not None for job in queued)
        assert manager._closed and assets._leases == {} and results._reserved == set()
        unblock.set()
        return original_shutdown(*args, **kwargs)

    monkeypatch.setattr(manager._executor, "shutdown", checked_shutdown)
    try:
        manager.close()
    finally:
        unblock.set()
