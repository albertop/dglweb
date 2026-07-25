"""The public leaders page (/lideres/): board building, navigation, and the view."""

from typing import Any

import pytest
from django.test import Client
from django.urls import reverse

from dglweb.players.models import Player
from dglweb.profiles.leaderboards import leaders_context
from dglweb.stats.models import Leader, Metric
from tests.test_players import _other_player


def _player(pid: int, dgl: str, name: str) -> Player:
    return Player.objects.create(**_other_player(player_id=pid, dgl_id=dgl, full_name=name, pos="1B"))


def _metric(
    group: str, column: str, abbrev: str, *, name_es: str = "", career: bool = True, season: bool = True
) -> Metric:
    return Metric.objects.create(
        stat_group=group,
        column=column,
        abbrev=abbrev,
        name_es=name_es,
        kind=Metric.Kind.CUMULATIVE,
        direction=Metric.Direction.HIGHER,
        best_career=career,
        best_season=season,
        is_active=True,
    )


def _leader(
    metric: Metric, player: Player, rank: int, value: float, *, season: int | None = None, career: bool = True
) -> None:
    Leader.objects.create(
        metric=metric,
        board=Leader.Board.BEST_CAREER if career else Leader.Board.BEST_SEASON,
        season=season,
        player=player,
        value=value,
        rank=rank,
        postseason=False,
    )


def _worst_leader(
    metric: Metric, player: Player, rank: int, value: float, *, season: int | None = None, career: bool = True
) -> None:
    """Una fila del tablero de peores — el que alimenta la tabla de la derecha."""
    Leader.objects.create(
        metric=metric,
        board=Leader.Board.WORST_CAREER if career else Leader.Board.WORST_SEASON,
        season=season,
        player=player,
        value=value,
        rank=rank,
        postseason=False,
    )


def _best(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Las filas de la tabla de los primeros (la primera columna del tablero)."""
    rows: list[dict[str, Any]] = ctx["board"]["columns"][0]["rows"]
    return rows


def _worst(ctx: dict[str, Any]) -> list[dict[str, Any]]:
    """Las filas de la tabla de los últimos, o [] si esta métrica/selección no la trae."""
    columns: list[dict[str, Any]] = ctx["board"]["columns"]
    return columns[1]["rows"] if len(columns) > 1 else []


@pytest.mark.django_db
def test_career_board_ranks_and_formats_values() -> None:
    """De por vida: filas en orden de puesto, valor formateado como en el perfil, nombre enlazado."""
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    pujols = _player(1, "a01", "Albert Pujols")
    sosa = _player(2, "b01", "Sammy Sosa")
    _leader(hr, pujols, 1, 703.0)
    _leader(hr, sosa, 2, 609.0)

    ctx = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")
    rows = _best(ctx)

    assert [(r["rank"], r["name"], r["value"]) for r in rows] == [(1, "Albert Pujols", "703"), (2, "Sammy Sosa", "609")]
    assert ctx["board"]["name"] == "Jonrones" and ctx["board"]["abbr"] == "HR"


@pytest.mark.django_db
def test_metric_dropdown_lists_only_its_divisions_metrics() -> None:
    """El dropdown de métrica solo trae las métricas activas de la división elegida (orden de tabla)."""
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    _metric("batting", "iso", "ISO", name_es="Poder aislado")  # Avanzado, no debe salir en Estándar
    _leader(hr, _player(3, "c01", "David Ortiz"), 1, 541.0)

    ctx = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")

    assert [m["name"] for m in ctx["metrics"]] == ["Jonrones"]
    assert "Estándar" in [d["label"] for d in ctx["divisions"]]


@pytest.mark.django_db
def test_season_scope_lists_years_newest_first_and_filters_the_board() -> None:
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    sosa = _player(4, "d01", "Sammy Sosa")
    _leader(hr, sosa, 1, 66.0, season=1998, career=False)
    _leader(hr, sosa, 1, 50.0, season=2000, career=False)

    ctx = leaders_context(group="batting", tab="Estándar", scope="temporada", metric_col="hr", season="1998")

    assert [y["year"] for y in ctx["seasons"]] == [2000, 1998]  # más reciente primero
    assert [(r["name"], r["value"]) for r in _best(ctx)] == [("Sammy Sosa", "66")]  # solo 1998


@pytest.mark.django_db
def test_active_player_is_flagged_when_he_played_the_latest_season() -> None:
    """Un jugador con línea (bateo/pitcheo/fildeo) en la última temporada registrada lleva `active`."""
    from dglweb.stats.models import Batting

    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    activo = _player(20, "act", "Activo A")
    retirado = _player(21, "ret", "Retirado R")
    _leader(hr, activo, 1, 500.0)
    _leader(hr, retirado, 2, 400.0)
    Batting.objects.create(player=activo, season=2025, stint=1, hr=30)  # última temporada -> activo
    Batting.objects.create(player=retirado, season=2010, stint=1, hr=40)  # temporada vieja -> no

    ctx = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")
    active = {r["name"]: r["active"] for r in _best(ctx)}

    assert active["Activo A"] is True
    assert active["Retirado R"] is False
    assert ctx["board"]["shows_active"] is True


@pytest.mark.django_db
def test_the_latest_season_board_marks_nobody_as_active() -> None:
    """En el board de la última temporada todos jugaron ese año: el verde no distinguiría a nadie."""
    from dglweb.stats.models import Batting

    hr = _metric("batting", "hr", "HR")
    uno, dos = _player(30, "u01", "Uno U"), _player(31, "d01", "Dos D")
    _leader(hr, uno, 1, 40.0, season=2025, career=False)
    _leader(hr, dos, 2, 30.0, season=2025, career=False)
    Batting.objects.create(player=uno, season=2025, stint=1, hr=40)  # 2025 es la última temporada
    Batting.objects.create(player=dos, season=2025, stint=1, hr=30)

    ctx = leaders_context(group="batting", tab="Estándar", scope="temporada", metric_col="hr", season="2025")

    assert [r["active"] for r in _best(ctx)] == [False, False]
    assert ctx["board"]["shows_active"] is False  # sin filas marcadas, la leyenda tampoco va


@pytest.mark.django_db
def test_boards_cut_by_rank_and_keep_the_whole_tie() -> None:
    """Cada tabla llega al puesto 10 y el empate del último puesto entra entero, aunque pase de 10 filas."""
    hr = _metric("batting", "hr", "HR")
    for rank in range(1, 31):  # puestos 1..30 en ambos tableros
        jugador = _player(100 + rank, f"c{rank:02d}", f"Carrera {rank}")
        _leader(hr, jugador, rank, 500.0 - rank)
    for rank in range(1, 16):
        jugador = _player(200 + rank, f"t{rank:02d}", f"Temporada {rank}")
        _leader(hr, jugador, rank, 50.0 - rank, season=2020, career=False)
    empatado = _player(299, "t99", "Empatado E")  # tercero en el puesto 10 de la temporada
    _leader(hr, empatado, 10, 40.0, season=2020, career=False)

    carrera = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")
    temporada = leaders_context(group="batting", tab="Estándar", scope="temporada", metric_col="hr", season="2020")

    assert max(r["rank"] for r in _best(carrera)) == 10
    assert len(_best(carrera)) == 10
    assert max(r["rank"] for r in _best(temporada)) == 10
    # 10 puestos, pero 11 filas: el puesto 10 lo comparten dos jugadores y ninguno se corta.
    assert len(_best(temporada)) == 11
    assert [r["tie"] for r in _best(temporada) if r["rank"] == 10] == [True, True]


@pytest.mark.django_db
def test_a_tie_writes_the_rank_and_value_only_on_its_first_row() -> None:
    """Empate: una fila por jugador, pero el puesto y el valor no se repiten (`leads` los controla)."""
    hr = _metric("batting", "hr", "HR")
    _leader(hr, _player(40, "x01", "Ana A"), 1, 40.0)
    _leader(hr, _player(41, "x02", "Beto B"), 1, 40.0)  # empatado en el 1
    _leader(hr, _player(42, "x03", "Ciro C"), 2, 30.0)  # sin empate

    rows = _best(leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season=""))

    assert [(r["name"], r["rank"], r["leads"]) for r in rows] == [
        ("Ana A", 1, True),  # abre el empate: escribe "1" y "40"
        ("Beto B", 1, False),  # lo repite: puesto y valor van en blanco
        ("Ciro C", 2, True),
    ]


@pytest.mark.django_db
def test_the_page_shows_best_and_worst_side_by_side() -> None:
    """Dos tablas: Mejores (tablero best) a la izquierda y Peores (tablero worst) a la derecha."""
    hr = _metric("batting", "hr", "HR")
    for rank in range(1, 4):
        _leader(hr, _player(300 + rank, f"s{rank:02d}", f"Bueno {rank}"), rank, 500.0 - rank)
    for rank in range(1, 4):
        _worst_leader(hr, _player(320 + rank, f"w{rank:02d}", f"Malo {rank}"), rank, float(rank))

    board = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")["board"]

    assert [column["label"] for column in board["columns"]] == ["Primeros 10", "Últimos 10"]
    assert [r["name"] for r in board["columns"][0]["rows"]] == ["Bueno 1", "Bueno 2", "Bueno 3"]
    assert [r["name"] for r in board["columns"][1]["rows"]] == ["Malo 1", "Malo 2", "Malo 3"]


@pytest.mark.django_db
def test_a_player_in_both_ends_is_dropped_from_the_worst_table() -> None:
    """Con pocos calificados las puntas se solapan: quien sale de líder no puede salir de colista."""
    hr = _metric("batting", "hr", "HR")
    lider = _player(500, "y01", "Líder L")
    medio = _player(501, "y02", "Medio M")
    _leader(hr, lider, 1, 50.0)
    _leader(hr, medio, 2, 10.0)
    _worst_leader(hr, medio, 1, 10.0)  # el mismo jugador en las dos puntas
    _worst_leader(hr, lider, 2, 50.0)

    board = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")["board"]

    assert [r["name"] for r in board["columns"][0]["rows"]] == ["Líder L", "Medio M"]
    assert len(board["columns"]) == 1  # los dos de Peores ya salieron en Mejores: la tabla se cae


@pytest.mark.django_db
def test_the_worst_table_rewrites_the_rank_after_dropping_a_repeat() -> None:
    """Si el que abría un empate se fue por repetido, el puesto pasa al que quedó (no queda huérfano)."""
    hr = _metric("batting", "hr", "HR")
    repetido = _player(600, "z01", "Repetido R")
    queda = _player(601, "z02", "Queda Q")
    otro = _player(602, "z03", "Otro O")
    _leader(hr, repetido, 1, 50.0)  # sale en Mejores
    _leader(hr, otro, 2, 40.0)
    _worst_leader(hr, repetido, 1, 5.0)  # empatados en el puesto 1 de Peores
    _worst_leader(hr, queda, 1, 5.0)

    peores = _worst(leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season=""))

    assert [(r["name"], r["rank"], r["leads"], r["tie"]) for r in peores] == [("Queda Q", 1, True, False)]


@pytest.mark.django_db
def test_shared_rank_is_flagged_as_a_tie() -> None:
    hr = _metric("batting", "hr", "HR")
    _leader(hr, _player(5, "e01", "Uno"), 1, 40.0)
    _leader(hr, _player(6, "f01", "Dos"), 1, 40.0)  # empate en el puesto 1

    ctx = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")

    assert all(r["tie"] for r in _best(ctx))


@pytest.mark.django_db
def test_invalid_metric_falls_back_to_the_first_of_the_division() -> None:
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    _leader(hr, _player(7, "g01", "Alguien"), 1, 500.0)

    ctx = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="no_existe", season="")

    assert ctx["board"]["name"] == "Jonrones"  # cayó a la primera métrica válida


@pytest.mark.django_db
def test_leaders_page_renders_and_links_to_the_profile() -> None:
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    pujols = _player(8, "h01", "Albert Pujols")
    _leader(hr, pujols, 1, 703.0)

    response = Client().get(reverse("leaders"), {"g": "batting", "d": "Estándar", "m": "hr", "scope": "carrera"})

    assert response.status_code == 200
    assert b"Albert Pujols" in response.content
    assert b"703" in response.content
    assert f"/jugador/{pujols.slug}/".encode() in response.content
