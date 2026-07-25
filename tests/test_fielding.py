"""Tests for the fielding table and its mapping/download (Fase 3).

Fielding is keyed by (player, season, team, pos) — not stint — because it is per position, and
the source's stint counter carries duplicate rows we drop (owner's decision). Values checked
against real proxy responses (Héctor Luna 2006, a traded multi-position player).
"""

from typing import Any

import pytest
from django.db import IntegrityError, models

from dglweb.players.models import Player
from dglweb.stats.fielding_mapping import map_fielding
from dglweb.stats.fielding_source import fetch_season
from dglweb.stats.models import Fielding
from tests.test_players import RECORD

LINE: dict[str, object] = {"season": 2006, "team": "SLN", "league": "NL", "pos": "2B", "gp": 41}


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


# --- model -----------------------------------------------------------------------------


def test_uses_the_agreed_table_name() -> None:
    assert Fielding._meta.db_table == "mlb_fielding"


@pytest.mark.django_db
def test_a_player_can_field_several_positions_in_one_season(player: Player) -> None:
    Fielding.objects.create(player=player, **{**LINE, "pos": "2B"})
    Fielding.objects.create(player=player, **{**LINE, "pos": "SS"})

    assert player.fielding_seasons.count() == 2


@pytest.mark.django_db
def test_the_natural_key_is_player_season_team_pos(player: Player) -> None:
    Fielding.objects.create(player=player, **LINE)

    with pytest.raises(IntegrityError):
        Fielding.objects.create(player=player, **LINE)


@pytest.mark.django_db
def test_same_position_can_repeat_across_teams_and_the_xxx_total(player: Player) -> None:
    Fielding.objects.create(player=player, **{**LINE, "team": "SLN", "pos": "2B"})
    Fielding.objects.create(player=player, **{**LINE, "team": "CLE", "pos": "2B"})
    Fielding.objects.create(player=player, **{**LINE, "team": "XXX", "league": "XX", "pos": "2B"})

    assert player.fielding_seasons.filter(pos="2B").count() == 3


def test_only_the_key_is_required() -> None:
    required = {
        f.name
        for f in Fielding._meta.get_fields()
        if isinstance(f, models.Field) and not f.null and f.name not in {"id", "pk"}
    }

    assert required == {"player", "season", "team", "pos"}


# --- mapping (no formulas; rate lines come from the proxy as strings) -------------------


def test_maps_the_fielding_stat_keys() -> None:
    mapped = map_fielding({"G": 61, "A": 144, "PO": 108, "E": 9, "TC": 261, "INN": "469.2", "DP": 20})

    assert mapped["gp"] == 61
    assert mapped["a"] == 144
    assert mapped["chances"] == 261  # TC
    assert mapped["throwing_errors"] is None  # ThrE absent -> NULL
    assert mapped["double_plays"] == 20


def test_rate_lines_are_parsed_to_float() -> None:
    mapped = map_fielding({"fielding": ".978", "RFpG": "4.55", "INN": "469.2"})

    assert mapped["fld_pct"] == 0.978
    assert mapped["rf_per_g"] == 4.55
    assert mapped["innings"] == 469.2  # baseball notation kept


def test_catcher_only_keys_map_and_are_null_for_others() -> None:
    catcher = map_fielding({"passedBall": 5, "catcherERA": "3.90", "SB": 36, "CS": 11, "PKO": 3})
    assert catcher["passed_balls"] == 5
    assert catcher["catcher_era"] == 3.90
    assert catcher["stolen_bases"] == 36

    infielder = map_fielding({"G": 10, "A": 20})
    assert infielder["passed_balls"] is None
    assert infielder["catcher_era"] is None


# --- download --------------------------------------------------------------------------

TEAMS = {
    "teams": [
        {"id": 138, "teamCode": "sln", "name": "St. Louis Cardinals"},
        {"id": 114, "teamCode": "cle", "name": "Cleveland Indians"},
    ]
}
NL = {"id": 104, "name": "NL"}
AL = {"id": 103, "name": "AL"}


def _split(**kwargs: Any) -> dict[str, Any]:
    return {"season": "2006", **kwargs}


def _pos_split(pos: str, **kwargs: Any) -> dict[str, Any]:
    return _split(position={"abbreviation": pos}, **kwargs)


class FakeClient:
    def __init__(self, responses: dict[tuple[str, str], dict[str, Any]]) -> None:
        self._responses = responses

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        key = str(params.get("stats") or "")
        if not key and "hydrate" in params:
            key = str(params["hydrate"]).split("type=[")[1].split("]")[0]
        return self._responses.get((path, key), {})


# Luna 2006: 2B with both teams (combined + per-team), 1B with SLN only.
RESPONSES = {
    ("/api/v1/teams", ""): TEAMS,
    ("/api/v1/stats", "season"): {
        "stats": [
            {
                "splits": [
                    _pos_split(
                        "2B", stat={"G": 61, "PO": 108}, team={"id": 114}, league=AL, player={"id": 425659}, numTeams=2
                    ),
                    _pos_split(
                        "1B", stat={"G": 6, "PO": 25}, team={"id": 138}, league=NL, player={"id": 425659}, numTeams=1
                    ),
                ]
            }
        ]
    },
    ("/api/v1/stats", "sabermetrics"): {
        "stats": [
            {
                "splits": [
                    _pos_split("2B", stat={"UZR": -3.32}, team={"id": 114}, player={"id": 425659}, numTeams=2),
                    _pos_split("1B", stat={"UZR": 0.39}, team={"id": 138}, player={"id": 425659}, numTeams=1),
                ]
            }
        ]
    },
    ("/api/v1/people/425659", "season"): {
        "people": [
            {
                "stats": [
                    {
                        "splits": [
                            _pos_split("2B", stat={"G": 61, "PO": 108}),  # combined, no team -> skipped
                            _pos_split("2B", stat={"G": 20, "PO": 39}, team={"id": 114}, league=AL),
                            _pos_split("2B", stat={"G": 41, "PO": 69}, team={"id": 138}, league=NL),
                        ]
                    }
                ]
            }
        ]
    },
}


def test_a_traded_position_yields_the_xxx_total_plus_per_team_rows() -> None:
    rows = fetch_season(FakeClient(RESPONSES), 2006, {425659})  # type: ignore[arg-type]

    two_b = sorted((r["team"], r["gp"]) for r in rows if r["pos"] == "2B")
    assert two_b == [("CLE", 20), ("SLN", 41), ("XXX", 61)]


def test_uzr_lands_only_on_the_season_total_row() -> None:
    rows = fetch_season(FakeClient(RESPONSES), 2006, {425659})  # type: ignore[arg-type]

    by = {(r["pos"], r["team"]): r for r in rows}
    assert by[("2B", "XXX")]["uzr"] == -3.32  # total gets UZR
    assert by[("2B", "SLN")]["uzr"] is None  # per-team split does not
    assert by[("1B", "SLN")]["uzr"] == 0.39  # single-team: its own row is the total


def test_a_single_team_position_is_one_row_no_xxx() -> None:
    rows = fetch_season(FakeClient(RESPONSES), 2006, {425659})  # type: ignore[arg-type]

    first_base = [r for r in rows if r["pos"] == "1B"]
    assert len(first_base) == 1
    assert (first_base[0]["team"], first_base[0]["league"]) == ("SLN", "NL")


def test_players_outside_the_master_table_are_ignored() -> None:
    assert fetch_season(FakeClient(RESPONSES), 2006, {999999}) == []  # type: ignore[arg-type]


def test_innings_convert_to_a_summable_outs_column() -> None:
    """The FIX-5 guardrail: .1/.2 are outs, so innings must not be summed as decimals."""
    assert map_fielding({"INN": "111.1"})["innings_outs"] == 111 * 3 + 1  # 334
    assert map_fielding({"INN": "469.2"})["innings_outs"] == 469 * 3 + 2  # 1409
    assert map_fielding({"INN": "111.0"})["innings_outs"] == 333
    assert map_fielding({"INN": "9"})["innings_outs"] == 27
    assert map_fielding({})["innings_outs"] is None


def test_impossible_innings_fractions_are_rejected_not_guessed() -> None:
    """Review v4 DEV-04: `.1`/`.2` son los únicos outs válidos; `.3`, `.9`, `.25` o basura no existen
    en notación beisbolera y deben dar None, no un outs plausible-pero-falso."""
    assert map_fielding({"INN": "111.3"})["innings_outs"] is None  # .3 sería una entrada completa
    assert map_fielding({"INN": "111.9"})["innings_outs"] is None
    assert map_fielding({"INN": "111.25"})["innings_outs"] is None  # antes truncaba a .2 en silencio
    assert map_fielding({"INN": "abc"})["innings_outs"] is None
    assert map_fielding({"INN": "111.1.2"})["innings_outs"] is None
