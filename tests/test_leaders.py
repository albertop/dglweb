"""The leaders engine: position breakdown, boards, qualifier gating, dense rank."""

from typing import Any

import pytest

from dglweb.players.models import Player
from dglweb.stats.leaders import build_leaders
from dglweb.stats.models import Batting, Fielding, Leader, Metric, Pitching, QualifierDefault
from tests.test_players import _other_player


def _player(pid: int, dgl: str, name: str) -> Player:
    return Player.objects.create(**_other_player(player_id=pid, dgl_id=dgl, full_name=name))


def _metric(**kwargs: Any) -> Metric:
    defaults = {"kind": Metric.Kind.CUMULATIVE, "direction": Metric.Direction.HIGHER, "is_active": True}
    return Metric.objects.create(**{**defaults, **kwargs})


@pytest.fixture
def players(db: None) -> dict[str, Player]:
    return {
        "a": _player(1, "a01", "Player A"),
        "b": _player(2, "b01", "Player B"),
        "c": _player(3, "c01", "Player C"),
    }


@pytest.mark.django_db
def test_fielding_leaders_break_down_by_position(players: dict[str, Player]) -> None:
    """PutOuts leaders for LF in 2020 — the LF and CF boards are separate."""
    Fielding.objects.create(player=players["a"], season=2020, team="BOS", pos="LF", po=10)
    Fielding.objects.create(player=players["b"], season=2020, team="NYA", pos="LF", po=5)
    Fielding.objects.create(player=players["c"], season=2020, team="LAN", pos="CF", po=20)
    metric = _metric(stat_group="fielding", column="po", best_season=True)

    build_leaders()

    board = Leader.objects.filter(metric=metric, board="best_season", season=2020, fielding_pos="LF")
    lf = list(board.order_by("rank"))
    assert [(row.player_id, row.value, row.rank) for row in lf] == [(1, 10.0, 1), (2, 5.0, 2)]
    # CF is its own board; the 20-putout CF leader does not outrank the LF board.
    cf = Leader.objects.get(metric=metric, board="best_season", season=2020, fielding_pos="CF")
    assert (cf.player_id, cf.rank) == (3, 1)


@pytest.mark.django_db
def test_career_counting_sums_over_seasons(players: dict[str, Player]) -> None:
    """PutOuts leader for CF across history."""
    Fielding.objects.create(player=players["a"], season=2019, team="LAN", pos="CF", po=15)
    Fielding.objects.create(player=players["a"], season=2020, team="LAN", pos="CF", po=20)  # A = 35 career
    Fielding.objects.create(player=players["b"], season=2018, team="NYA", pos="CF", po=30)  # B = 30
    metric = _metric(stat_group="fielding", column="po", best_career=True)

    build_leaders()

    career = list(Leader.objects.filter(metric=metric, board="best_career", fielding_pos="CF").order_by("rank"))
    assert [(row.player_id, row.value, row.rank) for row in career] == [(1, 35.0, 1), (2, 30.0, 2)]
    assert career[0].season is None  # career boards carry no season


@pytest.mark.django_db
def test_rate_season_applies_the_qualifier_and_ranks_lower_is_better(players: dict[str, Player]) -> None:
    """ERA leaders: below the IP threshold is excluded, and a lower ERA ranks first."""
    QualifierDefault.objects.create(stat_group="pitching", qualifier_season="IP>=162")
    Pitching.objects.create(player=players["a"], season=2019, stint=1, era=2.00, outs=486)  # 162 IP
    Pitching.objects.create(player=players["b"], season=2019, stint=1, era=3.00, outs=500)  # qualifies
    Pitching.objects.create(player=players["c"], season=2019, stint=1, era=1.00, outs=30)  # 10 IP: excluded
    metric = _metric(
        stat_group="pitching", column="era", kind=Metric.Kind.RATE, direction=Metric.Direction.LOWER, best_season=True
    )

    build_leaders()

    board = list(Leader.objects.filter(metric=metric, board="best_season", season=2019).order_by("rank"))
    assert [(row.player_id, row.value, row.rank) for row in board] == [(1, 2.00, 1), (2, 3.00, 2)]
    assert not Leader.objects.filter(player_id=3).exists()  # C did not clear IP>=162


@pytest.mark.django_db
def test_worst_board_and_dense_rank_ties(players: dict[str, Player]) -> None:
    Batting.objects.create(player=players["a"], season=2019, stint=1, hr=40)
    Batting.objects.create(player=players["b"], season=2019, stint=1, hr=40)  # tie with A
    Batting.objects.create(player=players["c"], season=2019, stint=1, hr=30)
    metric = _metric(stat_group="batting", column="hr", best_season=True, worst_season=True)

    build_leaders()

    best = list(Leader.objects.filter(metric=metric, board="best_season").order_by("rank", "player_id"))
    assert [(row.player_id, row.rank) for row in best] == [(1, 1), (2, 1), (3, 2)]  # dense: 1,1,2
    worst = {row.player_id: row.rank for row in Leader.objects.filter(metric=metric, board="worst_season")}
    assert worst == {3: 1, 1: 2, 2: 2}  # fewest HR ranks first on the "worst" board
    assert all(row.fielding_pos is None for row in best)  # batting boards carry no position


@pytest.mark.django_db
def test_leaders_exclude_pre_1956_seasons(players: dict[str, Player]) -> None:
    Batting.objects.create(player=players["a"], season=1950, stint=1, hr=50)  # Negro Leagues era
    Batting.objects.create(player=players["b"], season=1960, stint=1, hr=20)
    _metric(stat_group="batting", column="hr", best_season=True)

    build_leaders()

    assert not Leader.objects.filter(season=1950).exists()
    assert Leader.objects.filter(season=1960).exists()


@pytest.mark.django_db
def test_batting_career_rate_recomputes_from_summed_components(players: dict[str, Player]) -> None:
    """Career AVG = sum(H)/sum(AB) over seasons — via the verified derive formulas, not an average of AVGs."""
    QualifierDefault.objects.create(stat_group="batting", qualifier_career="PA>=100")
    Batting.objects.create(player=players["a"], season=2018, stint=1, h=100, ab=300, pa=330)
    Batting.objects.create(player=players["a"], season=2019, stint=1, h=100, ab=200, pa=220)  # A: 200/500 = .400
    Batting.objects.create(player=players["b"], season=2019, stint=1, h=50, ab=200, pa=220)  # B: .250
    Batting.objects.create(player=players["c"], season=2019, stint=1, h=40, ab=80, pa=90)  # C: .500 but PA<100
    metric = _metric(stat_group="batting", column="avg", kind=Metric.Kind.RATE, best_career=True)

    build_leaders()

    board = list(Leader.objects.filter(metric=metric, board="best_career").order_by("rank"))
    assert [(row.player_id, round(row.value, 3), row.rank) for row in board] == [(1, 0.400, 1), (2, 0.250, 2)]
    assert not Leader.objects.filter(player_id=3).exists()  # C did not clear PA>=100


@pytest.mark.django_db
def test_pitching_career_rate_uses_the_standard_formula(players: dict[str, Player]) -> None:
    """Career ERA = 9·sum(ER)/sum(IP) = 27·sum(ER)/sum(outs) — recomputed, not averaged."""
    QualifierDefault.objects.create(stat_group="pitching", qualifier_career="IP>=100")
    Pitching.objects.create(player=players["a"], season=2018, stint=1, er=50, outs=486)
    Pitching.objects.create(player=players["a"], season=2019, stint=1, er=40, outs=486)  # 90 ER / 972 outs = 2.50
    Pitching.objects.create(player=players["b"], season=2019, stint=1, er=60, outs=486)  # 3.33
    metric = _metric(
        stat_group="pitching", column="era", kind=Metric.Kind.RATE, direction=Metric.Direction.LOWER, best_career=True
    )

    build_leaders()

    board = list(Leader.objects.filter(metric=metric, board="best_career").order_by("rank"))
    assert [(row.player_id, round(row.value, 2), row.rank) for row in board] == [(1, 2.50, 1), (2, 3.33, 2)]


@pytest.mark.django_db
def test_career_rate_without_a_formula_is_prorated_by_playing_time(players: dict[str, Player]) -> None:
    """FIP has no clean career sum, so it's an IP-weighted average of the per-season values."""
    QualifierDefault.objects.create(stat_group="pitching", qualifier_career="IP>=100")
    Pitching.objects.create(player=players["a"], season=2018, stint=1, fip=3.0, outs=486)
    Pitching.objects.create(player=players["a"], season=2019, stint=1, fip=4.0, outs=486)  # weighted avg = 3.5
    Pitching.objects.create(player=players["b"], season=2019, stint=1, fip=5.0, outs=486)
    metric = _metric(
        stat_group="pitching", column="fip", kind=Metric.Kind.RATE, direction=Metric.Direction.LOWER, best_career=True
    )

    result = build_leaders()

    board = list(Leader.objects.filter(metric=metric, board="best_career").order_by("rank"))
    assert [(row.player_id, round(row.value, 2), row.rank) for row in board] == [(1, 3.50, 1), (2, 5.00, 2)]
    assert result["prorated_rate_career"] == 1  # fip fell back to proration


@pytest.mark.django_db
def test_only_active_metrics_produce_leaders(players: dict[str, Player]) -> None:
    Batting.objects.create(player=players["a"], season=2019, stint=1, hr=40)
    _metric(stat_group="batting", column="hr", best_season=True, is_active=False)

    build_leaders()

    assert Leader.objects.count() == 0
