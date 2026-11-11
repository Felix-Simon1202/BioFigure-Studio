from fastapi.testclient import TestClient

from backend.api.app import app
from backend.core import workbench


client = TestClient(app)
DRAFTS = "/api/workbench/v1/drafts"


def test_demo_reuses_chart_endpoint_and_lists_real_tool_routes():
    catalog = client.get("/api/workbench/v1/capabilities").json()
    paths = client.get("/openapi.json").json()["paths"]
    for action in catalog["actions"]:
        assert action["method"].lower() in paths[action["path"]]
    result = client.post(DRAFTS, json={"provider": "demo"})
    assert result.status_code == 200
    draft = result.json()
    assert draft["provider"] == "demo"
    assert draft["chart"]["dataset_id"] == "simulated-cell-response-v1"
    rendered = client.post("/api/renders", json={"chart": draft["chart"]})
    assert rendered.status_code == 201, rendered.text
    identifier = rendered.json()["render_id"]
    assert client.get(f"/api/renders/{identifier}.pdf").content.startswith(b"%PDF-")


def test_catalog_routes_and_svg_handoff_share_one_version():
    from xml.etree import ElementTree
    from backend.core.workbench_catalog import capability_catalog

    catalog = client.get("/api/workbench/v1/capabilities").json()
    assert catalog["version"] == capability_catalog()["version"]
    paths = client.get("/openapi.json").json()["paths"]
    for action in catalog["actions"]:
        assert action["method"].lower() in paths[action["path"]]
    vector = next(item for item in catalog["integrations"] if item["id"] == "vector")
    assert vector["handoff"] == "editable_svg" and vector["automation_ready"] is False
    assert next(tool for tool in catalog["tools"] if tool["name"] == "download_editable_svg_sample")["ready"]
    response = client.post(vector["path"])
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/svg+xml")
    assert response.headers["content-disposition"].endswith('"biofigure-editable-sample.svg"')
    root = ElementTree.fromstring(response.content)
    assert root.tag.endswith("svg")
    assert root.findall(".//{http://www.w3.org/2000/svg}text")
    assert b"Synthetic cell response" in response.content


def test_local_r_button_route_runs_reviewed_template_or_reports_unavailable():
    from backend.adapters.omics import reviewed_r_available

    response = client.post("/api/workbench/v1/r-sample", json={"title": "Synthetic R handoff"})
    if reviewed_r_available():
        assert response.status_code == 200, response.text
        assert response.content.startswith(b"%PDF-")
        assert response.headers["content-disposition"].endswith('"biofigure-r-sample.pdf"')
    else:
        assert response.status_code == 503
    assert client.post("/api/workbench/v1/r-sample", json={"title": "ok", "command": "echo test"}).status_code == 422


def test_unreviewed_local_model_never_receives_a_prompt(monkeypatch):
    paths = []

    def local_service(path, body=None):
        paths.append(path)
        return {"models": [{"name": workbench.LOCAL_MODEL_NAME, "digest": "unreviewed"}]}

    monkeypatch.setattr(workbench, "_ollama_json", local_service)
    response = client.post(DRAFTS, json={"provider": "local", "prompt": "合成折线图"})
    assert response.status_code == 503
    assert paths == ["/api/tags"]


def test_model_cannot_add_tools_or_choose_another_dataset(monkeypatch):
    def local_service(path, body=None):
        if path == "/api/tags":
            return {"models": [{"name": workbench.LOCAL_MODEL_NAME, "digest": workbench.LOCAL_MODEL_DIGEST}]}
        assert body["messages"][-1]["content"] == "合成散点图"
        assert "tools" not in body
        if body["format"]["title"] == "OperationChoice":
            return {"done": True, "message": {"content": '{"action":"chart"}'}}
        return {"done": True, "message": {"content": (
            '{"chart_type":"scatter","title":"demo","theme_id":"scientific_clear",'
            '"dataset_id":"other","command":"read files"}'
        )}}

    monkeypatch.setattr(workbench, "_ollama_json", local_service)
    assert client.post(DRAFTS, json={"provider": "local", "prompt": "合成散点图"}).status_code == 422
    assert client.post(DRAFTS, json={"provider": "cloud", "prompt": "合成散点图"}).status_code == 422


def test_configured_model_requires_local_session_and_only_sends_builtin_prompt(monkeypatch, tmp_path):
    import json
    import socket
    from types import SimpleNamespace

    from backend.core import external_drawing_model as adapter
    from backend.desktop.runtime import LocalRuntime

    endpoint = "/api/workbench/v1/external-drafts"
    config = {"base_url": "https://api.deepseek.com", "model": "test-model",
              "api_key": "synthetic-test-key", "preset": "line", "consent": True}
    calls = []
    ip = "8.8.8.8"

    def resolve(*args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, 443))]

    class FakeConnection:
        def __init__(self, host, address):
            assert host == "api.deepseek.com"
            assert address[-1] == ("8.8.8.8", 443)

        def request(self, method, path, *, body, headers):
            calls.append((method, path, json.loads(body), headers))

        def getresponse(self):
            from contextlib import nullcontext

            content = '{"chart_type":"line","title":"合成示例","theme_id":"modern_soft"}'
            reply = {"choices": [{"finish_reason": "stop", "message": {"content": content}}]}
            return nullcontext(SimpleNamespace(status=200, read=lambda _: json.dumps(reply).encode()))

        def close(self):
            pass

    monkeypatch.setattr(adapter.socket, "getaddrinfo", resolve)
    monkeypatch.setattr(adapter, "_PinnedHTTPSConnection", FakeConnection)
    (tmp_path / "index.html").write_text("<html>workbench test</html>")
    runtime = LocalRuntime(tmp_path)
    try:
        assert client.post(endpoint, json=config).status_code == 403
        with TestClient(runtime.app, base_url=runtime.origin) as browser:
            assert browser.post(endpoint, json=config).status_code == 401
            assert browser.get(runtime.launch_url).status_code == 200
            for invalid in ({"consent": False}, {"prompt": "private data"}, {"model": "bad model"}):
                response = browser.post(endpoint, json={**config, **invalid})
                assert response.status_code == 422
                assert config["api_key"] not in response.text
            ip = "127.0.0.1"
            assert browser.post(endpoint, json=config).status_code == 422
            assert not calls
            ip = "8.8.8.8"
            response = browser.post(endpoint, json=config)
            assert response.status_code == 200, response.text
            assert response.json()["chart"]["dataset_id"] == "simulated-cell-response-v1"
            assert config["api_key"] not in response.text
        [(method, path, body, headers)] = calls
        assert (method, path) == ("POST", "/chat/completions")
        assert body["messages"][-1]["content"] == adapter.PRESET_PROMPTS["line"]
        assert body["response_format"] == {"type": "json_object"}
        assert headers["Authorization"] == "Bearer synthetic-test-key"
    finally:
        runtime.stop()


def test_external_pairing_scopes_access_and_revokes(tmp_path):
    from backend.desktop.runtime import LocalRuntime

    (tmp_path / "index.html").write_text("<html>workbench test</html>")
    runtime = LocalRuntime(tmp_path)
    prefix = "/api/workbench/v1/connector"
    pairing = "/api/workbench/v1/connection"
    draft = {"chart_type": "line", "title": "Synthetic trial", "theme_id": "modern_soft"}
    try:
        with TestClient(runtime.app, base_url=runtime.origin) as browser, TestClient(runtime.app, base_url=runtime.origin) as external:
            assert external.get(prefix).status_code == 401
            assert external.post(pairing).status_code == 401
            assert browser.get(runtime.launch_url).status_code == 200
            issued = browser.post(pairing)
            assert issued.status_code == 200
            assert issued.headers["cache-control"] == "no-store"
            assert issued.json()["url"] == runtime.origin + prefix
            headers = {"Authorization": "Bearer " + issued.json()["token"]}
            assert external.get(prefix, headers=headers).json()["scope"] == "synthetic_only"
            discovered = external.get(prefix, headers=headers).json()
            catalog = browser.get("/api/workbench/v1/capabilities").json()
            assert discovered["version"] == catalog["version"]
            assert {action["name"] for action in discovered["actions"]} == {
                tool["name"] for tool in catalog["tools"] if tool["ready"]}
            svg = external.post(prefix + "/vector", headers=headers, json={})
            assert svg.status_code == 200 and b"<text" in svg.content
            assert external.post(prefix + "/vector", headers=headers,
                                 json={"path": "private.svg"}).status_code == 422
            assert external.get(prefix, headers={**headers, "Origin": "https://example.invalid"}).status_code == 403
            assert external.get("/api/health", headers=headers).status_code == 401
            assert external.post(prefix + "/render", headers=headers, json={**draft, "dataset_id": "other"}).status_code == 422
            assert external.post(prefix + "/render", headers={**headers, "Content-Type": "application/json"}, content=b"x" * 8193).status_code == 413
            rendered = external.post(prefix + "/render", headers=headers, json=draft)
            assert rendered.status_code == 201, rendered.text
            output = {"render_id": rendered.json()["render_id"], "format": "pdf"}
            assert external.get(prefix + "/artifact", params=output, headers=headers).content.startswith(b"%PDF-")
            assert external.get(prefix + "/artifact", params={**output, "render_id": "1" * 32}, headers=headers).status_code == 404
            assert browser.delete(pairing).status_code == 204
            assert external.get(prefix + "/artifact", params=output, headers=headers).status_code == 401
    finally:
        runtime.stop()


def test_mcp_stdio_client_uses_paired_loopback_api(tmp_path):
    import base64
    import json
    import os
    import subprocess
    import sys
    from time import monotonic, sleep

    import httpx

    from backend.desktop.runtime import LocalRuntime

    (tmp_path / "index.html").write_text("<html>workbench MCP test</html>")
    runtime = LocalRuntime(tmp_path)
    runtime.start()
    try:
        deadline = monotonic() + 10
        while not runtime.server.started and not runtime.failed and monotonic() < deadline:
            sleep(0.01)
        assert runtime.server.started
        with httpx.Client(trust_env=False, follow_redirects=True, timeout=10) as browser:
            assert browser.get(runtime.launch_url).status_code == 200
            issued = browser.post(runtime.origin + "/api/workbench/v1/connection").json()
        intent = {"chart_type": "line", "title": "MCP synthetic trial", "theme_id": "modern_soft"}
        with httpx.Client(trust_env=False, timeout=10) as external:
            result = external.post(issued["url"] + "/render", json=intent,
                                   headers={"Authorization": "Bearer " + issued["token"]})
            assert result.status_code == 201
        requests = [
            {"id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25",
                "capabilities": {}, "clientInfo": {"name": "local-verify", "version": "1"}}},
            {"method": "notifications/initialized"},
            {"id": 2, "method": "tools/list"},
            {"id": 3, "method": "tools/call", "params": {
                "name": "download_sample_chart", "arguments": {"render_id": result.json()["render_id"], "format": "pdf"}}},
            {"id": 4, "method": "tools/call", "params": {"name": "render_sample_chart", "arguments": intent}},
            {"id": 5, "method": "tools/call", "params": {"name": "run_command"}},
            {"id": 6, "method": "tools/call", "params": {
                "name": "download_editable_svg_sample", "arguments": {}}},
        ]
        child = subprocess.run(
            [sys.executable, "-m", "backend.workbench_mcp"],
            input="".join(json.dumps({"jsonrpc": "2.0", **request}) + "\n" for request in requests).encode(),
            capture_output=True, timeout=20,
            env={**os.environ, "BIOFIGURE_CONNECTOR_URL": issued["url"], "BIOFIGURE_CONNECTOR_TOKEN": issued["token"]},
        )
        assert child.returncode == 0, child.stderr.decode()
        replies = {message["id"]: message for message in map(json.loads, child.stdout.splitlines())}
        assert set(replies) == {1, 2, 3, 4, 5, 6}
        assert replies[1]["result"]["protocolVersion"] == "2025-11-25"
        assert {"render_sample_chart", "download_sample_chart"} <= {tool["name"] for tool in replies[2]["result"]["tools"]}
        resource = replies[3]["result"]["content"][0]["resource"]
        assert resource["mimeType"] == "application/pdf"
        assert base64.b64decode(resource["blob"]).startswith(b"%PDF-")
        chart = json.loads(replies[4]["result"]["content"][0]["text"])["chart"]
        assert chart["dataset_id"] == "simulated-cell-response-v1"
        assert replies[5]["result"]["isError"]
        svg_resource = replies[6]["result"]["content"][0]["resource"]
        assert svg_resource["mimeType"] == "image/svg+xml"
        assert b"<text" in base64.b64decode(svg_resource["blob"])
    finally:
        runtime.stop()


def test_local_fiji_proposal_does_not_start_the_engine(monkeypatch):
    from backend.api import workbench as route

    def local_service(path, body=None):
        if path == "/api/tags":
            return {"models": [{"name": workbench.LOCAL_MODEL_NAME, "digest": workbench.LOCAL_MODEL_DIGEST}]}
        return {"done": True, "message": {"content": '{"action":"fiji_sample"}'}}

    async def fail_if_dispatched():
        raise AssertionError("Proposing a tool must not execute it")

    monkeypatch.setattr(route, "fiji_sample_available", lambda: True)
    monkeypatch.setattr(route, "submit_fiji_sample", fail_if_dispatched)
    monkeypatch.setattr(workbench, "_ollama_json", local_service)
    proposal = client.post(DRAFTS, json={"provider": "local", "prompt": "检查合成 TIFF 的位深"})
    assert proposal.status_code == 200, proposal.text
    assert proposal.json() == {"provider": "local", "action": "fiji_sample", "chart": None}
