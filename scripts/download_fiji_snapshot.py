"""Resume the pinned Fiji archive with verified ranged official-mirror reads.

This only downloads bytes. `prepare_fiji_runtime.py` must verify the official
SHA-256 before extraction, and component review precedes execution.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
from pathlib import Path
import time
from urllib.request import Request, urlopen

from prepare_fiji_runtime import ARCHIVE, EXPECTED_SHA256


EXPECTED_BYTES = 705125914
CHUNK = 16 * 1024 * 1024
SOURCES = (
    "https://downloads.imagej.net/fiji/archive/latest/20261013-1517/fiji-latest-win64-jdk.zip",
    "https://downloads.micron.ox.ac.uk/fiji_update/mirrors/fiji-latest/fiji-latest-win64-jdk.zip",
    "https://mirrors.pasteur.fr/fiji/downloads/latest/fiji-latest-win64-jdk.zip",
)
PARTS = ARCHIVE.parent / ".parts"


def download_part(index: int, start: int, end: int) -> Path:
    target = PARTS / f"{index:04d}-{start}-{end}.bin"
    if target.exists() and target.stat().st_size == end - start + 1:
        return target
    for attempt in range(8):
        source = SOURCES[(index + attempt) % len(SOURCES)]
        request = Request(source, headers={"Range": f"bytes={start}-{end}", "User-Agent": "BioFigure-Fiji-Audit/1.0"})
        try:
            with urlopen(request, timeout=120) as response:
                content_range = response.headers.get("Content-Range", "")
                if response.status != 206 or content_range != f"bytes {start}-{end}/{EXPECTED_BYTES}":
                    raise ValueError(f"Unexpected HTTP range: {response.status} {content_range}")
                staging = target.with_suffix(".tmp")
                with staging.open("wb") as output:
                    while data := response.read(1024 * 1024):
                        output.write(data)
                if staging.stat().st_size != end - start + 1:
                    raise ValueError("Short ranged response")
                staging.replace(target)
                return target
        except Exception as error:
            print(f"Part {index}, attempt {attempt + 1}: {type(error).__name__}: {error}", flush=True)
            time.sleep(min(attempt + 1, 5))
    raise RuntimeError(f"Cannot download part {index}")


def main() -> None:
    prefix_size = ARCHIVE.stat().st_size if ARCHIVE.exists() else 0
    if prefix_size >= EXPECTED_BYTES:
        raise ValueError("Existing file is complete or oversized; verify it directly")
    PARTS.mkdir(parents=True, exist_ok=True)
    ranges = [(index, start, min(start + CHUNK, EXPECTED_BYTES) - 1)
              for index, start in enumerate(range(prefix_size, EXPECTED_BYTES, CHUNK))]
    print(f"Resuming {prefix_size}/{EXPECTED_BYTES} bytes in {len(ranges)} parts", flush=True)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(download_part, *entry): entry for entry in ranges}
        for future in as_completed(futures):
            entry = futures[future]
            future.result()
            print(f"Part {entry[0] + 1}/{len(ranges)} complete", flush=True)
    digest = hashlib.sha256()
    with ARCHIVE.open("ab") as output:
        for index, start, end in ranges:
            part = PARTS / f"{index:04d}-{start}-{end}.bin"
            with part.open("rb") as source:
                while data := source.read(1024 * 1024):
                    output.write(data)
    if ARCHIVE.stat().st_size != EXPECTED_BYTES:
        raise ValueError("Assembled archive has incorrect length")
    with ARCHIVE.open("rb") as source:
        while data := source.read(4 * 1024 * 1024):
            digest.update(data)
    if digest.hexdigest() != EXPECTED_SHA256:
        raise ValueError(f"Assembled SHA-256 mismatch: {digest.hexdigest()}")
    print(f"Official SHA-256 verified: {EXPECTED_SHA256}", flush=True)


if __name__ == "__main__":
    main()
