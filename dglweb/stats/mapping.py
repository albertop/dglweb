"""Translate proxy stat payloads into `Batting` field values.

Pure functions, no I/O: given the `stat` dict of a split, return the columns it fills. Keeping
this separate from the fetching is what lets the naming traps be tested exhaustively without
touching the network.

Two things make this less trivial than a rename:

* **The proxy renames upstream fields** (`strikeOuts` -> `K`, `doubles` -> `X2B`), so the keys
  here are the *proxy's*, taken from real responses — and `K` still lands in our `so` column.
* **Absent means NULL, never 0.** MLB simply does not have swing data before 1971 or pitch
  counts before 1891. Defaulting a missing key to 0 would claim a 1950 hitter never swung, and
  would poison every rate and every "fewest" ranking built on top.
"""

from typing import Any

# Proxy key -> our column, for values copied straight across.
_REGULAR_KEYS = {
    "G": "g",
    "PA": "pa",
    "AB": "ab",
    "R": "r",
    "H": "h",
    "X2B": "x2b",
    "X3B": "x3b",
    "HR": "hr",
    "RBI": "rbi",
    "SB": "sb",
    "CS": "cs",
    "BB": "bb",
    "K": "so",
    "IBB": "ibb",
    "HBP": "hbp",
    "SH": "sh",
    "SF": "sf",
    "GIDP": "gidp",
    "Pitches": "pitches",
    "TB": "tb",
    "LOB": "lob",
    "CI": "catcher_int",
    "AOuts": "air_outs",
}

_ADVANCED_KEYS = {
    "GOuts": "ground_outs",
    "FOuts": "fly_outs",
    "POuts": "pop_outs",
    "LOuts": "line_outs",
    "FH": "fly_hits",
    "PH": "pop_hits",
    "LH": "line_hits",
    "GH": "ground_hits",
    "Swings": "total_swings",
    "SwingMiss": "swing_and_misses",
    "BIP": "balls_in_play",
    "WO": "walk_offs",
}

_SABERMETRIC_KEYS = {
    "wOBA": "woba",
    "wRAA": "w_raa",
    "wRC": "w_rc",
    "wRCPlus": "w_rc_plus",
    "RAR": "rar",
    "WAR": "war",
    "UBR": "ubr",
    "wGDP": "w_gdp",
    "wSB": "w_sb",
    "SPD": "spd",
    "positional": "positional_adj",
    "wLeague": "w_league",
    "batting": "batting",
    "fielding": "fielding",
    "baseRunning": "base_running",
    "replacement": "replacement",
}


def _pick(stat: dict[str, Any], keys: dict[str, str]) -> dict[str, Any]:
    return {column: stat.get(key) for key, column in keys.items()}


def _subtract(*values: int | None) -> int | None:
    """Difference of counting stats, or None if any input is missing."""
    known = [v for v in values if v is not None]
    if len(known) != len(values):
        return None
    first, *rest = known
    return first - sum(rest)


def _add(*values: int | None) -> int | None:
    known = [v for v in values if v is not None]
    if len(known) != len(values):
        return None
    return sum(known)


def map_regular(stat: dict[str, Any]) -> dict[str, Any]:
    """Columns from the `season` / `yearByYear` payload, plus the three derived counts."""
    mapped = _pick(stat, _REGULAR_KEYS)

    # MLB reports neither singles nor extra-base hits nor unintentional walks.
    mapped["x1b"] = _subtract(mapped["h"], mapped["x2b"], mapped["x3b"], mapped["hr"])
    mapped["xbh"] = _add(mapped["x2b"], mapped["x3b"], mapped["hr"])
    mapped["nibb"] = _subtract(mapped["bb"], mapped["ibb"])
    return mapped


def map_advanced(stat: dict[str, Any]) -> dict[str, Any]:
    """Batted-ball and plate-discipline columns (`seasonAdvanced` / `yearByYearAdvanced`)."""
    return _pick(stat, _ADVANCED_KEYS)


def map_sabermetrics(stat: dict[str, Any]) -> dict[str, Any]:
    """WAR and friends (`sabermetrics`); absent for the eras MLB does not compute."""
    return _pick(stat, _SABERMETRIC_KEYS)
