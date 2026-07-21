"""Tests for the batting loader command (Fase 3)."""

from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from dglweb.mlb.client import MlbProxyError
from dglweb.players.models import Player
from dglweb.stats.models import Batting
from tests.test_players import RECORD


def _row(**overrides: Any) -> dict[str, Any]:
    return {
        "player_id": RECORD["player_id"],
        "season": 1988,
        "stint": 1,
        "team": "SLN",
        "league": "NL",
        "pos": "P",
        "g": 8,
        "ab": 2,
        "h": 1,
        **overrides,
    }


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


@pytest.fixture
def fetched(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """Replaces the network layer; the download itself is tested in test_batting_source."""
    rows: list[dict[str, Any]] = []

    def fake_fetch(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        return [row for row in rows if row["season"] == season]

    monkeypatch.setattr("dglweb.stats.management.commands.import_batting.fetch_season", fake_fetch)
    return rows


@pytest.mark.django_db
def test_loads_the_rows_of_one_season(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.append(_row())

    call_command("import_batting", "--season", "1988")

    assert Batting.objects.count() == 1
    assert Batting.objects.get().team == "SLN"


@pytest.mark.django_db
def test_running_it_twice_updates_instead_of_duplicating(player: Player, fetched: list[dict[str, Any]]) -> None:
    """The property that makes a retry safe after a failed night."""
    fetched.append(_row(h=1))
    call_command("import_batting", "--season", "1988")

    fetched[0] = _row(h=2)  # MLB corrected the line
    call_command("import_batting", "--season", "1988")

    assert Batting.objects.count() == 1
    assert Batting.objects.get().h == 2


@pytest.mark.django_db
def test_loads_a_range_of_seasons(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.extend([_row(season=1988), _row(season=1989), _row(season=1990)])

    call_command("import_batting", "--from", "1988", "--to", "1990")

    assert sorted(Batting.objects.values_list("season", flat=True)) == [1988, 1989, 1990]


@pytest.mark.django_db
def test_a_failing_season_does_not_stop_the_others(player: Player, monkeypatch: pytest.MonkeyPatch) -> None:
    def flaky(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        if season == 1989:
            raise MlbProxyError("el proxy respondió HTTP 503")
        return [_row(season=season)]

    monkeypatch.setattr("dglweb.stats.management.commands.import_batting.fetch_season", flaky)

    with pytest.raises(CommandError, match="1989"):
        call_command("import_batting", "--from", "1988", "--to", "1990")

    # The good seasons still landed, and the failure is loud.
    assert sorted(Batting.objects.values_list("season", flat=True)) == [1988, 1990]


@pytest.mark.django_db
def test_refuses_to_run_with_an_empty_master_table(fetched: list[dict[str, Any]]) -> None:
    with pytest.raises(CommandError, match="dgl_master"):
        call_command("import_batting", "--season", "1988")


@pytest.mark.django_db
def test_requires_a_season_or_a_range(player: Player, fetched: list[dict[str, Any]]) -> None:
    with pytest.raises(CommandError, match="--season"):
        call_command("import_batting")


@pytest.mark.django_db
def test_rejects_a_backwards_range(player: Player, fetched: list[dict[str, Any]]) -> None:
    with pytest.raises(CommandError, match="--from"):
        call_command("import_batting", "--from", "1990", "--to", "1988")


@pytest.mark.django_db
def test_a_season_with_no_dominicans_is_a_no_op(player: Player, fetched: list[dict[str, Any]]) -> None:
    call_command("import_batting", "--season", "1901")

    assert Batting.objects.count() == 0
