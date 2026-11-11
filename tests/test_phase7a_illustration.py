import pytest
from pydantic import ValidationError

from backend.core.specs import IllustrationSpec


def sample_document():
    return {
        "spec_version": "1.0",
        "title": "受体与配体示意",
        "canvas": {"width": 960, "height": 640, "background": "#ffffff"},
        "nodes": [
            {"id": "receptor_1", "component_id": "receptor_membrane", "x": 180, "y": 230, "width": 105, "height": 120, "rotation": 0, "z_index": 0, "label": "受体", "fill": "#79a3a0", "text_color": "#26332f", "scientific_status": "illustrative"},
            {"id": "ligand_1", "component_id": "ligand_generic", "x": 420, "y": 160, "width": 70, "height": 58, "rotation": 0, "z_index": 1, "label": "配体", "fill": "#bc78a1", "text_color": "#26332f", "scientific_status": "needs_review"},
        ],
        "edges": [{"id": "edge_1", "source": {"node_id": "ligand_1", "anchor_id": "left"}, "target": {"node_id": "receptor_1", "anchor_id": "right"}, "relation": "activation", "label": "", "scientific_status": "needs_review"}],
        "groups": [{"id": "group_1", "name": "受体配体", "node_ids": ["receptor_1", "ligand_1"], "edge_ids": ["edge_1"]}],
        "provenance": {"registry_version": "1.0", "component_ids": ["ligand_generic", "receptor_membrane"], "note": "BioFigure Studio 原创组件；科学关系需由用户核实。"},
    }


def test_illustration_spec_round_trip_and_provenance():
    spec = IllustrationSpec.model_validate(sample_document())
    restored = IllustrationSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec
    assert restored.edges[0].scientific_status == "needs_review"
    assert restored.provenance.component_ids == ["ligand_generic", "receptor_membrane"]


@pytest.mark.parametrize("mutation", ["unknown_component", "dangling_edge", "outside_canvas", "duplicate_node", "provenance_mismatch"])
def test_illustration_spec_rejects_unsafe_or_inconsistent_documents(mutation):
    document = sample_document()
    if mutation == "unknown_component":
        document["nodes"][0]["component_id"] = "remote_svg"
    elif mutation == "dangling_edge":
        document["edges"][0]["target"]["node_id"] = "missing"
    elif mutation == "outside_canvas":
        document["nodes"][0]["x"] = 900
    elif mutation == "duplicate_node":
        document["nodes"][1]["id"] = "receptor_1"
    else:
        document["provenance"]["component_ids"] = ["ligand_generic"]
    with pytest.raises(ValidationError):
        IllustrationSpec.model_validate(document)


def test_illustration_text_rejects_control_characters():
    document = sample_document()
    document["nodes"][0]["label"] = "受体\n<script>"
    with pytest.raises(ValidationError):
        IllustrationSpec.model_validate(document)
