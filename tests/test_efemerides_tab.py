"""El tab de Efemérides del perfil.

Lo que hay que probar acá no es el contenido —ese lo produce y lo comprueba el exportador— sino las
tres decisiones que tomó ESTE tab: qué se muestra, en qué orden, y qué fecha se pinta.

La del orden es la menos obvia y la más fácil de romper: en las gestas de persona la columna `fecha`
guarda el aniversario de ESTE año, no el año en que pasó. Ordenar por ahí pondría un debut de 1960
encima de un ciclo de 2019.
"""

from datetime import date
from typing import Any

import pytest
from django.template.loader import render_to_string

from dglweb.players.models import Player
from dglweb.profiles.tabs import EfemeridesTab, tabs_for
from dglweb.stats.models import Efemeride
from tests.test_players import _other_player


def _jugador(**cambios: Any) -> Player:
    return Player.objects.create(
        **_other_player(player_id=646240, dgl_id="dev01", full_name="Rafael Devers", **cambios)
    )


def _efemeride(jugador: Player, **cambios: Any) -> Efemeride:
    base = {
        "tipo": "ciclo",
        "gesta": "un ciclo",
        "etiquetas": "",
        "rol": "bateador",
        "signo": 1,
        "cobertura": "completa",
        "mlb_id": jugador.player_id,
        "nombre": "Rafael Devers",
        "fecha": date(2019, 4, 5),
        "mes": 4,
        "dia": 5,
        "temporada": 2019,
        "anos": 7,
        "game_id": "PHI201904050",
        "event_id": 0,
        "game_type": "R",
        "equipo": "BOS",
        "equipo_nombre": "Boston Red Sox",
        "rival": "PHI",
        "rival_nombre": "Philadelphia Phillies",
        "en_casa": 0,
        "oponente": "",
        "magnitud": 4.0,
        "wpa_jugador": None,
        "li_max": None,
        "detalle": "",
        "veces_total": 20,
        "jugadores_total": 16,
        "orden": 18,
        "veces_jugador": 1,
        "orden_jugador": 1,
        "rareza": 457.2,
        "puntaje": 715,
        "titular": "Bateó para el ciclo contra Philadelphia Phillies.",
        "situacion": "Es uno de los 16 dominicanos con un ciclo.",
    }
    return Efemeride.objects.create(**(base | cambios))


def _pintar(jugador: Player) -> str:
    tab = EfemeridesTab()
    return render_to_string(tab.template, {"tab": {"data": tab.context(jugador)}})


@pytest.mark.django_db
def test_the_tab_is_hidden_for_a_player_with_no_efemerides() -> None:
    """Un tab vacío es peor que ninguno: promete algo que no hay."""
    jugador = _jugador()

    assert not EfemeridesTab().applies_to(jugador)
    assert "efemerides" not in [tab.key for tab in tabs_for(jugador)]


@pytest.mark.django_db
def test_the_tab_appears_once_the_player_has_one() -> None:
    jugador = _jugador()
    _efemeride(jugador)

    assert EfemeridesTab().applies_to(jugador)
    assert "efemerides" in [tab.key for tab in tabs_for(jugador)]


@pytest.mark.django_db
def test_person_facts_are_ordered_by_the_year_it_happened_and_not_by_the_anniversary() -> None:
    """La trampa de este dataset, y la razón de que el orden no sea por `fecha`.

    El debut de 1960 viaja con `fecha` en el año en curso —así es como el archivo se consulta por «un
    día como hoy»— y el año de verdad vive en `temporada`. Ordenando por `fecha` el debut saldría
    arriba de todo, por delante de gestas cincuenta años posteriores.
    """
    jugador = _jugador()
    _efemeride(jugador, tipo="ciclo", temporada=2019, fecha=date(2019, 4, 5), mes=4, dia=5)
    _efemeride(
        jugador,
        tipo="debut",
        gesta="un debut en Grandes Ligas",
        game_id="",
        game_type="-",
        temporada=1960,
        fecha=date(2026, 9, 5),  # el aniversario de este año, como lo escribe el exportador
        mes=9,
        dia=5,
        titular="Debutó en Grandes Ligas a los 21 años.",
    )

    filas = EfemeridesTab().context(jugador)["rows"]

    assert [fila["anio"] for fila in filas] == [2019, 1960]


@pytest.mark.django_db
def test_a_person_fact_shows_the_real_date_not_the_anniversary() -> None:
    """Y la fecha que se pinta se arma con el día y el mes de `fecha` más el año de `temporada`."""
    jugador = _jugador()
    _efemeride(
        jugador,
        tipo="debut",
        game_id="",
        temporada=1960,
        fecha=date(2026, 9, 5),
        mes=9,
        dia=5,
        titular="Debutó en Grandes Ligas a los 21 años.",
    )

    fila = EfemeridesTab().context(jugador)["rows"][0]

    assert fila["fecha"] == date(1960, 9, 5)


@pytest.mark.django_db
def test_a_game_fact_keeps_its_own_date_untouched() -> None:
    jugador = _jugador()
    _efemeride(jugador)

    assert EfemeridesTab().context(jugador)["rows"][0]["fecha"] == date(2019, 4, 5)


@pytest.mark.django_db
def test_a_february_29_in_a_non_leap_year_keeps_the_year_instead_of_inventing_a_day() -> None:
    """No se corre al 28: se pierde el día y se conserva lo que sí se sabe."""
    jugador = _jugador()
    _efemeride(
        jugador,
        tipo="fallecimiento",
        game_id="",
        temporada=1999,  # no bisiesto
        fecha=date(2024, 2, 29),
        mes=2,
        dia=29,
        titular="Falleció en 1999.",
    )

    fila = EfemeridesTab().context(jugador)["rows"][0]

    assert fila["fecha"] is None
    assert fila["anio"] == 1999


@pytest.mark.django_db
def test_birthdays_do_not_reach_the_profile() -> None:
    """«Cumple 68 años» es una afirmación sobre HOY, y en una lista cronológica se contradice sola.

    Es lo único que el tab excluye, y por eso hay una prueba: para que sacarlo o volver a meterlo sea
    una decisión y no un descuido.
    """
    jugador = _jugador()
    _efemeride(jugador, tipo="cumpleanos", game_id="", temporada=1996, titular="Cumple 30 años.")

    assert not EfemeridesTab().applies_to(jugador)


@pytest.mark.django_db
def test_a_dishonour_travels_marked_so_it_is_not_read_as_a_feat() -> None:
    jugador = _jugador()
    _efemeride(
        jugador,
        tipo="sombrero_mismo_lanzador",
        signo=-1,
        titular="Se puso el sombrero dorado contra Los Angeles Dodgers.",
    )

    assert EfemeridesTab().context(jugador)["rows"][0]["negativa"] is True


@pytest.mark.django_db
def test_a_short_career_gets_no_show_more_button() -> None:
    """835 de los 984 peloteros tienen menos de diez: el caso normal no ve botón ninguno."""
    jugador = _jugador()
    for i in range(5):
        _efemeride(jugador, game_id=f"BOS20190405{i}", temporada=2019 - i)

    datos = EfemeridesTab().context(jugador)

    assert datos["ocultas"] == 0
    assert not any(fila["de_mas"] for fila in datos["rows"])
    assert "data-desplegar" not in _pintar(jugador)


@pytest.mark.django_db
def test_a_long_career_hides_the_tail_behind_a_button_but_ships_every_row() -> None:
    """El recorte es visual: las filas están TODAS en el HTML.

    Es lo que separa esto de un paginador — y es lo que permite que no haya petición nueva ni cambio
    de URL, que en esta página devolvería al lector al primer tab.
    """
    jugador = _jugador()
    for i in range(30):
        _efemeride(jugador, game_id=f"BOS2019{i:04d}", temporada=2020 - i, titular=f"Hazaña número {i}.")

    datos = EfemeridesTab().context(jugador)
    cuerpo = _pintar(jugador)

    assert datos["total"] == 30
    assert datos["ocultas"] == 10
    assert sum(1 for fila in datos["rows"] if fila["de_mas"]) == 10
    assert "Ver las 10 restantes" in cuerpo
    # La número 29 es de las escondidas, y aun así viaja: recorte, no ausencia.
    assert "Hazaña número 29." in cuerpo
    assert cuerpo.count("dgl-efem-de-mas") == 10


@pytest.mark.django_db
def test_the_rendered_tab_shows_the_redacted_text_as_it_comes() -> None:
    """El tab no redacta: si algo se lee mal, se arregla en el `.sql` que lo produce."""
    jugador = _jugador()
    _efemeride(jugador)

    cuerpo = _pintar(jugador)

    assert "Bateó para el ciclo contra Philadelphia Phillies." in cuerpo
    assert "Es uno de los 16 dominicanos con un ciclo." in cuerpo
    assert "5 de abril de 2019" in cuerpo
