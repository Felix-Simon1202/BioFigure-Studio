"""Versioned local chart colors, shared with the interface and Biodot."""
import json
from pathlib import Path
from typing import Literal

PaletteId = Literal[
    "theme", "colorblind", "viridis", "cividis", "magma", "coolwarm", "clay", "lagoon",
    "oc_clear", "oc_soft", "oc_paired", "oc_blues", "oc_balance",
    "oc_ocean", "oc_garden", "oc_warm", "oc_cool",
    "oc_flower", "oc_jewel", "oc_pair_teal_rose", "oc_pair_garden",
    "oc_seq_teal", "oc_seq_green", "oc_seq_violet", "oc_seq_orange",
    "oc_seq_red", "oc_seq_gray", "oc_seq_cyan", "oc_seq_pink",
    "oc_div_teal_rose", "oc_div_violet_lime", "oc_div_indigo_amber", "oc_div_cyan_red",
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


def categorical_palette_guidance() -> str:
    """Compact shared names for the synthetic scatter/line proposal task only."""
    return "Available categorical palette IDs (choose by requested color mood): " + "; ".join(
        f"{key}: {item['name']['en']} / {item['name']['zh-CN']}"
        for key, item in SCIENTIFIC_PALETTES.items() if item["kind"] == "categorical"
    ) + ". Paired palettes require review of category order. Never infer biological meaning from names."


def continuous_palette(identifier: str):
    """Resolve only reviewed ramps; preserve existing Matplotlib palette names."""
    if identifier in SCIENTIFIC_PALETTES and SCIENTIFIC_PALETTES[identifier]["kind"] != "categorical":
        from matplotlib.colors import LinearSegmentedColormap
        return LinearSegmentedColormap.from_list(identifier, SCIENTIFIC_PALETTES[identifier]["colors"])
    return identifier if identifier in {"viridis", "cividis", "magma", "coolwarm"} else "viridis"
