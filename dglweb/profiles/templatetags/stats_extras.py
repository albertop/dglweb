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
    """A signed decimal that KEEPS its leading zero and groups thousands.

    Run/win values: `0.5`, `-2.3`, `54.5`, WHIP `0.98` — and career run estimators that run into
    four figures, `1,536.6` (BsR, RC, wRC), which read as gibberish ungrouped.
    """
    return "—" if value is None else f"{float(value):,.{places}f}"


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
    if outs is None:
        return "—"
    whole, remainder = divmod(int(outs), 3)
    return f"{whole:,}.{remainder}"


@register.filter
def pct(value: Any, places: int = 1) -> str:  # noqa: ANN401 — a template filter takes any value
    """A proportion shown as a percentage number, no `%` sign: `0.452` -> `45.2`; `—` for None."""
    return "—" if value is None else f"{float(value) * 100:.{places}f}"
