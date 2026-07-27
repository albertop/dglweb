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
def test_fielding_career_excludes_dh() -> None:
    player = _player(1, "a01")
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="LF", po=10, gp=50)
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="DH", po=0, gp=40)  # not fielding

    build_career_totals()

    assert not FieldingCareer.objects.filter(player=player, pos="DH").exists()
    assert FieldingCareer.objects.get(player=player, level=CareerLevel.TOTAL).gp == 50  # DH's 40 games excluded


@pytest.mark.django_db
def test_career_total_sums_cumulative_sabermetrics() -> None:
    # SAB-03: WAR is a cumulative float — career total sums it (5 + 6 = 11), not prorates.
    player = _player(1, "a01")
    Batting.objects.create(player=player, season=2018, stint=1, team="BOS", league="AL", war=5.0, pa=600)
    Batting.objects.create(player=player, season=2019, stint=1, team="BOS", league="AL", war=6.0, pa=600)

    build_career_totals()

    assert BattingCareer.objects.get(player=player, level=CareerLevel.TOTAL).war == 11.0


@pytest.mark.django_db
def test_build_career_totals_command_is_recorded_in_the_ingest_log(batter: Player) -> None:
    call_command("build_career_totals", "--force")

    run = IngestRun.objects.get(command="build_career_totals")
    assert run.status == IngestRun.Status.SUCCESS


@pytest.mark.django_db
def test_career_cera_is_weighted_by_innings_and_not_by_games() -> None:
    """cERA son carreras limpias por 9 entradas MIENTRAS el receptor está detrás del plato.

    Con el peso de fildeo —juegos— tres apariciones de un inning pesaban casi como una temporada de
    titular. Caso real de la base, Guillermo García: 82,7 entradas en 11 juegos con 6,31 y luego 4,3
    entradas en 3 juegos con 0,00.

        por juegos    (6.31·11 + 0·3) / 14   = 4.96   <- lo que se mostraba
        por entradas  (6.31·248 + 0·13) / 261 = 6.00  <- lo correcto

    Y no es solo «más justo»: es exacto. Como cERA = 9·ER/IP, la media ponderada por entradas colapsa
    a 9·ΣER/ΣIP, que es la cERA de carrera de verdad.
    """
    player = Player.objects.create(**_other_player(player_id=770001, dgl_id="cera01"))
    Fielding.objects.create(
        player=player, season=1998, team="BOS", pos="C", gp=11, innings_outs=248, catcher_era=6.31
    )
    Fielding.objects.create(player=player, season=1999, team="BOS", pos="C", gp=3, innings_outs=13, catcher_era=0.0)

    build_career_totals()

    fila = FieldingCareer.objects.get(player=player, level=CareerLevel.POSITION, pos="C")
    assert fila.catcher_era is not None
    assert fila.catcher_era == pytest.approx(6.31 * 248 / 261, abs=0.01)
    assert fila.catcher_era > 5.9  # y NO 4.96, que es lo que daba por juegos


@pytest.mark.django_db
def test_a_season_without_the_rate_no_longer_drags_the_career_down() -> None:
    """El peso se cuenta por tasa, así que una temporada sin el dato no entra en el divisor.

    Antes el divisor era el tiempo de juego total, viniera o no la tasa: una campaña con entradas
    pero sin cERA registrada —histórico incompleto— restaba sin aportar.
    """
    player = Player.objects.create(**_other_player(player_id=770002, dgl_id="cera02"))
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="C", gp=100, innings_outs=2400, catcher_era=3.0)
    Fielding.objects.create(
        player=player, season=1975, team="BOS", pos="C", gp=100, innings_outs=2400, catcher_era=None
    )

    build_career_totals()

    fila = FieldingCareer.objects.get(player=player, level=CareerLevel.POSITION, pos="C")
    assert fila.catcher_era == pytest.approx(3.0)  # y no 1.5, que era diluirla con la que no existe
