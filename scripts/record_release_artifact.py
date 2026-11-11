"""Record a desktop installer only when it matches the reviewed source record."""

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "work/third-party/release-source.json"
NSIS = ROOT / "work/cargo-target/release/bundle/nsis"
OUTPUT = ROOT / "work/phase9-evidence/installer-candidate.json"


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hashed.update(chunk)
    return hashed.hexdigest().upper()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def select_installer(directory: Path, version: str) -> Path:
    expected = f"BioFigure Studio_{version}_x64-setup.exe"
    candidates = sorted(directory.glob("*.exe"))
    if len(candidates) != 1 or candidates[0].name != expected:
        raise ValueError(f"Expected only {expected} in {directory}; found {[path.name for path in candidates]}")
    installer = candidates[0]
    if not installer.resolve().is_relative_to(directory.resolve()) or installer.stat().st_size == 0:
        raise ValueError("Installer is empty or points outside the bundle directory")
    return installer


def build_record() -> dict:
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Release source has uncommitted or untracked files")
    if not SOURCE.is_file():
        raise ValueError("Release source record is missing")
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    commit = git("rev-parse", "HEAD")
    if source["source_commit"] != commit or source["target"] != "windows-x64-nsis-current-user":
        raise ValueError("Release source record differs from this checkout")
    if source["product_version"] == "0.2.0" or source["webview_install_mode"] != "offlineInstaller":
        raise ValueError("Release source record is not a new offline installer candidate")
    installer = select_installer(NSIS, source["product_version"])
    if installer.stat().st_mtime_ns < SOURCE.stat().st_mtime_ns:
        raise ValueError("Installer predates the current release source record")
    return {
        "schema_version": "1.0",
        "source_commit": commit,
        "product_version": source["product_version"],
        "target": source["target"],
        "webview_install_mode": source["webview_install_mode"],
        "worktree_clean": True,
        "release_source_sha256": digest(SOURCE),
        "installer_path": str(installer.relative_to(ROOT)).replace("\\", "/"),
        "installer_size_bytes": installer.stat().st_size,
        "installer_sha256": digest(installer),
        "installer_modified_at_utc": datetime.fromtimestamp(installer.stat().st_mtime, timezone.utc).isoformat(),
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "build_host": {"system": platform.system(), "release": platform.release(), "machine": platform.machine()},
        "payload_verified": False,
        "clean_device_verified": False,
    }


def main() -> None:
    try:
        record = build_record()
    except (KeyError, ValueError) as exc:
        raise SystemExit(str(exc)) from None
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Installer evidence: {record['installer_sha256']} -> {OUTPUT}")


if __name__ == "__main__":
    main()
