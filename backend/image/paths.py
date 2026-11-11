"""Keep frozen image session files outside the installed program directory."""

import os
from pathlib import Path
import sys


def image_work_dir(name: str) -> Path:
    if getattr(sys, "frozen", False):
        local = os.environ.get("LOCALAPPDATA")
        if not local:
            raise RuntimeError("Windows user data directory is unavailable")
        return Path(local) / "BioFigureStudioData" / "image-work" / name
    return Path(__file__).resolve().parents[2] / "work" / name
