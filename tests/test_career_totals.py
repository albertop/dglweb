"""Materialized career totals: counting sums, rate recompute (exact/prorated), per-position, all seasons."""

import pytest
from django.core.management import call_command

from dglweb.players.models import Player
from dglweb.stats.career_totals import build_career_totals
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    Fielding,
    FieldingCareer,
    IngestRun,
    Pitching,
    PitchingCareer,
)
from tests.test_players import _other_player


def _player(pid: int, dgl: str) -> Player:
    return Player.objects.create(**_other_player(player_id=pid, dgl_id=dgl))


@pytest.mark.django_db
def test_batting_career_sums_counts_and_recomputes_avg_over_all_seasons() -> None:
    player = _player(1, "a01")
    Batting.objects.create(player=player, season=1950, stint=1, h=100, ab=300)  # pre-1956 counts for career
    Batting.objects.create(player=player, season=2000, stint=1, h=100, ab=200)

    build_career_totals()

    career = BattingCareer.objects.get(player=player)
    assert (career.h, career.ab) == (200, 500)
    assert career.avg is not None
    assert round(career.avg, 3) == 0.400  # sum(H)/sum(AB), via derive — not an average of AVGs


@pytest.mark.django_db
def test_pitching_career_recomputes_era_from_summed_components() -> None:
    player = _player(1, "a01")
    Pitching.objects.create(player=player, season=2018, stint=1, er=50, outs=486)
    Pitching.objects.create(player=player, season=2019, stint=1, er=40, outs=486)

    build_career_totals()

    career = PitchingCareer.objects.get(player=player)
    assert (career.er, career.outs) == (90, 972)
    assert career.era is not None
    assert round(career.era, 2) == 2.50  # 27·sum(ER)/sum(outs)


@pytest.mark.django_db
def test_fielding_career_is_per_position() -> None:
    player = _player(1, "a01")
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="LF", po=10)
    Fielding.objects.create(player=player, season=2020, team="BOS", pos="LF", po=20)
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="CF", po=5)

    build_career_totals()

    assert FieldingCareer.objects.get(player=player, pos="LF").po == 30
    assert FieldingCareer.objects.get(player=player, pos="CF").po == 5


@pytest.mark.django_db
def test_career_rate_without_a_formula_is_prorated_by_playing_time() -> None:
    player = _player(1, "a01")  # wOBA has no career sum -> PA-weighted average
    Batting.objects.create(player=player, season=2018, stint=1, woba=0.400, pa=600)
    Batting.objects.create(player=player, season=2019, stint=1, woba=0.300, pa=400)

    build_career_totals()

    woba = BattingCareer.objects.get(player=player).woba
    assert woba is not None
    assert round(woba, 3) == 0.360  # (0.4·600 + 0.3·400)/1000


@pytest.mark.django_db
def test_build_career_totals_command_is_recorded_in_the_ingest_log() -> None:
    player = _player(1, "a01")
    Batting.objects.create(player=player, season=2019, stint=1, hr=40)

    call_command("build_career_totals")

    run = IngestRun.objects.get(command="build_career_totals")
    assert run.status == IngestRun.Status.SUCCESS
    assert BattingCareer.objects.get(player=player).hr == 40
