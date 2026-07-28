"""The leaders engine: position breakdown, boards, qualifier gating, dense rank."""

from typing import Any

import pytest
from django.core.management import call_command

from dglweb.players.models import Player
from dglweb.stats.leaders import build_leaders
from dglweb.stats.leagues import COMBINED_LEAGUE, COMBINED_TEAM
from dglweb.stats.models import Batting, Fielding, IngestRun, Leader, Metric, Pitching, QualifierDefault
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
def test_counting_minimum_is_gated_by_the_qualifier(players: dict[str, Player]) -> None:
    """ "Menos boletos" sin umbral lo gana quien lanzó una entrada: el tablero de BB abría con un
    jugador de posición que tiró 1.0 IP y no dio boletos."""
    QualifierDefault.objects.create(stat_group="pitching", qualifier_season="IP>=162", qualifier_career="IP>=100")
    _metric(stat_group="pitching", column="bb", direction=Metric.Direction.LOWER, best_season=True, best_career=True)
    # 3 outs = 1.0 IP, cero boletos: la "mejor" marca posible si nada lo filtra.
    Pitching.objects.create(player=players["a"], season=2015, stint=1, outs=3, bb=0)
    Pitching.objects.create(player=players["b"], season=2015, stint=1, outs=600, bb=40)  # 200 IP

    build_leaders()

    season = Leader.objects.get(board=Leader.Board.BEST_SEASON, season=2015, rank=1)
    assert season.player == players["b"]  # el único que califica, aunque dio 40
    career = Leader.objects.get(board=Leader.Board.BEST_CAREER, rank=1)
    assert career.player == players["b"]


@pytest.mark.django_db
def test_the_worst_board_of_a_positive_count_is_gated_too(players: dict[str, Player]) -> None:
    """El umbral lo pide el TABLERO, no la dirección de la métrica.

    HR apunta hacia arriba, así que su tablero de "más" no necesita nada; pero el de "menos" sí, o lo
    gana quien tuvo 20 turnos y ningún jonrón. Leyendo la dirección en vez del tablero, el board de
    "menos HR de por vida" salía con 384 jugadores empatados en un jonrón, un lanzador entre ellos.
    """
    QualifierDefault.objects.create(stat_group="batting", qualifier_season="PA>=100", qualifier_career="PA>=100")
    _metric(stat_group="batting", column="hr", direction=Metric.Direction.HIGHER, best_career=True, worst_career=True)
    Batting.objects.create(player=players["a"], season=2015, stint=1, pa=20, hr=0)  # taza de café
    Batting.objects.create(player=players["b"], season=2015, stint=1, pa=600, hr=3)  # el peor de verdad
    Batting.objects.create(player=players["c"], season=2015, stint=1, pa=600, hr=50)

    build_leaders()

    peores = Leader.objects.filter(board=Leader.Board.WORST_CAREER).order_by("rank")
    assert [row.player for row in peores] == [players["b"], players["c"]]  # A no califica
    # El tablero de "más" sigue sin umbral: acumular un liderato en pocos turnos es imposible.
    assert Leader.objects.filter(board=Leader.Board.BEST_CAREER).count() == 3


@pytest.mark.django_db
def test_postseason_boards_aggregate_a_whole_october(players: dict[str, Player]) -> None:
    """Los tableros de postemporada suman todo octubre por (jugador, temporada), no por ronda: los 3
    HR de A en la Serie Divisional + los 2 de la Serie Mundial son 5 en 2019. Y solo conteos '+'."""
    from dglweb.stats.models import BattingPost

    _metric(stat_group="batting", column="hr", best_season=True, best_career=True, postseason=True)
    BattingPost.objects.create(player=players["a"], season=2019, round="DS", hr=3)
    BattingPost.objects.create(player=players["a"], season=2019, round="WS", hr=2)  # A: 5 en 2019
    BattingPost.objects.create(player=players["b"], season=2019, round="WS", hr=4)  # B: 4

    build_leaders()

    season = list(Leader.objects.filter(board="best_season", postseason=True, season=2019).order_by("rank"))
    assert [(row.player_id, row.value, row.rank) for row in season] == [(1, 5.0, 1), (2, 4.0, 2)]
    career = list(Leader.objects.filter(board="best_career", postseason=True).order_by("rank"))
    assert [(row.player_id, row.value) for row in career] == [(1, 5.0), (2, 4.0)]
    # Los tableros de temporada regular no se tocan.
    assert not Leader.objects.filter(postseason=False).exists()


@pytest.mark.django_db
def test_postseason_skips_negative_counts(players: dict[str, Player]) -> None:
    """Un conteo '-' (SO) no recibe tablero de postemporada aunque esté marcado `postseason=True`:
    liderar en "menos ponches" con un turno es ruido. (Las tasas sí lo reciben, con piso fijo.)"""
    from dglweb.stats.models import BattingPost

    _metric(stat_group="batting", column="so", direction=Metric.Direction.LOWER, best_season=True, postseason=True)
    BattingPost.objects.create(player=players["a"], season=2019, round="WS", so=1)

    build_leaders()

    assert not Leader.objects.filter(postseason=True).exists()


@pytest.mark.django_db
def test_postseason_honors_best_season_and_best_career_flags(players: dict[str, Player]) -> None:
    """Los flags gatean octubre igual que la temporada regular (review v4 DEV-03): sin `best_career`
    no hay tablero de carrera de postemporada, y sin `best_season` no hay de temporada."""
    from dglweb.stats.models import BattingPost

    solo_season = _metric(stat_group="batting", column="hr", best_season=True, best_career=False, postseason=True)
    solo_career = _metric(stat_group="batting", column="rbi", best_season=False, best_career=True, postseason=True)
    BattingPost.objects.create(player=players["a"], season=2019, round="WS", hr=3, rbi=8)

    build_leaders()

    assert Leader.objects.filter(metric=solo_season, postseason=True, board="best_season").exists()
    assert not Leader.objects.filter(metric=solo_season, postseason=True, board="best_career").exists()
    assert Leader.objects.filter(metric=solo_career, postseason=True, board="best_career").exists()
    assert not Leader.objects.filter(metric=solo_career, postseason=True, board="best_season").exists()


@pytest.mark.django_db
def test_postseason_rate_boards_recompute_from_totals_and_gate_by_floor(players: dict[str, Player]) -> None:
    """AVG de postemporada: el valor se RECOMPONE desde los totales (ΣH/ΣAB), no se promedian las
    tasas por ronda; y el piso fijo (25 PA temporada, 50 PA carrera) excluye muestras pequeñas."""
    from dglweb.stats.models import BattingPost

    metric = _metric(
        stat_group="batting", column="avg", kind=Metric.Kind.RATE, best_season=True, best_career=True, postseason=True
    )
    # A, 2019: 30 PA en dos rondas -> 12/30 = .400, sobre el piso de temporada (25).
    BattingPost.objects.create(player=players["a"], season=2019, round="DS", pa=15, ab=15, h=6, tb=6)
    BattingPost.objects.create(player=players["a"], season=2019, round="WS", pa=15, ab=15, h=6, tb=6)
    # A, 2018: otras 30 PA, 9 H -> carrera 60 PA (sobre 50), 21/60 = .350.
    BattingPost.objects.create(player=players["a"], season=2018, round="WS", pa=30, ab=30, h=9, tb=9)
    # B, 2019: 26 PA (sobre el piso de temporada) pero solo .192; carrera 26 PA < 50 -> fuera de carrera.
    BattingPost.objects.create(player=players["b"], season=2019, round="WS", pa=26, ab=26, h=5, tb=5)
    # C, 2019: 10 PA (.500) -> bajo el piso de temporada, excluido.
    BattingPost.objects.create(player=players["c"], season=2019, round="WS", pa=10, ab=10, h=5, tb=5)

    build_leaders()

    season_qs = Leader.objects.filter(metric=metric, board="best_season", postseason=True, season=2019)
    season = list(season_qs.order_by("rank"))
    assert [(row.player_id, row.value, row.rank) for row in season] == [(1, 0.400, 1), (2, 0.192, 2)]
    assert not Leader.objects.filter(metric=metric, postseason=True, player_id=3).exists()  # C: < 25 PA
    career = list(Leader.objects.filter(metric=metric, board="best_career", postseason=True).order_by("rank"))
    assert [(row.player_id, row.value) for row in career] == [(1, 0.350)]  # solo A cruza 50 PA de carrera


@pytest.mark.django_db
def test_postseason_era_board_recomputes_and_gates_by_ip(players: dict[str, Player]) -> None:
    """ERA de postemporada: se recompone (27·ΣER/Σouts), el menor gana (dir '-'), y el piso es en IP
    (8 temporada, 15 carrera)."""
    from dglweb.stats.models import PitchingPost

    metric = _metric(
        stat_group="pitching",
        column="era",
        kind=Metric.Kind.RATE,
        direction=Metric.Direction.LOWER,
        best_season=True,
        best_career=True,
        postseason=True,
    )
    # A, 2019: 8 IP (24 outs), 2 ER -> 27*2/24 = 2.25, sobre el piso (8). + 2018 para cruzar 15 IP carrera.
    PitchingPost.objects.create(player=players["a"], season=2019, round="LCS", outs=12, er=1)
    PitchingPost.objects.create(player=players["a"], season=2019, round="WS", outs=12, er=1)
    PitchingPost.objects.create(player=players["a"], season=2018, round="WS", outs=24, er=3)  # carrera 48 outs = 16 IP
    # B, 2019: 8 IP (24 outs), 6 ER -> 6.75, peor. Carrera 8 IP < 15 -> fuera de carrera.
    PitchingPost.objects.create(player=players["b"], season=2019, round="WS", outs=24, er=6)
    # C, 2019: 5 IP (15 outs) -> bajo el piso de temporada, excluido.
    PitchingPost.objects.create(player=players["c"], season=2019, round="WS", outs=15, er=0)

    build_leaders()

    season_qs = Leader.objects.filter(metric=metric, board="best_season", postseason=True, season=2019)
    season = list(season_qs.order_by("rank"))
    assert [(row.player_id, row.value, row.rank) for row in season] == [(1, 2.25, 1), (2, 6.75, 2)]
    assert not Leader.objects.filter(metric=metric, postseason=True, player_id=3).exists()  # C: < 8 IP
    # Carrera: A cruza 15 IP (16), 27*5/48 = 2.8125 -> 2.812 (redondeo bancario a 3 decimales); B no.
    career = list(Leader.objects.filter(metric=metric, board="best_career", postseason=True).order_by("rank"))
    assert [(row.player_id, row.value) for row in career] == [(1, 2.812)]


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


@pytest.mark.django_db
def test_innings_leader_value_is_innings_not_raw_outs(players: dict[str, Player]) -> None:
    # SAB-02: the "IP" board ranks `outs`, but the published value must be innings (outs/3).
    Pitching.objects.create(player=players["a"], season=2019, stint=1, outs=486)  # 162 IP
    metric = _metric(stat_group="pitching", column="outs", best_season=True)

    build_leaders()

    assert Leader.objects.get(metric=metric, board="best_season", season=2019).value == 162.0


@pytest.mark.django_db
def test_rate_ties_by_displayed_precision(players: dict[str, Player]) -> None:
    # SAB-06: two AVGs that both display .300 must tie, not split on a 1e-5 float difference.
    Batting.objects.create(player=players["a"], season=2019, stint=1, avg=0.29997, pa=600)
    Batting.objects.create(player=players["b"], season=2019, stint=1, avg=0.30003, pa=600)
    metric = _metric(stat_group="batting", column="avg", kind=Metric.Kind.RATE, best_season=True, fmt="#.000")

    build_leaders()

    ranks = {row.player_id: row.rank for row in Leader.objects.filter(metric=metric, board="best_season")}
    assert ranks == {1: 1, 2: 1}  # both .300 -> rank 1


@pytest.mark.django_db
def test_cumulative_sabermetric_career_sums_not_prorates(players: dict[str, Player]) -> None:
    # SAB-03: career WAR = sum of seasonal WAR (5 + 6 = 11), not an IP-weighted average.
    Batting.objects.create(player=players["a"], season=2018, stint=1, war=5.0, pa=600)
    Batting.objects.create(player=players["a"], season=2019, stint=1, war=6.0, pa=600)
    metric = _metric(stat_group="batting", column="war", kind=Metric.Kind.CUMULATIVE, best_career=True)

    build_leaders()

    assert Leader.objects.get(metric=metric, board="best_career").value == 11.0


@pytest.mark.django_db
def test_build_leaders_command_is_recorded_in_the_ingest_log(players: dict[str, Player]) -> None:
    """The scheduled job logs to the bitácora, like the daily refreshers."""
    Batting.objects.create(player=players["a"], season=2019, stint=1, hr=40)
    _metric(stat_group="batting", column="hr", best_season=True)

    call_command("build_leaders", "--force")

    run = IngestRun.objects.get(command="build_leaders")
    assert run.status == IngestRun.Status.SUCCESS
    assert run.rows_affected >= 1


# ── El umbral prorrateado: qué juegos se usan para cada fila ────────────────────────────────────


def test_una_temporada_con_un_solo_equipo_usa_los_juegos_de_ese_equipo() -> None:
    """Es la regla de MLB, y por eso la tabla guarda el grano por equipo: en 1981 el rango fue de 103
    a 111 juegos y los 26 equipos quedaron fuera de la mediana."""
    from dglweb.stats.leaders import _juegos_de

    por_equipo = {(1981, "NYA"): 107, (1981, "BOS"): 108}
    por_liga = {(1981, "AL"): 110}

    assert _juegos_de({"season": 1981, "team": "NYA", "league": "AL"}, por_equipo, por_liga) == 107


def test_un_traspasado_usa_el_maximo_de_su_liga() -> None:
    """Con el centinela de equipo combinado no hay UN equipo al que preguntarle.

    Se usa el máximo de su liga y no la mediana: es el calendario más largo que alguien de esa liga
    llegó a jugar, así que nadie califica por juegos que su liga no disputó.
    """
    from dglweb.stats.leaders import _juegos_de

    fila = {"season": 1961, "team": COMBINED_TEAM, "league": "NL"}

    assert _juegos_de(fila, {}, {(1961, "NL"): 156, (1961, "AL"): 163}) == 156


def test_la_liga_importa_y_1961_lo_prueba() -> None:
    """Ese año la Americana se expandió a 10 equipos y pasó a 162 juegos mientras la Nacional seguía
    con 8 y 154. Un número único para toda la liga habría pedido 21 apariciones de más a la mitad de
    los jugadores de esa temporada."""
    from dglweb.stats.leaders import _juegos_de

    por_liga = {(1961, "AL"): 163, (1961, "NL"): 156}
    americana = _juegos_de({"season": 1961, "team": COMBINED_TEAM, "league": "AL"}, {}, por_liga)
    nacional = _juegos_de({"season": 1961, "team": COMBINED_TEAM, "league": "NL"}, {}, por_liga)

    assert (americana, nacional) == (163, 156)


def test_un_traspasado_entre_ligas_se_mide_con_el_umbral_fijo() -> None:
    """Cambió de liga, así que el centinela está también en `league` y no queda nada a lo que
    agarrarse. Devolver `None` deja mandar al fijo, que es el más exigente: el error va del lado de
    dejar fuera, no de colar a alguien que no calificaba."""
    from dglweb.stats.leaders import _juegos_de

    fila = {"season": 2019, "team": COMBINED_TEAM, "league": COMBINED_LEAGUE}

    assert _juegos_de(fila, {}, {(2019, "AL"): 162}) is None


def test_un_equipo_que_no_esta_en_la_tabla_cae_a_su_liga() -> None:
    """Una temporada a medio cargar no puede dejar sin umbral a media liga."""
    from dglweb.stats.leaders import _juegos_de

    assert _juegos_de({"season": 2026, "team": "XXY", "league": "AL"}, {}, {(2026, "AL"): 107}) == 107
