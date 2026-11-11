"""Lossless JSON measurement records and a one-row numeric CSV summary."""

import csv
from io import StringIO
import json


def measurement_record(snapshot: dict) -> dict:
    result = snapshot["result"]
    return {"schema_version": "1.0", "operation": "measure_selection", "job_id": snapshot["id"],
            "created_at_unix": snapshot["created_at"], "finished_at_unix": snapshot["finished_at"],
            "source": result["source"], "selection": snapshot["selection"],
            "result": {key: value for key, value in result.items() if key not in ("source", "selection")}}


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"))


def _csv_text(value: str) -> str:
    # A filename is data, even if it begins with a spreadsheet formula marker.
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def measurement_json(record: dict) -> bytes:
    return (_json(record) + "\n").encode("utf-8")


def measurement_csv(record: dict) -> bytes:
    source, selection, result = record["source"], record["selection"], record["result"]
    analyzer = result.get("imagej1_analyzer", {})
    row = {"schema_version": record["schema_version"], "job_id": record["job_id"],
           "source_name": source["original_name"], "source_sha256": source["sha256"],
           "source_bytes": source["bytes"], "pixel_type": result.get("pixel_type", ""),
           "bit_depth": result.get("bit_depth", ""),
           **{key.lower() + "_index": selection["indices"].get(key, "") for key in ("C", "Z", "T")},
           "roi_kind": selection["roi"]["kind"], "roi_json": _json(selection["roi"]),
           "source_axes_json": _json(selection["source_axes"]),
           "extra_measurements_json": _json(selection["extra_measurements"]),
           "candidate_pixels": selection["sample_count"],
           **{key: result.get(key, "") for key in ("sample_count", "sum", "mean", "min", "max")},
           "area": analyzer.get("area", ""), "area_unit": analyzer.get("area_unit", ""),
           **{"imagej1_" + key: analyzer.get(key, "") for key in ("mean", "min", "max")},
           **{key: analyzer.get(key, "") for key in ("std_dev", "median", "mode", "integrated_density", "raw_integrated_density")},
           "runtime_archive_sha256": result["execution"]["runtime_archive_sha256"]}
    with StringIO(newline="") as output:
        writer = csv.DictWriter(output, fieldnames=list(row))
        writer.writeheader()
        writer.writerow({key: _csv_text(value) if isinstance(value, str) else value for key, value in row.items()})
        return output.getvalue().encode("utf-8-sig")
