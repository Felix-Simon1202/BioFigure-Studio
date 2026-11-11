from hashlib import sha256
from io import BytesIO

from fastapi.testclient import TestClient
import numpy as np
from PIL import Image
import pytest

from backend.api.app import app
from backend.image import api, preview
from backend.image.assets import ImageAsset
from backend.image.montage import render_exact_grid
from backend.image.results import ImageResultStore


@pytest.mark.parametrize("pixels,expected", [
    (np.array([[0, 32768, 65535]], dtype=np.uint16), [0, 127, 255]),
    (np.array([[-100, 0, 100]], dtype=np.float32), [0, 127, 255]),
    (np.array([[float('nan'), float('inf'), float('-inf')]], dtype=np.float32), [0, 0, 0]),
    (np.array([[4, 4, 4]], dtype=np.uint16), [0, 0, 0]),
])
def test_grayscale_preview_mapping_is_explicit_and_original_file_unchanged(tmp_path, pixels, expected):
    path = tmp_path / "source.tif"
    Image.fromarray(pixels).save(path)
    before = sha256(path.read_bytes()).hexdigest()
    content, headers = preview.display_png(path)
    with Image.open(BytesIO(content)) as displayed:
        assert np.asarray(displayed).tolist() == [expected]
    assert headers["X-Display-Mapping"] == "finite-min-max-linear"
    assert headers["X-Preview-Only"] == "true"
    assert sha256(path.read_bytes()).hexdigest() == before


def test_rgba_preview_retains_alpha_and_is_size_bounded(tmp_path):
    path = tmp_path / "source.tif"
    Image.new("RGBA", (2048, 1024), (199, 33, 77, 0)).save(path)
    content, headers = preview.display_png(path)
    with Image.open(BytesIO(content)) as displayed:
        assert displayed.mode == "RGBA" and displayed.size == (1024, 512)
        assert displayed.getpixel((0, 0)) == (199, 33, 77, 0)
    assert headers["X-Display-Mapping"] == "original-8bit"


def test_preview_rejects_source_over_pixel_budget_before_decoding(tmp_path, monkeypatch):
    path = tmp_path / "source.tif"
    Image.new("L", (3, 2), 1).save(path)
    monkeypatch.setattr(preview, "MAX_PREVIEW_SOURCE_PIXELS", 5)
    with pytest.raises(ValueError):
        preview.display_png(path)


def test_result_preview_and_inline_annotation_are_separate_from_export(tmp_path, monkeypatch):
    store = ImageResultStore(tmp_path / "results")
    monkeypatch.setattr(api, "results", store)
    path = tmp_path / "source.tif"
    Image.new("L", (64, 32), 19).save(path)
    asset = ImageAsset("one", path.name, path.stat().st_size, sha256(path.read_bytes()).hexdigest(), path)
    identifier, output = store.reserve()
    proof = render_exact_grid([asset], 1, 0, output)
    store.finish(identifier, proof)
    client = TestClient(app)
    try:
        response = client.get(f"/api/image/results/{identifier}/preview.png")
        assert response.status_code == 200 and response.headers["X-Preview-Only"] == "true"
        assert client.get("/api/image/results/missing/preview.png").status_code == 404
        response = client.put(f"/api/image/results/{identifier}/annotations", json={"version": "1.0", "items": [
            {"kind": "text", "text": "A", "x": 4, "y": 20, "font_px": 12, "color": "#ffffff"}]})
        assert response.status_code == 200
        overlay = client.get(f"/api/image/results/{identifier}/annotations-preview.svg")
        assert overlay.status_code == 200
        assert "content-disposition" not in overlay.headers
        assert overlay.headers["X-Content-Type-Options"] == "nosniff"
        assert b">A<" in overlay.content
        parameters = client.get(f"/api/image/results/{identifier}/annotations.json")
        assert parameters.status_code == 200
        assert parameters.headers["content-disposition"] == f'attachment; filename="biofigure-annotations-{identifier[:8]}.json"'
        assert parameters.headers["X-Content-Type-Options"] == "nosniff"
        assert parameters.json()["items"][0]["text"] == "A" and "svg" not in parameters.json()
        assert client.get("/api/image/results/missing/annotations.json").status_code == 404
        assert sha256(client.get(f"/api/image/results/{identifier}/file").content).hexdigest() == proof.output_sha256
    finally:
        store.close()
