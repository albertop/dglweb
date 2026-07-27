"""Career value of a rate metric — two tiers.

* **Exact** (`exact_value`): recompute from the career-summed counting components, for rates whose
  formula we know — batting via the verified `derive` module, pitching/fielding via the standard
  definitions (ERA = 9·ER/IP, WHIP = (H+BB)/IP, K/9 = 9·SO/IP, FLD% = (PO+A)/(PO+A+E), RF…). These
  match the stored per-season values, which come from the same definitions.
* **Prorated** (the engine's fallback for anything without a known formula — FIP, xFIP, wOBA, ERA-…):
  a playing-time-weighted average of the per-season rate (weight = PA batting, IP pitching, G
  fielding). A good career approximation for context-dependent sabermetrics that do not sum.

`IP` is the canonical `outs` (IP = outs / 3); the 9-inning factor becomes 27 over `outs`.
"""

from collections.abc import Callable, Mapping
from typing import Any

from dglweb.stats import derive

# Counting components to sum per group (a superset covering the exact formulas and the weight column).
COMPONENTS: dict[str, tuple[str, ...]] = {
    "batting": (
        "h",
        "ab",
        "bb",
        "hbp",
        "sf",
        "so",
        "hr",
        "x2b",
        "x3b",
        "x1b",
        "pa",
        "r",
        "rbi",
        "tb",
        "sb",
        "sh",
        "cs",
        "ibb",
        "gidp",
        # Batted-ball / swing inputs: the group-3 coefficients recompute from these career sums.
        "ground_outs",
        "ground_hits",
        "fly_outs",
        "fly_hits",
        "line_outs",
        "line_hits",
        "pop_outs",
        "pop_hits",
        "balls_in_play",
        "total_swings",
        "swing_and_misses",
    ),
    "pitching": (
        "er",
        "outs",
        "h",
        "bb",
        "hr",
        "so",
        "w",
        "l",
        "ab",
        "r",
        # Batted-ball / swing inputs, so the career coefficients recompute from these sums.
        "ground_outs",
        "ground_hits",
        "fly_outs",
        "fly_hits",
        "line_outs",
        "line_hits",
        "pop_outs",
        "pop_hits",
        "balls_in_play",
        "total_swings",
        "swing_and_misses",
    ),
    "fielding": ("po", "a", "e", "gp", "innings_outs"),
}

# The playing-time weight column used both to prorate and to test the qualifier.
WEIGHT: dict[str, str] = {"batting": "pa", "pitching": "outs", "fielding": "gp"}

# Tasas que NO se ponderan con el peso de su oficio, porque su denominador natural es otro.
#
# `catcher_era` son carreras limpias por 9 entradas MIENTRAS el receptor está detrás del plato. Con
# el peso de fildeo —juegos— dos temporadas de 50 juegos pesaban igual fueran 900 entradas o 90, que
# es la diferencia entre un receptor titular y un cambio defensivo de la novena entrada.
#
# Ponderar por entradas no es solo más justo: es EXACTO. Como cERA = 9·ER/IP, la media ponderada por
# entradas Σ(cERA·IP)/ΣIP colapsa a 9·ΣER/ΣIP, que es la cERA de carrera de verdad. Pasa de
# aproximación a fórmula cerrada sin necesidad de guardar las limpias por separado.
PESO_PROPIO: dict[tuple[str, str], str] = {
    ("fielding", "catcher_era"): "innings_outs",
}


def peso_de(group: str, column: str) -> str:
    """La columna que pondera esta tasa: la suya propia si la tiene, si no la de su oficio."""
    return PESO_PROPIO.get((group, column), WEIGHT[group])

# Floats that are ADDITIVE (runs/wins above average), not rates: their career value is the SUM over
# seasons, never a prorated average. Rates/indexes/scores (wOBA, wRC+, SPD, FIP-, ERA-, LI) are not
# here. Curated with the owner (review v2, SAB-03).
CUMULATIVE_FLOATS: frozenset[tuple[str, str]] = frozenset(
    [
        ("batting", column)
        for column in (
            "w_raa",
            "w_rc",
            "rar",
            "war",
            "ubr",
            "w_gdp",
            "w_sb",
            "positional_adj",
            "w_league",
            "batting",
            "fielding",
            "base_running",
            "replacement",
        )
    ]
    + [("pitching", column) for column in ("rar", "war", "ra9_war")]
    + [("fielding", "uzr")]
)


def _div(numerator: float | None, denominator: float | None) -> float | None:
    return None if numerator is None or not denominator else numerator / denominator


def _per9(key: str) -> Callable[[Mapping[str, Any]], float | None]:
    return lambda c: _div(None if c.get(key) is None else 27 * c[key], c.get("outs"))


def _pct(win: str, loss: str) -> Callable[[Mapping[str, Any]], float | None]:
    def rate(c: Mapping[str, Any]) -> float | None:
        w, losses = c.get(win), c.get(loss)
        return None if w is None or losses is None else _div(w, w + losses)

    return rate


def _fld_pct(c: Mapping[str, Any]) -> float | None:
    po, a, e = c.get("po"), c.get("a"), c.get("e")
    if po is None or a is None or e is None:
        return None
    return _div(po + a, po + a + e)


_PITCHING: dict[str, Callable[[Mapping[str, Any]], float | None]] = {
    "era": lambda c: _div(None if c.get("er") is None else 27 * c["er"], c.get("outs")),
    "whip": lambda c: _div(
        None if c.get("h") is None or c.get("bb") is None else 3 * (c["h"] + c["bb"]), c.get("outs")
    ),
    "r_per9": _per9("r"),
    "so_per9": _per9("so"),
    "bb_per9": _per9("bb"),
    "hr_per9": _per9("hr"),
    "h_per9": _per9("h"),
    "win_pct": _pct("w", "l"),
    "baa": lambda c: _div(c.get("h"), c.get("ab")),
    "so_to_bb": lambda c: _div(c.get("so"), c.get("bb")),
    # Batted-ball coefficients: same formulas as batting, over the balls put in play against him.
    **{
        column: (lambda col: lambda c: derive.batted_ball_coefficients(dict(c)).get(col))(column)
        for column in derive.batted_ball_coefficients({})
    },
}

_FIELDING: dict[str, Callable[[Mapping[str, Any]], float | None]] = {
    "fld_pct": _fld_pct,
    "rf_per_g": lambda c: _div(None if c.get("po") is None or c.get("a") is None else c["po"] + c["a"], c.get("gp")),
    "rf_per9": lambda c: _div(
        None if c.get("po") is None or c.get("a") is None else 27 * (c["po"] + c["a"]), c.get("innings_outs")
    ),
}

# Batting exact set = derive's rate outputs (drop runs_produced, a count).
_BATTING: set[str] = set(derive.derived_rates({})) - {"runs_produced"}


def has_exact(group: str, column: str) -> bool:
    """True if this rate has a known career formula (else the engine prorates it)."""
    return column in {"batting": _BATTING, "pitching": _PITCHING.keys(), "fielding": _FIELDING.keys()}[group]


def exact_value(group: str, column: str, counts: Mapping[str, Any]) -> float | None:
    if group == "batting":
        value = derive.derived_rates(dict(counts)).get(column)
        return None if value is None else float(value)
    formula = (_PITCHING if group == "pitching" else _FIELDING)[column]
    return formula(counts)
