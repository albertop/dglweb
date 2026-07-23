"""Career totals with subtotals: per team, per league, per position, grand total, sort order."""

import pytest
from django.core.management import call_command

from dglweb.players.models import Player
from dglweb.stats.career_totals import build_career_totals
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    CareerLevel,
    Fielding,
    FieldingCareer,
    IngestRun,
    Pitching,
    PitchingCareer,
)
from tests.test_players import _other_player


def _player(pid: int, dgl: str) -> Player:
    return Player.objects.create(**_other_player(player_id=pid, dgl_id=dgl))


@pytest.fixture
def batter(db: None) -> Player:
    """A batter who played two AL teams and one NL team, across seasons (incl. one pre-1956)."""
    player = _player(1, "a01")
    Batting.objects.create(player=player, season=1950, stint=1, team="BOS", league="AL", h=100, ab=300, pa=330)
    Batting.objects.create(player=player, season=2019, stint=1, team="NYA", league="AL", h=90, ab=300, pa=330)
    Batting.objects.create(player=player, season=2020, stint=1, team="LAN", league="NL", h=80, ab=200, pa=220)
    return player


@pytest.mark.django_db
def test_grand_total_sums_all_seasons(batter: Player) -> None:
    build_career_totals()

    total = BattingCareer.objects.get(player=batter, level=CareerLevel.TOTAL)
    assert (total.h, total.ab) == (270, 800)  # includes the 1950 season
    assert total.avg is not None
    assert round(total.avg, 4) == round(270 / 800, 4)  # recomputed on the summed components
    assert total.team is None and total.league is None


@pytest.mark.django_db
def test_team_and_league_subtotals(batter: Player) -> None:
    build_career_totals()

    teams = {row.team: row.h for row in BattingCareer.objects.filter(player=batter, level=CareerLevel.TEAM)}
    assert teams == {"BOS": 100, "NYA": 90, "LAN": 80}

    leagues = {row.league: row.h for row in BattingCareer.objects.filter(player=batter, level=CareerLevel.LEAGUE)}
    assert leagues == {"AL": 190, "NL": 80}  # AL = BOS + NYA


@pytest.mark.django_db
def test_sort_order_is_teams_by_pa_then_leagues_then_total(batter: Player) -> None:
    build_career_totals()

    ordered = list(BattingCareer.objects.filter(player=batter).order_by("sort_order"))
    labels = [(row.level, row.team or row.league or "—") for row in ordered]
    # teams first (BOS/NYA at 330 PA before LAN at 220), then leagues (AL 660 before NL 220), then total.
    assert labels == [
        ("team", "BOS"),
        ("team", "NYA"),
        ("team", "LAN"),
        ("league", "AL"),
        ("league", "NL"),
        ("total", "—"),
    ]


@pytest.mark.django_db
def test_traded_season_subtotals_reconcile_with_the_grand_total() -> None:
    """Team subtotals use the per-team rows (not the XXX combined), and still sum to the total."""
    player = _player(2, "b01")
    Batting.objects.create(player=player, season=2019, stint=1, team="BOS", league="AL", h=50, ab=150, pa=165)
    Batting.objects.create(player=player, season=2019, stint=2, team="NYA", league="AL", h=40, ab=150, pa=165)
    Batting.objects.create(player=player, season=2019, stint=3, team="XXX", league="XX", h=90, ab=300, pa=330)

    build_career_totals()

    assert BattingCareer.objects.get(player=player, level=CareerLevel.TOTAL).h == 90  # the XXX combined
    teams = {row.team: row.h for row in BattingCareer.objects.filter(player=player, level=CareerLevel.TEAM)}
    assert teams == {"BOS": 50, "NYA": 40}  # 50 + 40 == 90
    assert BattingCareer.objects.get(player=player, level=CareerLevel.LEAGUE, league="AL").h == 90


@pytest.mark.django_db
def test_pitching_career_total_recomputes_era() -> None:
    player = _player(1, "a01")
    Pitching.objects.create(player=player, season=2018, stint=1, team="BOS", league="AL", er=50, outs=486, bf=700)
    Pitching.objects.create(player=player, season=2019, stint=1, team="BOS", league="AL", er=40, outs=486, bf=700)

    build_career_totals()

    total = PitchingCareer.objects.get(player=player, level=CareerLevel.TOTAL)
    assert (total.er, total.outs) == (90, 972)
    assert total.era is not None
    assert round(total.era, 2) == 2.50
    assert PitchingCareer.objects.get(player=player, level=CareerLevel.TEAM, team="BOS").er == 90


@pytest.mark.django_db
def test_fielding_career_has_position_subtotals_then_total() -> None:
    player = _player(1, "a01")
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="LF", po=10, gp=50)
    Fielding.objects.create(player=player, season=2020, team="BOS", pos="LF", po=20, gp=60)
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="CF", po=5, gp=30)

    build_career_totals()

    assert FieldingCareer.objects.get(player=player, level=CareerLevel.POSITION, pos="LF").po == 30
    assert FieldingCareer.objects.get(player=player, level=CareerLevel.POSITION, pos="CF").po == 5
    assert FieldingCareer.objects.get(player=player, level=CareerLevel.TOTAL).po == 35  # across positions

    ordered = list(FieldingCareer.objects.filter(player=player).order_by("sort_order"))
    labels = [(row.level, row.pos or "—") for row in ordered]
    assert labels == [("pos", "LF"), ("pos", "CF"), ("total", "—")]  # positions by G (LF 110 > CF 30), then total


@pytest.mark.django_db
def test_build_career_totals_command_is_recorded_in_the_ingest_log(batter: Player) -> None:
    call_command("build_career_totals")

    run = IngestRun.objects.get(command="build_career_totals")
    assert run.status == IngestRun.Status.SUCCESS
