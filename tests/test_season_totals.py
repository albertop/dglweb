"""Tests for the canonical season-total querysets (FIX-6).

Leaders must never sum the per-team breakdown rows of a traded player: that double-counts him.
`season_totals()` / `position_totals()` return exactly one row per season (per position for
fielding): the `XXX` total when the player was traded, the single row when he was not.
"""

import pytest
from django.db.models import Sum

from dglweb.players.models import Player
from dglweb.stats.models import Batting, Fielding, Pitching
from tests.test_players import RECORD, _other_player


@pytest.fixture
def traded(db: None) -> Player:
    """A traded batter: 2 team rows + the XXX total (30 + 10 = 40 HR)."""
    player = Player.objects.create(**RECORD)
    Batting.objects.create(player=player, season=2024, stint=1, team="AAA", hr=30)
    Batting.objects.create(player=player, season=2024, stint=2, team="BBB", hr=10)
    Batting.objects.create(player=player, season=2024, stint=3, team="XXX", hr=40)
    return player


@pytest.mark.django_db
def test_season_totals_keeps_the_xxx_row_for_a_traded_player(traded: Player) -> None:
    totals = Batting.objects.season_totals()

    assert totals.count() == 1
    assert totals.get().team == "XXX"
    assert totals.get().hr == 40


@pytest.mark.django_db
def test_season_totals_keeps_the_single_row_for_a_non_traded_player() -> None:
    player = Player.objects.create(**RECORD)
    Batting.objects.create(player=player, season=2024, stint=1, team="AAA", hr=25)

    totals = Batting.objects.season_totals()

    assert totals.count() == 1
    assert (totals.get().team, totals.get().hr) == ("AAA", 25)


@pytest.mark.django_db
def test_summing_totals_does_not_double_count(traded: Player) -> None:
    other = Player.objects.create(**_other_player())
    Batting.objects.create(player=other, season=2024, stint=1, team="CCC", hr=15)

    # Naively summing every row would give 30+10+40+15 = 95; the totals give 40+15 = 55.
    assert Batting.objects.aggregate(bad=Sum("hr"))["bad"] == 95
    assert Batting.objects.season_totals().aggregate(good=Sum("hr"))["good"] == 55


@pytest.mark.django_db
def test_pitching_season_totals_work_the_same_way() -> None:
    player = Player.objects.create(**RECORD)
    Pitching.objects.create(player=player, season=2008, stint=1, team="PIT", so=47)
    Pitching.objects.create(player=player, season=2008, stint=2, team="NYA", so=24)
    Pitching.objects.create(player=player, season=2008, stint=3, team="XXX", so=71)

    totals = Pitching.objects.season_totals()
    assert totals.count() == 1
    assert totals.get().so == 71


@pytest.mark.django_db
def test_fielding_position_totals_are_per_position() -> None:
    """A player traded mid-season: each position keeps its XXX total, single-team positions stay."""
    player = Player.objects.create(**RECORD)
    # 2B with two teams -> XXX total; 1B with one team -> single row.
    Fielding.objects.create(player=player, season=2006, team="SLN", pos="2B", po=69)
    Fielding.objects.create(player=player, season=2006, team="CLE", pos="2B", po=39)
    Fielding.objects.create(player=player, season=2006, team="XXX", pos="2B", po=108)
    Fielding.objects.create(player=player, season=2006, team="SLN", pos="1B", po=25)

    totals = Fielding.objects.position_totals().order_by("pos")

    assert [(t.pos, t.team, t.po) for t in totals] == [("1B", "SLN", 25), ("2B", "XXX", 108)]
