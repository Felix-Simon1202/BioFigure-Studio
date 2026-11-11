"""Bounded native ShapeRoi path validation shared by measurement and interchange."""
from math import isfinite
from typing import Any

def validate_shape_path(path: Any, width: int, height: int) -> list[float]:
    if (not isinstance(path, list) or len(path) > 4096
            or any(type(value) not in (int, float) or not isfinite(value) for value in path)):
        raise ValueError("ShapeRoi 路径长度或浮点数无效。")
    index = segments = moves = closes = 0
    active = False
    while index < len(path):
        command = path[index]
        if command not in (0, 1, 2, 3, 4) or not float(command).is_integer():
            raise ValueError("ShapeRoi 路径命令无效。")
        index += 1
        count = {0: 2, 1: 2, 2: 4, 3: 6, 4: 0}[int(command)]
        if index + count > len(path):
            raise ValueError("ShapeRoi 路径坐标截断。")
        if command == 0:
            if active:
                raise ValueError("ShapeRoi 子路径未闭合。")
            active = True
            moves += 1
        elif command == 4:
            if not active:
                raise ValueError("ShapeRoi 关闭命令缺少子路径。")
            active = False
            closes += 1
        elif not active:
            raise ValueError("ShapeRoi 路径须从移动命令开始。")
        for offset in range(0, count, 2):
            x, y = path[index + offset:index + offset + 2]
            if not -0.01 <= x <= width + 0.01 or not -0.01 <= y <= height + 0.01:
                raise ValueError("ShapeRoi 路径超出图像范围。")
        index += count
        segments += 1
        if segments > 256:
            raise ValueError("ShapeRoi 路径段数超过 256。")
    if active or not moves or moves != closes:
        raise ValueError("ShapeRoi 路径须包含闭合轮廓。")
    return [float(value) for value in path]

