"""Opt-in RoiEncoder/RoiDecoder and RoiManager ZIP roundtrip on audited Fiji."""

from hashlib import sha256
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import tempfile
from threading import Event
import time
import unittest
from zipfile import ZipFile

from backend.image.assets import ImageAsset
from backend.image.native_roi_exchange import run_roi_exchange
from PIL import Image, TiffImagePlugin


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = Path(os.environ.get("BFS_TEST_FIJI_RUNTIME", ""))
SOURCE = Path(os.environ.get("BFS_TEST_SYNTHETIC_TIFF", ""))
SCRIPT = ROOT / "scripts" / "fiji_native_roi_exchange.groovy"


def points():
    return [{"x": 1.25, "y": 1.25}, {"x": 3.5, "y": 1.25}, {"x": 2.0, "y": 3.0}]


def box(kind, x=0.5, y=0.5, width=2.5, height=2.5):
    return {"version": "1.0", "kind": kind, "x": x, "y": y,
            "width": width, "height": height}


def collection(asset):
    regions = [
        box("rectangle"), box("oval"),
        *[{"version": "1.0", "kind": kind, "points": points()}
          for kind in ("polygon", "freehand")],
        {"version": "1.0", "kind": "traced", "points": [
            {"x": 1, "y": 1}, {"x": 3, "y": 1}, {"x": 2, "y": 3}]},
        {"version": "1.0", "kind": "spline_polygon", "points": points(),
         "evaluation_points": 100},
        {"version": "1.0", "kind": "rotated_rectangle", "x1": 1, "y1": 1,
         "x2": 3, "y2": 2, "rect_width": 1},
        {"version": "1.0", "kind": "rotated_ellipse", "x1": 1, "y1": 1,
         "x2": 3, "y2": 2, "aspect_ratio": 0.5},
        {"version": "1.0", "kind": "shape", "operation": "subtract",
         "operands": [box("rectangle", 0, 0, 4, 4), box("oval", 1, 1, 2, 2)]},
        {"version": "1.0", "kind": "line", "points": [
            {"x": 1.25, "y": 1.5}, {"x": 3.25, "y": 2.5}], "stroke_width": 2.5},
        *[{"version": "1.0", "kind": kind, "points": points(), "stroke_width": 2.5}
          for kind in ("polyline", "freeline")],
        {"version": "1.0", "kind": "angle", "points": points()},
        {"version": "1.0", "kind": "multipoint", "points": [
            {"x": 1.25, "y": 1.5}, {"x": 3.5, "y": 2.5}],
         "point_positions": [0, 0], "point_counters": [1, 2]},
    ]
    source = {"sha256": asset.sha256, "bytes": asset.bytes, "axes": asset.metadata["axes"]}
    return {"version": "2.0", "source": source,
            "items": [{"id": f"{i+1:032x}", "name": f"Synthetic {i+1}",
                       "indices": {}, "roi": roi} for i, roi in enumerate(regions)]}


@unittest.skipUnless(RUNTIME.is_dir() and SOURCE.is_file(), "audited Fiji and synthetic TIFF required")
class NativeRoiExchangeRuntime(unittest.TestCase):
    def test_zip_file_and_known_fidelity_limits(self):
        asset = ImageAsset(id="synthetic", name=SOURCE.name, bytes=SOURCE.stat().st_size,
                           sha256=sha256(SOURCE.read_bytes()).hexdigest(), path=SOURCE,
                           metadata={"axes": [{"name": "X", "length": 5},
                                               {"name": "Y", "length": 4}]})
        with tempfile.TemporaryDirectory() as folder:
            temporary = Path(folder)

            def runner(asset, job_id, cancel, request):
                result = temporary / f"{job_id}.json"
                job = temporary / f"{job_id}-request.json"
                job.write_text(json.dumps({"input_path": str(asset.path),
                                           "output_path": str(result), **request}), encoding="utf-8")
                env = {key: value for key, value in os.environ.items()
                       if key.upper() in {"SYSTEMROOT", "WINDIR", "TEMP", "TMP", "USERPROFILE", "PATH"}}
                env["BFS_FIJI_JOB_JSON"] = str(job)
                log = temporary / f"{job_id}.log"
                with log.open("wb") as output:
                    process = subprocess.Popen([str(RUNTIME / "fiji-windows-x64.exe"), "--mem=2g",
                                                "-Dimagej.updater.disableAutocheck=true", "--",
                                                "--headless", "--run", str(SCRIPT)],
                                               cwd=ROOT, env=env, stdout=output,
                                               stderr=subprocess.STDOUT)
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
                if not data.get("ok"):
                    raise ValueError((data, log.read_text(errors="replace")[-1000:]))
                return data

            original = collection(asset)
            exported = run_roi_exchange(asset, "export_zip", Event(), runner, collection=original)
            self.assertEqual(len(exported["proofs"]), 14)
            self.assertEqual(exported["proofs"][6]["class_name"], "ij.gui.RotatedRectRoi")
            self.assertTrue(exported["proofs"][6]["rotated_header_repaired"])
            imported = run_roi_exchange(asset, "import_zip", Event(), runner,
                                        file_bytes=exported["bytes"])
            self.assertTrue(imported["manifest_matches_source"])
            self.assertEqual([item["roi"]["kind"] for item in imported["collection"]["items"]],
                             [item["roi"]["kind"] if item["roi"]["kind"] != "shape" else "shape_path"
                              for item in original["items"]])
            self.assertEqual(imported["collection"]["items"][-1]["roi"]["point_counters"], [1, 2])
            self.assertEqual([item["name"] for item in imported["collection"]["items"]],
                             [item["name"] for item in original["items"]])
            self.assertEqual(imported["collection"]["items"][5]["roi"]["evaluation_points"], 100)
            self.assertEqual(imported["collection"]["items"][9]["roi"]["stroke_width"], 2.5)
            self.assertEqual(imported["collection"]["items"][6]["roi"]["rect_width"], 1)
            reexported = run_roi_exchange(asset, "export_zip", Event(), runner,
                                          collection=imported["collection"])
            self.assertEqual(len(reexported["proofs"]), 14)
            unbound_stream = BytesIO()
            with ZipFile(BytesIO(exported["bytes"])) as source_zip, ZipFile(unbound_stream, "w") as target_zip:
                for member in source_zip.infolist():
                    if member.filename != "biofigure-source.json":
                        target_zip.writestr(member.filename, source_zip.read(member))
            unbound = run_roi_exchange(asset, "import_zip", Event(), runner,
                                       file_bytes=unbound_stream.getvalue())
            self.assertFalse(unbound["manifest_matches_source"])
            rotated = {**original, "items": [original["items"][6]]}
            single = run_roi_exchange(asset, "export_roi", Event(), runner, collection=rotated)
            self.assertEqual(single["bytes"][6], 7)
            restored = run_roi_exchange(asset, "import_roi", Event(), runner,
                                        file_bytes=single["bytes"])
            self.assertFalse(restored["manifest_matches_source"])
            self.assertEqual(restored["collection"]["items"][0]["roi"]["kind"], "rotated_rectangle")
            legacy = bytearray(single["bytes"])
            legacy[6] = 0
            repaired = run_roi_exchange(asset, "import_roi", Event(), runner,
                                        file_bytes=bytes(legacy))
            self.assertTrue(repaired["proofs"][0]["rotated_header_repaired"])
            unstable = {**original, "items": [{**original["items"][5],
                "roi": {**original["items"][5]["roi"], "evaluation_points": 32}}]}
            with self.assertRaisesRegex(ValueError, "cannot preserve geometry"):
                run_roi_exchange(asset, "export_roi", Event(), runner, collection=unstable)

            stack_path = temporary / "two-z-planes.tif"
            pages = [Image.new("I;16", (5, 4), value) for value in (1000, 2000)]
            info = TiffImagePlugin.ImageFileDirectory_v2()
            info[270] = ("ImageJ=1.54\nimages=2\nslices=2\nhyperstack=true\n"
                         "mode=grayscale\nunit=um\n")
            pages[0].save(stack_path, save_all=True, append_images=pages[1:],
                          tiffinfo=info, compression="tiff_deflate")
            for page in pages:
                page.close()
            stack = ImageAsset(id="stack", name=stack_path.name, bytes=stack_path.stat().st_size,
                               sha256=sha256(stack_path.read_bytes()).hexdigest(), path=stack_path,
                               metadata={"axes": [{"name": "X", "length": 5},
                                                   {"name": "Y", "length": 4},
                                                   {"name": "Z", "length": 2}]})
            positioned = {"version": "2.0", "source": {"sha256": stack.sha256,
                           "bytes": stack.bytes, "axes": stack.metadata["axes"]},
                          "items": [{"id": "f" * 32, "name": "Positioned points", "indices": {"Z": 0},
                                     "roi": {"version": "1.0", "kind": "multipoint", "points": [
                                         {"x": 1.25, "y": 1.5}, {"x": 3.5, "y": 2.5}],
                                         "point_positions": [1, 2], "point_counters": [1, 2]}}]}
            point_file = run_roi_exchange(stack, "export_roi", Event(), runner, collection=positioned)
            point_import = run_roi_exchange(stack, "import_roi", Event(), runner,
                                            file_bytes=point_file["bytes"])
            point_roi = point_import["collection"]["items"][0]["roi"]
            self.assertEqual(point_roi["point_positions"], [1, 2])
            self.assertEqual(point_roi["point_counters"], [1, 2])


if __name__ == "__main__":
    unittest.main()
