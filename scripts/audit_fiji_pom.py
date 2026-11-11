"""Inventory source declarations without downloading or executing dependencies.

This is deliberately not a Maven resolver or an installed-command inventory.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import xml.etree.ElementTree as ET

NS = {"m": "http://maven.apache.org/POM/4.0.0"}


def inventory(payload: bytes, source_ref: str) -> dict:
    root = ET.fromstring(payload)
    def value(node, tag, default=None):
        text = node.findtext(f"m:{tag}", namespaces=NS)
        return text.strip() if text else default
    declarations = []
    sections = [(None, root)] + [(value(profile, "id"), profile) for profile in root.findall("m:profiles/m:profile", NS)]
    for profile_id, section in sections:
        for dependency in section.findall("m:dependencies/m:dependency", NS):
            declarations.append({
                "group_id": value(dependency, "groupId"),
                "artifact_id": value(dependency, "artifactId"),
                "declared_version": value(dependency, "version"),
                "scope": value(dependency, "scope", "compile"),
                "classifier": value(dependency, "classifier"),
                "optional": value(dependency, "optional", "false") == "true",
                "profile_id": profile_id,
            })
    parent = root.find("m:parent", NS)
    return {
        "schema_version": "1.0",
        "source_repository": "https://github.com/fiji/fiji",
        "source_ref": source_ref,
        "source_file": "pom.xml",
        "source_sha256": sha256(payload).hexdigest(),
        "source_project_version": value(root, "version"),
        "parent": None if parent is None else {tag: value(parent, tag) for tag in ("groupId", "artifactId", "version")},
        "declaration_count": len(declarations),
        "unique_coordinate_count": len({(item["group_id"], item["artifact_id"]) for item in declarations}),
        "runtime_inventory_complete": False,
        "runtime_installed": False,
        "limitations": [
            "Source declarations include inactive Maven profiles and test scope.",
            "Inherited versions and transitive dependencies are unresolved.",
            "One artifact can expose many commands; these counts are not feature counts.",
            "Runtime JARs, scripts, macros, commands and interactive tools must be enumerated separately.",
        ],
        "declarations": declarations,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pom", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--ref", required=True)
    args = parser.parse_args()
    result = inventory(args.pom.read_bytes(), args.ref)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{result['declaration_count']} declarations; {result['unique_coordinate_count']} unique coordinates; runtime inventory incomplete.")


if __name__ == "__main__":
    main()
