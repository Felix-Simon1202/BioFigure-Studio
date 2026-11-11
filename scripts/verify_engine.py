"""Exercise a frozen engine with synthetic input and no Python environment."""
import io
import json
import os
from pathlib import Path
import queue
import socket
import subprocess
import sys
import threading

import httpx
from openpyxl import Workbook

binary = Path(sys.argv[1]).resolve()
output = Path(sys.argv[2]).resolve()
output.mkdir(parents=True, exist_ok=True)
env = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON") and key != "VIRTUAL_ENV"}
env["PATH"] = str(Path(os.environ["SystemRoot"]) / "System32")
process = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    text=True, cwd=output, env=env, creationflags=subprocess.CREATE_NO_WINDOW)
try:
    process.stdin.write("START\n")
    process.stdin.flush()
    ready = queue.Queue()
    threading.Thread(target=lambda: ready.put(process.stdout.readline()), daemon=True).start()
    line = ready.get(timeout=45)
    if not line:
        raise RuntimeError(process.stderr.read())
    url = json.loads(line)["url"]
    origin = url.split("/_launch/")[0]
    base = dict(dataset_id="simulated-cell-response-v1", x_column="response", y_column="viability", dpi=100)
    with httpx.Client(base_url=origin, trust_env=False, follow_redirects=True, timeout=90) as client:
        assert client.get(url).status_code == 200
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["response", "viability"])
        sheet.append([1, 2])
        sheet.append([2, 3])
        stream = io.BytesIO()
        workbook.save(stream)
        for filename, content in (("合成数据.xlsx", stream.getvalue()), ("合成数据.csv", b"response,viability\n1,2\n2,3\n")):
            imported = client.post("/api/datasets", files={"file": (filename, content)})
            assert imported.status_code == 201, imported.text
        for kind in ("scatter", "bar", "line", "box", "heatmap"):
            created = client.post("/api/renders", json={"chart": {**base, "chart_type": kind}})
            assert created.status_code == 201, created.text
            for fmt, signature in (("png", b"\x89PNG"), ("pdf", b"%PDF"), ("svg", b"<?xml")):
                artifact = client.get(f"/api/renders/{created.json()['render_id']}.{fmt}")
                assert artifact.status_code == 200 and artifact.content.startswith(signature)
                (output / f"{kind}.{fmt}").write_bytes(artifact.content)
        created = client.post("/api/figures", json={"panels": [base] * 4, "dpi": 100})
        assert created.status_code == 201, created.text
        for fmt in ("png", "pdf", "svg"):
            artifact = client.get(f"/api/figures/{created.json()['render_id']}.{fmt}")
            assert artifact.status_code == 200
            (output / f"four-panels.{fmt}").write_bytes(artifact.content)
    process.communicate("STOP\n", timeout=10)
    assert process.returncode == 0
    with socket.socket() as probe:
        assert probe.connect_ex(("127.0.0.1", int(origin.rsplit(":", 1)[1]))) != 0
    print("PASS: frozen engine, clean environment, CSV/XLSX, five charts, four panels, 18 exports, shutdown")
finally:
    if process.poll() is None:
        process.kill()
        process.communicate(timeout=10)
