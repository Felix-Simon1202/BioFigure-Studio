"""Verify and unpack the pinned official Fiji Windows bundle, without running it.

The archive is downloaded separately into work/fiji-runtime. This script only
accepts its exact SHA-256 and records every extracted file for license review.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "work" / "fiji-runtime"
ARCHIVE = WORK / "fiji-latest-win64-jdk.zip"
TARGET = WORK / "Fiji.app"
EXPECTED_SHA256 = "9201287a86967d1dc93a5a8426ef8c5048c6186c50642c75164fb2c813794c54"
SNAPSHOT = "fiji-latest-win64-jdk-20261013-1517"
SOURCE_URL = "https://downloads.imagej.net/fiji/archive/latest/20261013-1517/fiji-latest-win64-jdk.zip"
MAX_FILES = 15000
MAX_UNPACKED_BYTES = 6 * 1024**3


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_archive(archive: Path) -> dict[str, object]:
    digest = file_sha256(archive)
    if digest != EXPECTED_SHA256:
        raise ValueError(f"Fiji archive SHA-256 mismatch: {digest}")
    with ZipFile(archive) as zipped:
        infos = zipped.infolist()
        if len(infos) > MAX_FILES or sum(info.file_size for info in infos) > MAX_UNPACKED_BYTES:
            raise ValueError("Fiji archive exceeds reviewed extraction limits")
        for info in infos:
            name = PurePosixPath(info.filename.replace("\\", "/"))
            if name.is_absolute() or not name.parts or name.parts[0] != "Fiji" or any(part in ("", ".", "..") for part in name.parts):
                raise ValueError(f"Unsafe archive entry: {info.filename}")
            if (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"Symlink in archive: {info.filename}")
    return {"snapshot_id": SNAPSHOT, "archive": ARCHIVE.name, "archive_sha256": digest,
            "source_url": SOURCE_URL, "files": len(infos),
            "expanded_bytes": sum(info.file_size for info in infos)}


def extract(archive: Path = ARCHIVE) -> dict[str, object]:
    receipt = inspect_archive(archive)
    if TARGET.exists():
        raise FileExistsError(f"Refusing to overwrite existing runtime: {TARGET}")
    staging = WORK / ".fiji-extracting"
    if staging.exists():
        raise FileExistsError(f"Remove or inspect incomplete extraction first: {staging}")
    staging.mkdir(parents=True)
    try:
        with ZipFile(archive) as zipped:
            for info in zipped.infolist():
                if info.is_dir():
                    continue
                relative = PurePosixPath(info.filename.replace("\\", "/"))
                target = staging.joinpath(*relative.parts)
                target.parent.mkdir(parents=True, exist_ok=True)
                with zipped.open(info) as source, target.open("wb") as destination:
                    shutil.copyfileobj(source, destination, length=4 * 1024 * 1024)
        (staging / "Fiji").rename(TARGET)
        staging.rmdir()
    except Exception:
        # Preserve staged files for inspection instead of destroying evidence.
        raise
    files = []
    for path in sorted(TARGET.rglob("*")):
        if path.is_file():
            files.append({"path": path.relative_to(TARGET).as_posix(), "bytes": path.stat().st_size,
                          "sha256": file_sha256(path)})
    receipt["components"] = files
    (WORK / "runtime-receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return receipt


if __name__ == "__main__":
    try:
        result = extract()
        print(json.dumps({key: value for key, value in result.items() if key != "components"}, indent=2))
    except Exception as error:
        print(f"Fiji preparation failed: {error}", file=sys.stderr)
        raise SystemExit(1)
