"""El widget «Un día como hoy» de la portada.

Lo que se prueba acá es la ELECCIÓN y el RITMO, que es todo lo que hace este módulo: cuáles de las
efemérides del día caben, en qué pares se reparten, cuánto se queda cada par y quién no puede salir.
El texto no se prueba porque no se escribe acá: viene ya redactado del archivo (`docs/EFEMERIDES.md`).
"""

import re
from datetime import date
from typing import Any

import pytest
from django.template.loader import render_to_string
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from dglweb.players.models import Player
from dglweb.stats import efemerides
from dglweb.stats.models import Efemeride
from tests.test_players import _other_player

HOY = date(2026, 8, 4)


def _jugador(**cambios: Any) -> Player:
    base = {"player_id": 405395, "dgl_id": "puj01", "full_name": "Albert Pujols"}
    return Player.objects.create(**_other_player(**(base | cambios)))


def _efemeride(jugador: Player, **cambios: Any) -> Efemeride:
    base = {
        "tipo": "hito_hr",
        "gesta": "700 jonrones",
        "etiquetas": "",
        "rol": "bateador",
        "signo": 1,
        "cobertura": "completa",
        "mlb_id": jugador.player_id,
        "nombre": "Albert Pujols",
        "fecha": date(2022, 9, 23),
        "mes": HOY.month,
        "dia": HOY.day,
        "temporada": 2022,
        "anos": 42,
        "game_id": "LAN202209230",
        "event_id": 0,
        "game_type": "R",
        "equipo": "SLN",
        "equipo_nombre": "St. Louis Cardinals",
        "rival": "MIL",
        "rival_nombre": "Milwaukee Brewers",
        "en_casa": 0,
        "oponente": "",
        "magnitud": 700.0,
        "wpa_jugador": None,
        "li_max": None,
        "detalle": "",
        "veces_total": 1,
        "jugadores_total": 1,
        "orden": 1,
        "veces_jugador": 1,
        "orden_jugador": 1,
        "rareza": 600.0,
        "puntaje": 900,
        "titular": "Conectó su jonrón 700 contra Milwaukee Brewers.",
        "situacion": "Es el único dominicano con 700 jonrones.",
        "participantes": "",
    }
    return Efemeride.objects.create(**(base | cambios))


def _llenar(cuantas: int, **cambios: Any) -> list[Efemeride]:
    """`cuantas` efemérides del mismo día, cada una de un jugador distinto y de puntaje decreciente."""
    filas = []
    for i in range(cuantas):
        jugador = _jugador(player_id=500000 + i, dgl_id=f"x{i:04d}", full_name=f"Pelotero {i}")
        filas.append(_efemeride(jugador, puntaje=900 - i, nombre=f"Pelotero {i}", **cambios))
    return filas


@pytest.mark.django_db
def test_a_day_with_nothing_gives_none_so_the_panel_is_not_drawn() -> None:
    """Ocho días del año no tienen ninguna. Un panel con título y cuerpo hueco se lee como roto."""
    assert efemerides.del_dia(HOY) is None


@pytest.mark.django_db
def test_only_the_facts_of_that_calendar_day_come_out() -> None:
    jugador = _jugador()
    _efemeride(jugador)
    _efemeride(jugador, mes=12, dia=25, game_id="SLN202212250", titular="Otra cosa, en Navidad.")

    datos = efemerides.del_dia(HOY)

    assert datos is not None
    assert [t.titular for t in datos["tarjetas"]] == ["Conectó su jonrón 700 contra Milwaukee Brewers."]


@pytest.mark.django_db
def test_the_day_is_capped_and_the_best_scored_are_the_ones_that_survive() -> None:
    """La mediana son 17 al día y el máximo 54. Enseñarlas todas serían minutos de rotación."""
    _llenar(25)

    datos = efemerides.del_dia(HOY)

    assert datos is not None
    assert len(datos["tarjetas"]) == efemerides.TOPE
    # Las de más puntaje, y en ese orden.
    assert [t.nombre for t in datos["tarjetas"]] == [f"Pelotero {i}" for i in range(efemerides.TOPE)]


@pytest.mark.django_db
def test_the_cards_travel_loose_and_not_in_pairs() -> None:
    """El servidor NO empareja, y esa es la pieza que deja al móvil enseñar una sola a la vez.

    Emparejar acá obligaba al teléfono a partir un par ya armado, que no se puede: la ventana mide
    dos o una según el ancho, y el ancho solo se sabe en el navegador. Quien agrupa es
    `dia_como_hoy.js` con la misma consulta de 768px que usa el CSS.
    """
    _llenar(5)

    datos = efemerides.del_dia(HOY)

    assert datos is not None
    assert len(datos["tarjetas"]) == 5
    # Y cada una trae SU cuenta, no la del par: es lo que el JavaScript suma según cuántas se vean.
    assert all(t.ms > 0 for t in datos["tarjetas"])


@pytest.mark.django_db
def test_a_hidden_player_does_not_reach_the_front_page() -> None:
    """Dar de baja a alguien en el Backoffice lo saca del sitio, y esto es el sitio.

    Sin el filtro, la tarjeta lo nombraría igual —el nombre viene del archivo, no de `Player`— y solo
    fallaría al construir el enlace a un perfil que ya no responde. Es la misma regla que cubre
    `test_visibilidad_widgets.py` para los otros widgets de portada.
    """
    visible = _jugador()
    oculto = _jugador(player_id=999999, dgl_id="ocu01", full_name="Dado de baja", hidden=True)
    _efemeride(visible, puntaje=500)
    _efemeride(oculto, puntaje=900, nombre="Dado de baja")

    datos = efemerides.del_dia(HOY)

    assert datos is not None
    assert [t.nombre for t in datos["tarjetas"]] == ["Albert Pujols"]


@pytest.mark.django_db
def test_hiding_someone_does_not_leave_the_widget_short() -> None:
    """Por eso se piden `TOPE + _MARGEN` a la base y se recorta después de filtrar."""
    _llenar(19)
    Player.objects.filter(player_id=500000).update(hidden=True, disabled_reason="prueba")

    datos = efemerides.del_dia(HOY)

    assert datos is not None
    assert len(datos["tarjetas"]) == efemerides.TOPE


@pytest.mark.django_db
def test_each_card_costs_what_its_own_text_costs_with_no_cap_applied() -> None:
    """Un tiempo fijo trata igual «Cumple 70 años.» y una entrada de 250 caracteres.

    SIN TOPAR ACÁ, que es lo que cambió al meter el móvil: el suelo y el techo son de la VENTANA, y
    la ventana mide dos tarjetas o una según el ancho. Toparlas de una en una haría que dos
    cumpleaños seguidos costaran veinte segundos en escritorio, cuando entre los dos no llegan a
    cuarenta caracteres. Quien topa es `dia_como_hoy.js`, con `data-min` y `data-max`.
    """
    corto = _jugador()
    _efemeride(corto, puntaje=900, nombre="A", titular="Cumple 70 años.", situacion="")
    largo = _jugador(player_id=120074, dgl_id="ort01", full_name="David Ortiz")
    _efemeride(largo, puntaje=100, nombre="B", titular="x" * 250, situacion="y" * 100)

    tarjetas = efemerides.del_dia(HOY)["tarjetas"]  # type: ignore[index]

    # 16 caracteres: por debajo del suelo de 10 s, y sale por debajo porque acá no se topa.
    assert tarjetas[0].ms == 1333
    # 351 caracteres: 351/12 = 29,25 s, por encima del techo de 24. Tampoco se topa.
    assert tarjetas[1].ms == 29250


@pytest.mark.django_db
def test_the_window_caps_travel_in_the_payload_so_the_number_lives_in_python() -> None:
    """El `.js` los aplica pero no los sabe: así el suelo y el techo se prueban acá."""
    _efemeride(_jugador())

    datos = efemerides.del_dia(HOY)

    assert datos is not None
    assert datos["minimo_ms"] == efemerides._MINIMO * 1000
    assert datos["maximo_ms"] == efemerides._MAXIMO * 1000


@pytest.mark.django_db
def test_the_rendered_widget_names_the_player_and_links_to_the_profile() -> None:
    """El titular del cumpleaños es «Cumple 70 años.» y no dice de quién: el nombre lo pone la plantilla."""
    jugador = _jugador()
    _efemeride(jugador, tipo="cumpleanos", titular="Cumple 46 años.", situacion="", temporada=1980)

    cuerpo = render_to_string("widgets/_dia_como_hoy.html", {"dia_como_hoy": efemerides.del_dia(HOY)})

    assert "Albert Pujols" in cuerpo
    assert reverse("player_detail", args=[jugador.slug]) in cuerpo
    assert "Cumple 46 años." in cuerpo
    assert "1980" in cuerpo


@pytest.mark.django_db
def test_every_card_ships_in_the_html_with_its_own_duration() -> None:
    """La rotación es enseñar y esconder lo que ya está: sin `fetch` y sin una consulta por vuelta."""
    _llenar(6)

    cuerpo = render_to_string("widgets/_dia_como_hoy.html", {"dia_como_hoy": efemerides.del_dia(HOY)})

    assert cuerpo.count('class="dgl-dch-caja') == 6
    assert cuerpo.count("data-ms=") == 6
    # SIN JAVASCRIPT se ven la primera —siempre— y la segunda solo a partir de 768px, y quien lo
    # decide es el CSS. El `.js` quita estas dos clases en cuanto arranca.
    assert cuerpo.count("es-primera") == 1
    assert cuerpo.count("es-segunda") == 1


@pytest.mark.django_db
def test_no_number_reaches_the_html_with_a_spanish_decimal_or_thousands_separator() -> None:
    """`parseInt("24.000")` devuelve 24 y `parseFloat("8,6")` devuelve 8. Los dos recortan callados.

    Ya pasó una vez —el atributo salía `data-segundos="24,0"`— y por eso los números van en
    milisegundos enteros y pasan por `unlocalize`.
    """
    _llenar(4)

    cuerpo = render_to_string("widgets/_dia_como_hoy.html", {"dia_como_hoy": efemerides.del_dia(HOY)})

    for atributo in ("data-ms", "data-min", "data-max"):
        for valor in re.findall(rf'{atributo}="([^"]*)"', cuerpo):
            assert valor.isdigit(), f"{atributo}={valor!r} no es un entero limpio"


@pytest.mark.django_db
def test_the_controls_ship_hidden_because_without_javascript_they_move_nothing() -> None:
    """Sin el script no hay rotación, y unas flechas que no mueven nada son un botón roto."""
    _llenar(4)

    cuerpo = render_to_string("widgets/_dia_como_hoy.html", {"dia_como_hoy": efemerides.del_dia(HOY)})

    assert 'class="dgl-dch-controles" hidden' in cuerpo
    # `dgl-pill`, el mismo control que Bateo/Pitcheo en líderes. Si alguien le pone estilo propio a
    # estos dos botones, esto lo delata.
    assert cuerpo.count('class="dgl-pill" data-dch-mover=') == 2
    assert "Anterior" in cuerpo
    assert "Próximo" in cuerpo
    # Los puntos los dibuja el `.js`: cuántos hay depende del ancho —ocho pantallas en escritorio y
    # dieciséis en móvil— y eso el servidor no lo sabe.
    assert cuerpo.count("dgl-dch-punto ") == 0


@pytest.mark.django_db
def test_the_home_page_shows_the_widget() -> None:
    # Con el día de VERDAD y no con `HOY`: la portada no recibe fecha, pregunta por hoy. Fijarla acá
    # dejaría una prueba que pasa el 4 de agosto y falla el 5.
    dia = timezone.localdate()
    jugador = _jugador()
    _efemeride(jugador, mes=dia.month, dia=dia.day)

    cuerpo = Client().get("/").content.decode()

    assert "Un día como hoy" in cuerpo
    assert "Conectó su jonrón 700 contra Milwaukee Brewers." in cuerpo


@pytest.mark.django_db
def test_the_home_page_survives_a_day_with_no_efemerides() -> None:
    """El 29 de febrero y siete días de invierno no tienen ninguna, y la portada tiene que cargar."""
    respuesta = Client().get("/")

    assert respuesta.status_code == 200
    assert "Un día como hoy" not in respuesta.content.decode()
