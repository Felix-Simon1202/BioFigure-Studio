"""Integration-test child. Block non-loopback Python networking before imports."""
import ipaddress
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
blocked = []


def audit(event, args):
    if event not in ("socket.connect", "socket.getaddrinfo", "socket.sendto"):
        return
    host = args[0] if event == "socket.getaddrinfo" else args[-1][0]
    try:
        allowed = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        allowed = False
    if not allowed:
        blocked.append(event)
        raise OSError("Offline test denies non-loopback network access")


sys.addaudithook(audit)
from backend.desktop.runtime import LocalRuntime

runtime = LocalRuntime(Path(sys.argv[1]))
runtime.start()
deadline = time.monotonic() + 20
while not runtime.server.started:
    if runtime.failed or time.monotonic() > deadline:
        raise RuntimeError("Startup failed")
    time.sleep(0.02)
print(json.dumps({"url": runtime.launch_url}), flush=True)
sys.stdin.readline()
stopped = runtime.stop()
print(json.dumps({"stopped": stopped, "blocked": blocked}), flush=True)
sys.exit(0 if stopped and not blocked else 1)
