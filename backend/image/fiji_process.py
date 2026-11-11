"""One-off, bounded Fiji process for the first reviewed metadata operation."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
from threading import Event, Lock
import time
from typing import Any

from backend.image.assets import ImageAsset, ImageAssetImportCancelled, verify_asset_bytes
from backend.image.selection import ImageSelection
from scripts.prepare_fiji_runtime import EXPECTED_SHA256
from backend.image.paths import image_work_dir


ROOT = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2]


def _runtime_path() -> Path:
    override = os.environ.get("BFS_FIJI_RUNTIME")
    if override:
        return Path(override).resolve()
    if not getattr(sys, "frozen", False):
        return ROOT / "work" / "fiji-runtime" / "Fiji.app"
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("Windows 用户数据目录不可用。")
    user_data = Path(local) / "BioFigureStudioData"
    config = user_data / "fiji-runtime.json"
    if config.is_file():
        try:
            payload = json.loads(config.read_text(encoding="utf-8"))
            if (set(payload) != {"snapshot_id", "archive_sha256", "runtime_path"}
                    or payload["snapshot_id"] != "fiji-latest-win64-jdk-20261013-1517"
                    or payload["archive_sha256"] != EXPECTED_SHA256
                    or not isinstance(payload["runtime_path"], str)
                    or not Path(payload["runtime_path"]).is_absolute()):
                raise ValueError
            return Path(payload["runtime_path"]).resolve()
        except (OSError, ValueError, TypeError):
            pass
    return user_data / "fiji-runtime" / "Fiji.app"


RUNTIME = _runtime_path()
RECEIPT = RUNTIME.parent / "runtime-receipt.json"
JOBS_ROOT = image_work_dir("image-jobs")
SCRIPT = ROOT / "scripts" / "fiji_inspect_asset.groovy"
INVERT_SCRIPT = ROOT / "scripts" / "fiji_invert_8bit.groovy"
MEASURE_SCRIPT = ROOT / "scripts" / "fiji_measure_selection.groovy"
ROI_COLLECTION_SCRIPT = ROOT / "scripts" / "fiji_verify_roi_collection.groovy"
ROI_ZIP_SCRIPT = ROOT / "scripts" / "fiji_roi_zip.groovy"
ROI_BATCH_MEASURE_SCRIPT = ROOT / "scripts" / "fiji_measure_roi_collection.groovy"
ROI_MULTI_MEASURE_SCRIPT = ROOT / "scripts" / "fiji_native_multi_measure.groovy"
SET_MEASUREMENTS_SCRIPT = ROOT / "scripts" / "fiji_set_measurements.groovy"
NON_AREA_MEASURE_SCRIPT = ROOT / "scripts" / "fiji_non_area_measure.groovy"
NATIVE_AREA_GEOMETRY_SCRIPT = ROOT / "scripts" / "fiji_native_area_geometry.groovy"
NATIVE_ROI_EXCHANGE_SCRIPT = ROOT / "scripts" / "fiji_native_roi_exchange.groovy"
SCRIPT_REPORT_LIMITS = {
    SCRIPT: 65536, INVERT_SCRIPT: 65536, MEASURE_SCRIPT: 65536,
    ROI_COLLECTION_SCRIPT: 65536, ROI_ZIP_SCRIPT: 1048576,
    ROI_BATCH_MEASURE_SCRIPT: 262144, ROI_MULTI_MEASURE_SCRIPT: 4 * 1048576,
    SET_MEASUREMENTS_SCRIPT: 65536, NON_AREA_MEASURE_SCRIPT: 262144,
    NATIVE_AREA_GEOMETRY_SCRIPT: 1048576,
    NATIVE_ROI_EXCHANGE_SCRIPT: 2 * 1048576,
}
TIMEOUT_SECONDS = 180
_verify_lock = Lock()
_verified_stats: tuple[tuple[str, int, int], ...] | None = None


class FijiUnavailable(RuntimeError):
    pass


class FijiCancelled(RuntimeError):
    pass


def _digest(path: Path) -> str:
    value = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def verify_runtime() -> Path:
    """Reject missing or modified files from the official pinned extraction."""
    global _verified_stats
    launcher = RUNTIME / "fiji-windows-x64.exe"
    if not RECEIPT.is_file() or not launcher.is_file():
        raise FijiUnavailable("Fiji 固定运行时尚未准备。")
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    if receipt.get("archive_sha256") != EXPECTED_SHA256:
        raise FijiUnavailable("Fiji 发行包摘要不匹配。")
    entries = receipt.get("components", [])
    if not entries:
        raise FijiUnavailable("Fiji 文件清单缺失。")
    root = RUNTIME.resolve()
    paths: list[Path] = []
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise FijiUnavailable("Fiji 文件清单格式无效。")
        relative = Path(entry["path"])
        raw_path = RUNTIME / relative
        candidate = raw_path.resolve()
        if (relative.is_absolute() or ".." in relative.parts or raw_path.is_symlink()
                or candidate == root or root not in candidate.parents):
            raise FijiUnavailable("Fiji 文件清单包含不受控路径。")
        paths.append(candidate)
    expected = {path.relative_to(root) for path in paths}
    for folder_name in ("jars", "plugins", "scripts", "macros", "java", "lib"):
        folder = RUNTIME / folder_name
        if not folder.is_dir() or folder.is_symlink():
            raise FijiUnavailable("Fiji 代码目录缺失或被替换。")
        for path in folder.rglob("*"):
            if path.is_symlink() or (path.is_file() and path.relative_to(RUNTIME) not in expected):
                raise FijiUnavailable("Fiji 运行时发现清单之外的可执行组件。")
    with _verify_lock:
        try:
            stats = tuple((entry["path"], path.stat().st_size, path.stat().st_mtime_ns)
                          for entry, path in zip(entries, paths))
        except OSError as error:
            raise FijiUnavailable("Fiji 运行时文件缺失。") from error
        if any(size != entry["bytes"] for (_, size, _), entry in zip(stats, entries)):
            raise FijiUnavailable("Fiji 运行时文件大小与固定清单不符。")
        if _verified_stats != stats:
            for entry, path in zip(entries, paths):
                if _digest(path) != entry["sha256"]:
                    raise FijiUnavailable("Fiji 运行时文件摘要与固定清单不符。")
            _verified_stats = stats
    return launcher


def _run_script(asset: ImageAsset, job_id: str, cancel: Event, script: Path,
                extra_request: dict[str, Any] | None = None) -> dict[str, Any]:
    if script not in SCRIPT_REPORT_LIMITS or not script.is_file():
        raise FijiUnavailable("Fiji 任务脚本未通过固定白名单。")
    max_report = SCRIPT_REPORT_LIMITS[script]
    launcher = verify_runtime()
    try:
        verify_asset_bytes(asset, cancel)
    except ImageAssetImportCancelled as error:
        raise FijiCancelled() from error
    except ValueError as error:
        raise FijiUnavailable("图像源文件与导入摘要不符。") from error
    if cancel.is_set():
        raise FijiCancelled()
    if not job_id.isalnum() or len(job_id) != 32:
        raise ValueError("Invalid generated job ID")
    JOBS_ROOT.mkdir(parents=True, exist_ok=True)
    directory = JOBS_ROOT / job_id
    directory.mkdir(exist_ok=False)
    request_file = directory / "request.json"
    result_file = directory / "result.json"
    log_file = directory / "engine.log"
    pid_file = directory / "engine.pid"
    request_file.write_text(json.dumps({"input_path": str(asset.path), "output_path": str(result_file),
                                        **(extra_request or {})}), encoding="utf-8")
    command = [str(launcher), "--mem=2g", "-Dimagej.updater.disableAutocheck=true", "--",
               "--headless", "--run", str(script)]
    # Avoid sending arbitrary parent environment values into a plugin process.
    env = {key: value for key, value in os.environ.items()
           if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "PATH"}}
    env["BFS_FIJI_JOB_JSON"] = str(request_file)
    process: subprocess.Popen[bytes] | None = None
    try:
        with log_file.open("wb") as log:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            pid_file.write_text(str(process.pid), encoding="ascii")
            deadline = time.monotonic() + TIMEOUT_SECONDS
            while time.monotonic() < deadline:
                if cancel.is_set():
                    raise FijiCancelled()
                if result_file.is_file() and result_file.stat().st_size > max_report:
                    raise ValueError("Fiji 结果报告超过当前操作的容量上限。")
                if result_file.is_file() and result_file.stat().st_size <= max_report:
                    try:
                        payload = json.loads(result_file.read_text(encoding="utf-8"))
                    except (json.JSONDecodeError, UnicodeDecodeError, OSError):
                        pass
                    else:
                        if not payload.get("ok"):
                            raise ValueError("Fiji 无法完成受限图像操作；请检查格式与图像类型。")
                        return payload
                if process.poll() is not None:
                    raise ValueError("Fiji 进程在返回任务结果前退出。")
                time.sleep(0.1)
            raise TimeoutError("Fiji 图像任务超过 180 秒时限。")
    finally:
        if process is not None and process.poll() is None:
            if os.name == "nt":
                try:
                    subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   check=False, timeout=10)
                except (OSError, subprocess.TimeoutExpired):
                    pass
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        for path in (request_file, result_file, log_file, pid_file):
            path.unlink(missing_ok=True)
        directory.rmdir()


def inspect_asset(asset: ImageAsset, job_id: str, cancel: Event) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, SCRIPT)


def invert_8bit_asset(asset: ImageAsset, job_id: str, cancel: Event, output: Path) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, INVERT_SCRIPT,
                       {"image_output_path": str(output)})


def measure_selection(asset: ImageAsset, job_id: str, cancel: Event,
                      selection: ImageSelection) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, MEASURE_SCRIPT,
                       {"selection": selection.public()})


def verify_roi_collection_native(asset: ImageAsset, job_id: str, cancel: Event,
                                 collection: dict[str, Any]) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, ROI_COLLECTION_SCRIPT,
                       {"collection": collection})


def run_roi_zip(asset: ImageAsset, job_id: str, cancel: Event,
                operation: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, ROI_ZIP_SCRIPT,
                       {"operation": operation, **payload})


def measure_roi_collection(asset: ImageAsset, job_id: str, cancel: Event,
                           collection: dict[str, Any], extras: list[str]) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, ROI_BATCH_MEASURE_SCRIPT,
                       {"collection": collection, "extra_measurements": extras})


def native_multi_measure(asset: ImageAsset, job_id: str, cancel: Event,
                         collection: dict[str, Any], current_plane: dict[str, int],
                         runs: list[dict[str, bool]], flags: list[str]) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, ROI_MULTI_MEASURE_SCRIPT,
                       {"collection": collection, "current_plane": current_plane,
                        "runs": runs, "measurement_flags": flags})


def native_set_measurements(asset: ImageAsset, job_id: str, cancel: Event,
                            selection: dict[str, Any], settings: dict[str, Any],
                            redirect: dict[str, Any] | None) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, SET_MEASUREMENTS_SCRIPT,
                       {"selection": selection, "settings": settings, "redirect": redirect,
                        "source_sha256": asset.sha256})


def native_non_area_measure(asset: ImageAsset, job_id: str, cancel: Event,
                            source_axes: list[dict[str, Any]], current_plane: dict[str, int],
                            roi: dict[str, Any], settings: dict[str, Any],
                            redirect: dict[str, Any] | None) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, NON_AREA_MEASURE_SCRIPT,
                       {"source_axes": source_axes, "current_plane": current_plane,
                        "roi": roi, "settings": settings, "redirect": redirect,
                        "source_sha256": asset.sha256})


def native_area_geometry_measure(asset: ImageAsset, job_id: str, cancel: Event,
                                 source_axes: list[dict[str, Any]], current_plane: dict[str, int],
                                 roi: dict[str, Any], settings: dict[str, Any], measurement_bits: int,
                                 redirect: dict[str, Any] | None) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, NATIVE_AREA_GEOMETRY_SCRIPT,
                       {"source_axes": source_axes, "current_plane": current_plane,
                        "roi": roi, "settings": settings, "measurement_bits": measurement_bits,
                        "redirect": redirect, "source_sha256": asset.sha256})


def native_roi_exchange(asset: ImageAsset, job_id: str, cancel: Event,
                        request: dict[str, Any]) -> dict[str, Any]:
    return _run_script(asset, job_id, cancel, NATIVE_ROI_EXCHANGE_SCRIPT, request)
