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


def _innings_to_outs(value: str | int | float | None) -> int | None:
    """`"111.1"` (baseball notation: 111 innings + 1 out) -> 334 outs. `.1`/`.2` are OUTS.

    The fraction is a count of outs into the next inning, so it can only be 0, 1 or 2 — `.3` would be
    a whole inning. Anything else (`.3`, `.9`, `.25`, a stray digit, garbage) is malformed and returns
    `None` rather than a plausible-but-false outs count that would silently poison totals, RF/9 and the
    fielding leaderboards (review v4 DEV-04). Ingest fails soft here; a real gap surfaces in parity.
    """
    if value is None:
        return None
    whole, _, frac = str(value).strip().partition(".")
    if (whole and not whole.isdigit()) or frac not in ("", "0", "1", "2"):
        return None
    return int(whole or 0) * 3 + int(frac or 0)


def map_fielding(stat: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, column in _KEYS.items():
        value = stat.get(key)
        out[column] = _to_float(value) if column in _FLOAT_COLUMNS else value
    # Canonical, additive innings — `innings` itself must never be summed (see the Fielding model).
    out["innings_outs"] = _innings_to_outs(stat.get("INN"))
    return out
