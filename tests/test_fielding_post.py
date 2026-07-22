"""Tests for the postseason fielding table (Fase 3) — the last piece of the phase.

Source `dbo.mlbFieldingPost` (24 columns). The simplest table: per position per round, no XXX, no
UZR (the post script fetches only `season`, not sabermetrics), no stolen-bases/caught-stealing.
Keyed by (player, season, round, pos); verified 0 duplicates, 0 XXX rows.
"""

from typing import Any

import pytest
from django.db import IntegrityError, models

from dglweb.players.models import Player
from dglweb.stats.fielding_post_source import fetch_season
from dglweb.stats.models import FieldingPost
from tests.test_players import RECORD

EXPECTED_FIELDS = (
    "player",
    "season",
    "round",
    "team",
    "league",
    "pos",
    "gp",
    "gs",
    "a",
    "po",
    "e",
    "chances",
    "fld_pct",
    "rf_per_g",
    "rf_per9",
    "innings",
    "innings_outs",
    "double_plays",
    "triple_plays",
    "throwing_errors",
    "passed_balls",
    "catcher_era",
    "catcher_int",
    "wild_pitches",
    "pickoffs",
)

ROW: dict[str, object] = {"season": 2013, "round": "WS", "team": "BOS", "league": "AL", "pos": "SS", "po": 8}


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


def test_has_every_source_column_in_order() -> None:
    ours = tuple(f.name for f in FieldingPost._meta.get_fields() if f.name != "id")

    assert ours == EXPECTED_FIELDS


def test_uses_the_agreed_table_name() -> None:
    assert FieldingPost._meta.db_table == "mlb_fielding_post"


@pytest.mark.django_db
def test_a_player_can_field_several_positions_in_a_round(player: Player) -> None:
    FieldingPost.objects.create(player=player, **{**ROW, "pos": "SS"})
    FieldingPost.objects.create(player=player, **{**ROW, "pos": "2B"})

    assert player.fielding_post_seasons.count() == 2


@pytest.mark.django_db
def test_the_key_is_player_season_round_pos(player: Player) -> None:
    FieldingPost.objects.create(player=player, **ROW)

    with pytest.raises(IntegrityError):
        FieldingPost.objects.create(player=player, **ROW)


def test_only_the_natural_key_is_required() -> None:
    required = {
        f.name for f in FieldingPost._meta.get_fields() if isinstance(f, models.Field) and not f.null and f.name != "id"
    }

    assert required == {"player", "season", "round", "pos"}


# --- download --------------------------------------------------------------------------

TEAMS = {"teams": [{"id": 111, "teamCode": "bos", "name": "Boston Red Sox"}]}
AL = {"id": 103, "name": "AL"}
PID = 120074


def _pos_split(pos: str, **kwargs: Any) -> dict[str, Any]:
    return {"season": "2013", "position": {"abbreviation": pos}, **kwargs}


class FakeClient:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self._responses = responses
        self.game_types: list[str] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        if path == "/api/v1/teams":
            return TEAMS
        game_type = str(params.get("gameType") or "")
        self.game_types.append(game_type)
        return self._responses.get(game_type, {"stats": [{"splits": []}]})


# WS 2013: two positions (SS and 2B), one team, one round.
RESPONSES = {
    "W": {
        "stats": [
            {
                "splits": [
                    _pos_split(
                        "SS",
                        stat={"G": 6, "PO": 8, "A": 15, "E": 1, "INN": "50.1"},
                        team={"id": 111},
                        league=AL,
                        player={"id": PID},
                        numTeams=1,
                    ),
                    _pos_split(
                        "2B",
                        stat={"G": 2, "PO": 3, "A": 4, "E": 0, "INN": "12.0"},
                        team={"id": 111},
                        league=AL,
                        player={"id": PID},
                        numTeams=1,
                    ),
                ]
            }
        ]
    }
}


def test_one_row_per_position_per_round() -> None:
    rows = fetch_season(FakeClient(RESPONSES), 2013, {PID})  # type: ignore[arg-type]

    by_pos = {(r["round"], r["pos"]): r for r in rows}
    assert set(by_pos) == {("WS", "SS"), ("WS", "2B")}
    assert (by_pos[("WS", "SS")]["po"], by_pos[("WS", "SS")]["a"]) == (8, 15)
    assert by_pos[("WS", "SS")]["team"] == "BOS"


def test_innings_outs_is_computed() -> None:
    ss = next(r for r in fetch_season(FakeClient(RESPONSES), 2013, {PID}) if r["pos"] == "SS")  # type: ignore[arg-type]

    assert ss["innings_outs"] == 50 * 3 + 1  # 50.1 innings -> 151 outs


def test_all_four_rounds_are_queried() -> None:
    client = FakeClient(RESPONSES)

    fetch_season(client, 2013, {PID})  # type: ignore[arg-type]

    assert set(client.game_types) == {"D", "F", "L", "W"}
