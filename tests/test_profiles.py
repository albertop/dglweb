"""Public player pages: the tab registry (ordering, pitcher-first), the view, the slug, the filters."""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from typing import Any

import pytest
from django.db import connection
from django.test import Client, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from dglweb.players import mugshots
from dglweb.players.models import Player
from dglweb.profiles import columns
from dglweb.profiles.metric_layout import qualifier_lookups
from dglweb.profiles.tabs import (
    BattingTab,
    PuestosTab,
    _catalog,
    _personal_bests,
    _puestos_context,
    tabs_for,
)
from dglweb.profiles.templatetags.stats_extras import dec, innings, num, pct, rate
from dglweb.profiles.views import bio_lines
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    CareerLevel,
    Fielding,
    FieldingCareer,
    Leader,
    Metric,
    Pitching,
    PitchingCareer,
    QualifierDefault,
)
from tests.test_players import _other_player


def _player(pid: int, dgl: str, name: str, pos: str) -> Player:
    return Player.objects.create(**_other_player(player_id=pid, dgl_id=dgl, full_name=name, pos=pos))


@contextmanager
def _con_retrato(raiz: Any, player_id: int, tamano: int) -> Iterator[None]:
    """Deja el archivo del retrato donde `mugshots.existe` lo va a buscar, en una carpeta temporal.

    Los retratos no están en el repositorio —se bajan aparte y la carpeta se monta— así que un test
    que dependa de que el PNG de alguien esté ahí pasaría en esta máquina y fallaría en CI.
    """
    carpeta = raiz / "img" / "mugshots" / str(tamano)
    carpeta.mkdir(parents=True, exist_ok=True)
    (carpeta / f"{player_id}.png").write_bytes(b"")
    with override_settings(STATICFILES_DIRS=[raiz]):
        yield


# El techo de consultas de una página de perfil con los CUATRO tabs encendidos. Medido, no elegido:
# ver `test_el_presupuesto_esta_ajustado_y_no_es_un_numero_generoso`, que se cae si alguien lo sube
# para silenciar un fallo en vez de mirar por qué creció.
#
# Historia: el review v3 (DEV-01) midió 25 consultas para un perfil de dos tabs. Entraron Fildeo y
# Puestos y un perfil real llegó a 44 — y la prueba de presupuesto no se enteró, porque su fixture
# seguía siendo de dos tabs. Por eso el número de acá se mide sobre el caso peor.
#
# 2026-07-28, por la mañana: bajó de 42 a 31 al cachear las tres tablas de referencia que cada tab
# volvía a pedir (ver `metric_layout.qualifier_lookups`).
#
# 2026-07-28, por la tarde: subió a 40. La caché de esas tablas pasó a la BASE porque en memoria era
# por proceso, y con varios workers de gunicorn la invalidación por señal solo llegaba a uno — el
# dueño cambiaba un umbral y los demás servían el viejo hasta 24 horas. Correcto cuesta 9 consultas
# más que rápido-pero-mentiroso, y son ~2 ms contra la base local.
#
# EL DATO INCÓMODO, medido: sin NINGUNA caché esta página hace 44. O sea que toda esa maquinaria
# —tabla, migración, dos backends, señales— ahorra CUATRO consultas. Está anotado en el TODO como
# candidato a simplificar: puede que lo correcto sea no cachear esas tablas y consultarlas y ya.
_PRESUPUESTO_DE_CONSULTAS = 44


@contextmanager
def django_assert_num_queries_lte(limit: int) -> Iterator[None]:
    """Un techo, no un número exacto: el punto es cazar un salto de orden de magnitud, no obligar a
    editar el test cada vez que una query se reordena."""
    with CaptureQueriesContext(connection) as captured:
        yield
    assert len(captured) <= limit, f"{len(captured)} queries, presupuesto {limit}"


@pytest.mark.django_db
def test_slug_always_ends_in_the_id() -> None:
    player = _player(120074, "ortiz01", "David Ortiz", "DH")
    assert player.slug == "david-ortiz-120074"


@pytest.mark.django_db
def test_tabs_order_batter_batting_first() -> None:
    player = _player(1, "a01", "Un Bateador", "LF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    FieldingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=200)
    Fielding.objects.create(player=player, season=2020, team="BOS", pos="LF", gp=100)  # una línea real

    assert [tab.key for tab in tabs_for(player)] == ["batting", "fielding"]


@pytest.mark.django_db
def test_tabs_order_pitcher_pitching_first() -> None:
    player = _player(2, "b01", "Un Lanzador", "SP")  # SP is a pitcher code
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    PitchingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    FieldingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=200)
    Fielding.objects.create(player=player, season=2020, team="BOS", pos="P", gp=30)  # una línea real

    assert [tab.key for tab in tabs_for(player)] == ["pitching", "batting", "fielding"]


@pytest.mark.django_db
def test_tab_hidden_when_the_player_has_no_data_for_it() -> None:
    player = _player(3, "c01", "Solo Bateo", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)

    assert [tab.key for tab in tabs_for(player)] == ["batting"]  # no pitching/fielding career -> no tabs


@pytest.mark.django_db
def test_player_page_renders_the_name_and_a_stat() -> None:
    player = _player(4, "d01", "Juan Soto", "LF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300, hr=229, avg=0.288)
    Batting.objects.create(player=player, season=2024, stint=1, hr=41, avg=0.288)

    response = Client().get(reverse("player_detail", args=[player.slug]))

    assert response.status_code == 200
    assert b"Juan Soto" in response.content
    assert b"229" in response.content  # career HR statbox
    # `{# ... #}` es de UNA línea: partido en dos deja de ser comentario y se imprime en la página.
    assert b"{#" not in response.content


@pytest.mark.django_db
def test_the_profile_asks_for_the_big_portrait_and_the_widgets_for_the_small_one(tmp_path: Any) -> None:
    """Dos tamaños y cada sitio pide el suyo.

    El de la ficha se ve a 96px y el de 120 se vería lavado en pantalla de retina; el de los widgets
    se ve a 34px y bajar 360 ahí es cargar diez veces el peso para nada. Se confunden con solo
    cambiar un número, y la ruta la arma `mugshots` para los tres sitios a la vez.
    """
    player = _player(15, "o01", "Un Jugador", "LF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)

    with _con_retrato(tmp_path, 15, mugshots.GRANDE):
        response = Client().get(reverse("player_detail", args=[player.slug]))

    assert b"/img/mugshots/360/15.png" in response.content
    assert mugshots.url(15) == mugshots.url(15, mugshots.CHICO)  # el chico es el de por defecto
    assert mugshots.url(15, mugshots.CHICO).endswith("/img/mugshots/120/15.png")


@pytest.mark.django_db
def test_the_profile_of_someone_without_a_portrait_draws_no_portrait_at_all() -> None:
    """No es el caso raro: se bajan los de las dos últimas temporadas —637 de 981—, así que un tercio
    de las fichas no tiene retrato y los siete de las Ligas Negras no lo van a tener nunca.

    Y no se dibuja una etiqueta rota que el navegador quite después: el nombre nacería corrido 120px
    a la derecha y saltaría a su sitio al volver el 404, en un tercio de las fichas.
    """
    player = _player(16, "p01", "Sin Retrato", "LF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)

    response = Client().get(reverse("player_detail", args=[player.slug]))

    assert response.status_code == 200
    assert b"dgl-retrato" not in response.content


@pytest.mark.django_db
def test_wrong_name_slug_redirects_to_canonical() -> None:
    player = _player(5, "e01", "Manny Ramírez", "LF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)

    response = Client().get(f"/jugador/nombre-equivocado-{player.player_id}/")

    assert response.status_code == 301
    assert response.headers["Location"] == reverse("player_detail", args=[player.slug])


@pytest.mark.django_db
def test_slug_without_a_trailing_id_is_404() -> None:
    assert Client().get("/jugador/sin-id/").status_code == 404


def test_rate_filter_drops_the_leading_zero() -> None:
    assert rate(0.288) == ".288"
    assert rate(2.5, 2) == "2.50"
    assert rate(None) == "—"
    assert num(None) == "—"
    assert num(41) == "41"


def test_num_adds_thousands_separator() -> None:
    assert num(2472) == "2,472"
    assert num(541) == "541"


@pytest.mark.django_db
def test_bio_line_lists_every_field_it_has() -> None:
    player = _player(18, "b03", "Con Todo", "1B")
    player.bats, player.throws, player.height, player.weight = "L", "R", "6-3", 230
    player.birth_date = date(1975, 11, 18)
    player.birth_place, player.birth_province = "Santo Domingo", "Distrito Nacional"
    player.debut_date, player.death_date = date(1997, 9, 2), date(2050, 1, 5)
    player.save()

    play, origin = bio_lines(player)  # dos líneas: cómo juega, y de dónde/cuándo

    assert "Batea: Izq" in play  # el modelo no tiene choices: mapeo explícito, no get_*_display
    assert "Lanza: Der" in play
    assert "Estatura: 6-3" in play and "Peso: 230 lb" in play
    assert "Santo Domingo, Distrito Nacional" in origin
    assert any(p.startswith("Debut") for p in origin)
    assert any(p.startswith("Falleció") for p in origin)


@pytest.mark.django_db
def test_bio_line_spells_out_the_pitcher_role() -> None:
    """El maestro guarda el rol en el código de posición; el resto de posiciones pasa tal cual."""
    assert "Posición: P-Abr" in bio_lines(_player(23, "r01", "Abridor", "SP"))[0]
    assert "Posición: P-Rel" in bio_lines(_player(24, "r02", "Relevista", "RP"))[0]
    assert "Posición: P" in bio_lines(_player(25, "r03", "Genérico", "P"))[0]
    assert "Posición: LF" in bio_lines(_player(26, "r04", "Jardinero", "LF"))[0]


@pytest.mark.django_db
def test_bio_line_prints_the_birthplace_once_when_city_equals_province() -> None:
    """384 de 984 jugadores repiten el valor; `Hato Mayor, Hato Mayor` se lee como un error."""
    player = _player(19, "b04", "Mismo Lugar", "1B")
    player.birth_place = player.birth_province = "Hato Mayor"
    player.birth_date = player.debut_date = player.death_date = None
    player.save()

    _, origin = bio_lines(player)

    assert origin == ["Hato Mayor"]  # una vez, no "Hato Mayor, Hato Mayor"


@pytest.mark.django_db
def test_bio_line_skips_what_the_record_lacks() -> None:
    player = _player(20, "b05", "Sin Datos", "1B")
    player.pos = None
    player.bats = player.throws = player.height = player.weight = None
    player.birth_date = player.birth_place = player.birth_province = None
    player.debut_date = player.death_date = None
    player.save()

    assert bio_lines(player) == []  # ni etiquetas huérfanas ni separadores sueltos


def test_innings_uses_baseball_notation_not_a_decimal() -> None:
    """Los 8482 outs de Pedro son 2,827.1 IP — el `.1` es UN OUT, no una décima (2,827.3)."""
    assert innings(8482) == "2,827.1"
    assert innings(8483) == "2,827.2"
    assert innings(8484) == "2,828.0"
    assert innings(None) == "—"


def test_dec_keeps_the_leading_zero_and_groups_thousands() -> None:
    assert dec(0.5) == "0.5"  # el cero inicial se queda (no es una tasa de bateo)
    assert dec(-2.34, 2) == "-2.34"
    assert dec(1536.6) == "1,536.6"  # BsR/RC/wRC de carrera pasan de mil
    assert dec(None) == "—"


@pytest.mark.parametrize("junk", ["N/A", "--", "", [], object()])
def test_filters_render_a_dash_instead_of_exploding(junk: object) -> None:
    """Fail-soft en render, fail-loud en ingesta: una celda corrupta no puede tumbar la página
    entera de un jugador. La corrupción se caza en paridad/ingesta, no con un 500."""
    assert rate(junk) == "—"
    assert dec(junk) == "—"
    assert pct(junk) == "—"
    assert innings(junk) == "—"


def _jugador_de_cuatro_tabs() -> Player:
    """Un pelotero con TODOS los tabs encendidos: Bateo, Pitcheo, Fildeo y Puestos.

    Cada tab se enciende por su cuenta —`applies_to` mira una tabla distinta— así que hay que darle
    de comer a las cuatro: la carrera de bateo y la de pitcheo, una línea de fildeo que no sea DH, y
    un liderazgo para que Puestos tenga algo que enseñar.
    """
    player = _player(28, "q01", "Cuatro Tablas", "SP")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    PitchingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    FieldingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=2019, stint=1, team="BOS", pa=80, hr=1)
    Pitching.objects.create(player=player, season=2019, stint=1, team="BOS", outs=600, w=15)
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="P", gp=30, po=10)
    metrica = Metric.objects.create(
        stat_group="pitching",
        column="w",
        abbrev="W",
        kind=Metric.Kind.CUMULATIVE,
        direction=Metric.Direction.HIGHER,
        best_season=True,
    )
    Leader.objects.create(player=player, metric=metrica, board=Leader.Board.BEST_SEASON, season=2019, rank=1, value=15)
    return player


@pytest.mark.django_db
def test_the_player_page_stays_within_its_query_budget() -> None:
    """La página calcula TODOS los tabs, no solo el activo (DEV-01 del review v3).

    EL FIXTURE ES LA MITAD DE LA PRUEBA, y la primera versión lo tenía mal. Medía un pelotero con dos
    tabs y ponía el techo en 40; mientras tanto entraron Fildeo y Puestos, y un perfil real pasó de
    25 consultas a 44 — por encima del propio techo— sin que esta prueba dijera nada. O sea que el
    guardia puesto para que el crecimiento fuera ruidoso lo dejó pasar en silencio, que es
    exactamente lo que existía para impedir.

    De ahí que ahora mida el caso PEOR —los cuatro tabs— y no uno cómodo. Un presupuesto medido sobre
    un fixture que no se parece a la realidad no protege nada: da tranquilidad, que es peor que no
    dar nada.

    Es un TECHO y no un número exacto: el punto es cazar un salto de orden de magnitud, no obligar a
    editar el test cada vez que una consulta se reordena.
    """
    player = _jugador_de_cuatro_tabs()
    cliente = Client()
    # Se mide con la caché CALIENTE, que es lo que recibe un visitante. Las tablas de referencia
    # —métricas y umbrales— viven 24 horas y se invalidan por señal, así que la primera petición del
    # día paga 8 consultas más y las demás no. Medir en frío daría un número que casi nadie ve, y
    # ajustar el techo a él dejaría sitio de sobra para que el problema volviera a crecer.
    cliente.get(reverse("player_detail", args=[player.slug]))

    with django_assert_num_queries_lte(_PRESUPUESTO_DE_CONSULTAS):
        assert cliente.get(reverse("player_detail", args=[player.slug])).status_code == 200


@pytest.mark.django_db
def test_el_presupuesto_esta_ajustado_y_no_es_un_numero_generoso() -> None:
    """Un techo tres veces por encima de lo real no caza nada: deja sitio para que el problema crezca.

    Esta prueba mide lo que de verdad cuesta la página y exige que el presupuesto no le saque más de
    un puñado de consultas de margen. Si alguien sube el techo para «arreglar» un fallo del test de
    arriba en vez de mirar por qué creció, esta se cae.
    """
    player = _jugador_de_cuatro_tabs()
    cliente = Client()
    cliente.get(reverse("player_detail", args=[player.slug]))  # calienta cachés y conexión

    with CaptureQueriesContext(connection) as capturadas:
        cliente.get(reverse("player_detail", args=[player.slug]))

    margen = _PRESUPUESTO_DE_CONSULTAS - len(capturadas)
    assert 0 <= margen <= 8, f"{len(capturadas)} consultas contra un techo de {_PRESUPUESTO_DE_CONSULTAS}"


def test_pct_filter_shows_percentage_number() -> None:
    assert pct(0.452) == "45.2"
    assert pct(0.2, 1) == "20.0"
    assert pct(None) == "—"


@pytest.mark.django_db
def test_a_traded_season_lists_each_club_then_the_combined_line() -> None:
    """2021 de Pujols: cada equipo sale como fila, y la combinada del año cierra la temporada."""
    player = _player(17, "x01", "Traspasado", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=2020, stint=1, team="LAN", league="NL", pa=600, hr=40)
    Batting.objects.create(player=player, season=2021, stint=1, team="LAN", league="NL", pa=204, hr=12)
    Batting.objects.create(player=player, season=2021, stint=2, team="ANA", league="AL", pa=92, hr=5)
    Batting.objects.create(player=player, season=2021, stint=3, team="XXX", league="XX", pa=296, hr=17)

    data = BattingTab().context(player)
    lines = [(row.season, row.team) for row, _ in data["rows"]]

    assert lines == [(2020, "LAN"), (2021, "LAN"), (2021, "ANA"), (2021, "XXX")]
    assert data["season_count"] == 2  # 2 temporadas aunque sean 4 filas

    # El resaltado pertenece a la temporada completa, no a media temporada: solo la combinada.
    marked = [(row.season, row.team) for row, leads in data["rows"] if leads]
    assert all(team in {"LAN", "XXX"} for _, team in marked)
    split_rows = [leads for row, leads in data["rows"] if row.season == 2021 and row.team != "XXX"]
    assert all(leads == {} for leads in split_rows)


@pytest.mark.django_db
def test_totals_pane_counts_seasons_and_ends_with_the_career_total() -> None:
    """Una temporada dividida cuenta para CADA equipo, pero una sola vez en la carrera."""
    player = _player(16, "t01", "Cambio de Equipo", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TEAM, team="MIN", sort_order=100)
    BattingCareer.objects.create(player=player, level=CareerLevel.TEAM, team="BOS", sort_order=101)
    BattingCareer.objects.create(player=player, level=CareerLevel.LEAGUE, league="AL", sort_order=200)
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=2002, stint=1, team="MIN", league="AL", pa=400)
    Batting.objects.create(player=player, season=2003, stint=1, team="MIN", league="AL", pa=200)
    Batting.objects.create(player=player, season=2003, stint=2, team="BOS", league="AL", pa=200)
    Batting.objects.create(player=player, season=2003, stint=3, team="XXX", league="AL", pa=400)  # combinada

    totals = BattingTab().context(player)["totals"]
    by_label = {row["label"]: row["seasons"] for row in totals}

    assert by_label["MIN"] == 2  # 2002 y 2003
    assert by_label["BOS"] == 1  # solo la mitad de 2003
    assert by_label["Liga AL"] == 2
    assert totals[-1]["kind"] == "total"  # el total de carrera va de último
    assert totals[-1]["seasons"] == 2  # 2003 dividida cuenta UNA vez


@pytest.mark.django_db
def test_statcast_panes_hidden_for_a_player_without_batted_ball_data() -> None:
    """Un jugador del pasado sin Statcast no debe mostrar los pills."""
    player = _player(13, "s01", "Bateo Antiguo", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=1960, stint=1, team="SFG", pa=600)

    data = BattingTab().context(player)

    assert data["has_statcast"] is False
    assert data["statcast_rows"] == []


@pytest.mark.django_db
def test_statcast_has_no_total_when_coverage_is_partial() -> None:
    """Si Statcast cubre menos temporadas que bateo, la fila total engañaría: no se pone.

    El jugador cruza el piso de 1989: su temporada de 1988 no entra a los paneles Statcast."""
    player = _player(14, "s02", "Cobertura Parcial", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=1988, stint=1, team="BOS", pa=600, balls_in_play=400)
    Batting.objects.create(player=player, season=1996, stint=1, team="BOS", pa=600, balls_in_play=400)

    data = BattingTab().context(player)

    assert data["has_statcast"] is True
    assert len(data["statcast_rows"]) == 1  # 1988 queda fuera del piso
    assert data["statcast_rows"][0][0].season == 1996
    assert data["statcast_full"] is False  # -> sin fila total


@pytest.mark.django_db
def test_statcast_totals_when_every_season_has_data() -> None:
    player = _player(15, "s03", "Cobertura Total", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=2015, stint=1, team="BOS", pa=600, balls_in_play=400)
    Batting.objects.create(player=player, season=2016, stint=1, team="BOS", pa=600, balls_in_play=410)

    data = BattingTab().context(player)

    assert data["statcast_full"] is True


@pytest.mark.django_db
def test_personal_best_higher_is_better_is_the_season_maximum() -> None:
    player = _player(10, "h01", "Bateo HR", "1B")
    Metric.objects.create(
        stat_group="batting", column="hr", kind=Metric.Kind.CUMULATIVE, direction=Metric.Direction.HIGHER
    )
    Batting.objects.create(player=player, season=2018, stint=1, team="BOS", pa=600, hr=54)
    Batting.objects.create(player=player, season=2019, stint=1, team="BOS", pa=600, hr=30)

    seasons = list(Batting.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Batting, "batting", seasons, _catalog("batting"), *qualifier_lookups())

    assert (2018, "hr") in best
    assert (2019, "hr") not in best


@pytest.mark.django_db
def test_personal_best_lower_is_better_is_the_qualified_minimum() -> None:
    """SO (menor es mejor): la mejor marca es el mínimo ENTRE temporadas calificadas por PA,
    no el conteo más pequeño de una muestra chica sin calificar, ni el máximo (que es lo peor)."""
    player = _player(11, "k01", "Bateo Ponches", "1B")
    Metric.objects.create(
        stat_group="batting", column="so", kind=Metric.Kind.CUMULATIVE, direction=Metric.Direction.LOWER
    )
    QualifierDefault.objects.create(stat_group="batting", qualifier_season="PA>=502")
    Batting.objects.create(player=player, season=2018, stint=1, team="BOS", pa=600, so=90)  # mín calificado
    Batting.objects.create(player=player, season=2019, stint=1, team="BOS", pa=600, so=145)  # el peor
    Batting.objects.create(player=player, season=2020, stint=1, team="BOS", pa=40, so=8)  # muestra chica

    seasons = list(Batting.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Batting, "batting", seasons, _catalog("batting"), *qualifier_lookups())

    assert (2018, "so") in best  # el mínimo calificado es su mejor marca
    assert (2019, "so") not in best  # el máximo (peor) nunca
    assert (2020, "so") not in best  # muestra chica sin calificar no cuenta


@pytest.mark.django_db
def test_fielding_is_per_position_and_drops_the_dh() -> None:
    """Una fila por (temporada, posición); el DH no aparece (no defiende); y el resaltado se compara
    DENTRO de cada posición — el mejor PO como 3B no compite contra el PO como jardinero."""
    from dglweb.profiles.tabs import FieldingTab
    from dglweb.stats.models import Fielding, FieldingCareer

    player = _player(32, "f01", "Multi Posición", "3B")
    FieldingCareer.objects.create(player=player, level=CareerLevel.POSITION, pos="3B", sort_order=100)
    FieldingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="3B", gp=150, po=120)
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="SS", gp=5, po=8)
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="DH", gp=20, po=0)  # se descarta

    data = FieldingTab().context(player)
    shown = [(entry["row"].season, entry["row"].pos) for entry in data["lines"]]

    assert (2019, "DH") not in shown  # el DH no aparece
    assert (2019, "3B") in shown and (2019, "SS") in shown
    # PO=120 (3B) es su mejor marca en 3B; PO=8 (SS) es su mejor marca en SS. Cada uno en su posición.
    marks = {(entry["row"].pos): entry["leads"].get("po", "") for entry in data["lines"]}
    assert "lead-best" in marks["3B"]
    assert "lead-best" in marks["SS"]  # 8 no compite contra 120: es el mejor de SS


@pytest.mark.django_db
def test_catcher_total_is_scoped_to_catching_and_keeps_cera() -> None:
    """Las tablas de Receptor son de catcher: su total es la línea de carrera de la posición C (con
    cERA real), no el gran total multi-posición que blanquea las tasas."""
    from dglweb.profiles.tabs import FieldingTab
    from dglweb.stats.models import Fielding, FieldingCareer

    player = _player(33, "c33", "Un Receptor", "C")
    FieldingCareer.objects.create(player=player, level=CareerLevel.POSITION, pos="C", sort_order=100, catcher_era=3.65)
    FieldingCareer.objects.create(player=player, level=CareerLevel.POSITION, pos="1B", sort_order=110)
    FieldingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300, catcher_era=3.62)
    Fielding.objects.create(player=player, season=2019, team="BOS", pos="C", gp=100, innings_outs=2400)
    Fielding.objects.create(player=player, season=2020, team="BOS", pos="C", gp=90, innings_outs=2200)
    Fielding.objects.create(player=player, season=2020, team="BOS", pos="1B", gp=10)  # otra posición no cuenta

    total = FieldingTab().context(player)["catcher_total"]

    assert total is not None
    assert total["seasons"] == 2  # dos temporadas como receptor
    assert total["catcher"][-1]["text"] == "3.65"  # cERA (última col de FIELDING_CATCHER), no blanqueado


def test_catcher_cs_pct_recomputes_from_counts_and_is_none_without_attempts() -> None:
    """SAB-02: CS% = atrapados ÷ intentos (SB+CS), recomputado de los conteos de la fila; sin intentos
    es None (no 0 %), porque un catcher que nunca enfrentó un robo no tiene dato."""
    from dglweb.stats.models import Fielding

    assert Fielding(stolen_bases=70, caught_stealing=30).cs_pct == 0.30  # 30 / 100
    assert Fielding(stolen_bases=0, caught_stealing=0).cs_pct is None  # sin intentos → dato ausente
    assert Fielding().cs_pct is None  # ambos NULL


@pytest.mark.django_db
def test_postseason_single_round_leader_gets_the_season_badge_on_its_lone_line() -> None:
    """Review v4 DEV-02 (opción A): un octubre de UNA sola ronda no tiene fila Tot, así que esa línea
    única ES el agregado y lleva el badge de líder de temporada. En un octubre de varias rondas el
    badge va en la fila Tot, nunca en las rondas individuales."""
    from dglweb.stats.models import BattingPost

    player = _player(40, "z40", "Octubre Z", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    hr = Metric.objects.create(
        stat_group="batting",
        column="hr",
        kind=Metric.Kind.CUMULATIVE,
        direction=Metric.Direction.HIGHER,
        postseason=True,
        best_season=True,
        is_active=True,
    )
    BattingPost.objects.create(player=player, season=2019, round="WS", hr=5)  # una sola ronda
    BattingPost.objects.create(player=player, season=2004, round="DS", hr=2)  # dos rondas
    BattingPost.objects.create(player=player, season=2004, round="WS", hr=3)
    for season in (2019, 2004):  # líder de temporada de postemporada ambos años
        Leader.objects.create(
            metric=hr, board=Leader.Board.BEST_SEASON, season=season, player=player, value=5, rank=1, postseason=True
        )

    post = BattingTab().context(player)["post"]

    def leads(season: int, kind: str) -> dict[str, str]:
        return next(e["leads"] for e in post if e["row"].season == season and e["kind"] == kind)

    assert leads(2019, "line").get("hr") == "lead-season"  # ronda única = agregado → lleva el badge
    assert leads(2004, "season").get("hr") == "lead-season"  # multi-ronda → badge en la fila Tot
    rounds_2004 = [e for e in post if e["row"].season == 2004 and e["kind"] == "line"]
    assert all(not e["leads"] for e in rounds_2004)  # las rondas individuales, sin badge


@pytest.mark.django_db
def test_a_pitchers_batting_table_carries_no_leadership_badges() -> None:
    """Sus turnos al bate son incidentales: se ranquean contra bateadores de oficio. La mejor marca
    personal sí se queda — esa no compara con nadie."""
    pitcher = _player(22, "p02", "Un Abridor", "SP")
    BattingCareer.objects.create(player=pitcher, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=pitcher, season=2019, stint=1, team="BOS", pa=80, hr=2)
    metric = Metric.objects.create(
        stat_group="batting", column="hr", kind=Metric.Kind.CUMULATIVE, direction=Metric.Direction.HIGHER
    )
    Leader.objects.create(metric=metric, board=Leader.Board.BEST_SEASON, season=2019, player=pitcher, value=2, rank=1)
    Leader.objects.create(metric=metric, board=Leader.Board.BEST_CAREER, player=pitcher, value=2, rank=1)

    data = BattingTab().context(pitcher)

    assert data["total_leads"] == {}  # sin azul de líder de por vida
    classes = {css for _, leads in data["rows"] for css in leads.values()}
    assert "lead-season" not in classes and "lead-career" not in classes
    assert "lead-best" in classes  # su mejor marca personal sobrevive


@pytest.mark.django_db
def test_a_pre_1956_player_has_no_leaderships_to_explain() -> None:
    """Tetelo Vargas jugó 1927-1943: los tableros arrancan en 1956, así que no compite en ninguno.
    La leyenda no debe nombrar colores que su página nunca va a mostrar."""
    player = _player(27, "n01", "Tetelo Vargas", "CF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=1943, stint=1, team="NYC", pa=200, h=70)

    data = BattingTab().context(player)

    assert data["has_season_leads"] is False
    assert data["has_career_leads"] is False
    # Pero sus marcas personales siguen: esas solo lo comparan consigo mismo.
    assert any(leads for _, leads in data["rows"])


@pytest.mark.django_db
def test_a_cell_that_is_both_leader_and_personal_best_keeps_the_colour_and_adds_italics() -> None:
    """El color se lo queda el liderazgo —es lo más fuerte— y la itálica dice que además es su
    récord. Dos datos en una celda sin que compitan por el mismo canal."""
    player = _player(31, "i01", "Las Dos Cosas", "LF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    metric = Metric.objects.create(
        stat_group="batting", column="hr", kind=Metric.Kind.CUMULATIVE, direction=Metric.Direction.HIGHER
    )
    Batting.objects.create(player=player, season=2018, stint=1, team="BOS", pa=600, hr=20)
    Batting.objects.create(player=player, season=2019, stint=1, team="BOS", pa=600, hr=54)  # su máximo
    Leader.objects.create(metric=metric, board=Leader.Board.BEST_SEASON, season=2019, player=player, value=54, rank=1)

    marks = {row.season: leads.get("hr", "") for row, leads in BattingTab().context(player)["rows"]}

    assert "lead-season" in marks[2019] and "lead-personal" in marks[2019]  # ambas
    assert marks[2018] == ""  # ni líder ni su mejor marca


@pytest.mark.django_db
def test_exclude_zeros_keeps_a_zero_from_winning_the_personal_best() -> None:
    """`exclude_zeros` marca las métricas donde un cero es una ausencia, no un valor: los holds de
    un abridor, los jonrones de quien nunca sacó la bola. Sin esto la columna entera se pinta como
    su mejor marca — un logro que nadie consiguió porque nadie lo intentó. El flag ya existía y lo
    respetaba el motor de líderes; la página del jugador lo ignoraba."""
    player = _player(29, "z01", "Nunca Lo Hizo", "SP")
    Metric.objects.create(
        stat_group="pitching",
        column="hld",
        kind=Metric.Kind.CUMULATIVE,
        direction=Metric.Direction.HIGHER,
        exclude_zeros=True,
    )
    Pitching.objects.create(player=player, season=2018, stint=1, team="BOS", outs=600, hld=0)
    Pitching.objects.create(player=player, season=2019, stint=1, team="BOS", outs=600, hld=0)

    seasons = list(Pitching.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Pitching, "pitching", seasons, _catalog("pitching"), *qualifier_lookups())

    assert not [column for _, column in best if column == "hld"]  # ninguna temporada marcada


@pytest.mark.django_db
def test_exclude_zeros_still_marks_the_seasons_he_did_it() -> None:
    player = _player(30, "z02", "Sí Lo Hizo", "RP")
    Metric.objects.create(
        stat_group="pitching",
        column="hld",
        kind=Metric.Kind.CUMULATIVE,
        direction=Metric.Direction.HIGHER,
        exclude_zeros=True,
    )
    Pitching.objects.create(player=player, season=2018, stint=1, team="BOS", outs=200, hld=0)
    Pitching.objects.create(player=player, season=2019, stint=1, team="BOS", outs=200, hld=31)

    seasons = list(Pitching.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Pitching, "pitching", seasons, _catalog("pitching"), *qualifier_lookups())

    assert (2019, "hld") in best
    assert (2018, "hld") not in best


@pytest.mark.django_db
def test_cs_zero_is_a_personal_best_only_when_he_actually_ran() -> None:
    """No haber sido atrapado robando no dice nada si nunca intentó robar."""
    player = _player(21, "c02", "Nunca Corre", "1B")
    Metric.objects.create(
        stat_group="batting", column="cs", kind=Metric.Kind.CUMULATIVE, direction=Metric.Direction.LOWER
    )
    QualifierDefault.objects.create(stat_group="batting", qualifier_season="PA>=502")
    Batting.objects.create(player=player, season=2016, stint=1, team="BOS", pa=600, sb=0, cs=0)
    Batting.objects.create(player=player, season=2017, stint=1, team="BOS", pa=600, sb=12, cs=0)
    Batting.objects.create(player=player, season=2018, stint=1, team="BOS", pa=600, sb=5, cs=4)

    seasons = list(Batting.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Batting, "batting", seasons, _catalog("batting"), *qualifier_lookups())

    assert (2017, "cs") in best  # robó 12 y nunca lo atraparon: eso sí es una marca
    assert (2016, "cs") not in best  # 0 de 0 intentos no es un logro


@pytest.mark.django_db
def test_personal_best_rate_ignores_small_sample_extreme() -> None:
    """Un rate (BABIP) se dispara en una muestra chica de 51 PA; la verdadera mejor marca es la
    temporada CALIFICADA más alta, no la muestra chica (el bug reportado en 1997 de Ortiz)."""
    player = _player(12, "b02", "Bateo BABIP", "1B")
    Metric.objects.create(
        stat_group="batting", column="babip", kind=Metric.Kind.RATE, direction=Metric.Direction.HIGHER
    )
    QualifierDefault.objects.create(stat_group="batting", qualifier_season="PA>=502")
    Batting.objects.create(player=player, season=1997, stint=1, team="MIN", pa=51, babip=0.420)  # muestra chica
    Batting.objects.create(player=player, season=2006, stint=1, team="BOS", pa=686, babip=0.350)  # máx calificado
    Batting.objects.create(player=player, season=2007, stint=1, team="BOS", pa=667, babip=0.330)

    seasons = list(Batting.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Batting, "batting", seasons, _catalog("batting"), *qualifier_lookups())

    assert (1997, "babip") not in best  # muestra chica sin calificar no cuenta
    assert (2006, "babip") in best  # el máximo entre temporadas calificadas


def _metric(
    group: str,
    column: str,
    abbrev: str,
    *,
    sort_order: int = 0,
    name_es: str = "",
    direction: str = Metric.Direction.HIGHER,
) -> Metric:
    return Metric.objects.create(
        stat_group=group,
        column=column,
        abbrev=abbrev,
        name_es=name_es,
        sort_order=sort_order,
        kind=Metric.Kind.CUMULATIVE,
        direction=direction,
        best_season=True,
        is_active=True,
    )


def _puesto(metric: Metric, player: Player, season: int, rank: int, *, postseason: bool = False) -> None:
    Leader.objects.create(
        metric=metric,
        board=Leader.Board.BEST_SEASON,
        season=season,
        player=player,
        value=float(rank),
        rank=rank,
        postseason=postseason,
    )


def _puesto_career(metric: Metric, player: Player, rank: int, *, postseason: bool = False) -> None:
    Leader.objects.create(
        metric=metric,
        board=Leader.Board.BEST_CAREER,
        season=None,
        player=player,
        value=float(rank),
        rank=rank,
        postseason=postseason,
    )


def _flat(grid: dict[str, Any]) -> list[dict[str, Any]]:
    """Todas las filas de una rejilla (Serie Regular o Postemporada), aplanadas por sus divisiones."""
    return [row for section in grid["sections"] for row in section["rows"]]


@pytest.mark.django_db
def test_puestos_grid_pivots_top10_by_metric_and_season() -> None:
    """Una fila por métrica con top-10, una columna por temporada; la celda es el puesto y queda en
    blanco donde no estuvo en el top-10. Un puesto > 10 no entra y una métrica sin ningún top-10 se
    cae."""
    player = _player(1, "a01", "Bateador A", "1B")
    rival = _player(9, "z01", "Rival Z", "1B")
    hr = _metric("batting", "hr", "HR", sort_order=13, name_es="Jonrones")
    so = _metric("batting", "so", "SO", sort_order=14, name_es="Ponches", direction=Metric.Direction.LOWER)
    avg = _metric("batting", "avg", "AVG", sort_order=20, name_es="Promedio de bateo")
    _puesto(hr, player, 2001, 3)
    _puesto(hr, player, 2002, 1)  # HR: 2001 y 2002
    _puesto(hr, rival, 2002, 1)  # empate en 2002 -> el puesto 1 va con *
    _puesto(so, player, 2002, 5)  # SO: solo 2002
    _puesto(avg, player, 2001, 15)  # puesto 16+ no entra -> AVG no aparece
    _puesto_career(hr, player, 4)  # de por vida: HR puesto 4
    _puesto_career(so, player, 12)  # SO carrera puesto 12 (dentro del top-25 de por vida)

    reg = _puestos_context(player)["regular"]

    def show(cell: dict[str, Any]) -> str:
        return "" if cell["rank"] is None else f"{cell['rank']}{'*' if cell['tied'] else ''}"

    assert reg["seasons"] == [2001, 2002]
    assert [section["label"] for section in reg["sections"]] == ["Estándar"]  # HR y SO viven en Estándar
    grid = [
        (row["abbrev"], row["direction"], [show(c) for c in row["cells"]], show(row["career"])) for row in _flat(reg)
    ]
    assert grid == [
        ("HR", "+", ["3", "1*"], "4"),  # 2002 empatado -> *; de por vida #4 (sin empate)
        ("SO", "-", ["", "5"], "12"),  # de por vida top-25: el puesto 12 sí aparece
    ]
    assert _flat(reg)[0]["name"] == "Jonrones"  # columna 1 = nombre largo


@pytest.mark.django_db
def test_puestos_includes_a_metric_that_is_top25_only_de_por_vida() -> None:
    """Un jugador puede estar en el top-25 de por vida (última columna) sin haber estado nunca en un
    top-10 de temporada —constancia sin picos—: esa fila igual debe salir, con las celdas de temporada
    en blanco y solo el puesto de por vida. La de-por-vida llega al 25, no solo al 10."""
    player = _player(7, "c07", "Constante C", "1B")
    hr = _metric("batting", "hr", "HR", sort_order=13, name_es="Jonrones")
    bb = _metric("batting", "bb", "BB", sort_order=15, name_es="Bases por bolas")
    afuera = _metric("batting", "rbi", "RBI", sort_order=14, name_es="Impulsadas")
    _puesto(hr, player, 2001, 2)  # HR sí tuvo top-10 de temporada
    _puesto_career(bb, player, 20)  # BB: solo de por vida, puesto 20 (dentro del top-25)
    _puesto_career(afuera, player, 30)  # RBI carrera puesto 30: fuera del top-25 -> no aparece

    reg = _puestos_context(player)["regular"]

    rows = {row["abbrev"]: row for row in _flat(reg)}
    assert set(rows) == {"HR", "BB"}  # BB entra por el top-25 de por vida; RBI (30) no
    assert [c["rank"] for c in rows["BB"]["cells"]] == [None]  # celdas de temporada vacías
    assert rows["BB"]["career"]["rank"] == 20  # solo el puesto de por vida (top-25)


@pytest.mark.django_db
def test_puestos_shows_only_the_players_trade() -> None:
    """Un lanzador solo ve sus puestos de PITCHEO: su bateo incidental se rankea contra bateadores de
    verdad, así que no es su puesto. (Y a la inversa para un bateador.)"""
    pitcher = _player(2, "p01", "Lanzador P", "P")
    era = _metric("pitching", "era", "ERA", sort_order=17, name_es="Efectividad")
    bat_hr = _metric("batting", "hr", "HR", sort_order=13, name_es="Jonrones")
    _puesto(era, pitcher, 2010, 2)
    _puesto(bat_hr, pitcher, 2010, 1)  # su bateo incidental: NO debe aparecer

    reg = _puestos_context(pitcher)["regular"]

    assert [row["abbrev"] for row in _flat(reg)] == ["ERA"]


@pytest.mark.django_db
def test_puestos_groups_metrics_into_table_divisions_in_order() -> None:
    """Las filas se agrupan en las divisiones de las tablas (Estándar, Avanzado, Statcast,
    Coeficientes) y en su mismo orden. Sencillos (1B) va entre H y 2B dentro de Estándar."""
    player = _player(8, "d08", "Completo D", "1B")
    metrics = {
        "H": _metric("batting", "h", "H"),
        "1B": _metric("batting", "x1b", "1B"),
        "2B": _metric("batting", "x2b", "2B"),
        "ISO": _metric("batting", "iso", "ISO"),
        "AO": _metric("batting", "air_outs", "AO"),
        "GB%": _metric("batting", "gb_pct", "GB%"),
    }
    for metric in metrics.values():
        _puesto(metric, player, 2005, 3)

    reg = _puestos_context(player)["regular"]

    assert [(s["label"], [r["abbrev"] for r in s["rows"]]) for s in reg["sections"]] == [
        ("Estándar", ["H", "1B", "2B"]),  # 1B entre H y 2B
        ("Avanzado", ["ISO"]),
        ("Statcast", ["AO"]),
        ("Coeficientes", ["GB%"]),
    ]
    gb = next(r for s in reg["sections"] for r in s["rows"] if r["abbrev"] == "GB%")
    assert gb["descriptive"] is True  # SAB-01: GB% es descriptiva, no "mejor/peor"


@pytest.mark.django_db
def test_puestos_has_separate_regular_and_postseason_boards() -> None:
    """Dos rejillas independientes: Serie Regular y Postemporada, cada una con sus propios puestos."""
    player = _player(10, "e10", "Octubre E", "1B")
    hr = _metric("batting", "hr", "HR", name_es="Jonrones")
    _puesto(hr, player, 2004, 3)  # regular 2004: puesto 3
    _puesto(hr, player, 2004, 1, postseason=True)  # octubre 2004: puesto 1
    _puesto_career(hr, player, 5, postseason=True)  # octubre carrera: puesto 5

    data = _puestos_context(player)

    assert [r["abbrev"] for r in _flat(data["regular"])] == ["HR"]
    assert data["regular"]["seasons"] == [2004]
    post = data["postseason"]
    assert post is not None
    hr_row = _flat(post)[0]
    assert hr_row["cells"][0]["rank"] == 1  # puesto 1 en octubre 2004
    assert hr_row["career"]["rank"] == 5  # de por vida en octubre, puesto 5


@pytest.mark.django_db
def test_puestos_postseason_is_none_without_october_top10() -> None:
    """Sin ningún top-10 de octubre, la rejilla de Postemporada es None (el pill no se muestra)."""
    player = _player(11, "e11", "Solo Regular", "1B")
    hr = _metric("batting", "hr", "HR")
    _puesto(hr, player, 2004, 3)  # solo regular

    data = _puestos_context(player)

    assert data["regular"] is not None
    assert data["postseason"] is None


@pytest.mark.django_db
def test_puestos_tab_hidden_without_any_top10() -> None:
    player = _player(3, "b01", "Bateador B", "1B")
    hr = _metric("batting", "hr", "HR", sort_order=13)
    _puesto(hr, player, 2001, 12)  # fuera del top-10

    assert PuestosTab().applies_to(player) is False
    assert "puestos" not in [tab.key for tab in tabs_for(player)]


# ── SAB-03b: la marca de dato incompleto va en la CELDA, no sobre el panel ───────────────────────


@pytest.mark.django_db
def test_solo_se_marcan_las_columnas_que_de_verdad_estan_incompletas() -> None:
    """En 1989-97 la fuente no tipificó todos los HITS. Los OUTS por tipo están completos.

    Advertir sobre el panel entero marcaba 5 columnas de 12 sin motivo, y obligaba al lector a
    cruzar el año con los nombres de las columnas de memoria. La marca en la celda lo dice donde se
    toma la decisión de creerle o no a un número.
    """
    from dglweb.profiles.tabs import _marcar_sin_tipificar

    marcados = _marcar_sin_tipificar(1990, {})

    # Los hits por tipo y los coeficientes, sí: su numerador incluye los hits que faltan.
    assert all(marcados[c] == "dato-parcial" for c in ("ground_hits", "fly_hits", "gb_pct", "gb_fb"))
    # Los outs por tipo, NO. Es el finding entero.
    assert not any(c in marcados for c in ("ground_outs", "fly_outs", "line_outs", "pop_outs", "ao"))
    # Contact% y Whiff% tampoco: se calculan sobre swings, que la fuente sí entrega completos.
    assert "contact_pct" not in marcados and "whiff_pct" not in marcados


@pytest.mark.django_db
def test_una_temporada_sana_no_lleva_ninguna_marca() -> None:
    from dglweb.profiles.tabs import _marcar_sin_tipificar

    assert _marcar_sin_tipificar(2001, {}) == {}


@pytest.mark.django_db
def test_la_marca_se_suma_al_resaltado_sin_pisarlo() -> None:
    """Una celda puede ser líder de temporada Y estar incompleta. Quedarse con una sola de las dos
    marcas perdería información — y el color ya está tomado, por eso la marca es un subrayado."""
    from dglweb.profiles.tabs import _marcar_sin_tipificar

    marcados = _marcar_sin_tipificar(1990, {"gb_pct": "lead-season"})

    assert marcados["gb_pct"] == "lead-season dato-parcial"


@pytest.mark.django_db
def test_marcar_no_toca_el_diccionario_original() -> None:
    """Los `leads` los comparten las filas de Estándar y Avanzado, que NO están afectados. Mutarlos
    pintaría el subrayado en paneles donde el dato está completo."""
    from dglweb.profiles.tabs import _marcar_sin_tipificar

    original = {"gb_pct": "lead-season"}
    _marcar_sin_tipificar(1990, original)

    assert original == {"gb_pct": "lead-season"}


# ── Cobertura punto 4: los subtotales de fildeo en POSTEMPORADA ─────────────────────────────────
#
# Todo este bloque de `_fielding_context` estaba sin una sola prueba. No es código de borde: es la
# tabla que ve cualquiera que abra el tab de Fildeo de un pelotero con octubres, y su regla más
# delicada —borrar los promedios cuando el total suma posiciones— es justo del tipo que se rompe sin
# que nadie lo note, porque un número equivocado ahí sigue pareciendo un número.


def _fildeo_octubre(player: Player, pos: str, season: int, ronda: str, **extra: object) -> None:
    from dglweb.stats.models import FieldingPost

    FieldingPost.objects.create(player=player, season=season, round=ronda, team="BOS", league="AL", pos=pos, **extra)


@pytest.mark.django_db
def test_el_fildeo_de_octubre_se_subtotaliza_por_posicion() -> None:
    """Un pelotero que jugó dos posiciones en octubre lleva una fila de subtotal por cada una.

    Ordenadas por juegos, de más a menos: la posición donde de verdad jugó va primero, no la que
    salga antes en el alfabeto.
    """
    from dglweb.profiles.tabs import FieldingTab

    jugador = Player.objects.create(**_other_player(player_id=900, dgl_id="f01", full_name="Un Fildeador"))
    _fildeo_octubre(jugador, "2B", 2013, "WS", gp=2, po=4)
    _fildeo_octubre(jugador, "SS", 2013, "LCS", gp=6, po=10)

    datos = FieldingTab().context(jugador)

    etiquetas = [t["label"] for t in datos["post_totals"]]
    assert etiquetas == ["SS", "2B", "Total"], "por juegos de más a menos, y el Total al cierre"
    assert datos["post_totals"][0]["seasons"] == 1


@pytest.mark.django_db
def test_el_total_de_octubre_borra_los_promedios_cuando_suma_posiciones() -> None:
    """La regla que hace honesta la fila de Total.

    Un fildeo promedio que mezcla campocorto con segunda base no significa nada: son dificultades
    distintas. Sumar los CONTEOS sí vale —los outs son outs— pero publicar el promedio resultante
    sería inventar una métrica. Se borra en vez de calcularse.
    """
    from dglweb.profiles.tabs import FieldingTab

    jugador = Player.objects.create(**_other_player(player_id=901, dgl_id="f02", full_name="Otro Fildeador"))
    _fildeo_octubre(jugador, "2B", 2013, "WS", gp=2, po=4, a=2, e=0)
    _fildeo_octubre(jugador, "SS", 2013, "LCS", gp=6, po=10, a=8, e=1)

    total = FieldingTab().context(jugador)["post_total_cells"]["standard"]
    columnas = {c.attr: celda["text"] for c, celda in zip(columns.FIELDING_STANDARD, total, strict=True)}

    assert columnas["po"] == "14", "los conteos SÍ se suman"
    assert columnas["fld_pct"] == "—", "el promedio de dos posiciones distintas no se publica"


@pytest.mark.django_db
def test_con_una_sola_posicion_el_promedio_de_octubre_si_se_publica() -> None:
    """El reverso: si no hay mezcla, no hay nada que borrar y esconderlo sería perder un dato."""
    from dglweb.profiles.tabs import FieldingTab

    jugador = Player.objects.create(**_other_player(player_id=902, dgl_id="f03", full_name="Un Campocorto"))
    _fildeo_octubre(jugador, "SS", 2013, "WS", gp=4, po=10, a=8, e=0)
    _fildeo_octubre(jugador, "SS", 2018, "WS", gp=5, po=12, a=9, e=0)

    datos = FieldingTab().context(jugador)
    total = datos["post_total_cells"]["standard"]
    columnas = {c.attr: celda["text"] for c, celda in zip(columns.FIELDING_STANDARD, total, strict=True)}

    assert columnas["fld_pct"] != "—"
    assert [t["label"] for t in datos["post_totals"]] == ["SS", "Total"]
    assert datos["post_totals"][-1]["seasons"] == 2, "dos octubres, aunque sean cuatro rondas"


# ── La caché de las tablas de referencia (métricas y umbrales) ───────────────────────────────────


@pytest.mark.django_db
def test_los_umbrales_no_vuelven_a_tocar_sus_tablas() -> None:
    """La página los pedía una vez POR TAB: cuatro consultas a una tabla de TRES filas.

    Ya no son cero consultas —la caché vive en la base, para que la vean todos los workers— sino UNA
    lectura de la caché por llamada, en vez de las tres tablas de referencia. Lo que esta prueba
    protege es eso: que no se vuelva a `dgl_metric` ni a `dgl_qualifier_*`.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from dglweb.profiles.metric_layout import qualifier_lookups

    qualifier_lookups()  # la primera llena la caché

    with CaptureQueriesContext(connection) as capturadas:
        for _ in range(5):
            qualifier_lookups()

    tablas = " ".join(q["sql"] for q in capturadas)
    assert "dgl_qualifier" not in tablas, "volvió a la tabla de umbrales"
    assert "dgl_metric" not in tablas


@pytest.mark.django_db
def test_editar_un_umbral_lo_publica_de_inmediato() -> None:
    """La otra mitad, y la que de verdad importa.

    Una caché sin invalidación no es una optimización: es un fallo con retraso. El dueño cambia un
    umbral en el Backoffice, la página sigue publicando el viejo hasta 24 horas y nada lo dice —
    peor que la consulta de más que se quería ahorrar.
    """
    from dglweb.profiles.metric_layout import qualifier_lookups
    from dglweb.stats.models import QualifierDefault

    fila = QualifierDefault.objects.create(
        stat_group="batting", qualifier_season="PA>=502", qualifier_career="PA>=3000"
    )
    assert qualifier_lookups()[0]["batting"][0] == "PA>=502"

    fila.qualifier_season = "PA>=400"
    fila.save()

    assert qualifier_lookups()[0]["batting"][0] == "PA>=400", "la señal no tiró la caché"


@pytest.mark.django_db
def test_borrar_una_metrica_tambien_tira_la_cache() -> None:
    """`post_delete` además de `post_save`: una métrica retirada tiene que desaparecer del catálogo,
    o la página seguiría rankeando por una columna que ya nadie mantiene."""
    from dglweb.profiles.metric_layout import metric_catalog

    metrica = Metric.objects.create(
        stat_group="batting",
        column="inventada",
        abbrev="XX",
        kind=Metric.Kind.CUMULATIVE,
        direction=Metric.Direction.HIGHER,
    )
    assert "inventada" in metric_catalog("batting")

    metrica.delete()

    assert "inventada" not in metric_catalog("batting")
