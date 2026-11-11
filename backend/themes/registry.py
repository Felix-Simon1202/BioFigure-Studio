"""Convert named themes into Matplotlib-safe rendering settings."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    identifier: str
    figure_facecolor: str
    axes_facecolor: str
    text_color: str
    grid_color: str
    palette: tuple[str, ...]


THEMES = {
    "scientific_clear": Theme(
        "scientific_clear", "#ffffff", "#ffffff", "#17252a", "#d9e1e3",
        ("#2374ab", "#d05a3b", "#3e8e72", "#8a5ca5"),
    ),
    "modern_soft": Theme(
        "modern_soft", "#f8f5ef", "#f8f5ef", "#27353a", "#d8d4c9",
        ("#5f8f9b", "#d6806c", "#9eae79", "#9b86b7"),
    ),
    "high_contrast": Theme(
        "high_contrast", "#ffffff", "#ffffff", "#17252a", "#ccd6d9",
        ("#0072b2", "#d55e00", "#009e73", "#cc79a7", "#f0e442"),
    ),
}


def get_theme(identifier: str) -> Theme:
    """Return a reviewed theme; validation prevents arbitrary rcParams."""
    return THEMES[identifier]
