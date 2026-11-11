from copy import deepcopy

import pytest
from pydantic import ValidationError

from backend.core.specs import IllustrationSpec


def workflow_document():
    return {
        "spec_version": "1.3", "document_kind": "experimental_workflow", "title": "合成实验流程",
        "canvas": {"width": 960, "height": 640, "background": "#ffffff", "grid_size": 20, "show_grid": True, "snap_to_grid": True},
        "nodes": [], "edges": [], "groups": [],
        "sections": [
            {"id": "step_a", "kind": "step", "title": "步骤 A", "description": "用户填写", "x": 40, "y": 105, "width": 280, "height": 430, "scientific_status": "illustrative", "evidence_ids": []},
            {"id": "step_b", "kind": "step", "title": "步骤 B", "description": "用户填写", "x": 340, "y": 105, "width": 280, "height": 430, "scientific_status": "verified", "evidence_ids": ["ev_1"]},
            {"id": "step_c", "kind": "step", "title": "步骤 C", "description": "用户填写", "x": 640, "y": 105, "width": 280, "height": 430, "scientific_status": "illustrative", "evidence_ids": []},
        ],
        "flow_links": [{"id": "flow_1", "source_section_id": "step_a", "target_section_id": "step_b", "label": "用户指定的顺序"}],
        "evidence_records": [{"id": "ev_1", "evidence_type": "user_note", "citation": "合成说明", "locator": "", "note": "", "added_by": "测试者", "date": "2026-10-18"}],
        "provenance": {"registry_version": "1.0", "mechanism_schema_version": "1.0", "composition_schema_version": "1.0", "component_ids": [], "note": "原创组件"},
    }


def test_phase7d_workflow_round_trip_and_separate_sequence_semantics():
    spec = IllustrationSpec.model_validate(workflow_document())
    assert IllustrationSpec.model_validate_json(spec.model_dump_json()) == spec
    assert spec.flow_links[0].source_section_id == "step_a"
    assert spec.edges == []


@pytest.mark.parametrize("mutation", [
    "reversed_flow", "duplicate_flow", "dangling_flow", "cross_mode_flow", "overlap", "out_of_bounds",
    "verified_without_evidence", "dangling_evidence", "control_character", "too_many_sections", "text_overflow", "unknown_field",
])
def test_phase7d_rejects_invalid_layout_sequence_or_evidence(mutation):
    value = deepcopy(workflow_document())
    if mutation == "reversed_flow":
        value["flow_links"][0]["source_section_id"], value["flow_links"][0]["target_section_id"] = "step_c", "step_a"
    elif mutation == "duplicate_flow":
        value["flow_links"].append({**value["flow_links"][0], "id": "flow_2"})
    elif mutation == "dangling_flow":
        value["flow_links"][0]["target_section_id"] = "missing"
    elif mutation == "cross_mode_flow":
        value["document_kind"] = "graphical_abstract"
        for section in value["sections"]:
            section["kind"] = "panel"
    elif mutation == "overlap":
        value["sections"][1]["x"] = 300
    elif mutation == "out_of_bounds":
        value["sections"][2]["x"] = 800
    elif mutation == "verified_without_evidence":
        value["sections"][1]["evidence_ids"] = []
    elif mutation == "dangling_evidence":
        value["sections"][1]["evidence_ids"] = ["missing"]
    elif mutation == "control_character":
        value["sections"][0]["description"] = "bad\ntext"
    elif mutation == "too_many_sections":
        value["sections"] += [{**value["sections"][0], "id": f"extra_{i}"} for i in range(6)]
    elif mutation == "unknown_field":
        value["sections"][0]["unreviewed_markup"] = "<svg/>"
    else:
        value["sections"][0]["title"] = "过长标题" * 12
    with pytest.raises(ValidationError):
        IllustrationSpec.model_validate(value)


def test_phase7d_assigned_node_must_remain_inside_section():
    value = workflow_document()
    value["nodes"] = [{"id": "protein_1", "component_id": "protein_generic", "x": 70, "y": 170, "width": 110, "height": 82, "rotation": 0, "z_index": 0, "label": "占位组件", "fill": "#e4b96c", "text_color": "#26332f", "scientific_status": "illustrative", "entity_type": "protein", "evidence_ids": [], "section_id": "step_a"}]
    value["provenance"]["component_ids"] = ["protein_generic"]
    IllustrationSpec.model_validate(value)
    value["nodes"][0]["x"] = 300
    with pytest.raises(ValidationError):
        IllustrationSpec.model_validate(value)
