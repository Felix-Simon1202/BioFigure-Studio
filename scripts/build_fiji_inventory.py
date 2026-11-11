"""Build a conservative Fiji discovery catalog from an audited local snapshot.

The catalog is deliberately not an execution allowlist. Static declarations and
runtime enumeration can overlap; they remain separate evidence until reviewed.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from zipfile import BadZipFile, ZipFile


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "work" / "fiji-runtime" / "Fiji.app"
RUNTIME_COMMANDS = ROOT / "work" / "fiji-runtime" / "runtime-commands.json"
OUTPUT = ROOT / "docs" / "FIJI_COMMAND_INVENTORY.json"
SNAPSHOT = "fiji-latest-win64-jdk-20261013-1517"
CONFIG_RE = re.compile(r'^\s*([^,]+),\s*"([^"]+)"\s*,\s*(.+?)\s*$')
PROPS_RE = re.compile(r'^([A-Za-z]+\d+)=(.+)$')
MENU_COMMENT_RE = re.compile(r'^#\s*Plugins installed in the (.+?) (?:sub)?menu\s*$')
SCRIPT_SUFFIXES = {".ijm", ".groovy", ".py", ".js", ".bsh", ".clj", ".rb", ".scala"}


def category(menu: str, label: str) -> str:
    value = (menu + " " + label).lower()
    if any(term in value for term in ("stitch", "mosaic", "registration", "register", "align", "montage")):
        return "拼版、拼接与配准"
    if any(term in value for term in ("trackmate", "tracking", "time series", "timelapse", "time-lapse", "kymograph")):
        return "时间与追踪"
    if any(term in value for term in ("3d", "3-d", "volume", "orthogonal", "z project", "3d viewer")):
        return "三维与体数据"
    if any(term in value for term in ("measure", "analy", "segment", "threshold", "particle", "skeleton", "coloc", "count", "watershed")):
        return "二维测量与分割"
    if any(term in value for term in ("macro", "script", "batch", "process folder")):
        return "自动化与任务"
    if any(term in value for term in ("save", "export", "print", "scale bar")):
        return "导出与核验"
    if any(term in value for term in ("open", "import", "bio-format", "roi manager", "view", "browse")):
        return "导入与浏览"
    if any(term in value for term in ("adjust", "channel", "lut", "filter", "color", "brightness", "contrast", "process>")):
        return "调整与通道"
    if menu.startswith(("Help", "Plugins>Utilities", "Edit>Options", "Plugins>Update")):
        return "组件与环境"
    return "待归类"


def item(kind: str, source: str, key: str, label: str, menu: str, parameters: list[dict] | None = None) -> dict:
    token = hashlib.sha256(f"{kind}\0{source}\0{key}\0{menu}\0{label}".encode()).hexdigest()[:20]
    return {
        "id": f"{kind}:{token}", "label": label, "menu_path": menu,
        "category": category(menu, label), "kind": kind, "source": source,
        "original_identifier": key, "parameters": parameters or [],
        "status": {"discovered": True, "source_reviewed": False,
                   "runtime_verified": False, "ui_adapted": False, "parity_verified": False},
    }


def build() -> dict:
    if not RUNTIME.is_dir():
        raise FileNotFoundError("Pinned Fiji runtime has not been extracted and audited")
    items = []
    warnings = []
    for jar in sorted(RUNTIME.rglob("*.jar")):
        relative = jar.relative_to(RUNTIME).as_posix()
        try:
            with ZipFile(jar) as archive:
                for name in archive.namelist():
                    if Path(name).name != "plugins.config":
                        continue
                    content = archive.read(name).decode("utf-8", errors="replace")
                    for line in content.splitlines():
                        if line.lstrip().startswith("#"):
                            continue
                        match = CONFIG_RE.match(line)
                        if match:
                            menu, label, implementation = match.groups()
                            items.append(item("imagej1_declared", relative + "!" + name,
                                              implementation, label, menu + ">" + label))
        except (BadZipFile, OSError) as error:
            warnings.append({"source": relative, "error": type(error).__name__})

    for jar in sorted((RUNTIME / "jars").glob("ij-*.jar")):
        with ZipFile(jar) as archive:
            if "IJ_Props.txt" not in archive.namelist():
                continue
            menu = ""
            for line in archive.read("IJ_Props.txt").decode("utf-8", errors="replace").splitlines():
                heading = MENU_COMMENT_RE.match(line)
                if heading:
                    menu = heading.group(1).replace("/", ">")
                    continue
                if "right-click popup menu" in line.lower():
                    menu = "Image popup"
                    continue
                match = PROPS_RE.match(line)
                if not match or not menu:
                    continue
                property_key, definition = match.groups()
                if definition == "-":
                    continue
                if definition.startswith('"') and '",' in definition:
                    label, implementation = definition[1:].split('",', 1)
                else:
                    label, implementation = definition, ""
                items.append(item("imagej1_core_declared", jar.relative_to(RUNTIME).as_posix() + "!IJ_Props.txt",
                                  property_key + ":" + implementation, label, menu + ">" + label))

    for folder in (RUNTIME / "scripts", RUNTIME / "macros", RUNTIME / "plugins"):
        if not folder.exists():
            continue
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SCRIPT_SUFFIXES:
                continue
            relative = path.relative_to(RUNTIME).as_posix()
            items.append(item("script_or_macro", relative, relative, path.stem,
                              relative.replace("/", ">")))

    if RUNTIME_COMMANDS.is_file():
        runtime = json.loads(RUNTIME_COMMANDS.read_text(encoding="utf-8"))
        for command in runtime.get("scijava_commands", []):
            identifier = str(command.get("identifier") or command.get("class_name") or "")
            if not identifier:
                continue
            label = str(command.get("title") or identifier)
            menu = str(command.get("menu_path") or "")
            if menu.startswith("[") and menu.endswith("]"):
                menu = menu[1:-1].replace(", ", ">")
            items.append(item("scijava_runtime", str(command.get("class_name") or identifier),
                              identifier, label, menu, command.get("inputs") or []))
        for command in runtime.get("imagej1_commands", []):
            label = str(command.get("label") or "")
            implementation = str(command.get("implementation") or "")
            if label and implementation:
                items.append(item("imagej1_runtime", implementation, implementation, label, label))
    else:
        warnings.append({"source": "runtime-commands.json", "error": "runtime enumeration pending"})

    # Identical declarations may appear in multiple JAR resources. Preserve only
    # the first identical evidence record; cross-kind observations remain separate.
    deduped = {entry["id"]: entry for entry in items}
    return {"schema_version": "1.0", "snapshot_id": SNAPSHOT,
            "inventory_state": "runtime_enumerated" if RUNTIME_COMMANDS.is_file() else "static_only",
            "warnings": warnings, "items": sorted(deduped.values(), key=lambda value: (value["category"], value["menu_path"], value["id"]))}


if __name__ == "__main__":
    catalog = build()
    OUTPUT.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Discovered {len(catalog['items'])} records; state={catalog['inventory_state']}; warnings={len(catalog['warnings'])}")
