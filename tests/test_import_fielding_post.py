"""Tests for the postseason fielding loader commands (Fase 3)."""

from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from dglweb.mlb.client import MlbProxyError
from dglweb.players.models import Player
from dglweb.stats.models import FieldingPost, IngestRun
from tests.test_players import RECORD


def _row(**overrides: Any) -> dict[str, Any]:
    return {
        "player_id": RECORD["player_id"],
        "season": 2013,
        "round": "WS",
        "team": "BOS",
        "league": "AL",
        "pos": "SS",
        "po": 8,
        **overrides,
    }


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


@pytest.fixture
def fetched(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def fake_fetch(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        return [row for row in rows if row["season"] == season]

    monkeypatch.setattr("dglweb.stats.management.commands.import_fielding_post.fetch_season", fake_fetch)
    return rows


@pytest.mark.django_db
def test_loads_a_season_and_records_the_run(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.append(_row())

    call_command("import_fielding_post", "--season", "2013")

    assert FieldingPost.objects.get().po == 8
    assert IngestRun.objects.get().command == "import_fielding_post"


@pytest.mark.django_db
def test_two_positions_same_round_both_load(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.extend([_row(pos="SS"), _row(pos="2B")])

    call_command("import_fielding_post", "--season", "2013")

    assert FieldingPost.objects.count() == 2


@pytest.mark.django_db
def test_running_it_twice_updates_on_the_round_pos_key(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.append(_row(po=8))
    call_command("import_fielding_post", "--season", "2013")

    fetched[0] = _row(po=9)
    call_command("import_fielding_post", "--season", "2013")

    assert FieldingPost.objects.count() == 1
    assert FieldingPost.objects.get().po == 9


@pytest.mark.django_db
def test_a_failing_season_is_recorded_and_loud(player: Player, monkeypatch: pytest.MonkeyPatch) -> None:
    def flaky(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        if season == 2014:
            raise MlbProxyError("el proxy respondió HTTP 503")
        return [_row(season=season)]

    monkeypatch.setattr("dglweb.stats.management.commands.import_fielding_post.fetch_season", flaky)

    with pytest.raises(CommandError, match="bitácora"):
        call_command("import_fielding_post", "--from", "2013", "--to", "2015")

    assert sorted(FieldingPost.objects.values_list("season", flat=True)) == [2013, 2015]
    assert IngestRun.objects.get().status == IngestRun.Status.PARTIAL


@pytest.mark.django_db
def test_update_fielding_post_refreshes_the_current_season(player: Player, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dglweb.stats.management.commands.update_fielding_post.fetch_season",
        lambda client, season, player_ids: [_row(season=season)],
    )

    call_command("update_fielding_post", "--force")

    assert IngestRun.objects.get().command == "update_fielding_post"
    assert FieldingPost.objects.count() == 1
