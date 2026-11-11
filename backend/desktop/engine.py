"""Packaged engine protocol: START on stdin, ready JSON on stdout, EOF to stop."""
import ipaddress
import json
import os
from pathlib import Path
import sys
import threading
import time


def local_network_only(event, args):
    if event not in ("socket.connect", "socket.getaddrinfo", "socket.sendto"):
        return
    host = args[0] if event == "socket.getaddrinfo" else args[-1][0]
    try:
        allowed = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        allowed = False
    if not allowed:
        raise OSError("The local drawing engine does not allow external network access")


def main():
    # The parent assigns process ownership before permitting startup. If the
    # parent disappears before this handshake, EOF exits without a listener.
    if sys.stdin.readline().strip() != "START":
        return
    sys.addaudithook(local_network_only)
    from backend.desktop.runtime import LocalRuntime
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
    runtime = LocalRuntime(root / "apps/web/dist")
    runtime.start()
    deadline = time.monotonic() + 30
    while not runtime.server.started:
        if runtime.failed or time.monotonic() > deadline:
            raise RuntimeError("Engine startup failed")
        time.sleep(0.02)
    print(json.dumps({"url": runtime.launch_url}), flush=True)
    # Parent closes the pipe on exit. Do not depend on browser/tab events.
    def watch_parent():
        sys.stdin.readline()
        runtime.stop(4)
        os._exit(0)
    threading.Thread(target=watch_parent, daemon=True).start()
    while runtime.thread.is_alive():
        time.sleep(0.1)


if __name__ == "__main__":
    main()
