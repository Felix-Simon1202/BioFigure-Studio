from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.core.specs import IllustrationSpec


def document():
    return {
        "spec_version": "1.1",
        "title": "7B 画布测试",
        "canvas": {"width": 960, "height": 640, "background": "#ffffff", "grid_size": 20, "show_grid": True, "snap_to_grid": True},
        "nodes": [
            {"id": "cell_1", "component_id": "cell_generic", "x": 150, "y": 130, "width": 190, "height": 130, "rotation": 30, "z_index": 0, "label": "细胞", "fill": "#d7ece7", "text_color": "#26332f", "scientific_status": "illustrative"},
            {"id": "protein_1", "component_id": "protein_generic", "x": 520, "y": 290, "width": 110, "height": 82, "rotation": -25, "z_index": 1, "label": "蛋白质", "fill": "#e4b96c", "text_color": "#26332f", "scientific_status": "needs_review"},
        ],
        "edges": [{"id": "edge_1", "source": {"node_id": "cell_1", "anchor_id": "right"}, "target": {"node_id": "protein_1", "anchor_id": "left"}, "relation": "activation", "routing": "orthogonal", "label": "", "scientific_status": "needs_review"}],
        "groups": [],
        "provenance": {"registry_version": "1.0", "component_ids": ["cell_generic", "protein_generic"], "note": "BioFigure Studio 原创组件；科学关系需由用户核实。"},
    }


def test_phase7b_round_trip_preserves_canvas_transform_and_routing():
    spec = IllustrationSpec.model_validate(document())
    restored = IllustrationSpec.model_validate_json(spec.model_dump_json())
    assert restored == spec
    assert restored.canvas.grid_size == 20
    assert restored.nodes[0].rotation == 30
    assert restored.edges[0].routing == "orthogonal"


@pytest.mark.parametrize("mutation", ["rotation", "rotated_outside", "small", "grid", "routing"])
def test_phase7b_rejects_invalid_advanced_canvas_state(mutation):
    value = document()
    if mutation == "rotation":
        value["nodes"][0]["rotation"] = 181
    elif mutation == "rotated_outside":
        value["nodes"][0].update({"x": 0, "y": 0, "rotation": 45})
    elif mutation == "small":
        value["nodes"][0]["width"] = 12
    elif mutation == "grid":
        value["canvas"]["grid_size"] = 101
    else:
        value["edges"][0]["routing"] = "user_path"
    with pytest.raises(ValidationError):
        IllustrationSpec.model_validate(value)


def test_phase7b_frontend_keeps_safe_canvas_features_and_no_external_svg():
    root = Path(__file__).parents[1]
    source = (root / "apps/web/src/IllustrationStudio.tsx").read_text(encoding="utf-8")
    schema = (root / "apps/web/src/illustration.ts").read_text(encoding="utf-8")
    assert "orthogonalPoints" in source
    assert "框选" in source and "层级面板" in source
    assert "migrateIllustration" in source
    assert "foreignObject" not in source
    assert "innerHTML" not in source + schema
