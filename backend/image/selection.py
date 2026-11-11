"""Explicit C/Z/T plane and rectangular ROI contract for Fiji tasks."""

from dataclasses import dataclass
from typing import Any

from backend.image.assets import ImageAsset


MAX_SELECTION_PIXELS = 1_000_000
PLANE_AXES = {"C": "Channel", "Z": "Z", "T": "Time"}
EXTRA_MEASUREMENTS = ("std_dev", "median", "mode", "integrated_density")


def stack_plane_count(axes: list[dict[str, Any]]) -> int:
    count = 1
    for axis in axes:
        if axis["name"] in PLANE_AXES.values():
            count *= axis["length"]
    return count


def linear_stack_index(axes: list[dict[str, Any]], plane: dict[str, int]) -> int:
    """ImageJ1 one-based stack index, after build_plane_selection validation."""
    lengths = {axis["name"]: axis["length"] for axis in axes}
    return 1 + plane.get("C", 0) + lengths.get("Channel", 1) * (
        plane.get("Z", 0) + lengths.get("Z", 1) * plane.get("T", 0))


def _segments_cross(a: tuple[int, int], b: tuple[int, int],
                    c: tuple[int, int], d: tuple[int, int]) -> bool:
    def turn(p: tuple[int, int], q: tuple[int, int], r: tuple[int, int]) -> int:
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])

    ab_c, ab_d = turn(a, b, c), turn(a, b, d)
    cd_a, cd_b = turn(c, d, a), turn(c, d, b)
    if ab_c == 0 and min(a[0], b[0]) <= c[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= c[1] <= max(a[1], b[1]):
        return True
    if ab_d == 0 and min(a[0], b[0]) <= d[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= d[1] <= max(a[1], b[1]):
        return True
    if cd_a == 0 and min(c[0], d[0]) <= a[0] <= max(c[0], d[0]) and min(c[1], d[1]) <= a[1] <= max(c[1], d[1]):
        return True
    if cd_b == 0 and min(c[0], d[0]) <= b[0] <= max(c[0], d[0]) and min(c[1], d[1]) <= b[1] <= max(c[1], d[1]):
        return True
    return (ab_c > 0) != (ab_d > 0) and (cd_a > 0) != (cd_b > 0)


@dataclass(frozen=True)
class ImageSelection:
    indices: dict[str, int]
    roi: dict[str, Any]
    source_axes: list[dict[str, Any]]
    sample_count: int
    extra_measurements: tuple[str, ...] = ()

    def public(self) -> dict[str, object]:
        return {"indices": self.indices, "roi": self.roi,
                "source_axes": self.source_axes, "sample_count": self.sample_count,
                "extra_measurements": list(self.extra_measurements)}


def build_plane_selection(asset: ImageAsset, indices: dict[str, int]
                          ) -> tuple[list[dict[str, Any]], dict[str, int], int, int]:
    """Require explicit indices for every non-singleton C/Z/T axis."""
    axes = asset.metadata.get("axes") if asset.metadata else None
    if not isinstance(axes, list) or not all(isinstance(axis, dict) for axis in axes):
        raise ValueError("请先使用 Fiji 检查图像轴，再选择 ROI 与 C/Z/T 平面。")
    by_name: dict[str, dict[str, Any]] = {}
    for axis in axes:
        name = axis.get("name")
        if not isinstance(name, str) or name in by_name:
            raise ValueError("Fiji 图像轴名称缺失或重复。")
        by_name[name] = axis
    if not all(name in by_name for name in ("X", "Y")):
        raise ValueError("Fiji 图像缺少 X/Y 轴。")
    lengths = {name: axis.get("length") for name, axis in by_name.items()}
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 1
           for value in lengths.values()):
        raise ValueError("Fiji 图像轴长度无效。")
    if any(name not in {"X", "Y", *PLANE_AXES.values()} and length != 1
           for name, length in lengths.items()):
        raise ValueError("存在尚未适配的非单例图像轴。")
    if not isinstance(indices, dict) or any(key not in PLANE_AXES for key in indices):
        raise ValueError("平面索引仅允许 C/Z/T。")
    normalized: dict[str, int] = {}
    for key, name in PLANE_AXES.items():
        length = lengths.get(name)
        if length is None:
            if key in indices:
                raise ValueError(f"图像不存在 {key} 轴。")
            continue
        if length > 1 and key not in indices:
            raise ValueError(f"必须显式选择 {key} 轴索引。")
        index = indices.get(key, 0)
        if isinstance(index, bool) or not isinstance(index, int) or not 0 <= index < length:
            raise ValueError(f"{key} 轴索引超出范围。")
        normalized[key] = index
    width, height = lengths["X"], lengths["Y"]
    return axes, normalized, width, height


def build_selection(asset: ImageAsset, indices: dict[str, int],
                    roi: dict[str, Any] | None,
                    extra_measurements: list[str] | None = None) -> ImageSelection:
    extras = [] if extra_measurements is None else extra_measurements
    if (not isinstance(extras, list) or any(not isinstance(value, str) for value in extras)
            or len(extras) != len(set(extras))
            or any(value not in EXTRA_MEASUREMENTS for value in extras)):
        raise ValueError("额外测量仅支持标准差、中位数、众数与积分密度，且不能重复。")
    axes, normalized, width, height = build_plane_selection(asset, indices)
    if roi is None:
        region: dict[str, Any] = {"kind": "full", "x": 0, "y": 0,
                                         "width": width, "height": height}
    elif isinstance(roi, dict) and roi.get("kind") == "polygon":
        points = roi.get("points")
        if (set(roi) not in ({"kind", "points"}, {"kind", "points", "x", "y", "width", "height"})
                or not isinstance(points, list) or not 3 <= len(points) <= 32):
            raise ValueError("多边形 ROI 须提供 3 至 32 个整数顶点。")
        if any(not isinstance(point, dict) or set(point) != {"x", "y"} or
               any(isinstance(point[key], bool) or not isinstance(point[key], int) for key in ("x", "y")) or
               not (0 <= point["x"] < width and 0 <= point["y"] < height) for point in points):
            raise ValueError("多边形顶点须位于已检查图像边界内。")
        vertices = [(point["x"], point["y"]) for point in points]
        doubled_area = sum(vertices[index][0] * vertices[(index + 1) % len(vertices)][1]
                           - vertices[(index + 1) % len(vertices)][0] * vertices[index][1]
                           for index in range(len(vertices)))
        if len(set(vertices)) != len(vertices) or doubled_area == 0:
            raise ValueError("多边形顶点须互异且围成非零面积。")
        if any(_segments_cross(vertices[i], vertices[(i + 1) % len(vertices)],
                               vertices[j], vertices[(j + 1) % len(vertices)])
               for i in range(len(vertices)) for j in range(i + 1, len(vertices))
               if j != i + 1 and not (i == 0 and j == len(vertices) - 1)):
            raise ValueError("多边形 ROI 不支持边相交或自交。")
        x0, y0 = min(x for x, _ in vertices), min(y for _, y in vertices)
        region = {"kind": "polygon", "points": points, "x": x0, "y": y0,
                  "width": max(x for x, _ in vertices) - x0 + 1,
                  "height": max(y for _, y in vertices) - y0 + 1}
        if set(roi) != {"kind", "points"} and any(roi[key] != region[key]
                                                   for key in ("x", "y", "width", "height")):
            raise ValueError("多边形包围盒与顶点不一致。")
    else:
        kind = roi.get("kind", "rectangle") if isinstance(roi, dict) else None
        fields = {"x", "y", "width", "height"} | ({"kind"} if "kind" in roi else set()) if isinstance(roi, dict) else set()
        if kind not in {"rectangle", "ellipse"} or set(roi) != fields:
            raise ValueError("ROI 目前仅支持矩形或椭圆的 x/y/width/height。")
        values = (roi[key] for key in ("x", "y", "width", "height"))
        if any(isinstance(value, bool) or not isinstance(value, int) for value in values):
            raise ValueError("ROI 坐标与尺寸必须是整数像素。")
        x, y, w, h = roi["x"], roi["y"], roi["width"], roi["height"]
        if x < 0 or y < 0 or w < 1 or h < 1 or x + w > width or y + h > height:
            raise ValueError("ROI 超出 Fiji 图像 X/Y 边界。")
        region = {"kind": kind, "x": x, "y": y, "width": w, "height": h}
    count = region["width"] * region["height"]
    if count > MAX_SELECTION_PIXELS:
        raise ValueError("当前区域测量最多支持 100 万像素。")
    return ImageSelection(normalized, region, axes, count,
                          tuple(value for value in EXTRA_MEASUREMENTS if value in extras))
