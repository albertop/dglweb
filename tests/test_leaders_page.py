"""The public leaders page (/lideres/): board building, navigation, and the view."""

from datetime import date, timedelta
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from dglweb.players.models import Player
from dglweb.profiles.leaderboards import _TOP_RANK, leaders_context
from dglweb.stats.models import Leader, Metric, SeasonDates
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

    # «Todas» encabeza la lista y detrás van los años, del más reciente al más viejo.
    assert [y["year"] for y in ctx["seasons"]] == ["todas", 2000, 1998]
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
def test_a_season_board_marks_nobody_as_active() -> None:
    """El verde es solo de los tableros de por vida.

    En una temporada no separa nada: en la última todos jugaron ese año por definición, y en una
    reciente casi todos siguen activos, así que se pintaría la tabla entera. Acá el mismo jugador
    activo sale marcado de por vida y sin marcar en su temporada.
    """
    from dglweb.stats.models import Batting

    hr = _metric("batting", "hr", "HR")
    uno, dos = _player(30, "u01", "Uno U"), _player(31, "d01", "Dos D")
    _leader(hr, uno, 1, 40.0, season=2020, career=False)
    _leader(hr, dos, 2, 30.0, season=2020, career=False)
    _leader(hr, uno, 1, 400.0)  # el mismo, en el tablero de por vida
    Batting.objects.create(player=uno, season=2025, stint=1, hr=40)  # 2025 es la última temporada
    Batting.objects.create(player=dos, season=2010, stint=1, hr=30)

    temporada = leaders_context(group="batting", tab="Estándar", scope="temporada", metric_col="hr", season="2020")
    carrera = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")

    assert [r["active"] for r in _best(temporada)] == [False, False]
    assert temporada["board"]["shows_active"] is False  # sin filas marcadas, la leyenda tampoco va
    assert [r["active"] for r in _best(carrera)] == [True]  # de por vida sí se marca


@pytest.mark.django_db
def test_boards_cut_by_rank_and_keep_the_whole_tie() -> None:
    """Cada tabla llega hasta `_TOP_RANK` PUESTOS, y el empate del último entra entero aunque pase.

    De por vida corta más tarde que una temporada suelta. Atado a la constante a propósito: el número
    es una decisión editorial que ya cambió varias veces, y escrito a mano acá el test se rompía cada
    vez sin que nada estuviera mal.
    """
    hr = _metric("batting", "hr", "HR")
    de_por_vida, de_temporada = _TOP_RANK["carrera"], _TOP_RANK["temporada"]
    for rank in range(1, de_por_vida + 21):  # bastante más allá del corte
        jugador = _player(100 + rank, f"c{rank:02d}", f"Carrera {rank}")
        _leader(hr, jugador, rank, 500.0 - rank)
    for rank in range(1, de_temporada + 6):
        jugador = _player(200 + rank, f"t{rank:02d}", f"Temporada {rank}")
        _leader(hr, jugador, rank, 50.0 - rank, season=2020, career=False)
    empatado = _player(299, "t99", "Empatado E")  # segundo en el último puesto que entra
    _leader(hr, empatado, de_temporada, 50.0 - de_temporada, season=2020, career=False)

    carrera = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")
    temporada = leaders_context(group="batting", tab="Estándar", scope="temporada", metric_col="hr", season="2020")

    assert max(r["rank"] for r in _best(carrera)) == de_por_vida
    assert len(_best(carrera)) == de_por_vida
    assert max(r["rank"] for r in _best(temporada)) == de_temporada
    # Los puestos que tocan, pero una fila de más: el último lo comparten dos y ninguno se corta.
    assert len(_best(temporada)) == de_temporada + 1
    assert [r["tie"] for r in _best(temporada) if r["rank"] == de_temporada] == [True, True]


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
def test_the_tail_is_numbered_by_its_place_in_the_main_ranking() -> None:
    """La tabla de abajo publica el puesto del ranking de ARRIBA, no el del tablero ascendente.

    Los dos tableros no rankean a la misma gente: en un conteo el descendente no lleva umbral y el
    ascendente sí. Numerando la cola dentro de su propia población salían dos puestos "10" que no
    medían lo mismo (Manny Machado décimo entre 68, Julio Rodríguez décimo entre 17). Acá el ranking
    llega a 20 y la cola son los tres últimos, así que tienen que salir 18, 19 y 20 — con el extremo
    de último, no de primero.
    """
    hr = _metric("batting", "hr", "HR")
    todos = {rank: _player(300 + rank, f"s{rank:02d}", f"Jugador {rank:02d}") for rank in range(1, 21)}
    for rank, jugador in todos.items():
        _leader(hr, jugador, rank, 500.0 - rank)
    for cola, rank in enumerate([20, 19, 18], start=1):  # el 20 es el extremo: puesto 1 de peores
        _worst_leader(hr, todos[rank], cola, 500.0 - rank)

    board = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")["board"]
    top = _TOP_RANK["carrera"]

    assert [column["label"] for column in board["columns"]] == ["Primeros", "Últimos"]
    assert [r["rank"] for r in board["columns"][0]["rows"]] == list(range(1, top + 1))
    assert [(r["rank"], r["name"]) for r in board["columns"][1]["rows"]] == [
        (18, "Jugador 18"),
        (19, "Jugador 19"),
        (20, "Jugador 20"),
    ]


@pytest.mark.django_db
def test_the_postseason_pill_reads_its_own_boards_and_october_floor() -> None:
    """Postemporada es otro tablero, no otra división de columnas.

    Lee las filas con `postseason=True` —nunca las de serie regular— y su umbral sale del piso fijo
    de octubre, no de la cascada: una postemporada entera son unos pocos juegos, así que pedir los
    502 turnos de una campaña dejaría el tablero vacío.
    """
    avg = _metric("batting", "avg", "AVG", name_es="Promedio")
    Metric.objects.filter(pk=avg.pk).update(kind=Metric.Kind.RATE, postseason=True)
    octubre, regular = _player(800, "p01", "Octubre O"), _player(801, "p02", "Regular R")
    Leader.objects.create(
        metric=avg, board=Leader.Board.BEST_CAREER, player=octubre, value=0.4, rank=1, postseason=True
    )
    _leader(avg, regular, 1, 0.35)  # serie regular: no debe salir en el pill de octubre

    ctx = leaders_context(group="batting", tab="Postemporada", scope="carrera", metric_col="avg", season="")

    assert "Postemporada" in [d["label"] for d in ctx["divisions"]]
    assert [r["name"] for r in _best(ctx)] == ["Octubre O"]
    assert ctx["board"]["qualifier"] == "Mínimo para calificar: PA ≥ 44."  # el piso de octubre


@pytest.mark.django_db
def test_a_descriptive_metric_labels_its_two_ends_by_height_not_by_merit() -> None:
    """Un GB% bajo no es un mal GB%, es el perfil opuesto: las tablas se rotulan sin juzgar."""
    gb = _metric("batting", "gb_pct", "GB%", name_es="Porcentaje de rodados")
    _leader(gb, _player(700, "g01", "Rodador R"), 1, 0.60)
    _worst_leader(gb, _player(701, "g02", "Elevador E"), 1, 0.25)

    board = leaders_context(group="batting", tab="Coeficientes", scope="carrera", metric_col="gb_pct", season="")[
        "board"
    ]

    assert [column["label"] for column in board["columns"]] == ["Los más altos", "Los más bajos"]


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


# ── Con qué se abre la página ───────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_page_opens_on_home_runs_and_not_on_the_first_column() -> None:
    """Nadie llega a Líderes preguntándose quién jugó más partidos.

    El catálogo está ordenado para leer una tabla completa —G, PA, AB, R…— y la página abría con su
    primera columna. HR es la portada natural de la sección.
    """
    g = _metric("batting", "g", "G", name_es="Juegos")
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    jugador = _player(90, "z01", "Un Jugador")
    _leader(g, jugador, 1, 3080.0)
    _leader(hr, jugador, 1, 703.0)

    contexto = leaders_context(group="batting", tab="", scope="carrera", metric_col="", season="")

    assert contexto["board"]["abbr"] == "HR"


@pytest.mark.django_db
def test_asking_for_another_metric_still_wins() -> None:
    """El default es solo para cuando nadie pidió nada: cada tablero sigue siendo su propia URL."""
    g = _metric("batting", "g", "G", name_es="Juegos")
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    jugador = _player(91, "z02", "Un Jugador")
    _leader(g, jugador, 1, 3080.0)
    _leader(hr, jugador, 1, 703.0)

    contexto = leaders_context(group="batting", tab="", scope="carrera", metric_col="g", season="")

    assert contexto["board"]["abbr"] == "G"


@pytest.mark.django_db
def test_a_group_without_a_chosen_default_opens_on_its_first_metric() -> None:
    """Pitcheo y fildeo no están en el mapa: mantienen el comportamiento de siempre."""
    w = _metric("pitching", "w", "W", name_es="Victorias")
    so = _metric("pitching", "so", "SO", name_es="Ponches")
    jugador = _player(92, "z03", "Un Lanzador")
    _leader(w, jugador, 1, 219.0)
    _leader(so, jugador, 1, 3154.0)

    contexto = leaders_context(group="pitching", tab="", scope="carrera", metric_col="", season="")

    assert contexto["board"]["abbr"] == "W"


@pytest.mark.django_db
def test_if_home_runs_is_switched_off_the_page_still_opens() -> None:
    """El default no puede ser un punto de fallo: desactivar HR en el Backoffice no rompe la página."""
    g = _metric("batting", "g", "G", name_es="Juegos")
    _leader(g, _player(93, "z04", "Un Jugador"), 1, 3080.0)

    contexto = leaders_context(group="batting", tab="", scope="carrera", metric_col="", season="")

    assert contexto["board"]["abbr"] == "G"


# ── Cobertura punto 4: ramas reales de `leaderboards.py` que nadie ejercitaba ────────────────────


@pytest.mark.django_db
def test_las_entradas_se_escriben_en_notacion_de_beisbol() -> None:
    """`Leader.value` guarda entradas decimales (203.667) y el béisbol las escribe 203.2.

    No es redondeo: el tercio decimal son OUTS, así que .667 son dos outs y se escribe «.2». Un
    tablero de líderes de IP con «203.7» lo ve mal cualquiera que siga el juego, y es de esos errores
    que desacreditan la página entera aunque el orden sea correcto.
    """
    from dglweb.profiles.leaderboards import _format

    # La columna se llama `outs` y no `ip`: el dato canónico son outs, y las entradas se derivan.
    # Ese detalle lo destapó esta misma prueba —con «ip» caía en el formato de conteo y devolvía
    # «204»— y es justo la clase de cosa que la cobertura estaba tapando.
    assert _format("pitching", "outs", 203 + 2 / 3) == "203.2"
    assert _format("pitching", "outs", 1000.0) == "1,000.0"


@pytest.mark.django_db
def test_los_conteos_se_escriben_como_enteros() -> None:
    """`Leader.value` es float por diseño —una sola columna para conteos y tasas—, así que 703
    jonrones llegan como 703.0 y hay que devolverlos a entero antes de publicarlos."""
    from dglweb.profiles.leaderboards import _format

    assert _format("batting", "hr", 703.0) == "703"


@pytest.mark.django_db
def test_la_nota_del_umbral_dice_de_que_tablero_habla() -> None:
    """El pie que explica por qué falta gente en un tablero de tasas.

    Sin él, un lector que no encuentra a su pelotero en el top de AVG concluye que el dato está mal.
    Y el texto cambia según el tablero: en uno de «mejores» el umbral es para CALIFICAR, y en uno de
    «Últimos» es para ENTRAR — decir «calificar» ahí sugeriría que a los demás les fue mejor.
    """
    from dglweb.profiles.leaderboards import _qualifier_note

    tasa = _metric("batting", "avg", "AVG")
    tasa.kind = Metric.Kind.RATE
    tasa.qualifier_career = "PA>=3000"
    tasa.save()

    nota = _qualifier_note(tasa, "carrera", has_worst=False)

    assert nota.startswith("Mínimo para calificar:"), nota


@pytest.mark.django_db
def test_un_conteo_solo_lleva_nota_si_tiene_tablero_de_ultimos() -> None:
    """Un conteo no necesita umbral para el tablero de «más»: nadie lidera jonrones por accidente.

    Solo lo necesita cuando hay tablero de «Últimos», donde sin mínimo ganaría siempre quien jugó un
    solo partido — y eso no es una marca, es una anécdota.
    """
    from dglweb.profiles.leaderboards import _qualifier_note

    conteo = _metric("batting", "hr", "HR")
    conteo.qualifier_career = "PA>=3000"
    conteo.save()

    assert _qualifier_note(conteo, "carrera", has_worst=False) == ""
    assert _qualifier_note(conteo, "carrera", has_worst=True).startswith("Mínimo para entrar en Últimos:")


# ──────────────────────────────────────────────────────────────────────────────────────────────────
# «Todas»: las mejores temporadas INDIVIDUALES de la historia, no las de un año
# ──────────────────────────────────────────────────────────────────────────────────────────────────


def _todas(**cambios: str) -> dict[str, Any]:
    base = {"group": "batting", "tab": "Estándar", "scope": "temporada", "metric_col": "hr", "season": "todas"}
    return leaders_context(**(base | cambios))


@pytest.mark.django_db
def test_todas_ranks_seasons_of_different_years_against_each_other() -> None:
    """El puesto guardado es de SU temporada: los 66 de Sosa en 1998 y los 24 de otro en 1972 son los
    dos un `rank = 1`. Con «Todas» hay que comparar los valores, no los puestos."""
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    sosa = _player(4, "d01", "Sammy Sosa")
    ortiz = _player(5, "d02", "David Ortiz")
    otro = _player(6, "d03", "Juan Nadie")
    _leader(hr, sosa, 1, 66.0, season=1998, career=False)
    _leader(hr, ortiz, 1, 54.0, season=2006, career=False)
    _leader(hr, otro, 1, 24.0, season=1972, career=False)

    filas = _best(_todas())

    assert [(r["rank"], r["name"], r["season"], r["value"]) for r in filas] == [
        (1, "Sammy Sosa", 1998, "66"),
        (2, "David Ortiz", 2006, "54"),
        (3, "Juan Nadie", 1972, "24"),
    ]


@pytest.mark.django_db
def test_todas_lets_the_same_player_appear_more_than_once() -> None:
    """La fila es un JUGADOR-TEMPORADA. Sosa está tres veces en las mejores de jonrones y es correcto."""
    hr = _metric("batting", "hr", "HR")
    sosa = _player(4, "d01", "Sammy Sosa")
    for anio, valor in ((1998, 66.0), (2001, 64.0), (1999, 63.0)):
        _leader(hr, sosa, 1, valor, season=anio, career=False)

    filas = _best(_todas())

    assert [(r["season"], r["value"]) for r in filas] == [(1998, "66"), (2001, "64"), (1999, "63")]


@pytest.mark.django_db
def test_todas_breaks_a_players_tie_with_himself_by_the_older_season() -> None:
    """Dos temporadas del MISMO jugador con el mismo valor tenían la clave idéntica (QA-01, v21).

    `sorted` es estable, así que el orden lo acababa decidiendo la base — y como «Todas» pinta el
    año, la inestabilidad se veía en pantalla. La más vieja primero: la marca es de quien llegó antes.
    """
    hr = _metric("batting", "hr", "HR")
    arod = _player(4, "d01", "Alex Rodríguez")
    for anio in (2010, 2007, 2005):  # a propósito fuera de orden al insertar
        _leader(hr, arod, 1, 54.0, season=anio, career=False)

    filas = _best(_todas())

    assert [r["season"] for r in filas] == [2005, 2007, 2010]
    # Comparten puesto y cifra, pero el año se escribe en las tres: es lo único que las distingue.
    assert [r["rank"] for r in filas] == [1, 1, 1]
    assert [r["leads"] for r in filas] == [True, False, False]


@pytest.mark.django_db
def test_todas_orders_a_lower_is_better_metric_the_right_way_round() -> None:
    """En efectividad la mejor temporada es la MÁS BAJA. Asumir `reverse=True` la ponía al final."""
    era = Metric.objects.create(
        stat_group="pitching",
        column="era",
        abbrev="ERA",
        kind=Metric.Kind.RATE,
        direction=Metric.Direction.LOWER,
        best_season=True,
        is_active=True,
    )
    martinez = _player(7, "d04", "Pedro Martínez")
    marichal = _player(8, "d05", "Juan Marichal")
    _leader(era, marichal, 1, 2.10, season=1969, career=False)
    _leader(era, martinez, 1, 1.74, season=2000, career=False)

    filas = _best(_todas(group="pitching", metric_col="era"))

    assert [(r["name"], r["season"]) for r in filas] == [("Pedro Martínez", 2000), ("Juan Marichal", 1969)]


@pytest.mark.django_db
def test_todas_cuts_at_the_rank_and_keeps_the_whole_tie() -> None:
    """Hasta el PUESTO, no a las N filas — el mismo criterio que el `rank__lte` de los demás tableros."""
    hr = _metric("batting", "hr", "HR")
    tope = _TOP_RANK["temporada"]
    # Años sin recortar, que 1981, 1994 y 2020 no entran en «Todas» y desviarían la cuenta.
    for i in range(tope - 1):
        _leader(hr, _player(100 + i, f"e{i:02d}", f"Bateador {i}"), 1, 60.0 - i, season=2000 + i, career=False)
    for i in range(3):
        _leader(hr, _player(200 + i, f"f{i:02d}", f"Empatado {i}"), 1, 20.0, season=2010 + i, career=False)

    filas = _best(_todas())

    assert len(filas) == tope + 2  # los tres del último puesto entran completos
    assert [r["rank"] for r in filas[-3:]] == [tope, tope, tope]


@pytest.mark.django_db
def test_todas_only_marks_the_first_row_of_a_tie_but_always_writes_the_year() -> None:
    """Los empatados comparten puesto y cifra, pero NO el año: es lo único que los distingue."""
    hr = _metric("batting", "hr", "HR")
    for i, anio in enumerate((2006, 2007)):
        _leader(hr, _player(300 + i, f"g{i}", f"Bateador {i}"), 1, 54.0, season=anio, career=False)

    filas = _best(_todas())

    assert [r["leads"] for r in filas] == [True, False]
    assert all(r["tie"] for r in filas)
    # El año se pinta en las dos: la plantilla no lo esconde detrás de `leads`.
    assert [r["season"] for r in filas] == [2006, 2007]


@pytest.mark.django_db
def test_todas_dedupes_by_player_and_season_not_by_player_alone() -> None:
    """Una gran temporada no puede borrarle a alguien una mala DISTINTA de la otra punta."""
    # `rbi` y no `hr`: los jonrones ya no llevan tabla de Últimos en «Todas».
    rbi = _metric("batting", "rbi", "RBI")
    sosa = _player(4, "d01", "Sammy Sosa")
    _leader(rbi, sosa, 1, 160.0, season=1998, career=False)
    _worst_leader(rbi, sosa, 1, 20.0, season=2005, career=False)

    ctx = _todas(metric_col="rbi")

    assert [(r["season"], r["value"]) for r in _best(ctx)] == [(1998, "160")]
    assert [(r["season"], r["value"]) for r in _worst(ctx)] == [(2005, "20")]


@pytest.mark.django_db
def test_todas_still_drops_the_very_same_season_from_the_other_end() -> None:
    """Con pocos calificados las dos puntas se solapan; ahí manda la primera, igual que siempre."""
    hr = _metric("batting", "hr", "HR")
    sosa = _player(4, "d01", "Sammy Sosa")
    _leader(hr, sosa, 1, 66.0, season=1998, career=False)
    _worst_leader(hr, sosa, 1, 66.0, season=1998, career=False)

    ctx = _todas()

    assert [r["season"] for r in _best(ctx)] == [1998]
    assert _worst(ctx) == []


@pytest.mark.django_db
def test_todas_swaps_the_seasons_played_column_for_the_year_one() -> None:
    """Son excluyentes: «Temporadas» es de carrera y «Temporada» solo de «Todas»."""
    hr = _metric("batting", "hr", "HR")
    _leader(hr, _player(4, "d01", "Sammy Sosa"), 1, 66.0, season=1998, career=False)

    todas = _todas()["board"]
    una = leaders_context(
        group="batting", tab="Estándar", scope="temporada", metric_col="hr", season="1998"
    )["board"]
    carrera = leaders_context(group="batting", tab="Estándar", scope="carrera", metric_col="hr", season="")["board"]

    assert (todas["shows_season"], todas["shows_seasons"]) == (True, False)
    assert (una["shows_season"], una["shows_seasons"]) == (False, False)
    assert (carrera["shows_season"], carrera["shows_seasons"]) == (False, True)


@pytest.mark.django_db
def test_todas_says_each_season_was_measured_against_its_own_floor() -> None:
    """El umbral se recalcula cada año a partir de los juegos jugados: no hay UN número que escribir."""
    from dglweb.profiles.leaderboards import _qualifier_note

    tasa = _metric("batting", "avg", "AVG")
    tasa.kind = Metric.Kind.RATE
    tasa.qualifier_season = "PA>=502"
    tasa.save()

    nota = _qualifier_note(tasa, "temporada", has_worst=True, todas=True)

    assert nota == (
        "Cada temporada se midió contra su propio mínimo para calificar. "
        "1981, 1994 y 2020 no están consideradas: son temporadas recortadas y no se comparan con una completa."
    )
    assert "502" not in nota


@pytest.mark.django_db
@pytest.mark.parametrize("pedido", ["", "todas", "1899", "basura"])
def test_por_temporada_opens_on_todas_and_not_on_the_newest_year(pedido: str) -> None:
    """Abrir en 2026 convertía «Por temporada» en «los líderes de este año», que es otra pregunta.

    Un año solo gana si existe de verdad: vacío, «todas» y cualquier basura caen todos en «Todas».
    Antes un `?season=1899` aterrizaba en la temporada más reciente sin explicar por qué.
    """
    hr = _metric("batting", "hr", "HR")
    sosa = _player(4, "d01", "Sammy Sosa")
    _leader(hr, sosa, 1, 66.0, season=1998, career=False)
    _leader(hr, sosa, 1, 50.0, season=2000, career=False)

    ctx = _todas(season=pedido)

    assert ctx["board"]["shows_season"] is True
    assert ctx["board"]["scope_label"] == "todas las temporadas"
    assert [r["season"] for r in _best(ctx)] == [1998, 2000]
    assert [y["active"] for y in ctx["seasons"]] == [True, False, False]  # «Todas» marcada


@pytest.mark.django_db
def test_a_real_year_still_wins_over_the_default() -> None:
    hr = _metric("batting", "hr", "HR")
    sosa = _player(4, "d01", "Sammy Sosa")
    _leader(hr, sosa, 1, 66.0, season=1998, career=False)
    _leader(hr, sosa, 1, 50.0, season=2000, career=False)

    ctx = _todas(season="2000")

    assert ctx["board"]["shows_season"] is False
    assert ctx["board"]["scope_label"] == "temporada 2000"
    assert [r["value"] for r in _best(ctx)] == ["50"]


@pytest.mark.django_db
def test_todas_falls_back_to_the_newest_season_when_there_is_nothing_to_gather() -> None:
    """Sin años no hay «Todas» que ofrecer, y el desplegable no se dibuja."""
    _metric("batting", "hr", "HR")

    ctx = _todas()

    assert ctx["seasons"] == []
    assert ctx["board"]["shows_season"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("corta", [1981, 1994, 2020])
def test_todas_leaves_the_shortened_seasons_out_of_both_ends(corta: int) -> None:
    """111, 117 y 60 juegos contra 162. No se comparan con una completa, ni por arriba ni por abajo.

    El umbral se escala a los juegos disputados, así que colaban dos disparates a la vez: por abajo,
    Raimel Tapia encabezando los Últimos de jonrones con 1 en 206 turnos de 2020; por arriba, un .351
    en 196 turnos al lado del .366 de Rico Carty en 560.

    Se usa una métrica de bateo que SÍ conserva su tabla de Últimos — `hr` ya no la lleva en «Todas».
    """
    rbi = _metric("batting", "rbi", "RBI")
    _leader(rbi, _player(4, "d01", "Bateó Mucho"), 1, 40.0, season=2019, career=False)
    _leader(rbi, _player(5, "d02", "Temporada Corta"), 1, 99.0, season=corta, career=False)
    _worst_leader(rbi, _player(6, "d03", "Bateó Poco"), 1, 12.0, season=2019, career=False)
    _worst_leader(rbi, _player(7, "d04", "Corta Y Floja"), 1, 1.0, season=corta, career=False)

    ctx = _todas(metric_col="rbi")

    assert [r["season"] for r in _best(ctx)] == [2019]
    assert [r["season"] for r in _worst(ctx)] == [2019]


@pytest.mark.django_db
def test_1995_stays_in_because_its_cut_is_of_another_order() -> None:
    """145 juegos de 162 mueve el umbral de 502 a unos 449: no cambia quién califica de verdad."""
    rbi = _metric("batting", "rbi", "RBI")
    _leader(rbi, _player(4, "d01", "Del 95"), 1, 90.0, season=1995, career=False)

    assert [r["season"] for r in _best(_todas(metric_col="rbi"))] == [1995]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("grupo", "col"),
    [
        ("batting", "x3b"),
        ("batting", "hr"),
        ("batting", "sb"),
        ("batting", "cs"),
        ("batting", "ibb"),
        ("batting", "hbp"),
        ("batting", "sh"),
        ("batting", "sf"),
        ("pitching", "ibb"),
        ("pitching", "hbp"),
        ("pitching", "wp"),
    ],
)
def test_these_counts_drop_their_tail_table_in_todas(grupo: str, col: str) -> None:
    """«El que menos triples pegó» no es una marca, y juntando setenta años tampoco es una tabla.

    Medido antes de la lista: 610 filas en triples con 143 empatadas en el primer puesto, 634 en
    golpeados y 556 en atrapados robando; en pitcheo, 167 en descontrolados y 157 en intencionales.
    El corte va HASTA EL PUESTO y un empate entra completo, así que el primer puesto arrastraba la
    tabla entera debajo de un tablero de diez.
    """
    m = _metric(grupo, col, col.upper())
    _leader(m, _player(4, "d01", "Arriba"), 1, 30.0, season=1998, career=False)
    _worst_leader(m, _player(5, "d02", "Abajo"), 1, 1.0, season=1998, career=False)

    # En «Todas» no hay tabla de Últimos…
    assert _worst(_todas(group=grupo, metric_col=col)) == []
    # …pero en una temporada suelta sí: ahí son diez filas y son el dato de ese año.
    una = leaders_context(group=grupo, tab="Estándar", scope="temporada", metric_col=col, season="1998")
    assert [r["value"] for r in _worst(una)] == ["1"]


@pytest.mark.django_db
def test_a_count_that_is_not_on_the_list_keeps_its_tail_in_todas() -> None:
    """La lista es corta y explícita: lo que no está en ella no cambia de comportamiento."""
    rbi = _metric("batting", "rbi", "RBI")
    _leader(rbi, _player(4, "d01", "Arriba"), 1, 150.0, season=1998, career=False)
    _worst_leader(rbi, _player(5, "d02", "Abajo"), 1, 17.0, season=1998, career=False)

    assert [r["value"] for r in _worst(_todas(metric_col="rbi"))] == ["17"]


@pytest.mark.django_db
def test_pitching_keeps_its_tail_because_fewest_homers_allowed_is_a_feat() -> None:
    """La lista es por (oficio, columna) y no por columna suelta, y esta es la razón."""
    hr = _metric("pitching", "hr", "HR", name_es="Jonrones permitidos")
    _leader(hr, _player(4, "d01", "Permitió Muchos"), 1, 40.0, season=1998, career=False)
    _worst_leader(hr, _player(5, "d02", "Permitió Pocos"), 1, 3.0, season=1998, career=False)

    ctx = _todas(group="pitching", metric_col="hr")

    assert [r["value"] for r in _worst(ctx)] == ["3"]


def _calendario(season: int, *, fin: date) -> None:
    """La fila de `seasons_dates` que dice cuándo se acabó esa temporada."""
    SeasonDates.objects.create(
        season=season,
        sports_id=SeasonDates.MLB,
        season_start_date=date(season, 3, 26),
        season_end_date=fin,
    )


@pytest.mark.django_db
def test_todas_drops_the_season_in_progress_from_the_tail_only() -> None:
    """Un total a medio jugar solo puede quedarse CORTO, así que solo ensucia una de las dos puntas.

    Los 30 jonrones que alguien lleva en agosto son 30 de verdad y en la tabla de arriba no
    desmerecen nada. En la de abajo ganarían «menos jonrones de la historia» por no haber terminado
    de jugar — y el umbral no protege, porque la cascada lo escala a los juegos disputados: en agosto
    pide 332 turnos donde en octubre pedirá 502.
    """
    hoy = timezone.localdate()
    _calendario(hoy.year, fin=hoy + timedelta(days=60))  # en curso
    _calendario(hoy.year - 1, fin=date(hoy.year - 1, 10, 1))  # terminada

    rbi = _metric("batting", "rbi", "RBI")
    _leader(rbi, _player(4, "d01", "Va Jugando"), 1, 130.0, season=hoy.year, career=False)
    _leader(rbi, _player(5, "d02", "Ya Terminó"), 1, 120.0, season=hoy.year - 1, career=False)
    # Otros dos, para que el dedup por (jugador, temporada) no se lleve las filas de abajo.
    _worst_leader(rbi, _player(6, "d03", "Va Flojo"), 1, 20.0, season=hoy.year, career=False)
    _worst_leader(rbi, _player(7, "d04", "Terminó Flojo"), 1, 29.0, season=hoy.year - 1, career=False)

    ctx = _todas(metric_col="rbi")

    # Arriba sí: 30 jonrones son 30, esté la temporada abierta o cerrada.
    assert [r["season"] for r in _best(ctx)] == [hoy.year, hoy.year - 1]
    # Abajo no: los 2 de la temporada en curso se irían al primer puesto sin haberla terminado.
    assert [r["season"] for r in _worst(ctx)] == [hoy.year - 1]


@pytest.mark.django_db
def test_a_finished_season_stays_in_the_tail_the_day_after_it_ends() -> None:
    """El corte es el mismo `HOLGURA_AL_PUBLICAR` del resto del sitio, no una regla nueva."""
    hoy = timezone.localdate()
    _calendario(hoy.year, fin=hoy - timedelta(days=5))  # se acabó hace cinco días

    rbi = _metric("batting", "rbi", "RBI")
    _worst_leader(rbi, _player(4, "d01", "Ya Terminó"), 1, 29.0, season=hoy.year, career=False)
    _leader(rbi, _player(5, "d02", "Otro"), 1, 140.0, season=hoy.year, career=False)

    assert [r["season"] for r in _worst(_todas(metric_col="rbi"))] == [hoy.year]


@pytest.mark.django_db
def test_without_a_calendar_row_nothing_is_dropped_from_the_tail() -> None:
    """Sin fila en `seasons_dates` no se sabe si terminó, y callar es peor que tachar de más.

    Es el mismo criterio que `temporada_terminada()`: sin calendario no se afirma nada.
    """
    rbi = _metric("batting", "rbi", "RBI")
    _worst_leader(rbi, _player(4, "d01", "Sin Calendario"), 1, 29.0, season=1998, career=False)
    _leader(rbi, _player(5, "d02", "Otro"), 1, 140.0, season=1998, career=False)

    assert [r["season"] for r in _worst(_todas(metric_col="rbi"))] == [1998]


@pytest.mark.django_db
def test_2020_is_still_a_season_you_can_pick_on_its_own() -> None:
    """Queda fuera de la mezcla, no del sitio: su tablero se lee entero contra su propia vara."""
    hr = _metric("batting", "hr", "HR")
    covid = _player(5, "d02", "Temporada Corta")
    _leader(hr, covid, 1, 22.0, season=2020, career=False)

    ctx = leaders_context(group="batting", tab="Estándar", scope="temporada", metric_col="hr", season="2020")

    assert 2020 in [y["year"] for y in ctx["seasons"]]
    assert [r["season"] for r in _best(ctx)] == [2020]
    assert ctx["board"]["excluded"] == ""  # el aviso es solo de «Todas»


@pytest.mark.django_db
def test_todas_says_out_loud_which_season_it_dropped() -> None:
    """Descartar una temporada entera en silencio deja a quien lee buscando por qué falta la suya.

    Va PEGADO a la frase del umbral (dueño, 2026-08-04): «cada temporada se midió contra su propio
    mínimo» a secas se lee como que están todas, y justamente hay una que no está.
    """
    rbi = _metric("batting", "rbi", "RBI")
    _leader(rbi, _player(4, "d01", "Sammy Sosa"), 1, 160.0, season=1998, career=False)
    _worst_leader(rbi, _player(5, "d02", "Otro"), 1, 30.0, season=1998, career=False)

    board = _todas(metric_col="rbi")["board"]

    assert board["qualifier"].endswith(
        "1981, 1994 y 2020 no están consideradas: son temporadas recortadas y no se comparan con una completa."
    )
    assert board["excluded"] == ""  # no se repite


@pytest.mark.django_db
def test_the_notice_stands_alone_when_there_is_no_qualifier_sentence() -> None:
    """Un conteo sin tablero de Últimos no lleva frase de umbral, y el aviso no puede quedarse sin sitio."""
    hr = _metric("batting", "hr", "HR")
    _leader(hr, _player(4, "d01", "Sammy Sosa"), 1, 66.0, season=1998, career=False)

    board = _todas()["board"]

    assert board["qualifier"] == ""
    assert board["excluded"].startswith("1981, 1994 y 2020 no están consideradas")


@pytest.mark.django_db
def test_the_page_renders_the_year_column_when_todas_is_picked() -> None:
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    _leader(hr, _player(4, "d01", "Sammy Sosa"), 1, 66.0, season=1998, career=False)

    cuerpo = Client().get(reverse("leaders"), {"scope": "temporada", "m": "hr", "season": "todas"}).content.decode()

    assert ">Temporada<" in cuerpo
    assert ">Temporadas<" not in cuerpo
    assert ">1998<" in cuerpo
    # Y la opción encabeza el desplegable de Temporada.
    assert ">Todas<" in cuerpo
