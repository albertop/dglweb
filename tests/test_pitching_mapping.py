"""Tests for translating pitching proxy payloads into `Pitching` fields (Fase 3).

Keys were read from real proxy responses. Unlike batting, the pitching rate lines (ERA, WHIP,
AVG, IP…) come straight from the proxy — but as strings (".241", "46.2"), so they are parsed to
float. `X1B`/`NIBB` are derived and `BAA` uses the one mlbstats formula, verified against source.
"""

from dglweb.stats.pitching_mapping import (
    derive_pitching,
    map_advanced,
    map_regular,
    map_sabermetrics,
)

# Trimmed from a real /people/150122 season split (Dámaso Marte, 2008, Pittsburgh).
REGULAR = {
    "W": 4,
    "L": 2,
    "G": 47,
    "GP": 47,
    "GS": 0,
    "SV": 1,
    "BS": 2,
    "HLD": 15,
    "IP": "46.2",
    "H": 34,
    "R": 18,
    "HR": 3,
    "ER": 18,
    "ERA": "3.47",
    "BB": 21,
    "IBB": 4,
    "K": 47,
    "HBP": 2,
    "BF": 190,
    "X2B": 9,
    "X3B": 0,
    "AVG": ".205",
    "OBP": ".300",
    "SLG": ".350",
    "OPS": ".650",
    "SBpct": ".750",
    "Outs": 140,
    "GOuts": 57,
    "AOuts": 40,
    "Strikes": 480,
    "Strikepct": ".620",
    "CI": 0,
    "SH": 2,
    "SF": 1,
    "WHIP": "1.18",
    "Winpct": ".667",
    "Rp9": "3.47",
}

ADVANCED = {
    "Rp9": "3.47",
    "BABIP": ".280",
    "Kp9": "9.07",
    "BBp9": "4.05",
    "HRp9": "0.58",
    "Hp9": "6.56",
    "strikesoutsToWalks": "2.24",
    "BqR": 30,
    "BqRS": 10,
    "QS": 0,
    "GIDP_Opp": 40,
    "Swings": 500,
    "SwingMiss": 90,
    "BIP": 150,
    "RS": 12,
    "PpInn": "16.5",
    "PpPA": "3.9",
    "BBpPA": ".110",
    "KPpA": ".247",
    "BBpK": ".447",
    "ISO": ".145",
    "FOuts": 25,
    "POuts": 10,
    "LOuts": 12,
    "FH": 8,
    "PH": 1,
    "LH": 20,
    "GH": 13,
}

SABERMETRICS = {
    "FIP": "3.20",
    "xFIP": "3.55",
    "FIPminus": "78.0",
    "RA9WAR": "1.2",
    "RAR": "12.0",
    "WAR": "1.1",
    "SD": 20,
    "MD": 8,
    "pLI": "1.45",
    "inLI": "1.60",
    "gmLI": "1.50",
    "exLI": "1.40",
    "ERAminus": "80.0",
}


def test_strikeouts_and_blown_saves_get_our_column_names() -> None:
    mapped = map_regular(REGULAR)
    assert mapped["so"] == 47  # proxy calls them K
    assert mapped["bsv"] == 2  # proxy calls them BS


def test_string_rate_lines_are_parsed_to_float() -> None:
    mapped = map_regular(REGULAR)
    assert mapped["era"] == 3.47
    assert mapped["avg"] == 0.205
    assert mapped["whip"] == 1.18


def test_innings_pitched_keeps_the_baseball_notation() -> None:
    """46.2 is 46 innings and 2 outs, not a decimal — stored as the source stores it."""
    assert map_regular(REGULAR)["ip"] == 46.2


def test_counting_stats_land_in_the_right_columns() -> None:
    mapped = map_regular(REGULAR)
    assert mapped["ground_outs"] == 57  # GOuts
    assert mapped["air_outs"] == 40  # AOuts
    assert mapped["pitches"] is None or "pitches" in mapped


def test_unparseable_rate_placeholders_become_null() -> None:
    """The proxy sends '-.--' / '.---' for undefined rates; the source stores 0, we store NULL."""
    mapped = map_regular({"ERA": "-.--", "WHIP": ".---", "AVG": "-"})
    assert mapped["era"] is None
    assert mapped["whip"] is None
    assert mapped["avg"] is None


def test_advanced_uses_the_proxy_typo_key_for_so_to_bb() -> None:
    mapped = map_advanced(ADVANCED)
    assert mapped["so_to_bb"] == 2.24  # proxy key is the misspelled "strikesoutsToWalks"
    assert mapped["total_swings"] == 500  # Swings
    assert mapped["bequeathed_runners"] == 30  # BqR


def test_sabermetrics_are_mapped() -> None:
    mapped = map_sabermetrics(SABERMETRICS)
    assert mapped["fip"] == 3.20
    assert mapped["xfip"] == 3.55
    assert mapped["era_minus"] == 80.0
    assert mapped["war"] == 1.1


def test_derived_columns_and_baa() -> None:
    derived = derive_pitching({**map_regular(REGULAR)})
    assert derived["x1b"] == 34 - 9 - 0 - 3  # H - 2B - 3B - HR
    assert derived["nibb"] == 21 - 4  # BB - IBB
    # BAA = H / (BF - BB - HBP - SH - SF - CI) = 34 / (190 - 21 - 2 - 2 - 1 - 0)
    assert derived["baa"] == 34 / (190 - 21 - 2 - 2 - 1 - 0)


def test_baa_is_null_when_an_input_is_missing() -> None:
    assert derive_pitching({"h": 30, "bf": None})["baa"] is None


def test_missing_stats_are_null() -> None:
    mapped = map_regular({"W": 4})
    assert mapped["era"] is None
    assert mapped["so"] is None


def test_extra_fields_beyond_the_source_are_captured() -> None:
    regular = map_regular({"age": 30, "AB": 234})
    advanced = map_advanced({"SH_Fail": 1, "SH_Missed": 0})
    assert regular["age"] == 30
    assert regular["ab"] == 234  # at-bats against
    assert advanced["sh_fail"] == 1
    assert advanced["sh_missed"] == 0
