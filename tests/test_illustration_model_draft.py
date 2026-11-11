"""The illustration model sees only one fixed synthetic paragraph."""

import json
import re

from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core import workbench


client = TestClient(app)
PATH = "/api/workbench/v1/illustration-draft"
REQUEST = {"sample_id": "synthetic-branch-v1"}


def _reviewed_tags():
    return {"models": [{"name": workbench.LOCAL_MODEL_NAME,
                        "digest": workbench.LOCAL_MODEL_DIGEST}]}


def test_reviewed_local_model_extracts_exact_fixed_synthetic_spans(monkeypatch):
    calls = []

    def service(path, body=None):
        calls.append((path, body))
        if path == "/api/tags":
            return _reviewed_tags()
        assert path == "/api/chat"
        assert body["model"] == workbench.LOCAL_MODEL_NAME
        assert body["messages"][-1] == {"role": "user", "content": workbench.SYNTHETIC_BRANCH_SOURCE}
        assert body["think"] is False and body["stream"] is False and "tools" not in body
        return {"done": True, "message": {"content": json.dumps(workbench.BRANCH_SPAN_POSITIONS)}}

    monkeypatch.setattr(workbench, "_ollama_json", service)
    response = client.post(PATH, json=REQUEST)
    assert response.status_code == 200, response.text
    numbered = re.findall(r"\[([1-8])\]“([^”]+)”", workbench.SYNTHETIC_BRANCH_SOURCE)
    assert [int(number) for number, _ in numbered] == list(range(1, 9))
    spans = {int(number): text for number, text in numbered}
    assert response.json()["fields"] == {
        field: spans[number] for field, number in workbench.BRANCH_SPAN_POSITIONS.items()
    }
    assert response.json()["source_text"] == workbench.SYNTHETIC_BRANCH_SOURCE
    assert [path for path, _ in calls] == ["/api/tags", "/api/chat"]


def test_unreviewed_model_and_unapproved_input_never_reach_chat(monkeypatch):
    paths = []

    def service(path, body=None):
        paths.append(path)
        return {"models": [{"name": workbench.LOCAL_MODEL_NAME, "digest": "unreviewed"}]}

    monkeypatch.setattr(workbench, "_ollama_json", service)
    assert client.post(PATH, json=REQUEST).status_code == 503
    assert paths == ["/api/tags"]
    assert client.post(PATH, json={**REQUEST, "paragraph": "real experimental data"}).status_code == 422
    assert client.post(PATH, json={"sample_id": "another"}).status_code == 422
    assert paths == ["/api/tags"]


def test_missing_wrong_duplicate_out_of_range_and_extra_spans_are_rejected(monkeypatch):
    from backend.api import workbench as route

    def check(content):
        monkeypatch.setattr(workbench, "_ollama_json", lambda path, body=None:
                            _reviewed_tags() if path == "/api/tags" else
                            {"done": True, "message": {"content": content}})
        response = client.post(PATH, json=REQUEST)
        assert response.status_code == 422, response.text
        assert response.json()["detail"] == "本机模型未逐字提取合成流程；可手动填写合成示例。"

    correct = workbench.BRANCH_SPAN_POSITIONS
    check(json.dumps({key: value for key, value in correct.items() if key != "resultB"}))
    check(json.dumps({**correct, "stepA": 7, "stepB": 4}))
    check(json.dumps({**correct, "resultB": 7}))
    check(json.dumps({**correct, "resultB": 9}))
    check(json.dumps({**correct, "command": "read files"}))
    check(json.dumps({**correct, "stepA": "4"}))
    check('{"title":"a","title":"b"}')
    route._model_admission.acquire()
    try:
        assert client.post(PATH, json=REQUEST).status_code == 429
    finally:
        route._model_admission.release()
