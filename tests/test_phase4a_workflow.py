from fastapi.testclient import TestClient
from backend.api.app import app
from backend.api import app as api

client = TestClient(app)
BASE = dict(dataset_id='simulated-cell-response-v1', x_column='response', y_column='viability', dpi=72)


def test_single_render_is_atomic_and_download_is_cached(monkeypatch):
    response = client.post('/api/renders', json={'chart': BASE})
    assert response.status_code == 201
    identifier = response.json()['render_id']
    first = client.get(f'/api/renders/{identifier}.png').content
    monkeypatch.setattr(api, 'get_chart_adapter', lambda _: (_ for _ in ()).throw(AssertionError('must not render during export')))
    assert client.get(f'/api/renders/{identifier}.png').content == first
    assert client.get(f'/api/renders/{identifier}.pdf').content.startswith(b'%PDF')


def test_failure_in_any_format_does_not_publish_render(monkeypatch):
    before = set(api._renders)
    def adapter(spec, frame, fmt):
        if fmt == 'pdf':
            raise ValueError('expected format failure')
        return b'partial'
    monkeypatch.setattr(api, 'get_chart_adapter', lambda _: adapter)
    response = client.post('/api/renders', json={'chart': BASE})
    assert response.status_code == 422
    assert set(api._renders) == before


def test_expired_dataset_is_rejected_before_success():
    assert client.post('/api/renders', json={'chart': {**BASE, 'dataset_id': 'expired'}}).status_code == 404
    assert client.get('/api/datasets/expired/preview').status_code == 404


def test_dataset_preview_restores_config_reference():
    upload = client.post('/api/datasets', files={'file': ('test.csv', 'x,y\n1,2\n3,4\n', 'text/csv')}).json()
    identifier = upload['dataset_id']
    preview = client.get(f'/api/datasets/{identifier}/preview')
    assert preview.status_code == 200
    assert preview.json()['rows'] == upload['rows']


def test_render_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(api, 'get_chart_adapter', lambda _: lambda *args: b'cached')
    ids = [client.post('/api/renders', json={'chart': BASE}).json()['render_id'] for _ in range(9)]
    assert len(api._renders) == 8
    assert client.get(f'/api/renders/{ids[0]}.png').status_code == 404
    assert client.get(f'/api/renders/{ids[-1]}.png').status_code == 200
