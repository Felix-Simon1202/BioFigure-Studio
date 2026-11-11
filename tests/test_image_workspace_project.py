from hashlib import sha256
import json
from threading import Event
from uuid import uuid4
from zipfile import ZipFile

import numpy as np
from PIL import Image, TiffImagePlugin
import pytest

from backend.image.assets import ImageAsset, ImageAssetImportCancelled
from backend.image.project import GridRecipe, read_grid_project
from backend.image.roi_collection import source_identity
from backend.image.workspace_project import save_workspace_project, read_workspace_project


@pytest.fixture
def workspace(tmp_path):
    path = tmp_path / "组合图像栈.tif"
    pages = [Image.fromarray((np.arange(72).reshape(8, 9) + index * 1000).astype(np.uint16))
             for index in range(12)]
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[270] = "ImageJ=1.54\nimages=12\nchannels=2\nslices=3\nframes=2\nhyperstack=true\nunit=um\n"
    pages[0].save(path, save_all=True, append_images=pages[1:], tiffinfo=tags, compression="tiff_deflate")
    for page in pages:
        page.close()
    axes = [{"name": name, "length": length, "unit": "um" if name in ("X", "Y", "Z") else None,
             "scale": 1.0} for name, length in (("X", 9), ("Y", 8), ("Channel", 2), ("Z", 3), ("Time", 2))]
    stack = ImageAsset("old-stack", path.name, path.stat().st_size, sha256(path.read_bytes()).hexdigest(),
                       path, {"axes": axes, "bit_depth": 16})
    other = tmp_path / "transparent.png"
    Image.new("RGBA", (24, 24), (199, 33, 77, 0)).save(other)
    rgba = ImageAsset("old-rgba", other.name, other.stat().st_size, sha256(other.read_bytes()).hexdigest(), other)
    roi = {"kind": "ellipse", "x": 1, "y": 1, "width": 7, "height": 5}
    indices = {"C": 1, "Z": 2, "T": 1}
    collection = {"version": "1.0", "source": source_identity(stack), "items": [
        {"id": uuid4().hex, "name": "细胞核 A", "indices": indices, "roi": roi}]}
    state = {"collection": collection, "selection": {"indices": indices, "roi": roi,
                                                    "extra_measurements": ["std_dev", "mode"]}}
    return [stack, rgba], {stack.id: state}


def test_stack_workspace_retains_all_original_bytes_and_reviewed_state(tmp_path, workspace):
    assets, states = workspace
    output = tmp_path / "workspace.bfswork"
    saved = save_workspace_project(assets, states, output, active_asset_id=assets[0].id,
        selected_asset_ids=[assets[1].id, assets[0].id], grid=GridRecipe(columns=2, gap_px=3))
    assert saved.active_source_key == "s0" and saved.selected_source_keys == ["s1", "s0"]
    pending = read_workspace_project(output, tmp_path / "extracted")
    assert pending.verification_status == "requires_fresh_inspection"
    assert pending.manifest.source_states["s0"].selection.indices == {"C": 1, "Z": 2, "T": 1}
    assert pending.manifest.source_states["s0"].selection.extra_measurements == ["std_dev", "mode"]
    assert pending.manifest.source_states["s0"].collection["items"][0]["name"] == "细胞核 A"
    for asset, restored in zip(assets, pending.source_paths, strict=True):
        assert restored.read_bytes() == asset.path.read_bytes()
    with Image.open(assets[0].path) as original, Image.open(pending.source_paths[0]) as restored:
        assert original.n_frames == restored.n_frames == 12
        for index in range(12):
            original.seek(index)
            restored.seek(index)
            assert np.array_equal(np.asarray(original), np.asarray(restored))
    with Image.open(pending.source_paths[1]) as restored:
        assert restored.getpixel((0, 0)) == (199, 33, 77, 0)
    with pytest.raises(ValueError):
        read_grid_project(output, tmp_path / "wrong-kind")
    assert not (tmp_path / "wrong-kind").exists()


@pytest.mark.parametrize("case", ["unknown_source", "axis_index", "fractional", "extra_field", "source_digest"])
def test_invalid_save_state_never_creates_a_package(tmp_path, workspace, case):
    assets, states = workspace
    state = states[assets[0].id]
    if case == "unknown_source":
        states["missing"] = state
    elif case == "axis_index":
        state["selection"]["indices"]["Z"] = 99
    elif case == "fractional":
        state["selection"]["roi"]["x"] = .5
    elif case == "extra_field":
        state["command"] = "execute me"
    else:
        state["collection"]["source"]["sha256"] = "0" * 64
    output = tmp_path / "invalid.bfswork"
    with pytest.raises(ValueError):
        save_workspace_project(assets, states, output)
    assert not output.exists()


def test_loaded_metadata_claims_remain_pending_and_dont_change_live_assets(tmp_path, workspace):
    assets, states = workspace
    output = tmp_path / "original.bfswork"
    save_workspace_project(assets, states, output)
    changed = tmp_path / "claims.bfswork"
    with ZipFile(output) as original, ZipFile(changed, "x") as revised:
        for entry in original.infolist():
            data = original.read(entry.filename)
            if entry.filename == "project.json":
                document = json.loads(data)
                document["schema_version"] = "1.0"
                for state in document["source_states"].values():
                    state.pop("native_measurement")
                document["sources"][0]["recorded_metadata"]["axes"][0]["scale"] = 999
                data = json.dumps(document).encode()
            revised.writestr(entry.filename, data)
    pending = read_workspace_project(changed, tmp_path / "pending")
    assert pending.verification_status == "requires_fresh_inspection"
    assert pending.manifest.sources[0].recorded_metadata["axes"][0]["scale"] == 999
    assert assets[0].metadata["axes"][0]["scale"] == 1.0


def test_cancellation_and_existing_outputs_are_preserved(tmp_path, workspace):
    assets, states = workspace
    token = Event()
    token.set()
    output = tmp_path / "cancelled.bfswork"
    with pytest.raises(ImageAssetImportCancelled):
        save_workspace_project(assets, states, output, cancel=token)
    assert not output.exists()
    output.write_bytes(b"keep")
    with pytest.raises(FileExistsError):
        save_workspace_project(assets, states, output)
    assert output.read_bytes() == b"keep"


def test_workspace_restore_rechecks_sources_and_rebinds_state(tmp_path, workspace, monkeypatch):
    from backend.image.assets import ImageAssetStore
    from backend.image import project_import
    from backend.image.workspace_import import restore_workspace_project
    originals, states = workspace
    archive = tmp_path / 'state.bfswork'
    save_workspace_project(originals, states, archive, active_asset_id=originals[0].id,
        selected_asset_ids=[originals[1].id, originals[0].id], grid=GridRecipe(columns=2, gap_px=4))
    store = ImageAssetStore(tmp_path / 'assets')
    calls = []
    def inspect(source, *_):
        assert source.metadata is None and store.all_public() == []
        calls.append(source.id)
        return originals[0].metadata if source.id == 's0' else {'axes': [
            {'name': 'X', 'length': 24}, {'name': 'Y', 'length': 24}], 'bit_depth': 8}
    monkeypatch.setattr(project_import, 'inspect_asset', inspect)
    try:
        restored = restore_workspace_project(archive, store, 'restore-test', Event(), root=tmp_path / 'staging')
        assert calls == ['s0', 's1'] and len(store.all_public()) == 2
        first, second = restored['assets']
        current = restored['workspace']
        assert current['active_asset_id'] == first['id']
        assert current['selected_asset_ids'] == [second['id'], first['id']]
        assert current['grid'] == {'columns': 2, 'gap_px': 4}
        state = current['source_states'][first['id']]
        assert state['collection'] == states[originals[0].id]['collection']
        assert state['selection']['indices'] == {'C': 1, 'Z': 2, 'T': 1}
        assert state['selection']['extra_measurements'] == ['std_dev', 'mode']
        assert restored['source_verification'] == 'fresh_fiji_inspection'
        for original, reopened in zip(originals, restored['assets'], strict=True):
            assert original.path.read_bytes() == store.get(reopened['id']).path.read_bytes()
        assert list((tmp_path / 'staging').iterdir()) == []
    finally:
        store.close()


@pytest.mark.parametrize('failure', ['inspection', 'changed_axes', 'cancel', 'capacity', 'publication'])
def test_workspace_restore_failure_publishes_no_assets_or_state(tmp_path, workspace, monkeypatch, failure):
    from copy import deepcopy
    from backend.image.assets import ImageAssetStore
    from backend.image import project_import
    from backend.image.workspace_import import restore_workspace_project
    originals, states = workspace
    archive = tmp_path / 'state.bfswork'
    save_workspace_project(originals, states, archive)
    store = ImageAssetStore(tmp_path / 'assets', max_assets=1 if failure == 'capacity' else 8)
    cancel = Event()
    published = []
    def inspect(source, *_):
        if source.id == 's1' and failure == 'inspection':
            raise ValueError('controlled inspection failure')
        metadata = deepcopy(originals[0].metadata)
        if failure == 'changed_axes':
            metadata['axes'][3]['length'] = 1
        if source.id == 's1' and failure == 'cancel':
            cancel.set()
        return metadata
    def publish(payload):
        if failure == 'publication':
            raise ValueError('controlled publication failure')
        published.append(payload)
    monkeypatch.setattr(project_import, 'inspect_asset', inspect)
    try:
        with pytest.raises((ValueError, ImageAssetImportCancelled)):
            restore_workspace_project(archive, store, 'failure-test', cancel,
                root=tmp_path / 'staging', on_commit=publish)
        assert store.all_public() == published == []
        assert store._pending_bytes == store._pending_count == 0
        assert list(store.session.iterdir()) == []
        assert list((tmp_path / 'staging').iterdir()) == []
    finally:
        store.close()


@pytest.mark.skipif(__import__('os').environ.get('BFS_RUN_FIJI_INTEGRATION') != '1', reason='requires reviewed local Fiji')
def test_workspace_reopen_actual_fiji_keeps_stack_and_selection(tmp_path, workspace):
    from dataclasses import replace
    from backend.image.assets import ImageAssetStore
    from backend.image.fiji_process import inspect_asset, measure_selection
    from backend.image.selection import build_selection
    from backend.image.workspace_import import restore_workspace_project
    originals, states = workspace
    original = replace(originals[0], metadata=inspect_asset(originals[0], uuid4().hex, Event()))
    state = states[original.id]
    state['collection']['source'] = source_identity(original)
    archive = tmp_path / 'actual.bfswork'
    save_workspace_project([original], {original.id: state}, archive, active_asset_id=original.id)
    store = ImageAssetStore(tmp_path / 'assets')
    try:
        restored = restore_workspace_project(archive, store, uuid4().hex, Event(), root=tmp_path / 'staging')
        asset = store.get(restored['workspace']['active_asset_id'])
        assert asset.path.read_bytes() == original.path.read_bytes()
        assert {axis['name']: axis['length'] for axis in asset.metadata['axes']} == {
            'X': 9, 'Y': 8, 'Channel': 2, 'Z': 3, 'Time': 2}
        saved = restored['workspace']['source_states'][asset.id]
        assert saved['collection']['items'][0]['name'] == '细胞核 A'
        selection = build_selection(asset, **saved['selection'])
        measured = measure_selection(asset, uuid4().hex, Event(), selection)
        assert measured['sample_count'] == 31
        assert measured['imagej1_analyzer']['mean'] == 11031.0
        assert measured['imagej1_analyzer']['area'] == 31.0
    finally:
        store.close()

@pytest.mark.parametrize('cancel_first', [False, True])
def test_workspace_http_job_admission_atomic_state_and_cleanup(tmp_path, workspace, monkeypatch, cancel_first):
    from fastapi.testclient import TestClient
    from backend.api.app import app
    from backend.image import api, project_import
    from backend.image.assets import ImageAssetStore
    from backend.image.jobs import ImageJobManager
    from backend.image.results import ImageResultStore
    from backend.image.fiji_process import FijiCancelled
    originals, states = workspace
    archive = tmp_path / 'http.bfswork'
    save_workspace_project(originals, states, archive, active_asset_id=originals[0].id)
    assets = ImageAssetStore(tmp_path / 'assets')
    results = ImageResultStore(tmp_path / 'results')
    results.max_results = 0  # A workspace reopens raw sources, requiring no flattened result slot.
    manager = ImageJobManager()
    started, proceed = Event(), Event()
    def inspect(source, _, cancel):
        started.set()
        while not proceed.wait(.01):
            if cancel.is_set():
                raise FijiCancelled()
        return originals[0].metadata if source.id == 's0' else {'axes': [
            {'name': 'X', 'length': 24}, {'name': 'Y', 'length': 24}], 'bit_depth': 8}
    monkeypatch.setattr(api, 'store', assets)
    monkeypatch.setattr(api, 'results', results)
    monkeypatch.setattr(api, 'manager', manager)
    monkeypatch.setattr(api, 'PROJECT_INPUT_ROOT', tmp_path / 'inputs')
    monkeypatch.setattr(project_import, 'inspect_asset', inspect)
    client = TestClient(app)
    try:
        data = archive.read_bytes()
        submitted = client.post('/api/image/jobs/open-workspace', files={'file': ('state.bfswork', data)})
        assert submitted.status_code == 202, submitted.text
        assert started.wait(2)
        identifier = submitted.json()['id']
        assert submitted.json()['operation'] == 'open_workspace_project'
        assert assets.all_public() == results.all_public() == []
        assert client.post('/api/image/jobs/open-project', files={'file': ('other.bfsimg', data)}).status_code == 429
        if cancel_first:
            client.post(f'/api/image/jobs/{identifier}/cancel')
            manager.get(identifier).future.result(timeout=5)
            assert manager.get(identifier).state == 'cancelled'
            assert assets.all_public() == [] and assets._pending_count == 0
            assert list((tmp_path / 'inputs').iterdir()) == []
            proceed.set()
            submitted = client.post('/api/image/jobs/open-workspace', files={'file': ('retry.bfswork', data)})
            assert submitted.status_code == 202, submitted.text
            identifier = submitted.json()['id']
        else:
            proceed.set()
        manager.get(identifier).future.result(timeout=5)
        completed = client.get(f'/api/image/jobs/{identifier}').json()
        assert completed['state'] == 'succeeded', completed['error']
        assert len(completed['result']['assets']) == len(assets.all_public()) == 2
        active = completed['result']['workspace']['active_asset_id']
        assert completed['result']['workspace']['source_states'][active]['selection']['indices'] == {'C': 1, 'Z': 2, 'T': 1}
        assert client.post(f'/api/image/jobs/{identifier}/cancel').json()['state'] == 'succeeded'
        assert results.all_public() == [] and results._reserved == set()
        assert list((tmp_path / 'inputs').iterdir()) == []
    finally:
        proceed.set()
        manager.close()
        assets.close()
        results.close()


def test_workspace_native_form_export_contains_originals_and_releases_download(tmp_path, workspace, monkeypatch):
    from functools import partial
    from io import BytesIO
    from threading import Semaphore
    from fastapi import UploadFile
    from fastapi.testclient import TestClient
    import asyncio
    from backend.api.app import app
    from backend.image import api, project_export
    from backend.image.assets import ImageAssetStore
    originals, states = workspace
    store = ImageAssetStore(tmp_path / 'assets')
    # Unit test imports the fixture bytes with controlled metadata; real Fiji is tested separately.
    ids = []
    for original in originals:
        asset = asyncio.run(store.add(UploadFile(BytesIO(original.path.read_bytes()), filename=original.name)))
        if original.metadata:
            store.acquire(asset.id); store.set_metadata(asset.id, original.metadata); store.release(asset.id)
        ids.append(asset.id)
    request = {'asset_ids': ids, 'source_states': {ids[0]: states[originals[0].id]},
               'active_asset_id': ids[0], 'selected_asset_ids': ids[::-1], 'grid': {'columns': 2, 'gap_px': 4}}
    root, gate = tmp_path / 'exports', Semaphore(1)
    monkeypatch.setattr(api, 'store', store)
    monkeypatch.setattr(api, 'prepare_workspace_export', partial(project_export.prepare_workspace_export, root=root, gate=gate))
    client = TestClient(app)
    try:
        response = client.post('/api/image/workspace/project', data={'state': json.dumps(request)})
        assert response.status_code == 200, response.text[:500]
        assert '.bfswork' in response.headers['content-disposition']
        with ZipFile(BytesIO(response.content)) as packed:
            manifest = json.loads(packed.read('project.json'))
            assert manifest['kind'] == 'image_workspace'
            assert manifest['source_states']['s0']['selection']['indices'] == {'C': 1, 'Z': 2, 'T': 1}
            assert manifest['selected_source_keys'] == ['s1', 's0']
            assert [packed.read(f'sources/{index}.bin') for index in range(2)] == [asset.path.read_bytes() for asset in originals]
        assert list(root.iterdir()) == [] and gate.acquire(blocking=False)
        gate.release()
        assert store._leases == {}
        wrong = {**request, 'asset_ids': ['missing']}
        assert client.post('/api/image/workspace/project', data={'state': json.dumps(wrong)}).status_code == 404
        assert list(root.iterdir()) == [] and gate.acquire(blocking=False)
        gate.release()
        assert client.post('/api/image/workspace/project', content=b'x' * (4 * 1024 ** 2 + 1)).status_code == 413
        assert client.post('/api/image/workspace/project', data={'state': '{}', 'extra': 'bad'}).status_code == 422
    finally:
        store.close()


def test_cancelled_workspace_export_closes_abandoned_response(tmp_path, monkeypatch):
    import asyncio
    from starlette.requests import Request
    from backend.image import api
    started, proceed, closed = Event(), Event(), Event()
    observed = []
    class Prepared:
        def close(self):
            observed.append('closed')
            closed.set()
    def prepare(_store, _state, *, cancel):
        started.set()
        assert proceed.wait(3)
        assert cancel.is_set()
        return Prepared()
    monkeypatch.setattr(api, 'prepare_workspace_export', prepare)
    async def run():
        async def receive():
            return {'type': 'http.request', 'body': b'state=%7B%7D', 'more_body': False}
        request = Request({'type': 'http', 'method': 'POST', 'path': '/test',
                           'headers': [(b'content-type', b'application/x-www-form-urlencoded')]}, receive)
        task = asyncio.create_task(api.download_workspace_project(request))
        try:
            assert await asyncio.to_thread(started.wait, 2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        finally:
            proceed.set()
        assert await asyncio.to_thread(closed.wait, 2)
        assert observed == ['closed']
    asyncio.run(run())


def test_native_measurement_reopens_with_fresh_redirect_identity(tmp_path, workspace, monkeypatch):
    from dataclasses import replace
    from backend.image.assets import ImageAssetStore
    from backend.image import project_import
    from backend.image.workspace_import import restore_workspace_project

    originals, states = workspace
    primary = originals[0]
    target_path = tmp_path / 'target.tif'
    target_path.write_bytes(primary.path.read_bytes())
    target = replace(primary, id='target', name=target_path.name, path=target_path)
    indices = {'C': 1, 'Z': 2, 'T': 1}
    states[primary.id]['native_measurement'] = {
        'settings': {'measurements': ['mean', 'limit_to_threshold'], 'decimal_places': 5,
                     'threshold': {'min': 20, 'max': 200}},
        'roi': {'version': '1.0', 'kind': 'line', 'points': [{'x': 1.25, 'y': 1.5}, {'x': 5.25, 'y': 1.5}],
                'stroke_width': 2.5},
        'redirect_source': target.id, 'redirect_plane': indices,
    }
    archive = tmp_path / 'native.bfswork'
    manifest = save_workspace_project([primary, target], states, archive)
    assert manifest.source_states['s0'].native_measurement.redirect_source == 's1'
    monkeypatch.setattr(project_import, 'inspect_asset', lambda *_: primary.metadata)
    store = ImageAssetStore(tmp_path / 'assets')
    try:
        result = restore_workspace_project(archive, store, 'native-project', Event(), root=tmp_path / 'staging')
        source_id, target_id = [asset['id'] for asset in result['assets']]
        restored = result['workspace']['source_states'][source_id]['native_measurement']
        assert restored == {**states[primary.id]['native_measurement'], 'redirect_source': target_id}
    finally:
        store.close()
