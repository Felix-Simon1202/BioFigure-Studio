"""Native area ROI geometry input rejects unsafe or silently altered shapes."""

import pytest

from backend.image.native_area_geometry import validate_area_roi


def rectangle(x=0.5, y=0.5, width=2.5, height=2.5):
    return {"version": "1.0", "kind": "rectangle", "x": x, "y": y,
            "width": width, "height": height}


def test_native_area_roi_rejects_geometry_loss():
    valid = [
        rectangle(),
        {"version": "1.0", "kind": "oval", "x": 1.25, "y": 2.5,
         "width": 3.75, "height": 4.5},
        {"version": "1.0", "kind": "traced", "points": [
            {"x": 1, "y": 1}, {"x": 5, "y": 1}, {"x": 1, "y": 5}]},
        {"version": "1.0", "kind": "rotated_ellipse", "x1": 2, "y1": 2,
         "x2": 6, "y2": 4, "aspect_ratio": 0.5},
        {"version": "1.0", "kind": "shape", "operation": "subtract",
         "operands": [rectangle(0, 0, 8, 8), rectangle(2, 2, 2, 2)]},
    ]
    for roi in valid:
        assert validate_area_roi(roi, 20, 20)["kind"] == roi["kind"]
    bad = [
        {**rectangle(), "version": "2.0"},
        {**rectangle(), "width": 0},
        {**rectangle(), "x": float("nan")},
        {**rectangle(), "x": 19},
        {**rectangle(), "extra": "silent"},
        {"version": "1.0", "kind": "traced", "points": [
            {"x": 1.25, "y": 1}, {"x": 5, "y": 1}, {"x": 1, "y": 5}]},
        {"version": "1.0", "kind": "polygon", "points": [
            {"x": 1, "y": 1}, {"x": 5, "y": 5}, {"x": 1, "y": 5}, {"x": 5, "y": 1}]},
        {"version": "1.0", "kind": "spline_polygon", "evaluation_points": 900,
         "points": [{"x": 1, "y": 1}, {"x": 5, "y": 1}, {"x": 1, "y": 5}]},
        {"version": "1.0", "kind": "rotated_rectangle", "x1": 2, "y1": 2,
         "x2": 2, "y2": 2, "rect_width": 1},
        {"version": "1.0", "kind": "rotated_ellipse", "x1": 2, "y1": 2,
         "x2": 6, "y2": 4, "aspect_ratio": 1.1},
        {"version": "1.0", "kind": "shape", "operation": "subtract",
         "operands": [rectangle(), {"version": "1.0", "kind": "shape",
             "operation": "union", "operands": [rectangle(), rectangle()]}]},
    ]
    for roi in bad:
        with pytest.raises(ValueError):
            validate_area_roi(roi, 20, 20)


def test_native_area_roi_budget_is_bounded():
    with pytest.raises(ValueError):
        validate_area_roi(rectangle(0, 0, 1200, 1000), 2000, 2000)
    with pytest.raises(ValueError):
        validate_area_roi({"version": "1.0", "kind": "shape", "operation": "union",
                           "operands": [rectangle(0, 0, 10, 10),
                                        rectangle(1500, 1500, 10, 10)]}, 2000, 2000)


def test_rotated_geometry_accepts_exact_in_bounds_extents():
    for kind, extra in [('rotated_rectangle', {'rect_width': 2}), ('rotated_ellipse', {'aspect_ratio': .5})]:
        roi = {'version': '1.0', 'kind': kind, 'x1': 0, 'y1': 2, 'x2': 4, 'y2': 2, **extra}
        assert validate_area_roi(roi, 5, 4)['kind'] == kind
    for roi in [
        {**rectangle(), 'kind': []},
        {'version': '1.0', 'kind': 'shape', 'operation': [], 'operands': [rectangle(), rectangle()]},
    ]:
        with pytest.raises(ValueError): validate_area_roi(roi, 5, 4)


@pytest.mark.parametrize('changed', [None, 'float_bounds', 'type', 'plane', 'redirect', 'overlay', 'null_marker'])
def test_native_area_result_geometry_and_provenance_are_verified(tmp_path, changed):
    from copy import deepcopy
    from hashlib import sha256
    from threading import Event
    from backend.image.assets import ImageAsset
    from backend.image.native_area_geometry import run_native_area_geometry_measure
    path = tmp_path / 'synthetic.tif'; path.write_bytes(b'synthetic')
    asset = ImageAsset(id='synthetic', name='synthetic.tif', bytes=9, sha256=sha256(b'synthetic').hexdigest(),
        path=path, metadata={'axes': [{'name': 'X', 'length': 5}, {'name': 'Y', 'length': 4}]})
    roi = rectangle(); settings = {'measurements': ['mean'], 'decimal_places': 3, 'threshold': None}
    payload = {'source_sha256': asset.sha256, 'redirect_sha256': None, 'redirect_plane': None,
        'current_plane': {}, 'roi': deepcopy(roi), 'settings': settings, 'measurement_bits': 2,
        'source_stack_index': 1, 'sampled_stack_index': 1, 'row_count': 1,
        'native_roi': {'class_name': 'ij.gui.Roi', 'type_code': 0, 'subpixel': True, 'spline_fit': False,
            'bounds': {'x': 0, 'y': 0, 'width': 3, 'height': 3},
            'float_bounds': {'x': .5, 'y': .5, 'width': 2.5, 'height': 2.5},
            'float_outline': [{'x': .5, 'y': .5}, {'x': 3, 'y': .5}, {'x': 3, 'y': 3}, {'x': .5, 'y': 3}]},
        'headings': ['Mean'], 'row': {'Mean': 7}, 'non_finite_headings': [], 'displayed_row': '7', 'label': None,
        'overlay_count_before': 0, 'overlay_count': 0,
        'source_calibration': {'pixel_width': 1, 'pixel_height': 1, 'unit': 'pixel', 'value_unit': 'Gray Value'},
        'sampled_calibration': {'pixel_width': 1, 'pixel_height': 1, 'unit': 'pixel', 'value_unit': 'Gray Value'}}
    if changed == 'float_bounds': payload['native_roi']['float_bounds']['x'] = 1.5
    if changed == 'type': payload['native_roi']['type_code'] = False
    if changed == 'plane': payload['source_stack_index'] = True
    if changed == 'redirect': payload['redirect_plane'] = {'Z': 1}
    if changed == 'overlay': payload['overlay_count'] = 1
    if changed == 'null_marker': payload['row']['Mean'] = None
    execute = lambda *_: payload
    if changed:
        with pytest.raises(ValueError): run_native_area_geometry_measure(asset, {}, roi, settings, None, None, Event(), execute)
    else:
        assert run_native_area_geometry_measure(asset, {}, roi, settings, None, None, Event(), execute)['row']['Mean'] == 7
