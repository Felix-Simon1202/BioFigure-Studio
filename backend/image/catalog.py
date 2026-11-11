"""Read the pinned Fiji command inventory without loading third-party code.

Discovery is evidence only. A discovered menu entry is never executable merely
because it appears in this catalog.
"""

import json
from pathlib import Path
import sys
from typing import Any
from backend.image.fiji_process import RUNTIME as RUNTIME_PATH


ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]
INVENTORY_PATH = ROOT / "docs" / "FIJI_COMMAND_INVENTORY.json"
STAGES = ("discovered", "source_reviewed", "runtime_verified", "ui_adapted", "parity_verified")


def _empty_counts() -> dict[str, int]:
    return {stage: 0 for stage in STAGES}


def load_inventory(path: Path = INVENTORY_PATH) -> dict[str, Any]:
    if not path.is_file():
        return {"snapshot_id": None, "items": [], "counts": _empty_counts(), "inventory_state": "missing"}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "1.0" or not isinstance(payload.get("items"), list):
        raise ValueError("Fiji command inventory has an unsupported schema")
    items = payload["items"]
    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)) or any(not isinstance(value, str) or not value for value in ids):
        raise ValueError("Fiji command inventory contains invalid or duplicate IDs")
    counts = _empty_counts()
    for item in items:
        status = item.get("status", {})
        for stage in STAGES:
            counts[stage] += bool(status.get(stage, False))
    return {
        "snapshot_id": payload.get("snapshot_id"),
        "items": items,
        "counts": counts,
        "inventory_state": payload.get("inventory_state", "unverified"),
    }


def runtime_status() -> dict[str, Any]:
    inventory = load_inventory()
    installed = (RUNTIME_PATH / "fiji-windows-x64.exe").is_file()
    return {
        "state": "inventory_ready" if installed and inventory["items"] else "unavailable",
        "snapshot_id": inventory["snapshot_id"],
        "message": (
            "已发现发行包命令；每项仍需单独审核、适配与等效验证。"
            if installed and inventory["items"] else
            "Fiji 运行时或命令清单尚未准备完成。"
        ),
        "counts": inventory["counts"],
    }
