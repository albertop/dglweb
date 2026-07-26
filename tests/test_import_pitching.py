"""Tests for the pitching loader commands (Fase 3).

The shared flow (ingest/runlog/loader) is exercised by the batting command tests too; these
focus on the pitching wiring.
"""

from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from dglweb.mlb.client import MlbProxyError
from dglweb.players.models import Player
from dglweb.stats.models import IngestRun, Pitching
from tests.test_players import RECORD


def _row(**overrides: Any) -> dict[str, Any]:
    return {
        "player_id": RECORD["player_id"],
        "season": 2008,
        "stint": 1,
        "team": "PIT",
        "league": "NL",
        "g": 47,
        "so": 47,
        "era": 3.47,
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

    monkeypatch.setattr("dglweb.stats.management.commands.import_pitching.fetch_season", fake_fetch)
    return rows


@pytest.mark.django_db
def test_loads_a_season_and_records_the_run(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.append(_row())

    call_command("import_pitching", "--season", "2008")

    assert Pitching.objects.get().era == 3.47
    run = IngestRun.objects.get()
    assert run.command == "import_pitching"
    assert run.status == IngestRun.Status.SUCCESS
    assert run.rows_affected == 1


@pytest.mark.django_db
def test_running_it_twice_updates_instead_of_duplicating(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.append(_row(so=47))
    call_command("import_pitching", "--season", "2008")

    fetched[0] = _row(so=48)
    call_command("import_pitching", "--season", "2008")

    assert Pitching.objects.count() == 1
    assert Pitching.objects.get().so == 48


@pytest.mark.django_db
def test_a_failing_season_is_recorded_and_loud(player: Player, monkeypatch: pytest.MonkeyPatch) -> None:
    def flaky(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        if season == 2009:
            raise MlbProxyError("el proxy respondió HTTP 503")
        return [_row(season=season)]

    monkeypatch.setattr("dglweb.stats.management.commands.import_pitching.fetch_season", flaky)

    with pytest.raises(CommandError, match="bitácora"):
        call_command("import_pitching", "--from", "2008", "--to", "2010")

    assert sorted(Pitching.objects.values_list("season", flat=True)) == [2008, 2010]
    assert IngestRun.objects.get().status == IngestRun.Status.PARTIAL


@pytest.mark.django_db
def test_update_pitching_refreshes_the_current_season(player: Player, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_fetch(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        return [_row(season=season)]

    monkeypatch.setattr("dglweb.stats.management.commands.update_pitching.fetch_season", fake_fetch)

    call_command("update_pitching", "--force")

    run = IngestRun.objects.get()
    assert run.command == "update_pitching"
    assert "temporada actual" in run.scope
    assert Pitching.objects.count() == 1
