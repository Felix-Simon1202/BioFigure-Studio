"""Keep chart selection explicit rather than accepting arbitrary engines."""

from collections.abc import Callable

from backend.core.specs import ChartSpec


Adapter = Callable[..., object]
_CHARTS: dict[str, Adapter] = {}


def register_chart(chart_type: str, adapter: Adapter) -> None:
    """Register one reviewed chart implementation."""
    _CHARTS[chart_type] = adapter


def get_chart_adapter(chart_type: str) -> Adapter:
    """Resolve only a chart type known at application startup."""
    return _CHARTS[chart_type]
