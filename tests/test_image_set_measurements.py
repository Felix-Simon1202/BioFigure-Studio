"""Reject invalid full native measurement settings before launching Fiji."""

import asyncio
from io import BytesIO
from threading import Event

from fastapi import UploadFile
import pytest

from backend.image.assets import ImageAssetStore
from backend.image.selection import build_selection
from backend.image import set_measurements


def test_native_set_measurements_validates_settings_and_redirect_source(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    assets = []
    for filename in ("primary.tif", "redirect.tif"):
        asset = asyncio.run(store.add(UploadFile(filename=filename, file=BytesIO(filename.encode()))))
        store.acquire(asset.id)
        store.set_metadata(asset.id, {"axes": [{"name": "X", "length": 8}, {"name": "Y", "length": 6}]})
        store.release(asset.id)
        assets.append(store.get(asset.id))
    source, target = assets
    selection = build_selection(source, {}, {"kind": "rectangle", "x": 1, "y": 1, "width": 4, "height": 3})
    full_selection = build_selection(source, {}, None)
    assert full_selection.roi == {"kind": "full", "x": 0, "y": 0, "width": 8, "height": 6}
    settings = {"measurements": ["area", "mean"], "decimal_places": 3, "threshold": None}
    monkeypatch.setattr(set_measurements, "native_set_measurements",
                        lambda *_: (_ for _ in ()).throw(AssertionError("Fiji called")))
    cases = [
        ({**settings, "measurements": ["mean", "mean"]}, None, None),
        ({**settings, "measurements": ["fake"]}, None, None),
        ({**settings, "decimal_places": True}, None, None),
        ({**settings, "decimal_places": 10}, None, None),
        ({**settings, "measurements": ["limit_to_threshold"]}, None, None),
        ({**settings, "threshold": {"min": 20, "max": 10}}, None, None),
        ({**settings, "threshold": {"min": float("nan"), "max": 10}}, None, None),
        (settings, None, {}),
        (settings, source, {}),
    ]
    for options, redirect, plane in cases:
        with pytest.raises(ValueError):
            set_measurements.run_native_set_measurements(source, selection, options, redirect, plane, Event())
    with target.path.open("ab") as stream:
        stream.write(b"changed")
    with pytest.raises(ValueError, match="摘要"):
        set_measurements.run_native_set_measurements(source, selection, settings, target, {}, Event())
    with pytest.raises(AssertionError, match="Fiji called"):
        set_measurements.run_native_set_measurements(source, full_selection, settings, None, None, Event())
    store.close()


@pytest.mark.parametrize('invalid', [None, 'bits', 'plane', 'null_marker', 'overlay', 'display'])
def test_native_measure_checks_settings_and_nonfinite_provenance(tmp_path, monkeypatch, invalid):
    from dataclasses import replace
    store = ImageAssetStore(tmp_path / 'assets')
    asset = asyncio.run(store.add(UploadFile(filename='synthetic.tif', file=BytesIO(b'synthetic'))))
    store.acquire(asset.id)
    store.set_metadata(asset.id, {'axes': [{'name': 'X', 'length': 8}, {'name': 'Y', 'length': 6}]})
    store.release(asset.id)
    asset = store.get(asset.id)
    selection = build_selection(asset, {}, {'x': 1, 'y': 1, 'width': 4, 'height': 3})
    settings = {'measurements': ['area', 'mean'], 'decimal_places': 3, 'threshold': None}
    payload = {'selection': selection.public(), 'settings': settings, 'source_sha256': asset.sha256,
        'redirect_sha256': None, 'redirect_plane': None, 'row_count': 1,
        'headings': ['Area', 'Mean'], 'row': {'Area': 12.0, 'Mean': 2.0}, 'measurement_bits': 3,
        'source_stack_index': 1, 'sampled_stack_index': 1, 'non_finite_headings': [],
        'overlay_count_before': 0, 'overlay_count': 0, 'label': None, 'displayed_row': '1\t12\t2'}
    if invalid == 'bits': payload['measurement_bits'] = 1
    if invalid == 'plane': payload['sampled_stack_index'] = 2
    if invalid == 'null_marker': payload['row']['Mean'] = None
    if invalid == 'overlay': payload['overlay_count'] = 1
    if invalid == 'display': payload['displayed_row'] = 12
    monkeypatch.setattr(set_measurements, 'native_set_measurements', lambda *_: payload)
    try:
        with pytest.raises(ValueError):
            set_measurements.run_native_set_measurements(asset, replace(selection, sample_count=999), settings, None, None, Event())
        if invalid:
            with pytest.raises(ValueError):
                set_measurements.run_native_set_measurements(asset, selection, settings, None, None, Event())
        else:
            assert set_measurements.run_native_set_measurements(asset, selection, settings, None, None, Event())['row'] == payload['row']
    finally:
        store.close()


def test_native_measure_task_holds_both_sources_and_freezes_parameters(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api.app import app
    from backend.image import api, jobs
    from backend.image.jobs import ImageJobManager
    store = ImageAssetStore(tmp_path / 'assets')
    sources = []
    for name in ['main.tif', 'target.tif']:
        asset = asyncio.run(store.add(UploadFile(filename=name, file=BytesIO(name.encode()))))
        store.acquire(asset.id)
        store.set_metadata(asset.id, {'axes': [{'name': 'X', 'length': 8}, {'name': 'Y', 'length': 6}]})
        store.release(asset.id); sources.append(asset)
    manager = ImageJobManager()
    started, resume = Event(), Event()
    captured = []
    def engine(source, selection, settings, target, plane, cancel):
        started.set(); assert resume.wait(3)
        captured.append((source.id, target.id, settings['decimal_places']))
        return {'row': {'Area': 4}}  # Controlled worker boundary, not native scientific validation.
    monkeypatch.setattr(jobs, 'run_native_set_measurements', engine)
    monkeypatch.setattr(api, 'store', store); monkeypatch.setattr(api, 'manager', manager)
    client = TestClient(app)
    request = {'version': '1.0', 'indices': {}, 'roi': None,
               'settings': {'measurements': ['area'], 'decimal_places': 3, 'threshold': None},
               'redirect_asset_id': sources[1].id, 'redirect_plane': {}}
    endpoint = f'/api/image/assets/{sources[0].id}/native-measure'
    try:
        assert client.post(endpoint, json={**request, 'path': 'forbidden'}).status_code == 422
        assert client.post(endpoint, json={**request, 'indices': {'C': True}}).status_code == 422
        assert client.post(endpoint, content=b'x' * (32 * 1024 + 1)).status_code == 413
        job = manager.submit_native_measure(store, sources[0].id, request)
        assert started.wait(2)
        request['settings']['decimal_places'] = 9
        assert store._leases == {source.id: 1 for source in sources}
        for source in sources:
            assert client.delete(f'/api/image/assets/{source.id}').status_code == 409
        client.post(f'/api/image/jobs/{job.id}/cancel')
        resume.set(); job.future.result(timeout=3)
        assert captured == [(sources[0].id, sources[1].id, 3)]
        assert job.state == 'cancelled' and job.result is None and store._leases == {}
    finally:
        resume.set(); manager.close(); store.close()


def test_shared_source_verifier_rejects_growth_and_cancellation(tmp_path, monkeypatch):
    from backend.image.assets import ImageAssetImportCancelled, verify_asset_bytes
    store = ImageAssetStore(tmp_path / 'assets')
    asset = asyncio.run(store.add(UploadFile(filename='synthetic.tif', file=BytesIO(b'original'))))
    try:
        assert verify_asset_bytes(asset) == asset.sha256
        cancelled = Event(); cancelled.set()
        with pytest.raises(ImageAssetImportCancelled): verify_asset_bytes(asset, cancelled)
        asset.path.write_bytes(b'original-grown')
        with pytest.raises(ValueError, match='摘要'): verify_asset_bytes(asset)
    finally:
        store.close()



def test_shared_verifier_stops_reading_at_declared_length_and_on_cancel(tmp_path, monkeypatch):
    from dataclasses import replace
    from backend.image import assets as asset_module
    store = ImageAssetStore(tmp_path / 'assets')
    asset = asyncio.run(store.add(UploadFile(filename='synthetic.tif', file=BytesIO(b'original'))))
    monkeypatch.setattr(asset_module, 'CHUNK_BYTES', 4)
    reads = []
    cancel = Event()
    class Tracked(BytesIO):
        def read(self, amount):
            chunk = super().read(amount); reads.append(len(chunk))
            if mode == 'cancel' and len(reads) == 2: cancel.set()
            return chunk
    class ReadOnlyPath:
        def open(self, operation):
            assert operation == 'rb'
            return Tracked(b'original' + b'x' * 10000)
    controlled = replace(asset, path=ReadOnlyPath())
    try:
        mode = 'growth'
        with pytest.raises(ValueError, match='摘要'): asset_module.verify_asset_bytes(controlled)
        assert sum(reads) <= asset.bytes + 4
        reads.clear(); mode = 'cancel'
        with pytest.raises(asset_module.ImageAssetImportCancelled): asset_module.verify_asset_bytes(controlled, cancel)
        assert len(reads) == 2
    finally:
        store.close()



def test_native_settings_catalog_uses_fixed_runtime_options_and_request_schema():
    from fastapi.testclient import TestClient
    from backend.api.app import app
    response = TestClient(app).get('/api/image/measurement-settings')
    assert response.status_code == 200
    metadata = response.json()
    assert metadata['version'] == '1.0'
    assert [item['id'] for item in metadata['measurements']] == list(set_measurements.MEASUREMENT_OPTIONS)
    assert len(metadata['measurements']) == 24
    assert sum(item['native_bit'] for item in metadata['measurements']) == 16777215
    assert metadata['request_schema']['additionalProperties'] is False
    assert metadata['decimal_places']['affects'] == 'native_display_only'
    assert metadata['redirect']['identity'] == 'asset_id'
    assert metadata['roi_support']['non_area_native_types']['freeline'] == 7
    assert metadata['roi_support']['non_area_native_types']['polyline'] == 6
