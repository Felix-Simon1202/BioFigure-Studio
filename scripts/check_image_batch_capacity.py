"""Opt-in local batch capacity check with independently generated sample bits.

Runs reviewed project code only, writes anonymous test artifacts to a new
directory, and measures this verifier process rather than the whole product.
"""

import argparse
import ctypes
from datetime import datetime, timezone
from ctypes import wintypes
import gc
from hashlib import sha256
import importlib
from io import BytesIO
import json
from pathlib import Path
import sys
from threading import Event
from time import monotonic
from zipfile import ZipFile

import numpy as np
from PIL import Image


def memory_bytes() -> dict:
    class Counters(ctypes.Structure):
        _fields_ = [("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD)] + [
            (name, ctypes.c_size_t) for name in (
                "peak_rss", "rss", "peak_paged_pool", "paged_pool",
                "peak_nonpaged_pool", "nonpaged_pool", "pagefile", "peak_pagefile")]
    counters = Counters()
    counters.cb = ctypes.sizeof(counters)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise ctypes.WinError(ctypes.get_last_error())
    return {"rss": counters.rss, "peak_rss": counters.peak_rss}


def pattern(index: int) -> np.ndarray:
    y, x = np.indices((256, 1024), dtype=np.uint32)
    return np.stack(((x * 13 + index * 3) % 256, (y * 17 + index * 7) % 256,
                     (255 + y * 11 - x * 3 + index) % 256,
                     (x + y * 3 + index) % 256), axis=-1).astype(np.uint8)


def run(implementation: Path, destination: Path) -> dict:
    implementation = implementation.resolve()
    module_file = implementation / "backend" / "image" / "batch.py"
    montage_file = implementation / "backend" / "image" / "montage.py"
    source_hashes = {path.relative_to(implementation).as_posix(): sha256(path.read_bytes()).hexdigest()
                     for path in (module_file, montage_file)}
    sys.path.insert(0, str(implementation))
    batch = importlib.import_module("backend.image.batch")
    if Path(batch.__file__).resolve() != module_file:
        raise ValueError("Another batch module is already imported")
    destination.mkdir(parents=True, exist_ok=False)
    sources = destination / "sources"
    sources.mkdir()
    assets = []
    for index in range(64):
        path = sources / f"synthetic-{index:03d}.tif"
        with Image.fromarray(pattern(index)) as image:
            image.save(path, format="TIFF", compression="raw")
        assets.append(batch.ImageAsset(f"{index:032x}", path.name, path.stat().st_size,
                                       sha256(path.read_bytes()).hexdigest(), path))
    groups = [assets[start:start + 8] for start in range(0, 64, 8)]
    gc.collect()
    before = memory_bytes()
    runs = []
    for cycle in range(2):
        output = destination / f"batch-{cycle + 1}.zip"
        progress = []
        started = monotonic()
        proof = batch.run_grid_batch(groups, 4, 3, output, Event(),
                                     lambda done, total: progress.append([done, total]))
        differences = 0
        with ZipFile(output) as archive:
            assert archive.testzip() is None
            assert len(archive.namelist()) == 9
            manifest = json.loads(archive.read("manifest.json"))
            assert manifest["group_count"] == 8 and manifest["source_count"] == 64
            assert len(manifest["groups"]) == 8
            for group in manifest["groups"]:
                with Image.open(BytesIO(archive.read(group["filename"]))) as saved:
                    assert saved.mode == "RGBA" and saved.size == (4105, 515)
                    pixels = np.array(saved)
                for placement in group["proof"]["placements"]:
                    expected = pattern(int(placement["asset_id"], 16))
                    x, y = placement["x"], placement["y"]
                    region = pixels[y:y + 256, x:x + 1024]
                    assert region.dtype == expected.dtype and region.shape == expected.shape
                    differences += int(np.count_nonzero(region != expected))
                del pixels, expected, region
        assert differences == 0 and progress == [[index, 8] for index in range(1, 9)]
        gc.collect()
        runs.append({"cycle": cycle + 1, "seconds": round(monotonic() - started, 3),
                     "files": 64, "groups": 8, "compared_source_pixels": 64 * 256 * 1024,
                     "different_samples": differences, "zip_bytes": output.stat().st_size,
                     "zip_sha256": proof.output_sha256, "progress": progress,
                     "memory_after": memory_bytes()})
    after_hashes = {name: sha256((implementation / name).read_bytes()).hexdigest() for name in source_hashes}
    if after_hashes != source_hashes:
        raise ValueError("Implementation changed while checking; repeat against a stable snapshot")
    evidence = {"schema_version": "1.0", "date": datetime.now(timezone.utc).date().isoformat(), "implementation_sha256": source_hashes,
                "scope": "Two sequential core batches of 64 generated RGBA sources, not HTTP upload, full Fiji or large-data reliability proof",
                "memory_scope": "Windows current verifier process, including generation and independent ZIP decoding",
                "source_bytes": sum(asset.bytes for asset in assets), "memory_before": before,
                "runs": runs, "all_samples_preserved": True}
    (destination / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    return evidence


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("implementation", type=Path)
    parser.add_argument("destination", type=Path)
    options = parser.parse_args()
    result = run(options.implementation, options.destination)
    for cycle in result["runs"]:
        print(json.dumps(cycle))
