"""Record the exact local inputs used for a desktop candidate; no network access."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[1]
THIRD_PARTY = (ROOT / "work/third-party").resolve()
ENGINE = ROOT / "work/engine-dist/biofigure-engine"


def digest(path: Path) -> str:
    hashed = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            hashed.update(chunk)
    return hashed.hexdigest().upper()


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, check=True, capture_output=True, text=True).stdout.strip()


def files_under(directory: Path) -> list[Path]:
    return sorted(path for path in directory.rglob("*") if path.is_file())


def build_record(source_only: bool) -> dict:
    if Path(git("rev-parse", "--show-toplevel")).resolve() != ROOT.resolve():
        raise ValueError("Git root differs from this source tree")
    if git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Release source has uncommitted or untracked files")

    tauri = json.loads((ROOT / "apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8"))
    desktop = json.loads((ROOT / "apps/desktop/package.json").read_text(encoding="utf-8"))
    cargo = tomllib.loads((ROOT / "apps/desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8"))
    if tauri["version"] != desktop["version"] or tauri["version"] != cargo["package"]["version"]:
        raise ValueError("Desktop versions do not match")
    if not source_only and tauri["version"] == "0.2.0":
        raise ValueError("Old 0.2.0 installer version cannot label a phase 9 candidate")
    if tauri["bundle"]["windows"]["webviewInstallMode"]["type"] != "offlineInstaller":
        raise ValueError("Release is missing offline WebView2 installer mode")
    if tauri["bundle"]["windows"]["nsis"]["installMode"] != "currentUser":
        raise ValueError("Release must use current-user installation")
    if tauri["app"]["security"].get("capabilities") != []:
        raise ValueError("Desktop command capabilities are not reviewed")

    web = ROOT / "apps/web/dist"
    if not (web / "index.html").is_file():
        raise ValueError("Production web build is missing")
    web_files = files_under(web)
    inputs = [
        ROOT / "backend/requirements.lock.txt",
        ROOT / "backend/requirements-packaging.lock.txt",
        ROOT / "apps/web/package-lock.json",
        ROOT / "apps/desktop/package-lock.json",
        ROOT / "apps/desktop/src-tauri/Cargo.lock",
        ROOT / "assets/fonts/NotoSansSC-Regular.ttf",
        ROOT / "apps/web/public/assets/fossil-relief-v2.png",
        ROOT / "apps/web/public/assets/fossil-relief.webp",
        ROOT / "THIRD_PARTY_NOTICES.md",
        ROOT / "licenses/desktop/Microsoft-WebView2-Runtime-EULA.html",
        ROOT / "scripts/Set-BioFigure-FijiRuntime.ps1",
    ]
    record = {
        "schema_version": "1.0",
        "source_commit": git("rev-parse", "HEAD"),
        "product_version": tauri["version"],
        "target": "windows-x64-nsis-current-user",
        "webview_install_mode": "offlineInstaller",
        "webview_reviewed_guid": "14f2cd10-e392-45ff-a699-5e08c803d4c7",
        "webview_reviewed_sha256": "1D1C838E5971343C060415DA7C630C3C1CA7AD33FBB61CCA660F3C1122F4CCA8",
        "fiji_delivery": "external_pinned_runtime_required_for_imagej_operations",
        "inputs": {str(path.relative_to(ROOT)).replace("\\", "/"): digest(path) for path in inputs},
        "web_build": {str(path.relative_to(web)).replace("\\", "/"): digest(path) for path in web_files},
    }
    if not source_only:
        if not (THIRD_PARTY / "inventory.json").is_file():
            raise ValueError("Third-party inventory is missing")
        executable = ENGINE / "biofigure-engine.exe"
        if not executable.is_file():
            raise ValueError("Current engine build is missing")
        engine_files = files_under(ENGINE)
        combined = hashlib.sha256()
        for path in engine_files:
            combined.update(str(path.relative_to(ENGINE)).replace("\\", "/").encode("utf-8"))
            combined.update(b"\0")
            combined.update(bytes.fromhex(digest(path)))
        record["engine_file_count"] = len(engine_files)
        record["engine_tree_sha256"] = combined.hexdigest().upper()
        record["third_party_inventory_sha256"] = digest(THIRD_PARTY / "inventory.json")
    return record


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-only", action="store_true", help="Check source and web build without packaging")
    args = parser.parse_args()
    try:
        record = build_record(args.source_only)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    if args.source_only:
        print(json.dumps(record, ensure_ascii=False, indent=2))
    else:
        output = THIRD_PARTY / "release-source.json"
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Release source record: {record['source_commit']} -> {output}")


if __name__ == "__main__":
    main()
