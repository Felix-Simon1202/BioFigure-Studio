"""Conservative free-space preflight, grouped by filesystem volume."""

from pathlib import Path
import shutil


DISK_HEADROOM_BYTES = 64 * 1024 * 1024


def require_disk_space(writes: list[tuple[Path, int]]) -> None:
    volumes = {}
    for path, size in writes:
        if size < 0:
            raise ValueError("Invalid disk-space budget")
        existing = path.resolve()
        while not existing.exists():
            existing = existing.parent
        device = existing.stat().st_dev
        previous = volumes.get(device)
        volumes[device] = (existing, size + (previous[1] if previous else 0))
    for path, size in volumes.values():
        if shutil.disk_usage(path).free < size + DISK_HEADROOM_BYTES:
            raise ValueError("本机磁盘可用空间不足，无法安全完成图像项目；请先释放空间。")
