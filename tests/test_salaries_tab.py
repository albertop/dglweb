"""El tab Salarios del perfil.

Es el primer tab que se alimenta de un dataset de apoyo y no del proxy, así que lo primero que hay
que fijar es que no aparezca cuando no hay dato: la cobertura de `dom_salaries` es floja —343
jugadores en 60 temporadas— y un tab vacío en la mayoría de los perfiles sería peor que no tenerlo.
"""

from typing import Any

import pytest
from django.test import Client

from dglweb.players.models import Player
from dglweb.profiles.tabs import tabs_for
from dglweb.stats.models import DomSalary
from tests.test_players import _other_player


@pytest.fixture
def jugador(db: None) -> Player:
    return Player.objects.create(**_other_player(player_id=120074, dgl_id="s01", full_name="Juan Soto"))


def _salario(jugador: Player, season: int, team: str, salary: int | None, league: str = "NL") -> DomSalary:
    return DomSalary.objects.create(
        player_id=jugador.player_id, season=season, team_id=team, league_id=league, salary=salary
    )


def _tab(jugador: Player) -> Any:
    return next((tab for tab in tabs_for(jugador) if tab.key == "salarios"), None)


@pytest.mark.django_db
def test_the_tab_is_absent_when_the_player_has_no_salary_on_record(jugador: Player) -> None:
    """La mayoría de los perfiles no tienen salario: el tab no puede aparecer vacío."""
    assert _tab(jugador) is None


@pytest.mark.django_db
def test_the_tab_appears_once_there_is_something_to_show(jugador: Player) -> None:
    _salario(jugador, 2024, "NYY", 31_000_000)

    assert _tab(jugador) is not None


@pytest.mark.django_db
def test_it_comes_after_puestos(jugador: Player) -> None:
    """El orden que pidió el dueño. `base_order` lo decide, no el orden del registro."""
    from dglweb.profiles.tabs import PuestosTab, SalariesTab

    assert SalariesTab().base_order > PuestosTab().base_order


@pytest.mark.django_db
def test_the_rows_are_ordered_by_season_and_carry_team_league_and_amount(jugador: Player) -> None:
    _salario(jugador, 2024, "NYY", 31_000_000, league="AL")
    _salario(jugador, 2019, "WAS", 578_300)

    filas = _tab(jugador).context(jugador)["rows"]

    assert [(f["season"], f["team"], f["league"], f["salary"]) for f in filas] == [
        (2019, "WAS", "NL", "$578,300"),
        (2024, "NYY", "AL", "$31,000,000"),
    ]


@pytest.mark.django_db
def test_a_traded_season_shows_its_two_rows(jugador: Player) -> None:
    """El grano de la tabla es (temporada, equipo): un traspaso son dos filas y las dos se muestran."""
    _salario(jugador, 2022, "WAS", 17_100_000)
    _salario(jugador, 2022, "SDP", 5_700_000)

    filas = _tab(jugador).context(jugador)["rows"]

    assert len(filas) == 2
    assert {fila["team"] for fila in filas} == {"WAS", "SDP"}


@pytest.mark.django_db
def test_the_total_adds_up_every_row_including_a_traded_season(jugador: Player) -> None:
    _salario(jugador, 2022, "WAS", 17_100_000)
    _salario(jugador, 2022, "SDP", 5_700_000)
    _salario(jugador, 2024, "NYY", 31_000_000)

    datos = _tab(jugador).context(jugador)

    assert datos["total"] == "$53,800,000"


@pytest.mark.django_db
def test_a_row_without_an_amount_shows_a_dash_and_does_not_break_the_total(jugador: Player) -> None:
    """En la carga real no hay salarios nulos, pero la columna los admite y un None no puede reventar."""
    _salario(jugador, 2024, "NYY", 31_000_000)
    _salario(jugador, 1997, "BOS", None)

    datos = _tab(jugador).context(jugador)

    assert datos["rows"][0]["salary"] == "—"
    assert datos["total"] == "$31,000,000"


@pytest.mark.django_db
def test_the_page_renders_the_tab_with_its_caveat_footer(jugador: Player) -> None:
    """El footer no es decorativo: la fuente está incompleta y la página tiene que decirlo."""
    _salario(jugador, 2024, "NYY", 31_000_000)

    respuesta = Client().get(f"/jugador/{jugador.slug}/")
    cuerpo = respuesta.content.decode()

    assert respuesta.status_code == 200
    assert "Salarios" in cuerpo
    assert "$31,000,000" in cuerpo
    assert "incompleta" in cuerpo  # la advertencia de precisión
