"""Extract version/license evidence from the pinned Fiji files, without execution.

POM license declarations and embedded notice names are evidence to review, not
legal clearance. The full byte-level receipt remains in ignored local work/.
"""

import json
from pathlib import Path
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from prepare_fiji_runtime import ROOT, TARGET, WORK


OUT = ROOT / "docs" / "FIJI_COMPONENT_EVIDENCE.json"
RECEIPT = WORK / "runtime-receipt.json"
PACKAGE_SUFFIXES = {".jar", ".dll", ".exe", ".so", ".dylib", ".pb", ".onnx", ".h5", ".model"}


def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def child_text(element: ET.Element, name: str) -> str | None:
    for child in element:
        if local_name(child.tag) == name:
            return child.text.strip() if child.text else None
    return None


def pom_evidence(data: bytes) -> dict[str, object]:
    root = ET.fromstring(data)
    licenses = []
    for element in root.iter():
        if local_name(element.tag) == "license":
            entry = {key: child_text(element, key) for key in ("name", "url", "distribution")}
            if any(entry.values()):
                licenses.append(entry)
    return {"group_id": child_text(root, "groupId"), "artifact_id": child_text(root, "artifactId"),
            "version": child_text(root, "version"), "licenses": licenses[:10]}


def inspect_jar(path: Path) -> dict[str, object]:
    poms = []
    notice_entries = []
    with ZipFile(path) as archive:
        for name in archive.namelist():
            base = Path(name).name.lower()
            if name.startswith("META-INF/maven/") and base == "pom.xml":
                try:
                    poms.append({"path": name, **pom_evidence(archive.read(name))})
                except (ET.ParseError, UnicodeError):
                    poms.append({"path": name, "parse_error": True})
            elif base.startswith(("license", "licence", "notice", "copying")):
                notice_entries.append(name)
    return {"embedded_poms": poms[:20], "notice_entries": notice_entries[:100],
            "embedded_pom_count": len(poms), "notice_count": len(notice_entries)}


def build() -> dict[str, object]:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    components = []
    warnings = []
    for entry in receipt["components"]:
        relative = entry["path"]
        path = TARGET / relative
        suffix = path.suffix.lower()
        if suffix not in PACKAGE_SUFFIXES:
            continue
        component = {"path": relative, "bytes": entry["bytes"], "sha256": entry["sha256"],
                     "kind": suffix.lstrip("."), "license_review": "pending"}
        if suffix == ".jar":
            try:
                component.update(inspect_jar(path))
            except (BadZipFile, OSError) as error:
                warnings.append({"path": relative, "error": type(error).__name__})
        components.append(component)
    releases = []
    for path in sorted(TARGET.rglob("release")):
        if "java" in path.parts and path.is_file():
            releases.append({"path": path.relative_to(TARGET).as_posix(),
                             "text": path.read_text(encoding="utf-8", errors="replace")[:12000]})
    return {"schema_version": "1.0", "snapshot_id": receipt["snapshot_id"],
            "archive_sha256": receipt["archive_sha256"], "component_count": len(components),
            "components": components, "java_release_files": releases, "warnings": warnings,
            "scope_note": "Evidence only; all license reviews remain pending until individually checked."}


if __name__ == "__main__":
    result = build()
    OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Component evidence: {result['component_count']} packages, {len(result['warnings'])} warnings")
