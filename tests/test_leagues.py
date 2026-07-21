"""Tests for the league/team code mapping ported from the owner's R pipeline (Fase 3).

Every id and spelling below was read from the live proxy, not guessed.
"""

from typing import Any

import pytest

from dglweb.stats.leagues import COMBINED_LEAGUE, COMBINED_TEAM, league_code, team_code


@pytest.mark.parametrize(
    ("league_id", "expected"),
    [
        (103, "AL"),
        (104, "NL"),
        (100, "AA"),
        (101, "UA"),
        (105, "PL"),
        (106, "FL"),
    ],
)
def test_maps_the_recognised_leagues_by_id(league_id: int, expected: str) -> None:
    assert league_code({"id": league_id}) == expected


@pytest.mark.parametrize(
    ("league_id", "expected"),
    [
        (426, "AN"),
        (427, "EN"),
        (428, "NA"),
        (429, "EW"),
        (430, "N1"),
        (431, "N2"),
        (432, "SL"),
    ],
)
def test_maps_the_negro_leagues_by_id(league_id: int, expected: str) -> None:
    """Seven Dominicans played there; MLB counts these as major leagues since 2020."""
    assert league_code({"id": league_id}) == expected


def test_the_id_wins_over_the_abbreviation() -> None:
    """MLB spells the same league three ways; the id is the only stable one."""
    real_split_league = {"id": 431, "name": "NN2", "link": "/api/v1/league/431"}

    assert league_code(real_split_league) == "N2"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("NN2", "N2"),  # stats splits
        ("Negro National League (II)", "N2"),  # /league endpoint
        ("ECL", "EN"),
        ("NAL", "NA"),
        ("NNL", "N1"),
        ("National League", "NL"),
    ],
)
def test_falls_back_to_the_text_when_there_is_no_id(text: str, expected: str) -> None:
    assert league_code({"name": text}) == expected


def test_an_unknown_league_is_flagged_not_dropped() -> None:
    assert league_code({"id": 999, "name": "Liga Inventada"}) == "??"


def test_a_missing_league_is_flagged() -> None:
    assert league_code(None) == "??"
    assert league_code({}) == "??"


@pytest.mark.parametrize("payload", [{"id": None}, {"name": ""}, {"abbreviation": None}])
def test_empty_league_fields_do_not_crash(payload: dict[str, Any]) -> None:
    assert league_code(payload) == "??"


def test_team_codes_are_uppercased_like_the_source_table() -> None:
    assert team_code("kca") == "KCA"
    assert team_code("nyc") == "NYC"  # New York Cubans, where Tetelo Vargas played
    assert team_code("cse") == "CSE"  # Cuban Stars East
    assert team_code(None) is None


def test_the_combined_row_sentinels_match_the_source() -> None:
    assert (COMBINED_TEAM, COMBINED_LEAGUE) == ("XXX", "XX")
