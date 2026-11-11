from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.specs import IllustrationSpec


def mechanism_document():
    return {
        "spec_version": "1.2",
        "title": "受控机制图测试",
        "canvas": {"width": 960, "height": 640, "background": "#ffffff", "grid_size": 20, "show_grid": True, "snap_to_grid": True},
        "nodes": [
            {"id": "ligand_1", "component_id": "ligand_generic", "x": 120, "y": 180, "width": 70, "height": 58, "rotation": 0, "z_index": 0, "label": "用户命名配体", "fill": "#bc78a1", "text_color": "#26332f", "scientific_status": "verified", "entity_type": "ligand", "evidence_ids": ["evidence_1"]},
            {"id": "receptor_1", "component_id": "receptor_membrane", "x": 420, "y": 210, "width": 105, "height": 120, "rotation": 0, "z_index": 1, "label": "用户命名受体", "fill": "#79a3a0", "text_color": "#26332f", "scientific_status": "needs_review", "entity_type": "receptor", "evidence_ids": []},
        ],
        "edges": [{"id": "edge_1", "source": {"node_id": "ligand_1", "anchor_id": "right"}, "target": {"node_id": "receptor_1", "anchor_id": "left"}, "relation": "binding", "routing": "orthogonal", "label": "用户声明的结合", "scientific_status": "verified", "evidence_ids": ["evidence_1"]}],
        "groups": [],
        "evidence_records": [{"id": "evidence_1", "evidence_type": "literature", "citation": "用户录入的合成文献说明", "locator": "Figure 1", "note": "仅用于结构测试", "added_by": "测试用户", "date": "2026-09-30"}],
        "provenance": {"registry_version": "1.0", "mechanism_schema_version": "1.0", "component_ids": ["ligand_generic", "receptor_membrane"], "note": "BioFigure Studio 原创组件；实体、关系和核实状态均由用户负责。"},
    }


def test_phase7c_round_trip_preserves_entities_relations_and_evidence():
    spec = IllustrationSpec.model_validate(mechanism_document())
    restored = IllustrationSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec
    assert restored.nodes[0].entity_type == "ligand"
    assert restored.edges[0].relation == "binding"
    assert restored.evidence_records[0].evidence_type == "literature"


@pytest.mark.parametrize("mutation", ["verified_without_evidence", "dangling_evidence", "normal_relation", "duplicate_evidence", "control_character"])
def test_phase7c_rejects_untraceable_or_unsafe_mechanism_state(mutation):
    value = mechanism_document()
    if mutation == "verified_without_evidence":
        value["edges"][0]["evidence_ids"] = []
    elif mutation == "dangling_evidence":
        value["nodes"][0]["evidence_ids"] = ["missing"]
    elif mutation == "normal_relation":
        value["edges"][0]["relation"] = "normal"
    elif mutation == "duplicate_evidence":
        value["evidence_records"].append(dict(value["evidence_records"][0]))
    else:
        value["evidence_records"][0]["citation"] = "unsafe\ntext"
    with pytest.raises(ValidationError):
        IllustrationSpec.model_validate(value)


def test_phase7c_frontend_has_manual_relations_evidence_and_relation_free_templates():
    root = Path(__file__).parents[1]
    studio = (root / "apps/web/src/IllustrationStudio.tsx").read_text(encoding="utf-8")
    schema = (root / "apps/web/src/illustration.ts").read_text(encoding="utf-8")
    assert "IllustrationSpec 1.3" in studio
    assert "mechanism_schema_version:'1.0'" in schema
    assert "evidence_records" in studio + schema
    assert "模板只可插入空白机制项目" in studio
    assert "不推断或补全通路" in studio
    assert "innerHTML" not in studio + schema
    assert "foreignObject" not in studio + schema
