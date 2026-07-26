"""Tests for the fielding loader commands (Fase 3)."""

from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from dglweb.mlb.client import MlbProxyError
from dglweb.players.models import Player
from dglweb.stats.models import Fielding, IngestRun
from tests.test_players import RECORD


def _row(**overrides: Any) -> dict[str, Any]:
    return {
        "player_id": RECORD["player_id"],
        "season": 2006,
        "team": "SLN",
        "league": "NL",
        "pos": "2B",
        "gp": 41,
        "po": 69,
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

    monkeypatch.setattr("dglweb.stats.management.commands.import_fielding.fetch_season", fake_fetch)
    return rows


@pytest.mark.django_db
def test_loads_a_season_and_records_the_run(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.append(_row())

    call_command("import_fielding", "--season", "2006")

    assert Fielding.objects.get().po == 69
    run = IngestRun.objects.get()
    assert run.command == "import_fielding"
    assert run.status == IngestRun.Status.SUCCESS


@pytest.mark.django_db
def test_running_it_twice_updates_on_the_position_key(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.append(_row(po=69))
    call_command("import_fielding", "--season", "2006")

    fetched[0] = _row(po=70)  # corrected
    call_command("import_fielding", "--season", "2006")

    assert Fielding.objects.count() == 1
    assert Fielding.objects.get().po == 70


@pytest.mark.django_db
def test_two_positions_same_player_both_load(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.extend([_row(pos="2B"), _row(pos="SS")])

    call_command("import_fielding", "--season", "2006")

    assert Fielding.objects.count() == 2


@pytest.mark.django_db
def test_a_failing_season_is_recorded_and_loud(player: Player, monkeypatch: pytest.MonkeyPatch) -> None:
    def flaky(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        if season == 2007:
            raise MlbProxyError("el proxy respondió HTTP 503")
        return [_row(season=season)]

    monkeypatch.setattr("dglweb.stats.management.commands.import_fielding.fetch_season", flaky)

    with pytest.raises(CommandError, match="bitácora"):
        call_command("import_fielding", "--from", "2006", "--to", "2008")

    assert sorted(Fielding.objects.values_list("season", flat=True)) == [2006, 2008]
    assert IngestRun.objects.get().status == IngestRun.Status.PARTIAL


@pytest.mark.django_db
def test_update_fielding_refreshes_the_current_season(player: Player, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dglweb.stats.management.commands.update_fielding.fetch_season",
        lambda client, season, player_ids: [_row(season=season)],
    )

    call_command("update_fielding", "--force")

    assert IngestRun.objects.get().command == "update_fielding"
    assert Fielding.objects.count() == 1
