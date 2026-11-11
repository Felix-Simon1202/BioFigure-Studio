"""Collect exact installed release licenses; no network or code execution."""
import importlib.metadata
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tomllib
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CARGO_HOME = ROOT / "work/tooling/cargo"
cargo_home = Path(os.environ.get("CARGO_HOME", DEFAULT_CARGO_HOME))
cargo_exe = cargo_home / "bin/cargo.exe"
if not cargo_exe.is_file():
    raise SystemExit(f"No reviewed Cargo executable at {cargo_exe}; refusing an incomplete license inventory")
metadata_result = subprocess.run(
    [str(cargo_exe), "metadata", "--offline", "--locked", "--format-version", "1",
     "--filter-platform", "x86_64-pc-windows-msvc", "--manifest-path",
     str(ROOT / "apps/desktop/src-tauri/Cargo.toml")],
    capture_output=True, text=True, encoding="utf-8", errors="replace",
    env={**os.environ, "CARGO_HOME": str(cargo_home)},
)
if metadata_result.returncode:
    raise SystemExit(f"Offline Windows Cargo dependency resolution failed: {metadata_result.stderr.strip()}")
metadata = json.loads(metadata_result.stdout)
registry_root = (cargo_home / "registry/src").resolve()
cargo_manifests = []
for package in metadata["packages"]:
    if package["source"] is None:
        continue
    if not package["source"].startswith("registry+"):
        raise SystemExit(f"Unreviewed Cargo source for {package['name']}")
    manifest = Path(package["manifest_path"]).resolve()
    if not manifest.is_relative_to(registry_root) or not manifest.is_file():
        raise SystemExit(f"Cargo source is missing from the reviewed cache: {package['name']} {package['version']}")
    cargo_manifests.append(manifest)
cargo_manifests.sort()
locked = tomllib.loads((ROOT / "apps/desktop/src-tauri/Cargo.lock").read_text(encoding="utf-8"))
direct = {("tauri", "2.11.5"), ("tauri-build", "2.6.3"), ("windows-sys", "0.61.2")}
locked_names = {(package["name"], package["version"]) for package in locked["package"]}
if not direct <= locked_names:
    raise SystemExit("Desktop direct dependency versions differ from the reviewed release baseline")
source_names = set()
for manifest in cargo_manifests:
    meta = tomllib.loads(manifest.read_text(encoding="utf-8"))["package"]
    source_names.add((meta["name"], meta["version"]))
missing_direct = direct - source_names
if missing_direct:
    raise SystemExit(f"Missing reviewed Cargo source for: {sorted(missing_direct)}")
resolved_names = {(package["name"], package["version"]) for package in metadata["packages"] if package["source"] is not None}
if source_names != resolved_names or not source_names <= locked_names:
    raise SystemExit("Windows Cargo dependencies differ from reviewed source and lock")
for name in ("react", "react-dom", "scheduler"):
    package_file = ROOT / "apps/web/node_modules" / name / "package.json"
    if not package_file.is_file():
        raise SystemExit(f"Missing reviewed frontend package: {name}")
    installed_version = json.loads(package_file.read_text(encoding="utf-8"))["version"]
    lock = json.loads((ROOT / "apps/web/package-lock.json").read_text(encoding="utf-8"))
    locked_version = lock["packages"][f"node_modules/{name}"]["version"]
    if installed_version != locked_version:
        raise SystemExit(f"Frontend package {name} differs from lock: {installed_version} != {locked_version}")

python_distributions = list(importlib.metadata.distributions(path=[
    str(ROOT / "work/tooling/python-packager"), str(Path(sys.prefix) / "Lib/site-packages")
]))
def normalized_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()

installed_python = {normalized_name(dist.metadata["Name"]): dist.version for dist in python_distributions}
for lock_file in (ROOT / "backend/requirements.lock.txt", ROOT / "backend/requirements-packaging.lock.txt"):
    for line in lock_file.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z0-9_.-]+)==([^ ;]+)", line)
        if match and installed_python.get(normalized_name(match[1])) != match[2]:
            raise SystemExit(f"Python package {match[1]} differs from {lock_file.name}: expected {match[2]}")
work_root = (ROOT / "work").resolve()
DEST = (ROOT / "work/third-party").resolve()
if DEST.parent != work_root:
    raise SystemExit("Refusing to replace a third-party directory outside the workspace build folder")
if DEST.exists():
    shutil.rmtree(DEST)
DEST.mkdir(parents=True, exist_ok=True)
rows = []
for manifest in cargo_manifests:
    meta = tomllib.loads(manifest.read_text(encoding="utf-8"))["package"]
    name = f"{meta['name']}-{meta['version']}"
    target = DEST / "rust" / name
    target.mkdir(parents=True, exist_ok=True)
    copied = []
    for file in manifest.parent.iterdir():
        if file.is_file() and file.name.upper().startswith(("LICENSE", "COPYING", "NOTICE", "COPYRIGHT")):
            shutil.copy2(file, target / file.name)
            copied.append(file.name)
    supplemental = ROOT / "licenses/desktop" / name
    if supplemental.is_dir():
        shutil.copytree(supplemental, target, dirs_exist_ok=True)
        copied.extend(file.name for file in supplemental.iterdir() if file.is_file())
    if meta.get("license") == "MPL-2.0":
        # Include the exact unmodified source of file-copyleft dependencies.
        with zipfile.ZipFile(target / "unmodified-source.zip", "w", zipfile.ZIP_DEFLATED, strict_timestamps=False) as archive:
            for file in manifest.parent.rglob("*"):
                if file.is_file():
                    archive.write(file, file.relative_to(manifest.parent))
    rows.append({"ecosystem": "cargo", "name": meta["name"], "version": meta["version"],
                 "license": meta.get("license"), "source": meta.get("repository"), "files": copied})
seen = set()
for dist in python_distributions:
    name = dist.metadata["Name"]
    if name in seen:
        continue
    seen.add(name)
    target = DEST / "python" / f"{name}-{dist.version}"
    copied = []
    for relative in dist.files or []:
        if "__pycache__" in relative.parts or relative.suffix.lower() in {".pyc", ".pyo"}:
            continue
        if any(part.upper().startswith(("LICENSE", "COPYING", "NOTICE", "AUTHORS")) for part in relative.parts):
            source = Path(dist.locate_file(relative))
            if source.is_file():
                destination = target / str(relative).replace("../", "parent/")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination)
                copied.append(str(relative))
    rows.append({"ecosystem": "python", "name": name, "version": dist.version,
                 "license": dist.metadata.get("License-Expression", dist.metadata.get("License")), "files": copied})
    supplemental = ROOT / "licenses/desktop" / f"{name}-{dist.version}"
    if supplemental.is_dir():
        shutil.copytree(supplemental, target, dirs_exist_ok=True)
        copied.extend(file.name for file in supplemental.iterdir() if file.is_file())
for name in ("react", "react-dom", "scheduler"):
    package = ROOT / "apps/web/node_modules" / name
    if not package.exists():
        continue
    meta = json.loads((package / "package.json").read_text())
    target = DEST / "javascript" / name
    target.mkdir(parents=True, exist_ok=True)
    for file in package.glob("LICENSE*"):
        shutil.copy2(file, target / file.name)
    rows.append({"ecosystem": "npm", "name": name, "version": meta["version"], "license": meta.get("license")})
shutil.copytree(ROOT / "licenses", DEST / "project-licenses", dirs_exist_ok=True)
shutil.copy2(Path(sys.base_prefix) / "LICENSE.txt", DEST / "Python-LICENSE.txt")
(DEST / "inventory.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", DEST / "THIRD_PARTY_NOTICES.md")
print(f"Collected {len(rows)} dependency records; MPL release source included.")
print("No top-level license files:", [(r['name'], r['version']) for r in rows if r.get('files') == []])
