"""Tests for translating proxy payloads into `Batting` fields (Fase 3).

The proxy renames the upstream fields (`strikeOuts` -> `K`, `doubles` -> `X2B`), and the source
table adds a few columns MLB does not send (`X1B`, `XBH`, `NIBB` are derived). Every key here
was read from a real proxy response, not guessed.
"""

from dglweb.stats.mapping import map_advanced, map_regular, map_sabermetrics

# Trimmed from a real /people/134181 yearByYear response (Beltré, 1998).
REGULAR = {
    "age": 19,
    "G": 77,
    "GOuts": 57,
    "AOuts": 59,
    "R": 18,
    "X2B": 9,
    "X3B": 0,
    "HR": 7,
    "K": 37,
    "BB": 14,
    "IBB": 2,
    "H": 42,
    "HBP": 3,
    "AVG": ".215",
    "AB": 195,
    "OBP": ".278",
    "SLG": ".369",
    "OPS": ".647",
    "CS": 1,
    "SB": 3,
    "GIDP": 4,
    "Pitches": 737,
    "PA": 214,
    "TB": 72,
    "RBI": 22,
    "LOB": 81,
    "SH": 2,
    "SF": 0,
    "CI": 0,
}

ADVANCED = {
    "age": 19,
    "PA": 214,
    "TB": 72,
    "LOB": 81,
    "SH": 2,
    "SF": 0,
    "XH": 16,
    "HBP": 3,
    "Pitches": 737,
    "ROE": 4,
    "WO": 1,
    "FOuts": 25,
    "Swings": 500,
    "SwingMiss": 90,
    "BIP": 150,
    "POuts": 10,
    "LOuts": 12,
    "GOuts": 57,
    "FH": 8,
    "PH": 1,
    "LH": 20,
    "GH": 13,
}

SABERMETRICS = {
    "wOBA": 0.423469,
    "wRAA": 51.9439,
    "wRC": 133.402,
    "wRCPlus": 161.043,
    "RAR": 99.4052,
    "WAR": 9.67698,
    "batting": 51.6994,
    "fielding": 25.4623,
    "baseRunning": -2.21371,
    "positional": 2.30338,
    "wLeague": 1.76695,
    "replacement": 20.3869,
    "SPD": 2.98272,
    "UBR": -1.39999985694885,
    "wGDP": -1.2,
    "wSB": 0.38628,
}


def test_strikeouts_keep_our_column_name() -> None:
    """The proxy calls them `K`; the source table (and every Dominican fan) calls them SO."""
    assert map_regular(REGULAR)["so"] == 37


def test_counting_stats_are_copied_across() -> None:
    mapped = map_regular(REGULAR)

    assert mapped["g"] == 77
    assert mapped["ab"] == 195
    assert mapped["hr"] == 7
    assert mapped["rbi"] == 22
    assert mapped["air_outs"] == 59  # AOuts
    assert mapped["catcher_int"] == 0  # CI


def test_the_derived_counting_columns_are_computed() -> None:
    """MLB does not send singles, extra-base hits or non-intentional walks."""
    mapped = map_regular(REGULAR)

    assert mapped["x1b"] == 42 - 9 - 0 - 7  # H - 2B - 3B - HR
    assert mapped["xbh"] == 9 + 0 + 7
    assert mapped["nibb"] == 14 - 2  # BB - IBB


def test_a_missing_stat_becomes_null_not_zero() -> None:
    """1950 has no swing data. Absent must stay absent — 0 would be a lie."""
    mapped = map_regular({"G": 100, "AB": 350, "H": 90})

    assert mapped["pitches"] is None
    assert mapped["hr"] is None


def test_derived_columns_are_null_when_their_inputs_are_missing() -> None:
    mapped = map_regular({"G": 100, "H": 90})

    assert mapped["x1b"] is None
    assert mapped["nibb"] is None


def test_advanced_batted_ball_and_swing_columns() -> None:
    mapped = map_advanced(ADVANCED)

    assert mapped["total_swings"] == 500
    assert mapped["swing_and_misses"] == 90
    assert mapped["balls_in_play"] == 150
    assert mapped["walk_offs"] == 1
    assert mapped["ground_outs"] == 57
    assert mapped["fly_outs"] == 25
    assert mapped["pop_outs"] == 10
    assert mapped["line_outs"] == 12
    assert mapped["fly_hits"] == 8
    assert mapped["pop_hits"] == 1
    assert mapped["line_hits"] == 20
    assert mapped["ground_hits"] == 13


def test_advanced_is_null_for_eras_without_the_data() -> None:
    mapped = map_advanced({"PA": 214, "TB": 72})

    assert mapped["total_swings"] is None
    assert mapped["walk_offs"] is None


def test_sabermetrics_are_mapped_including_the_renamed_ones() -> None:
    mapped = map_sabermetrics(SABERMETRICS)

    assert mapped["war"] == 9.67698
    assert mapped["w_rc_plus"] == 161.043
    assert mapped["woba"] == 0.423469
    assert mapped["positional_adj"] == 2.30338  # `positional` upstream
    assert mapped["base_running"] == -2.21371
    assert mapped["w_gdp"] == -1.2
    assert mapped["replacement"] == 20.3869


def test_sabermetrics_missing_for_old_seasons() -> None:
    assert map_sabermetrics({})["war"] is None
