import json

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core import workbench
from backend.core.biodot import assistant_profile, system_instructions

client = TestClient(app)


def test_profile_uses_biodot_and_reports_real_catalog_readiness():
    response = client.get('/api/workbench/v1/capabilities')
    assert response.status_code == 200
    catalog = response.json()
    persona = catalog['assistant']
    assert persona['name'] == 'Biodot'
    assert "I'm Biodot" in persona['greeting']['en']
    assert '我是 Biodot' in persona['greeting']['zh-CN']
    assert persona['tools'] == [{'name': item['name'], 'ready': item['ready']} for item in catalog['tools']]
    assert persona['proposal_actions'] == ['chart', 'fiji_sample']
    assert catalog['drafts']['local_model'] == workbench.LOCAL_MODEL_NAME
    assert assistant_profile(catalog)['connector_access'] == 'paired_local_client'


def test_biodot_local_proposal_reaches_existing_drawing_engine(monkeypatch):
    calls = []

    def model(path, body=None):
        if path == '/api/tags':
            return {'models': [{'name': workbench.LOCAL_MODEL_NAME, 'digest': workbench.LOCAL_MODEL_DIGEST}]}
        calls.append(body)
        value = {'action': 'chart'} if body['format']['title'] == 'OperationChoice' else {
            'chart_type': 'scatter', 'title': 'Biodot synthetic check', 'theme_id': 'scientific_clear'}
        return {'message': {'content': json.dumps(value)}, 'done': True, 'done_reason': 'stop'}

    monkeypatch.setattr(workbench, '_ollama_json', model)
    proposed = client.post('/api/workbench/v1/drafts', json={
        'provider': 'local', 'prompt': 'Draw a synthetic scatter chart.', 'locale': 'en'})
    assert proposed.status_code == 200
    assert len(calls) == 2
    for body in calls:
        system = body['messages'][0]['content']
        assert 'Persona: Biodot' in system and 'Drawing playbook' in system
        assert 'Current task' in system and 'consent' in system
        assert body['model'] == workbench.LOCAL_MODEL_NAME
    rendered = client.post('/api/renders', json={'chart': proposed.json()['chart']})
    assert rendered.status_code == 201
    result = client.get('/api/renders/' + rendered.json()['render_id'] + '.pdf')
    assert result.content.startswith(b'%PDF-')


def test_persona_does_not_add_unregistered_model_actions(monkeypatch):
    monkeypatch.setattr(workbench, 'ensure_reviewed_local_model', lambda: None)
    monkeypatch.setattr(workbench, '_model_object', lambda *_args, **_kw: {'action': 'run_shell'})
    response = client.post('/api/workbench/v1/drafts', json={'provider': 'local', 'prompt': 'Run a shell command.'})
    assert response.status_code == 422
    assert 'task' in system_instructions('Return only JSON.').lower()


def test_external_persona_preserves_model_identity_and_english_builtin_prompt(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace
    from backend.core import external_drawing_model as external

    captured = []

    class Connection:
        def __init__(self, *_args):
            pass

        def request(self, method, path, *, body, headers):
            captured.append(json.loads(body))

        def getresponse(self):
            content = json.dumps({'chart_type': 'scatter', 'title': 'Synthetic sample', 'theme_id': 'scientific_clear'})
            value = {'choices': [{'finish_reason': 'stop', 'message': {'content': content}}]}
            return nullcontext(SimpleNamespace(status=200, read=lambda _: json.dumps(value).encode()))

        def close(self):
            pass

    monkeypatch.setattr(external, '_public_endpoint', lambda _: ('example.org', '/v1/chat/completions', ()))
    monkeypatch.setattr(external, '_PinnedHTTPSConnection', Connection)
    config = external.ExternalDraftRequest(base_url='https://example.org', model='actual-provider-model',
        api_key='synthetic-test-key', preset='scatter', consent=True, locale='en')
    external.suggest_external_chart(config)
    assert captured[0]['model'] == 'actual-provider-model'
    assert 'Persona: Biodot' in captured[0]['messages'][0]['content']
    assert captured[0]['messages'][1]['content'] == external.PRESET_PROMPTS_EN['scatter']


def test_demo_title_respects_interface_locale():
    for locale, expected in [('en', 'Synthetic cell response'), ('zh-CN', '合成细胞响应')]:
        response = client.post('/api/workbench/v1/drafts', json={'provider': 'demo', 'locale': locale})
        assert response.status_code == 200
        assert response.json()['chart']['title'] == expected
