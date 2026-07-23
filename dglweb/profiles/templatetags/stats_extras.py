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
def num(value: Any) -> str:  # noqa: ANN401 — a template filter takes any value
    """A counting stat, or `—` when absent (never a bare blank that misreads as zero)."""
    return "—" if value is None else str(value)
