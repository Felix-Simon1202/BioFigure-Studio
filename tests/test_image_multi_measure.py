"""Input bounds and provenance checks for the separate native Multi Measure core."""

import asyncio
from io import BytesIO
from threading import Event
from uuid import uuid4

from fastapi import UploadFile
import pytest

from backend.image.assets import ImageAssetStore
from backend.image import multi_measure
from backend.image.roi_collection import source_identity


def test_native_multi_measure_rejects_invalid_selections_without_running_fiji(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    asset = asyncio.run(store.add(UploadFile(filename="stack.tif", file=BytesIO(b"synthetic"))))
    store.acquire(asset.id)
    store.set_metadata(asset.id, {"axes": [
        {"name": "X", "length": 100}, {"name": "Y", "length": 100},
        {"name": "Channel", "length": 2}, {"name": "Z", "length": 3},
        {"name": "Time", "length": 2},
    ]})
    store.release(asset.id)
    asset = store.get(asset.id)
    item = {"id": uuid4().hex, "name": "Nucleus", "indices": {"C": 1, "Z": 2, "T": 1},
            "roi": {"kind": "ellipse", "x": 1, "y": 1, "width": 7, "height": 5}}
    document = {"version": "1.0", "source": source_identity(asset), "items": [item]}
    runs = [{"measure_all": True, "one_row_per_slice": True, "append_results": False}]
    monkeypatch.setattr(multi_measure, "native_multi_measure", lambda *_: (_ for _ in ()).throw(AssertionError("Fiji called")))
    bad_cases = [
        ([], {"C": 1, "Z": 2, "T": 1}, runs, []),
        ([item["id"], item["id"]], {"C": 1, "Z": 2, "T": 1}, runs, []),
        ([item["id"]], {"C": 1, "Z": 2}, runs, []),
        ([item["id"]], {"C": 1, "Z": 2, "T": 1}, [{**runs[0], "append_results": 1}], []),
        ([item["id"]], {"C": 1, "Z": 2, "T": 1}, runs * 4, []),
        ([item["id"]], {"C": 1, "Z": 2, "T": 1}, runs, ["std_dev", "std_dev"]),
    ]
    for ids, plane, options, flags in bad_cases:
        with pytest.raises(ValueError):
            multi_measure.run_native_multi_measure(asset, document, ids, plane, options, flags, Event())
    # Repeated native column names and append snapshots can exceed the report
    # bound even when the nominal number of new numeric cells is admissible.
    store.acquire(asset.id)
    store.set_metadata(asset.id, {"axes": [{"name": "X", "length": 100}, {"name": "Y", "length": 100},
                                         {"name": "Channel", "length": 64}]})
    store.release(asset.id)
    asset = store.get(asset.id)
    items = [{**item, "id": uuid4().hex, "name": "😀" * 78 + str(index), "indices": {"C": 0}}
             for index in range(16)]
    large = {"version": "1.0", "source": source_identity(asset), "items": items}
    with pytest.raises(ValueError, match="4 MiB"):
        multi_measure.run_native_multi_measure(asset, large, [roi["id"] for roi in items], {"C": 0},
            [{"measure_all": True, "one_row_per_slice": True, "append_results": True}] * 3, [], Event())
    store.close()


@pytest.mark.parametrize('invalid', [None, 'plane', 'roi', 'layout', 'columns', 'nan'])
def test_multi_measure_checks_complete_table_and_plane_provenance(tmp_path, monkeypatch, invalid):
    store = ImageAssetStore(tmp_path / 'assets')
    asset = asyncio.run(store.add(UploadFile(filename='source.tif', file=BytesIO(b'synthetic'))))
    store.acquire(asset.id)
    store.set_metadata(asset.id, {'axes': [{'name': 'X', 'length': 10}, {'name': 'Y', 'length': 10},
                                         {'name': 'Channel', 'length': 2}]})
    store.release(asset.id)
    asset = store.get(asset.id)
    item = {'id': uuid4().hex, 'name': 'ROI A', 'indices': {'C': 1},
            'roi': {'kind': 'rectangle', 'x': 1, 'y': 1, 'width': 2, 'height': 2}}
    document = {'version': '1.0', 'source': source_identity(asset), 'items': [item]}
    options = {'measure_all': True, 'one_row_per_slice': True, 'append_results': False}
    payload = {'source': document['source'], 'current_plane': {'C': 1}, 'measurement_flags': [],
        'roi_order': [{'id': item['id'], 'name': item['name'], 'saved_indices': item['indices'], 'roi': item['roi']}],
        'current_stack_index': 2,
        'stack_planes': [{'stack_index': 1, 'C': 0, 'Z': 0, 'T': 0}, {'stack_index': 2, 'C': 1, 'Z': 0, 'T': 0}],
        'runs': [{'options': options, 'layout': 'one_row_per_slice', 'row_count': 2,
                  'new_row_start': 0, 'new_row_count': 2, 'headings': ['Area(ROI A)'],
                  'rows': [{'Area(ROI A)': 4.0}, {'Area(ROI A)': 4.0}]}]}
    for heading in ['Mean(ROI A)', 'Min(ROI A)', 'Max(ROI A)']:
        payload['runs'][0]['headings'].append(heading)
        for row in payload['runs'][0]['rows']: row[heading] = 1.0
    if invalid == 'plane': payload['stack_planes'][1]['C'] = 0
    if invalid == 'roi': payload['roi_order'][0]['name'] = 'other'
    if invalid == 'layout': payload['runs'][0]['layout'] = 'wrong'
    if invalid == 'columns': payload['runs'][0]['rows'][1]['extra'] = 9
    if invalid == 'nan': payload['runs'][0]['rows'][0]['Area(ROI A)'] = float('nan')
    monkeypatch.setattr(multi_measure, 'native_multi_measure', lambda *_: payload)
    try:
        if invalid:
            with pytest.raises(ValueError):
                multi_measure.run_native_multi_measure(asset, document, [item['id']], {'C': 1}, [options], [], Event())
        else:
            assert multi_measure.run_native_multi_measure(asset, document, [item['id']], {'C': 1}, [options], [], Event())['runs'][0]['rows'] == payload['runs'][0]['rows']
    finally:
        store.close()


def test_multi_measure_http_cancel_owns_source_until_worker_finishes(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api.app import app
    from backend.image import api, jobs
    from backend.image.jobs import ImageJobManager
    store = ImageAssetStore(tmp_path / 'assets')
    asset = asyncio.run(store.add(UploadFile(filename='source.tif', file=BytesIO(b'synthetic'))))
    manager = ImageJobManager()
    started, resume = Event(), Event()
    def engine(_asset, _collection, _ids, _plane, _runs, _flags, cancel):
        started.set()
        assert resume.wait(3)
        return {'partial': True}  # A late successful return must lose to cancellation.
    monkeypatch.setattr(jobs, 'run_native_multi_measure', engine)
    monkeypatch.setattr(api, 'store', store)
    monkeypatch.setattr(api, 'manager', manager)
    client = TestClient(app)
    payload = {'collection': {}, 'selected_roi_ids': [], 'current_plane': {}, 'runs': [], 'measurement_flags': []}
    endpoint = f'/api/image/assets/{asset.id}/multi-measure'
    try:
        assert client.post(endpoint, json={'unknown': 1}).status_code == 422
        assert client.post(endpoint, content=b' ' * (128 * 1024 + 16385)).status_code == 413
        response = client.post(endpoint, json=payload)
        assert response.status_code == 202 and started.wait(2)
        identifier = response.json()['id']
        assert response.json()['resource_budget']['max_stack_planes'] == 64
        assert client.delete(f'/api/image/assets/{asset.id}').status_code == 409
        client.post(f'/api/image/jobs/{identifier}/cancel')
        assert store._leases == {asset.id: 1}
        resume.set()
        manager.get(identifier).future.result(timeout=3)
        finished = client.get(f'/api/image/jobs/{identifier}').json()
        assert finished['state'] == 'cancelled' and finished['result'] is None
        assert store._leases == {}
    finally:
        resume.set(); manager.close(); store.close()


def test_job_summary_omits_large_tables_without_mutating_result(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api.app import app
    from backend.image import api
    from backend.image.jobs import ImageJob, ImageJobManager
    manager = ImageJobManager()
    original = {'rows': [{'values': 'synthetic' * 1000} for _ in range(64)]}
    job = ImageJob(id='summary-test', asset_id='source-test', operation='native_multi_measure',
                   state='succeeded', result=original)
    manager._jobs[job.id] = job
    monkeypatch.setattr(api, 'manager', manager)
    try:
        client = TestClient(app)
        summary = client.get('/api/image/jobs', params={'include_results': 'false'})
        assert summary.status_code == 200 and summary.json()['items'][0]['result'] is None
        assert len(summary.content) < 1024
        assert client.get(f'/api/image/jobs/{job.id}').json()['result'] == original
        assert client.get('/api/image/jobs').json()['items'][0]['result'] == original
        assert job.result is original
    finally:
        manager.close()
