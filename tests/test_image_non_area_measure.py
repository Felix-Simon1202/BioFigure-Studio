"""Non-area ROI type, geometry and source guards before the native process."""

import asyncio
from io import BytesIO
from threading import Event

from fastapi import UploadFile
import pytest

from backend.image.assets import ImageAssetStore
from backend.image import non_area_measure


def test_non_area_roi_rejects_invalid_geometry_and_options_before_fiji(tmp_path, monkeypatch):
    store = ImageAssetStore(tmp_path / "assets")
    asset = asyncio.run(store.add(UploadFile(filename="stack.tif", file=BytesIO(b"synthetic"))))
    store.acquire(asset.id)
    store.set_metadata(asset.id, {"axes": [
        {"name": "X", "length": 100}, {"name": "Y", "length": 100},
        {"name": "Z", "length": 2},
    ]})
    store.release(asset.id)
    asset = store.get(asset.id)
    line = {"version": "1.0", "kind": "line", "points": [{"x": 1.25, "y": 2}, {"x": 8, "y": 2}],
            "stroke_width": 2.5}
    settings = {"measurements": ["mean"], "decimal_places": 3, "threshold": None}
    monkeypatch.setattr(non_area_measure, "native_non_area_measure",
                        lambda *_: (_ for _ in ()).throw(AssertionError("Fiji called")))
    bad = [
        ({**line, "version": "2.0"}, settings),
        ({**line, "stroke_width": 33}, settings),
        ({**line, "points": [{"x": 1, "y": 2}, {"x": 1, "y": 2}]}, settings),
        ({**line, "points": line["points"] + [{"x": 9, "y": 9}]}, settings),
        ({**line, "points": [{"x": 1, "y": 2}, {"x": float("nan"), "y": 2}]}, settings),
        ({**line, "point_positions": [0, 1]}, settings),
        ({"version": "1.0", "kind": "angle", "points": line["points"]}, settings),
        ({"version": "1.0", "kind": "multipoint", "points": line["points"],
          "point_positions": [1, 3]}, settings),
        (line, {**settings, "measurements": ["mean", "mean"]}),
        (line, {**settings, "measurements": ["limit_to_threshold"]}),
    ]
    for roi, options in bad:
        with pytest.raises(ValueError):
            non_area_measure.run_native_non_area_measure(asset, {"Z": 1}, roi, options,
                                                        None, None, Event())
    with pytest.raises(AssertionError, match="Fiji called"):
        non_area_measure.run_native_non_area_measure(asset, {"Z": 1}, line, settings,
                                                    None, None, Event())
    store.close()



@pytest.mark.parametrize('invalid', [None, 'type', 'coordinates', 'bits', 'overlay', 'null_marker', 'labels'])
def test_non_area_result_binds_native_type_coordinates_and_values(tmp_path, monkeypatch, invalid):
    from copy import deepcopy
    store = ImageAssetStore(tmp_path / 'assets')
    asset = asyncio.run(store.add(UploadFile(filename='synthetic.tif', file=BytesIO(b'synthetic'))))
    store.acquire(asset.id)
    store.set_metadata(asset.id, {'axes': [{'name': 'X', 'length': 100}, {'name': 'Y', 'length': 100}, {'name': 'Z', 'length': 2}]})
    store.release(asset.id); asset = store.get(asset.id)
    roi = {'version': '1.0', 'kind': 'freeline', 'points': [{'x': 1.25, 'y': 2.0}, {'x': 8.0, 'y': 2.0}], 'stroke_width': 2.5}
    settings = {'measurements': ['mean'], 'decimal_places': 3, 'threshold': None}
    payload = {'source_sha256': asset.sha256, 'redirect_sha256': None, 'redirect_plane': None,
        'current_plane': {'Z': 1}, 'roi': deepcopy(roi), 'settings': settings, 'row_count': 1,
        'source_stack_index': 2, 'sampled_stack_index': 2, 'headings': ['Mean'], 'rows': [{'Mean': 3.0}],
        'native_roi': {'class_name': 'ij.gui.PolygonRoi', 'type_code': 7, 'subpixel': True,
                       'stroke_width': 2.5, 'points': deepcopy(roi['points'])},
        'measurement_bits': 2, 'overlay_count_before': 0, 'overlay_count': 0,
        'labels': [None], 'displayed_rows': ['1\t3.000'], 'non_finite_headings': [[]]}
    if invalid == 'type': payload['native_roi']['type_code'] = 6  # Same class, different native branch.
    if invalid == 'coordinates': payload['native_roi']['points'][0]['x'] = 2.25
    if invalid == 'bits': payload['measurement_bits'] = 3
    if invalid == 'overlay': payload['overlay_count'] = 1
    if invalid == 'null_marker': payload['rows'][0]['Mean'] = None
    if invalid == 'labels': payload['labels'] = []
    monkeypatch.setattr(non_area_measure, 'native_non_area_measure', lambda *_: payload)
    try:
        if invalid:
            with pytest.raises(ValueError):
                non_area_measure.run_native_non_area_measure(asset, {'Z': 1}, roi, settings, None, None, Event())
        else:
            assert non_area_measure.run_native_non_area_measure(asset, {'Z': 1}, roi, settings, None, None, Event())['rows'] == [{'Mean': 3.0}]
    finally:
        store.close()
