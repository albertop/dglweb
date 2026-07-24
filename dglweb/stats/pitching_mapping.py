"""Translate pitching proxy payloads into `Pitching` field values.

Pure functions, no I/O. Keys are the proxy's (taken from real responses), and — unlike batting,
where the rate stats are computed — pitching's rate lines come straight from the proxy. They
arrive as strings (`".205"`, `"46.2"`, `"3.47"`), so the float-valued columns are parsed with
`_to_float`, which turns the proxy's undefined-rate placeholders (`"-.--"`, `".---"`, `"-"`)
into NULL. Two things are still derived (`X1B`, `NIBB`) and one uses the single mlbstats formula
(`BAA`), all verified against `dbo.mlbPitching`.

`IP` keeps the source's baseball notation (46.2 = 46 innings and 2 outs), not a decimal.
"""

from typing import Any

from dglweb.stats.derive import batted_ball_coefficients

# proxy key -> our column
_REGULAR = {
    "W": "w",
    "L": "l",
    "G": "g",
    "GP": "gp",
    "GS": "gs",
    "GF": "gf",
    "CG": "cg",
    "SHO": "sho",
    "SV": "sv",
    "BS": "bsv",
    "HLD": "hld",
    "IP": "ip",
    "H": "h",
    "R": "r",
    "HR": "hr",
    "ER": "er",
    "ERA": "era",
    "BB": "bb",
    "IBB": "ibb",
    "K": "so",
    "HBP": "hbp",
    "WP": "wp",
    "BK": "bk",
    "BF": "bf",
    "X2B": "x2b",
    "X3B": "x3b",
    "AVG": "avg",
    "OBP": "obp",
    "SLG": "slg",
    "OPS": "ops",
    "CS": "cs",
    "SB": "sb",
    "SBpct": "sb_pct",
    "GIDP": "gidp",
    "Pitches": "pitches",
    "SaveOpp": "save_opp",
    "Outs": "outs",
    "GOuts": "ground_outs",
    "AOuts": "air_outs",
    "Strikes": "strikes",
    "Strikepct": "strike_pct",
    "InhR": "inherit_runners",
    "InhRS": "inherit_runners_scored",
    "SH": "sh",
    "SF": "sf",
    "PKO": "pickoffs",
    "TB": "tb",
    "CI": "catcher_int",
    "WHIP": "whip",
    "Winpct": "win_pct",
    "Rp9": "r_per9",
    "AB": "ab",  # extra: at-bats against (the source uses BF)
    "age": "age",  # extra: the player's age that season
}

_ADVANCED = {
    "Rp9": "runs_scored_per9",
    "BABIP": "babip",
    "Kp9": "so_per9",
    "BBp9": "bb_per9",
    "HRp9": "hr_per9",
    "Hp9": "h_per9",
    "strikesoutsToWalks": "so_to_bb",
    "BqR": "bequeathed_runners",
    "BqRS": "bequeathed_runners_scored",
    "QS": "quality_starts",
    "GIDP_Opp": "gidp_opp",
    "SH_Fail": "sh_fail",  # extra (raw): sacrifice hits that failed
    "SH_Missed": "sh_missed",  # extra (raw): sacrifice hits missed
    "Swings": "total_swings",
    "SwingMiss": "swing_and_misses",
    "BIP": "balls_in_play",
    "RS": "run_support",
    "PpInn": "pitches_per_inning",
    "PpPA": "pitches_per_pa",
    "BBpPA": "walks_per_pa",
    "KPpA": "so_per_pa",
    "BBpK": "bb_per_so",
    "ISO": "iso",
    "FOuts": "fly_outs",
    "POuts": "pop_outs",
    "LOuts": "line_outs",
    "FH": "fly_hits",
    "PH": "pop_hits",
    "LH": "line_hits",
    "GH": "ground_hits",
}

_SABERMETRIC = {
    "FIP": "fip",
    "xFIP": "xfip",
    "FIPminus": "fip_minus",
    "RA9WAR": "ra9_war",
    "RAR": "rar",
    "WAR": "war",
    "SD": "sd",
    "MD": "md",
    "pLI": "p_li",
    "inLI": "in_li",
    "gmLI": "gm_li",
    "exLI": "ex_li",
    "ERAminus": "era_minus",
}

# Columns stored as floats; the proxy sends them as strings and they need parsing.
_FLOAT_COLUMNS = {
    "ip",
    "era",
    "avg",
    "obp",
    "slg",
    "ops",
    "sb_pct",
    "strike_pct",
    "whip",
    "win_pct",
    "r_per9",
    "runs_scored_per9",
    "babip",
    "so_per9",
    "bb_per9",
    "hr_per9",
    "h_per9",
    "so_to_bb",
    "pitches_per_inning",
    "pitches_per_pa",
    "walks_per_pa",
    "so_per_pa",
    "bb_per_so",
    "iso",
    "fip",
    "xfip",
    "fip_minus",
    "ra9_war",
    "rar",
    "war",
    "p_li",
    "in_li",
    "gm_li",
    "ex_li",
    "era_minus",
}


def _to_float(value: str | int | float | None) -> float | None:
    """Parse a proxy rate value; the undefined-rate placeholders become NULL, not 0."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(value.strip())
    except ValueError:
        return None


def _pick(stat: dict[str, Any], keys: dict[str, str]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, column in keys.items():
        value = stat.get(key)
        out[column] = _to_float(value) if column in _FLOAT_COLUMNS else value
    return out


def map_regular(stat: dict[str, Any]) -> dict[str, Any]:
    return _pick(stat, _REGULAR)


def map_advanced(stat: dict[str, Any]) -> dict[str, Any]:
    return _pick(stat, _ADVANCED)


def map_sabermetrics(stat: dict[str, Any]) -> dict[str, Any]:
    return _pick(stat, _SABERMETRIC)


def _sub(*values: int | None) -> int | None:
    known = [v for v in values if v is not None]
    if len(known) != len(values):
        return None
    first, *rest = known
    return first - sum(rest)


def derive_pitching(c: dict[str, Any]) -> dict[str, Any]:
    """The two derived counts and the one mlbstats formula, from the mapped counting stats."""
    h, bf, bb, hbp, sh, sf, ci = (
        c.get("h"),
        c.get("bf"),
        c.get("bb"),
        c.get("hbp"),
        c.get("sh"),
        c.get("sf"),
        c.get("catcher_int"),
    )
    at_bats_against = _sub(bf, bb, hbp, sh, sf, ci)

    baa = None
    if h is not None and at_bats_against:
        baa = h / at_bats_against

    return {
        "x1b": _sub(h, c.get("x2b"), c.get("x3b"), c.get("hr")),
        "nibb": _sub(bb, c.get("ibb")),
        "baa": baa,
        # The batted-ball profile of what was hit against him — same formulas as batting, shared so
        # the two groups can never drift apart.
        **batted_ball_coefficients(c),
    }
