"""Translate fielding proxy payloads into `Fielding` field values.

The simplest of the three groups: no mlbstats formulas at all — every value comes straight from
the proxy. The rate lines (fielding %, range factors, innings, catcher ERA) arrive as strings and
are parsed to float; their undefined-rate placeholders become NULL. Catcher-only keys
(passed balls, catcher ERA, stolen bases against…) are simply absent for other positions and map
to NULL there.
"""

from typing import Any

# proxy key -> our column
_KEYS = {
    "G": "gp",
    "GS": "gs",
    "A": "a",
    "PO": "po",
    "E": "e",
    "TC": "chances",
    "INN": "innings",
    "fielding": "fld_pct",
    "RFpG": "rf_per_g",
    "RFp9": "rf_per9",
    "DP": "double_plays",
    "TP": "triple_plays",
    "ThrE": "throwing_errors",
    "age": "age",
    # catcher-only
    "passedBall": "passed_balls",
    "catcherERA": "catcher_era",
    "CI": "catcher_int",
    "WP": "wild_pitches",
    "PKO": "pickoffs",
    "SB": "stolen_bases",
    "CS": "caught_stealing",
}

_FLOAT_COLUMNS = {"innings", "fld_pct", "rf_per_g", "rf_per9", "catcher_era"}


def _to_float(value: str | int | float | None) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value.strip())
    except ValueError:
        return None


def map_fielding(stat: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, column in _KEYS.items():
        value = stat.get(key)
        out[column] = _to_float(value) if column in _FLOAT_COLUMNS else value
    return out
