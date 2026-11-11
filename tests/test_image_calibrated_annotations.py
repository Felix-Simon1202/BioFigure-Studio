from dataclasses import replace
import xml.etree.ElementTree as ET

import pytest

from backend.image.annotations import create_overlay
from backend.image.montage import GridPlacement, GridProof


def proof():
    placements = []
    for index, scale in enumerate((0.25, 0.5)):
        axes = [{"name": "X", "length": 100, "scale": scale, "unit": "um"},
                {"name": "Y", "length": 60, "scale": 0.8, "unit": "um"}]
        placements.append(GridPlacement(str(index), index * 100, 0, 100, 60,
                                        "0" * 64, source_axes=axes))
    return GridProof(200, 60, "L", "TIFF", "1" * 64, tuple(placements), 12000)


def bar(identifier="0"):
    return {"kind": "scale_bar", "asset_id": identifier, "offset_x": 4,
            "offset_y": 20, "length_um": 5, "color": "#000000",
            "calibration_source": "fiji_inspected_axes"}


def test_mixed_tiles_use_their_own_verified_horizontal_scale_and_roundtrip():
    grid = proof()
    normalized, svg = create_overlay(grid, [bar("0"), bar("1")])
    assert [item["length_px"] for item in normalized] == [20, 10]
    assert [item["x_um_per_pixel"] for item in normalized] == [0.25, 0.5]
    assert all(item["calibration_source"] == "fiji_inspected_axes" for item in normalized)
    assert create_overlay(grid, normalized) == (normalized, svg)
    lines = ET.fromstring(svg).findall("{http://www.w3.org/2000/svg}line")
    assert [float(line.attrib["x2"]) for line in lines] == [24, 114]


@pytest.mark.parametrize("field,value", [("x_um_per_pixel", 0.3), ("length_px", 9),
                                         ("calibration_source", "invented")])
def test_forged_derived_scale_or_source_is_rejected(field, value):
    item = bar()
    item[field] = value
    with pytest.raises(ValueError):
        create_overlay(proof(), [item])


def test_missing_verified_axes_do_not_fall_back_to_a_default():
    grid = proof()
    grid = replace(grid, placements=(replace(grid.placements[0], source_axes=None),))
    with pytest.raises(ValueError):
        create_overlay(grid, [bar()])


def test_manual_override_retains_explicit_user_provenance():
    item = {**bar(), "calibration_source": "user_explicit", "x_um_per_pixel": 1}
    normalized, _ = create_overlay(proof(), [item])
    assert normalized[0]["length_px"] == 5
    assert normalized[0]["calibration_source"] == "user_explicit"
