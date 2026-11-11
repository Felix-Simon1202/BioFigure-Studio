"""C/Z/T and ROI requests must name a real, bounded Fiji plane."""

from pathlib import Path
from io import BytesIO
import asyncio
import time
from threading import Event

import pytest
from fastapi import UploadFile

from backend.image import jobs as image_jobs
from backend.image.assets import ImageAsset, ImageAssetStore
from backend.image.selection import build_selection


def _asset() -> ImageAsset:
    axes = [{"name": "X", "length": 32}, {"name": "Y", "length": 24},
            {"name": "Channel", "length": 2}, {"name": "Z", "length": 3},
            {"name": "Time", "length": 4}]
    return ImageAsset("a" * 32, "synthetic.tif", 1, "b" * 64, Path("unused"),
                      metadata={"axes": axes})


def test_explicit_plane_and_roi_are_preserved():
    region = build_selection(_asset(), {"C": 1, "Z": 2, "T": 3},
                             {"x": 4, "y": 5, "width": 7, "height": 6},
                             ["integrated_density", "mode", "median", "std_dev"])
    assert region.sample_count == 42
    assert region.public()["indices"] == {"C": 1, "Z": 2, "T": 3}
    assert region.public()["roi"] == {"kind": "rectangle", "x": 4, "y": 5,
                                       "width": 7, "height": 6}
    assert region.public()["extra_measurements"] == ["std_dev", "median", "mode", "integrated_density"]


def test_ellipse_bounds_are_preserved_and_bounded():
    ellipse = build_selection(_asset(), {"C": 1, "Z": 2, "T": 3},
                              {"kind": "ellipse", "x": 4, "y": 5, "width": 7, "height": 5})
    assert ellipse.public()["roi"] == {"kind": "ellipse", "x": 4, "y": 5,
                                        "width": 7, "height": 5}
    assert ellipse.sample_count == 35  # upper bound before ImageJ calculates the mask
    with pytest.raises(ValueError):
        build_selection(_asset(), {"C": 1, "Z": 2, "T": 3},
                        {"kind": "ellipse", "x": 30, "y": 5, "width": 7, "height": 5})


def test_polygon_vertices_are_preserved_and_validated():
    points = [{"x": 1, "y": 1}, {"x": 7, "y": 1}, {"x": 1, "y": 6}]
    polygon = build_selection(_asset(), {"C": 1, "Z": 2, "T": 3},
                              {"kind": "polygon", "points": points})
    assert polygon.public()["roi"] == {"kind": "polygon", "points": points,
                                       "x": 1, "y": 1, "width": 7, "height": 6}
    for invalid in (points[:2], points[:2] + [{"x": 1, "y": 1}],
                    [{"x": 1, "y": 1}, {"x": 7, "y": 1}, {"x": 33, "y": 6}],
                    [{"x": 1, "y": 1}, {"x": 7, "y": 6}, {"x": 1, "y": 6}, {"x": 7, "y": 1}]):
        with pytest.raises(ValueError):
            build_selection(_asset(), {"C": 1, "Z": 2, "T": 3},
                            {"kind": "polygon", "points": invalid})


@pytest.mark.parametrize("indices,roi", [
    ({"C": 1, "Z": 2}, None),
    ({"C": 1, "Z": 3, "T": 0}, None),
    ({"C": 1, "Z": 2, "T": 0, "Q": 0}, None),
    ({"C": 1, "Z": 2, "T": 0}, {"x": 31, "y": 0, "width": 2, "height": 1}),
    ({"C": 1, "Z": 2, "T": 0}, {"x": 0, "y": 0, "width": 0, "height": 1}),
])
def test_implicit_or_outside_selection_is_rejected(indices, roi):
    with pytest.raises(ValueError):
        build_selection(_asset(), indices, roi)


@pytest.mark.parametrize("extras", [["median", "median"], ["variance"], ["std_dev", "variance"], [["median"]]])
def test_unknown_or_duplicate_measurements_are_rejected(extras):
    with pytest.raises(ValueError, match="额外测量"):
        build_selection(_asset(), {"C": 1, "Z": 2, "T": 3}, None, extras)


def test_running_roi_measurement_cancel_releases_source(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    uploaded = asyncio.run(store.add(UploadFile(file=BytesIO(b"synthetic"), filename="source.tif")))
    store.acquire(uploaded.id)
    store.set_metadata(uploaded.id, {"axes": [
        {"name": "X", "length": 4}, {"name": "Y", "length": 3},
        {"name": "Z", "length": 2},
    ]})
    store.release(uploaded.id)
    entered = Event()

    def held_measure(_asset, _job_id, cancel, _selection):
        entered.set()
        assert cancel.wait(5)
        raise image_jobs.FijiCancelled()

    monkeypatch.setattr(image_jobs, "measure_selection", held_measure)
    manager = image_jobs.ImageJobManager()
    try:
        job = manager.submit_measure(store, uploaded.id, {"Z": 1},
                                     {"x": 1, "y": 1, "width": 2, "height": 2})
        assert entered.wait(5)
        with pytest.raises(ValueError, match="任务中使用"):
            store.remove(uploaded.id)
        manager.cancel(job.id)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and manager.get(job.id).state in ("queued", "running"):
            time.sleep(0.01)
        assert manager.get(job.id).state == "cancelled"
        assert manager.get(job.id).result is None
        store.remove(uploaded.id)
    finally:
        manager.close()
        store.close()
