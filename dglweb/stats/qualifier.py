"""Resolve and evaluate the qualifier for a rate leaderboard (the 3-level cascade).

Resolution (most specific wins):
  * season boards -> season override (group, season) -> metric's own -> group default
  * career boards -> metric's own -> group default

Evaluation is a *safe* parse of a simple formula ``FIELD OP NUMBER`` (e.g. ``PA>=502``) — never
``eval``. The field names the qualifier column per group (batting PA, pitching IP, fielding G); IP
is derived from the canonical ``outs`` (never the baseball-notation ``ip``).
"""

import logging
import operator
from collections.abc import Callable, Mapping
from typing import Any

from dglweb.stats.formula import QUALIFIER_RE
from dglweb.stats.models import Metric

logger = logging.getLogger(__name__)

_OPS: dict[str, Callable[[float, float], bool]] = {
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "=": operator.eq,
}

# Lookups the engine preloads once and passes in, to avoid a query per row.
Defaults = Mapping[str, tuple[str, str]]  # group -> (season formula, career formula)
Overrides = Mapping[tuple[str, int], str]  # (group, season) -> season formula


def resolve_season(metric: Metric, season: int, defaults: Defaults, overrides: Overrides) -> str:
    override = overrides.get((metric.stat_group, season))
    if override:
        return override
    if metric.qualifier_season:
        return metric.qualifier_season
    return defaults.get(metric.stat_group, ("", ""))[0]


def resolve_career(metric: Metric, defaults: Defaults) -> str:
    if metric.qualifier_career:
        return metric.qualifier_career
    return defaults.get(metric.stat_group, ("", ""))[1]


def _column(group: str, field: str) -> str:
    """The row column a qualifier field reads. Anything unmapped is the column of the same name."""
    if group == "pitching" and field == "IP":
        return "outs"  # IP is derived from the canonical outs
    return {"PA": "pa", "G": "gp" if group == "fielding" else "g"}.get(field, field.lower())


def field_column(group: str, formula: str) -> str | None:
    """The column a formula needs, so the caller can be sure it selected it.

    A threshold on a column the caller did not fetch reads as missing and fails **closed** — the
    board comes out empty instead of unfiltered. Metrics with their own qualifier (the batted-ball
    coefficients gate on `BALLS_IN_PLAY`, not `PA`) depend on this.
    """
    match = QUALIFIER_RE.match(formula or "")
    return None if match is None else _column(group, match.group(1))


def _field_value(group: str, field: str, row: Mapping[str, Any]) -> float | None:
    """The qualifier field's value for a totals row (IP = outs / 3; G = games at the position)."""
    if group == "pitching" and field == "IP":
        outs = row.get("outs")
        return None if outs is None else outs / 3
    value = row.get(_column(group, field))
    return None if value is None else float(value)


def qualifies(formula: str, group: str, row: Mapping[str, Any]) -> bool:
    """True if the row clears the threshold.

    A **blank** formula means *no threshold* (everyone qualifies). A non-blank but **unparseable**
    formula is fail-**closed**: it qualifies no one, so a typo publishes an empty board rather than an
    unfiltered one. (Forms reject invalid formulas via `validate_qualifier_formula`; this is defense
    in depth for anything that reaches the builder anyway.)
    """
    if not formula.strip():
        return True
    match = QUALIFIER_RE.match(formula)
    if match is None:
        logger.warning("Fórmula de umbral inválida %r: no califica a nadie (fail-closed).", formula)
        return False
    field, op, threshold = match.group(1), match.group(2), float(match.group(3))
    value = _field_value(group, field, row)
    if value is None:
        return False
    return _OPS[op](value, threshold)
