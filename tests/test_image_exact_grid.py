"""Pixel identity checks for the non-resampling grid layout operation."""

from hashlib import sha256
from io import BytesIO
import time

from fastapi.testclient import TestClient
from PIL import Image
import numpy as np
import pytest

from backend.api.app import app
from backend.image import api
from backend.image.assets import ImageAsset, ImageAssetStore
from backend.image.montage import render_exact_grid
from backend.image.results import ImageResultStore
from scripts.generate_image_acceptance_fixtures import generate


def _source(tmp_path, name, mode, size, offset):
    path = tmp_path / name
    image = Image.new(mode, size)
    for y in range(size[1]):
        for x in range(size[0]):
            value = (x * 17 + y * 23 + offset) % 255
            pixel = ((value, value + 1, value + 2, value // 2)
                     if mode == "RGBA" else
                     (value, value + 1, value + 2) if mode == "RGB" else
                     float(value) + 0.25 if mode == "F" else value * 257 if mode == "I;16" else value)
            image.putpixel((x, y), pixel)
    image.save(path)
    return ImageAsset(name, name, path.stat().st_size, sha256(path.read_bytes()).hexdigest(), path)


@pytest.mark.parametrize("mode,extension", [
    ("L", "tif"), ("I;16", "tif"), ("F", "tif"),
    ("RGB", "png"), ("RGBA", "png"),
])
def test_exact_grid_roundtrip_preserves_every_pixel(tmp_path, mode, extension):
    first = _source(tmp_path, f"a.{extension}", mode, (7, 5), 3)
    second = _source(tmp_path, f"b.{extension}", mode, (4, 8), 19)
    output = tmp_path / "grid.tif"
    proof = render_exact_grid([first, second], columns=2, gap_px=2, output=output)
    assert (proof.width, proof.height, proof.mode) == (13, 8, mode)
    assert proof.verified_pixels == 7 * 5 + 4 * 8
    assert proof.output_sha256 == sha256(output.read_bytes()).hexdigest()
    with Image.open(output) as saved:
        assert saved.mode == mode
        for source, placement in zip((first, second), proof.placements):
            with Image.open(source.path) as original:
                assert saved.crop((placement.x, placement.y,
                                   placement.x + placement.width,
                                   placement.y + placement.height)).tobytes() == original.tobytes()
    if mode == "RGBA":
        with Image.open(output) as saved:
            assert saved.getpixel((0, 0))[3] != 255


def test_grid_rejects_implicit_color_conversion(tmp_path):
    gray = _source(tmp_path, "gray.tif", "L", (3, 2), 1)
    rgba = _source(tmp_path, "rgba.png", "RGBA", (3, 2), 2)
    with pytest.raises(ValueError, match="相同位深和通道模式"):
        render_exact_grid([gray, rgba], 2, 0, tmp_path / "invalid.tif")
    assert not (tmp_path / "invalid.tif").exists()


def test_grid_matches_independent_synthetic_reference_including_hidden_rgba(tmp_path):
    root = tmp_path / "fixtures"
    manifest = generate(root)
    by_name = {item["file"]: item for item in manifest["items"]}
    for filename in ("rgb8.tif", "rgba8.png", "灰度16_非等距标定.tif", "float32_signed.tif"):
        path = root / filename
        asset = ImageAsset(filename, filename, path.stat().st_size,
                           sha256(path.read_bytes()).hexdigest(), path)
        output = tmp_path / (filename + ".grid.tif")
        proof = render_exact_grid([asset], 1, 0, output)
        expected = np.load(root / by_name[filename]["expected_array"], allow_pickle=False)
        with Image.open(output) as saved:
            actual = np.asarray(saved)
        assert actual.dtype == expected.dtype
        assert np.array_equal(actual, expected)
        assert proof.public()["metadata_preserved"] is False
    with Image.open(tmp_path / "rgba8.png.grid.tif") as rgba:
        assert rgba.getpixel((0, 0)) == (199, 33, 77, 0)


def test_grid_rejects_stack_without_explicit_axis_selection(tmp_path):
    root = tmp_path / "fixtures"
    generate(root)
    path = root / "zstack16.tif"
    asset = ImageAsset("stack", path.name, path.stat().st_size,
                       sha256(path.read_bytes()).hexdigest(), path)
    with pytest.raises(ValueError, match="显式选择"):
        render_exact_grid([asset], 1, 0, tmp_path / "grid.tif")


def test_grid_api_downloads_verified_rgba_tiff(tmp_path, monkeypatch):
    assets = ImageAssetStore(tmp_path / "assets")
    results = ImageResultStore(tmp_path / "results")
    monkeypatch.setattr(api, "store", assets)
    monkeypatch.setattr(api, "results", results)
    client = TestClient(app)
    source = _source(tmp_path, "rgba.png", "RGBA", (7, 5), 3)
    ids = []
    for name in ("first.png", "second.png"):
        uploaded = client.post("/api/image/assets", files={"file": (name, source.path.read_bytes(), "image/png")})
        assert uploaded.status_code == 201
        ids.append(uploaded.json()["id"])
    submitted = client.post("/api/image/jobs/exact-grid", json={
        "version": "1.0", "asset_ids": ids, "columns": 2, "gap_px": 3,
    })
    assert submitted.status_code == 202
    job_id = submitted.json()["id"]
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        job = client.get(f"/api/image/jobs/{job_id}").json()
        if job["state"] not in ("queued", "running"):
            break
        time.sleep(0.02)
    assert job["state"] == "succeeded", job["error"]
    result = job["result"]
    assert result["proof"]["pixel_identity_verified"]
    assert result["proof"]["metadata_preserved"] is False
    downloaded = client.get(f"/api/image/results/{result['id']}/file")
    assert downloaded.status_code == 200
    assert sha256(downloaded.content).hexdigest() == result["sha256"]
    with Image.open(BytesIO(downloaded.content)) as image:
        assert image.mode == "RGBA"
        with Image.open(source.path) as original:
            assert image.crop((0, 0, 7, 5)).tobytes() == original.tobytes()
            assert image.crop((10, 0, 17, 5)).tobytes() == original.tobytes()
    annotated = client.put(f"/api/image/results/{result['id']}/annotations", json={
        "version": "1.0", "items": [
            {"kind": "text", "text": "<script>研究</script>", "x": 1, "y": 2,
             "font_px": 12, "color": "#000000"},
            {"kind": "number", "text": "1", "x": 11, "y": 2,
             "font_px": 12, "color": "#ffffff"},
            {"kind": "scale_bar", "asset_id": ids[0], "offset_x": 1,
             "offset_y": 4, "length_um": 1, "x_um_per_pixel": 0.25,
             "color": "#ffffff"},
        ],
    })
    assert annotated.status_code == 200, annotated.text
    assert annotated.json()["items"][2]["length_px"] == 4
    assert annotated.json()["items"][2]["calibration_source"] == "user_explicit"
    appended = client.put(f"/api/image/results/{result['id']}/annotations", json={
        "version": "1.0", "items": annotated.json()["items"] + [
            {"kind": "text", "text": "追加", "x": 2, "y": 3,
             "font_px": 12, "color": "#000000"}],
    })
    assert appended.status_code == 200, appended.text
    assert len(appended.json()["items"]) == 4
    loaded = client.get(f"/api/image/results/{result['id']}/annotations").json()
    assert client.put(f"/api/image/results/{result['id']}/annotations", json={
        "version": "1.0", "items": loaded["items"],
    }).status_code == 200
    forged = [item.copy() for item in loaded["items"]]
    forged[2]["length_px"] = 99
    assert client.put(f"/api/image/results/{result['id']}/annotations", json={
        "version": "1.0", "items": forged,
    }).status_code == 422
    svg = client.get(f"/api/image/results/{result['id']}/annotations.svg")
    assert svg.status_code == 200
    assert b"&lt;script&gt;" in svg.content and b"<script>" not in svg.content
    assert b"scale_bar" not in svg.content
    assert sha256(client.get(f"/api/image/results/{result['id']}/file").content).hexdigest() == result["sha256"]
    invalid = client.put(f"/api/image/results/{result['id']}/annotations", json={
        "version": "1.0", "items": [{"kind": "scale_bar", "asset_id": ids[0],
          "offset_x": 1, "offset_y": 1, "length_um": 1,
          "x_um_per_pixel": 0, "color": "#000000"}],
    })
    assert invalid.status_code == 422
    assert client.delete(f"/api/image/results/{result['id']}").status_code == 204
    for asset_id in ids:
        assert client.delete(f"/api/image/assets/{asset_id}").status_code == 204
    results.close()
    assets.close()
