import json
import os
from pathlib import Path
import queue
import re
import socket
import subprocess
import sys
import threading
from urllib.parse import urlsplit

import httpx
import pytest
from fastapi.testclient import TestClient

from backend.desktop.runtime import LocalRuntime

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps/web/dist"
BASE = dict(dataset_id="simulated-cell-response-v1", x_column="response", y_column="viability", dpi=72)


@pytest.fixture
def local(tmp_path):
    (tmp_path / "index.html").write_text("<html>local test</html>")
    runtime = LocalRuntime(tmp_path)
    yield runtime
    runtime.stop()


def test_session_origin_and_file_boundary(local):
    with TestClient(local.app, base_url=local.origin) as client:
        assert client.get("/api/health").status_code == 401
        assert client.get("/_launch/wrong").status_code == 401
        response = client.get(local.launch_url)
        assert response.status_code == 200
        cookie = response.history[0].headers["set-cookie"]
        assert "HttpOnly" in cookie and "SameSite=strict" in cookie
        assert client.get("/api/health").json()["status"] == "ok"
        for headers in ({"Origin": "https://example.invalid"}, {"Host": "evil.invalid"}, {"Sec-Fetch-Site": "cross-site"}):
            assert client.get("/api/health", headers=headers).status_code == 403
            assert client.post("/api/renders", json={"chart": BASE}, headers=headers).status_code == 403
        assert client.get("/%2e%2e/README.md").status_code == 404
        assert client.get("/api/not-a-route").status_code == 404
        assert "connect-src 'self'" in response.headers["content-security-policy"]
        assert response.headers["referrer-policy"] == "no-referrer"
    with TestClient(local.app, base_url=local.origin) as other:
        assert other.get("/api/health").status_code == 401


def test_missing_web_fails_before_listening(tmp_path):
    with pytest.raises(RuntimeError, match="缺少"):
        LocalRuntime(tmp_path)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows instance ownership")
def test_duplicate_lock_and_release(tmp_path):
    from backend.desktop.launcher import InstanceLock
    first, second = InstanceLock(tmp_path), InstanceLock(tmp_path)
    try:
        assert not first.existing and second.existing
    finally:
        first.close()
        second.close()
    again = InstanceLock(tmp_path)
    try:
        assert not again.existing
    finally:
        again.close()


def spawn_worker():
    assert (WEB / "index.html").is_file(), "Build the frontend before desktop integration tests"
    process = subprocess.Popen([sys.executable, str(ROOT / "tests/desktop_worker.py"), str(WEB)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    result = queue.Queue()
    threading.Thread(target=lambda: result.put(process.stdout.readline()), daemon=True).start()
    try:
        line = result.get(timeout=30)
        return process, json.loads(line)["url"]
    except BaseException:
        process.kill()
        process.communicate(timeout=10)
        raise


def test_real_offline_five_charts_exports_and_shutdown():
    # Keep an unrelated listener occupied throughout; the runtime must neither
    # adopt it nor close it. No fixed development/user port is touched.
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        occupied.listen()
        process, url = spawn_worker()
        port = urlsplit(url).port
        try:
            assert port != occupied.getsockname()[1]
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", trust_env=False, follow_redirects=True, timeout=60) as client:
                page = client.get(url)
                assert page.status_code == 200
                assets = re.findall(r'(?:src|href)="(/assets/[^"]+)"', page.text)
                assert assets and all(client.get(asset).status_code == 200 for asset in assets)
                upload = client.post("/api/datasets", files={"file": ("合成数据.csv", "横轴,纵轴\n1,2\n2,4\n".encode(), "text/csv")})
                assert upload.status_code == 201
                for kind in ("scatter", "bar", "line", "box", "heatmap"):
                    spec = {**BASE, "chart_type": kind}
                    result = client.post("/api/renders", json={"chart": spec})
                    assert result.status_code == 201, result.text
                    identifier = result.json()["render_id"]
                    for fmt, signature in (("png", b"\x89PNG"), ("pdf", b"%PDF"), ("svg", b"<?xml")):
                        output = client.get(f"/api/renders/{identifier}.{fmt}")
                        assert output.status_code == 200 and output.content.startswith(signature)
                figure = client.post("/api/figures", json={"panels": [BASE] * 4, "dpi": 72})
                assert figure.status_code == 201
                for fmt in ("png", "pdf", "svg"):
                    assert client.get(f"/api/figures/{figure.json()['render_id']}.{fmt}").status_code == 200
            stdout, stderr = process.communicate("stop\n", timeout=15)
            assert process.returncode == 0, stderr
            assert json.loads(stdout) == {"stopped": True, "blocked": []}
            with socket.socket() as probe:
                assert probe.connect_ex(("127.0.0.1", port)) != 0
            assert occupied.fileno() != -1
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)


def test_abnormal_exit_releases_listener():
    process, url = spawn_worker()
    port = urlsplit(url).port
    try:
        process.kill()  # Only this test's own child, never a discovered PID.
        process.communicate(timeout=10)
        with socket.socket() as probe:
            assert probe.connect_ex(("127.0.0.1", port)) != 0
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
