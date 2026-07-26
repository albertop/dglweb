"""Tests for the postseason pitching loader commands (Fase 3)."""

from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from dglweb.mlb.client import MlbProxyError
from dglweb.players.models import Player
from dglweb.stats.models import IngestRun, PitchingPost
from tests.test_players import RECORD


def _row(**overrides: Any) -> dict[str, Any]:
    return {
        "player_id": RECORD["player_id"],
        "season": 2013,
        "round": "WS",
        "team": "BOS",
        "league": "AL",
        "so": 7,
        "era": 0.0,
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

    monkeypatch.setattr("dglweb.stats.management.commands.import_pitching_post.fetch_season", fake_fetch)
    return rows


@pytest.mark.django_db
def test_loads_a_season_and_records_the_run(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.append(_row())

    call_command("import_pitching_post", "--season", "2013")

    assert PitchingPost.objects.get().so == 7
    assert IngestRun.objects.get().command == "import_pitching_post"


@pytest.mark.django_db
def test_several_rounds_load(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.extend([_row(round="DS"), _row(round="LCS"), _row(round="WS")])

    call_command("import_pitching_post", "--season", "2013")

    assert PitchingPost.objects.count() == 3


@pytest.mark.django_db
def test_running_it_twice_updates_on_the_round_key(player: Player, fetched: list[dict[str, Any]]) -> None:
    fetched.append(_row(so=7))
    call_command("import_pitching_post", "--season", "2013")

    fetched[0] = _row(so=8)
    call_command("import_pitching_post", "--season", "2013")

    assert PitchingPost.objects.count() == 1
    assert PitchingPost.objects.get().so == 8


@pytest.mark.django_db
def test_a_failing_season_is_recorded_and_loud(player: Player, monkeypatch: pytest.MonkeyPatch) -> None:
    def flaky(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        if season == 2014:
            raise MlbProxyError("el proxy respondió HTTP 503")
        return [_row(season=season)]

    monkeypatch.setattr("dglweb.stats.management.commands.import_pitching_post.fetch_season", flaky)

    with pytest.raises(CommandError, match="bitácora"):
        call_command("import_pitching_post", "--from", "2013", "--to", "2015")

    assert sorted(PitchingPost.objects.values_list("season", flat=True)) == [2013, 2015]
    assert IngestRun.objects.get().status == IngestRun.Status.PARTIAL


@pytest.mark.django_db
def test_update_pitching_post_refreshes_the_current_season(player: Player, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "dglweb.stats.management.commands.update_pitching_post.fetch_season",
        lambda client, season, player_ids: [_row(season=season)],
    )

    call_command("update_pitching_post", "--force")

    assert IngestRun.objects.get().command == "update_pitching_post"
    assert PitchingPost.objects.count() == 1
