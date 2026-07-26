"""Tests for the scheduled current-season refresh (Fase 3)."""

from typing import Any

import pytest
from django.core.management import call_command
from django.utils import timezone

from dglweb.players.models import Player
from dglweb.stats.models import Batting, IngestRun
from tests.test_players import RECORD


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


@pytest.fixture
def seen_seasons(monkeypatch: pytest.MonkeyPatch) -> list[int]:
    """Capture which season the command asked for, and feed back one row."""
    asked: list[int] = []

    def fake_fetch(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        asked.append(season)
        return [{"player_id": RECORD["player_id"], "season": season, "stint": 1, "g": 1}]

    monkeypatch.setattr("dglweb.stats.management.commands.update_batting.fetch_season", fake_fetch)
    return asked


@pytest.mark.django_db
def test_refreshes_the_current_season(player: Player, seen_seasons: list[int]) -> None:
    call_command("update_batting", "--force")

    current_year = timezone.now().year
    assert seen_seasons == [current_year]
    assert Batting.objects.filter(season=current_year).count() == 1


@pytest.mark.django_db
def test_records_the_run(player: Player, seen_seasons: list[int]) -> None:
    call_command("update_batting", "--force")

    run = IngestRun.objects.get()
    assert run.command == "update_batting"
    assert str(timezone.now().year) in run.scope
    assert run.status == IngestRun.Status.SUCCESS
    assert run.rows_affected == 1


@pytest.mark.django_db
def test_refuses_with_an_empty_master_table(seen_seasons: list[int]) -> None:
    from django.core.management.base import CommandError

    with pytest.raises(CommandError, match="dgl_master"):
        call_command("update_batting", "--force")
