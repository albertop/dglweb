"""Display filters for stat tables (baseball formatting conventions).

These are **fail-soft on purpose**: a value that will not parse renders as `—` instead of raising.
The place to be strict about a corrupt number is ingest and parity, which already are; a public
player page should survive one bad cell rather than return a 500 for the whole career. The mappers
turn unparseable source values into NULL, so this is defence in depth — for a half-written backfill,
a hand-made fixture, or a future computed column.
"""

from collections.abc import Callable
from typing import Any

from django import template

register = template.Library()

_MISSING = "—"


def _guarded(render: Callable[[Any], str]) -> Callable[[Any], str]:
    """Render, or `—` when the value is absent or refuses to become a number."""

    def safe(value: Any) -> str:  # noqa: ANN401 — a template filter takes any value
        if value is None:
            return _MISSING
        try:
            return render(value)
        except (TypeError, ValueError):
            return _MISSING

    return safe


@register.filter
def rate(value: Any, decimals: int = 3) -> str:  # noqa: ANN401 — a template filter takes any value
    """A rate the baseball way: `.288` (no leading zero) for values under 1; `—` for None."""

    def render(raw: Any) -> str:  # noqa: ANN401
        text = f"{float(raw):.{decimals}f}"
        return text[1:] if text.startswith("0.") else text

    return _guarded(render)(value)


@register.filter
def dec(value: Any, places: int = 1) -> str:  # noqa: ANN401 — a template filter takes any value
    """A signed decimal that KEEPS its leading zero and groups thousands.

    Run/win values: `0.5`, `-2.3`, `54.5`, WHIP `0.98` — and career run estimators that run into
    four figures, `1,536.6` (BsR, RC, wRC), which read as gibberish ungrouped.
    """
    return _guarded(lambda raw: f"{float(raw):,.{places}f}")(value)


@register.filter
def num(value: Any) -> str:  # noqa: ANN401 — a template filter takes any value
    """A counting stat with thousands separators (`2,472`), or `—` when absent."""
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value)


@register.filter
def innings(outs: Any) -> str:  # noqa: ANN401 — a template filter takes any value
    """Outs -> innings pitched in baseball notation: 8482 outs is `2,827.1`.

    The `.1`/`.2` count **outs**, not tenths — dividing by three and printing a decimal would turn
    Pedro's 2,827.1 into 2,827.3. `ip` is never stored; `outs` is the canonical column.
    """

    def render(raw: Any) -> str:  # noqa: ANN401
        whole, remainder = divmod(int(raw), 3)
        return f"{whole:,}.{remainder}"

    return _guarded(render)(outs)


@register.filter
def pct(value: Any, places: int = 1) -> str:  # noqa: ANN401 — a template filter takes any value
    """A proportion shown as a percentage number, no `%` sign: `0.452` -> `45.2`; `—` for None."""
    return _guarded(lambda raw: f"{float(raw) * 100:.{places}f}")(value)
