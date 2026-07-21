"""Tests for the league/team code mapping ported from the owner's R pipeline (Fase 3)."""

import pytest

from dglweb.stats.leagues import COMBINED_LEAGUE, COMBINED_TEAM, league_code, team_code


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("National League", "NL"),
        ("American League", "AL"),
        ("NL", "NL"),  # modern season splits already come abbreviated
        ("AL", "AL"),
        ("Federal League", "FL"),
        ("Players League", "PL"),
        ("Union Association", "UA"),
        ("American Association", "AA"),
    ],
)
def test_maps_the_recognised_leagues(name: str, expected: str) -> None:
    assert league_code(name) == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Negro National League (I)", "N1"),
        ("Negro National League (II)", "N2"),
        ("Negro American League", "NA"),
        ("American Negro League", "AN"),
        ("Eastern Colored League", "EN"),
        ("Negro East West League", "EW"),
        ("Negro Southern League", "SL"),
    ],
)
def test_maps_the_negro_leagues(name: str, expected: str) -> None:
    """Seven Dominicans in the master table played there; MLB counts those as major leagues."""
    assert league_code(name) == expected


def test_an_unknown_league_is_flagged_not_dropped() -> None:
    assert league_code("Liga Inventada") == "??"


def test_a_missing_league_is_flagged() -> None:
    assert league_code(None) == "??"
    assert league_code("") == "??"


def test_team_codes_are_uppercased_like_the_source_table() -> None:
    assert team_code("kca") == "KCA"
    assert team_code("lan") == "LAN"
    assert team_code(None) is None


def test_the_combined_row_sentinels_match_the_source() -> None:
    assert (COMBINED_TEAM, COMBINED_LEAGUE) == ("XXX", "XX")
