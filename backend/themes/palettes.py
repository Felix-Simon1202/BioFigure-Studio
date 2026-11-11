"""Versioned local chart colors, shared with the interface and Biodot."""
import json
from pathlib import Path
from typing import Literal

PaletteId = Literal[
    "theme", "colorblind", "viridis", "cividis", "magma", "coolwarm", "clay", "lagoon",
    "oc_clear", "oc_soft", "oc_paired", "oc_blues", "oc_balance",
]

_CATALOG = json.loads((Path(__file__).resolve().parents[2] / "assets/palettes/scientific.json").read_text(encoding="utf-8"))
SCIENTIFIC_PALETTES = {item["id"]: item for item in _CATALOG["palettes"]}
PALETTE_VERSION = "1.0"
ART_PALETTES = {
    "clay": ("#A34F3E", "#D3A45B", "#527C78", "#73617F", "#7B854B", "#B86D86"),
    "lagoon": ("#246B78", "#5F9E91", "#CA8755", "#8D739C", "#A4A451", "#B95B68"),
}
ART_PALETTES.update({key: tuple(item["colors"]) for key, item in SCIENTIFIC_PALETTES.items() if item["kind"] == "categorical"})


def palette_catalog() -> list[dict]:
    """Return detached metadata; callers cannot modify the rendering registry."""
    import copy
    return copy.deepcopy(_CATALOG["palettes"])


def continuous_palette(identifier: str):
    """Resolve only reviewed ramps; preserve existing Matplotlib palette names."""
    if identifier in SCIENTIFIC_PALETTES and SCIENTIFIC_PALETTES[identifier]["kind"] != "categorical":
        from matplotlib.colors import LinearSegmentedColormap
        return LinearSegmentedColormap.from_list(identifier, SCIENTIFIC_PALETTES[identifier]["colors"])
    return identifier if identifier in {"viridis", "cividis", "magma", "coolwarm"} else "viridis"
