"""Conservative physical pixel spacing for single-plane grid TIFFs."""

import math

from PIL import TiffImagePlugin

from backend.image.assets import ImageAsset


_UM = {"um": 1.0, "µm": 1.0, "μm": 1.0, "micron": 1.0, "nm": 0.001, "mm": 1000.0}


def axis_spacing(axes: object, size: tuple[int, int]) -> tuple[float, float] | None:
    if not isinstance(axes, list) or not all(isinstance(axis, dict) for axis in axes):
        return None
    values = []
    for name, length in zip(("X", "Y"), size):
        candidates = [axis for axis in axes if str(axis.get("name", "")).upper() == name]
        if len(candidates) != 1:
            return None
        axis = candidates[0]
        scale = axis.get("scale")
        unit = axis.get("unit")
        factor = _UM.get(unit) if isinstance(unit, str) else None
        if (axis.get("length") != length or factor is None or isinstance(scale, bool)
                or not isinstance(scale, (int, float)) or not math.isfinite(scale) or scale <= 0):
            return None
        value = scale * factor
        if not math.isfinite(value) or value <= 0 or not math.isfinite(1 / value):
            return None
        values.append(value)
    return tuple(values)


def shared_spacing(assets: list[ImageAsset], sizes: list[tuple[int, int]]) -> dict | None:
    """No DPI inference, scale averaging or implicit change of sampling."""
    found = [axis_spacing(asset.metadata.get("axes") if asset.metadata else None, size)
             for asset, size in zip(assets, sizes, strict=True)]
    if not found or found[0] is None or any(value != found[0] for value in found[1:]):
        return None
    return {"unit": "um", "x_um_per_pixel": found[0][0], "y_um_per_pixel": found[0][1],
            "source": "fiji_inspected_axes"}


def spacing_tags(spacing: dict) -> TiffImagePlugin.ImageFileDirectory_v2:
    tags = TiffImagePlugin.ImageFileDirectory_v2()
    tags[270] = "ImageJ=1.54\nimages=1\nunit=um\nhyperstack=false\n"
    tags[282] = 1 / spacing["x_um_per_pixel"]
    tags[283] = 1 / spacing["y_um_per_pixel"]
    tags[296] = 1  # ImageJ's description supplies the physical unit, not inch DPI.
    return tags


def verify_spacing_tags(image, spacing: dict) -> None:
    try:
        matches = (image.tag_v2[296] == 1 and "unit=um\n" in image.tag_v2[270]
                   and all(math.isclose(1 / float(image.tag_v2[tag]), spacing[key], rel_tol=1e-7)
                           for tag, key in ((282, "x_um_per_pixel"), (283, "y_um_per_pixel"))))
    except (KeyError, ValueError, ZeroDivisionError, TypeError):
        matches = False
    if not matches:
        raise ValueError("保存后的 TIFF 空间间距与源标定不一致。")
