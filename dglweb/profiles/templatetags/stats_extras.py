"""Display filters for stat tables (baseball formatting conventions)."""

from typing import Any

from django import template

register = template.Library()


@register.filter
def rate(value: Any, decimals: int = 3) -> str:  # noqa: ANN401 — a template filter takes any value
    """A rate the baseball way: `.288` (no leading zero) for values under 1; `—` for None."""
    if value is None:
        return "—"
    text = f"{float(value):.{decimals}f}"
    return text[1:] if text.startswith("0.") else text


@register.filter
def dec(value: Any, places: int = 1) -> str:  # noqa: ANN401 — a template filter takes any value
    """A signed decimal that KEEPS its leading zero (run/win values: `0.5`, `-2.3`, `54.5`, WHIP `0.98`)."""
    return "—" if value is None else f"{float(value):.{places}f}"


@register.filter
def num(value: Any) -> str:  # noqa: ANN401 — a template filter takes any value
    """A counting stat, or `—` when absent (never a bare blank that misreads as zero)."""
    return "—" if value is None else str(value)
