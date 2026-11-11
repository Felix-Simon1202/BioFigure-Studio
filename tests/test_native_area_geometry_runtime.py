"""Opt-in fixed Fiji comparison for native area ROI types; synthetic TIFF only."""

from __future__ import annotations

import json
from hashlib import sha256
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Event
import time
import unittest

from backend.image.assets import ImageAsset
from backend.image.native_area_geometry import run_native_area_geometry_measure
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get("BFS_TEST_FIJI_RUNTIME", ""))
SOURCE = Path(os.environ.get("BFS_TEST_SYNTHETIC_TIFF", ""))
SCRIPT = ROOT / "scripts" / "fiji_native_area_geometry.groovy"


def box(kind: str, x: float = 0.5, y: float = 0.5, w: float = 2.5, h: float = 2.5) -> dict:
    return {"version": "1.0", "kind": kind, "x": x, "y": y, "width": w, "height": h}


CASES = [
    (box("rectangle"), "ij.gui.Roi", 0),
    (box("oval"), "ij.gui.OvalRoi", 1),
    ({"version": "1.0", "kind": "polygon", "points":
      [{"x": 0.5, "y": 0.5}, {"x": 3.5, "y": 0.5}, {"x": 1.5, "y": 3.5}]}, "ij.gui.PolygonRoi", 2),
    ({"version": "1.0", "kind": "freehand", "points":
      [{"x": 0.5, "y": 0.5}, {"x": 3.5, "y": 0.5}, {"x": 1.5, "y": 3.5}]}, "ij.gui.PolygonRoi", 3),
    ({"version": "1.0", "kind": "traced", "points":
      [{"x": 0, "y": 0}, {"x": 3, "y": 0}, {"x": 1, "y": 3}]}, "ij.gui.PolygonRoi", 4),
    ({"version": "1.0", "kind": "spline_polygon", "evaluation_points": 32, "points":
      [{"x": 1, "y": 1}, {"x": 3, "y": 1}, {"x": 2, "y": 2.5}]}, "ij.gui.PolygonRoi", 2),
    ({"version": "1.0", "kind": "rotated_rectangle", "x1": 1, "y1": 1,
      "x2": 3, "y2": 2, "rect_width": 1}, "ij.gui.RotatedRectRoi", 2),
    ({"version": "1.0", "kind": "rotated_ellipse", "x1": 1, "y1": 1,
      "x2": 3, "y2": 2, "aspect_ratio": 0.5}, "ij.gui.EllipseRoi", 3),
    ({"version": "1.0", "kind": "shape", "operation": "subtract",
      "operands": [box("rectangle", 0, 0, 4, 4), box("oval", 1, 1, 2, 2)]},
     "ij.gui.ShapeRoi", 9),
    *[({"version": "1.0", "kind": "shape", "operation": operation,
        "operands": [box("rectangle", 0, 0, 3, 3), box("rectangle", 2, 0, 3, 3)]},
       "ij.gui.ShapeRoi", 9) for operation in ("union", "intersection", "xor")],
]


@unittest.skipUnless(RUNTIME.is_dir() and SOURCE.is_file(), "explicit fixed Fiji runtime and synthetic TIFF required")
class NativeAreaRuntime(unittest.TestCase):
    def test_native_geometry_and_measure(self):
        asset = ImageAsset(id="synthetic", name="synthetic-16bit.tif", bytes=SOURCE.stat().st_size,
                           sha256=sha256(SOURCE.read_bytes()).hexdigest(), path=SOURCE,
                           metadata={"axes": [{"name": "X", "length": 5},
                                               {"name": "Y", "length": 4}]})
        for roi, class_name, type_code in CASES:
            if os.environ.get("BFS_TEST_AREA_KIND") and roi["kind"] != os.environ["BFS_TEST_AREA_KIND"]:
                continue
            with self.subTest(kind=roi["kind"]), tempfile.TemporaryDirectory() as folder:
                result = Path(folder) / "result.json"
                request = Path(folder) / "request.json"
                def runner(asset, job_id, cancel, axes, plane, checked_roi, settings, bits, redirect):
                    request.write_text(json.dumps({
                        "input_path": str(asset.path), "output_path": str(result),
                        "source_sha256": asset.sha256, "source_axes": axes,
                        "current_plane": plane, "roi": checked_roi, "settings": settings,
                        "measurement_bits": bits, "redirect": redirect,
                    }), encoding="utf-8")
                    env = {**os.environ, "BFS_FIJI_JOB_JSON": str(request)}
                    log = Path(folder) / "engine.log"
                    with log.open("wb") as output:
                        process = subprocess.Popen([str(RUNTIME / "fiji-windows-x64.exe"), "--mem=2g",
                                                    "-Dimagej.updater.disableAutocheck=true", "--", "--headless",
                                                    "--run", str(SCRIPT)], cwd=ROOT, env=env,
                                                   stdout=output, stderr=subprocess.STDOUT)
                        deadline = time.monotonic() + 90
                        while time.monotonic() < deadline and not result.is_file() and process.poll() is None:
                            time.sleep(0.2)
                        if process.poll() is None:
                            process.terminate()
                            try:
                                process.wait(timeout=5)
                            except subprocess.TimeoutExpired:
                                process.kill()
                    self.assertTrue(result.is_file(), log.read_text(errors="replace")[-1000:])
                    data = json.loads(result.read_text(encoding="utf-8"))
                    self.assertTrue(data["ok"], (data, log.read_text(errors="replace")[-1000:]))
                    return data

                data = run_native_area_geometry_measure(
                    asset, {}, roi,
                    {"measurements": ["area", "mean", "add_to_overlay"],
                     "decimal_places": 2, "threshold": None},
                    None, None, Event(), runner)
                self.assertEqual(data["native_roi"]["class_name"], class_name)
                self.assertEqual(data["native_roi"]["type_code"], type_code)
                self.assertEqual(data["measurement_bits"], 1 | 2 | 4194304)
                self.assertEqual(data["row_count"], 1)
                self.assertEqual(data["overlay_count_before"], 0)
                self.assertEqual(data["overlay_count"], 1)
                self.assertIn("Area", data["row"])
                self.assertIn("Mean", data["row"])
                if roi["kind"] == "spline_polygon":
                    self.assertTrue(data["native_roi"]["spline_fit"])
                    self.assertEqual(len(data["native_roi"]["float_outline"]), 32)
                if roi["kind"] in {"rotated_rectangle", "rotated_ellipse"}:
                    self.assertTrue(data["native_roi"]["subpixel"])
                    self.assertEqual(len(data["native_roi"]["native_params"]), 5)
                if roi["kind"] == "shape":
                    self.assertTrue(data["native_roi"]["shape_path"])
                    if roi["operation"] in {"union", "intersection", "xor"}:
                        self.assertEqual(data["row"]["Area"], {
                            "union": 15, "intersection": 3, "xor": 12,
                        }[roi["operation"]])
                if roi["kind"] == "rectangle":
                    target_path = Path(folder) / "target-2000.tif"
                    Image.new("I;16", (5, 4), 2000).save(target_path)
                    target = ImageAsset(id="target", name=target_path.name,
                                        bytes=target_path.stat().st_size,
                                        sha256=sha256(target_path.read_bytes()).hexdigest(),
                                        path=target_path, metadata=asset.metadata)
                    result.unlink()
                    redirected = run_native_area_geometry_measure(
                        asset, {}, roi,
                        {"measurements": ["area", "mean", "limit_to_threshold", "add_to_overlay"],
                         "decimal_places": 2, "threshold": {"min": 1999, "max": 2001}},
                        target, {}, Event(), runner)
                    self.assertEqual(redirected["redirect_sha256"], target.sha256)
                    self.assertEqual(redirected["row"]["Mean"], 2000)
                    self.assertEqual(redirected["measurement_bits"], 1 | 2 | 256 | 4194304)


if __name__ == "__main__":
    unittest.main()
