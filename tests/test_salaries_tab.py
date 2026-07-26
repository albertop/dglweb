"""El tab Salarios del perfil — construido, probado y HOY APAGADO.

No está publicado porque la fuente no da la talla: `dom_salaries` trae 1.385 filas para 343
jugadores en sesenta temporadas, y al dominicano mejor pagado de la historia le falta el registro.
Con esa cobertura el tab no informa, desinforma. Ver el comentario en `tabs.REGISTRY`.

Por eso estos tests hacen dos cosas a la vez. Fijan que **no aparece** —para que reactivarlo sea una
decisión y no un descuido— y siguen ejercitando la lógica del tab llamando a la clase directo, para
que el código no se podra mientras espera que mejore la cobertura del lado de DGL.
"""

from typing import Any

import pytest
from django.test import Client

from dglweb.players.models import Player
from dglweb.profiles.tabs import SalariesTab, tabs_for
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
    """La clase, no el registro: hoy el tab está fuera de `REGISTRY` a propósito."""
    return SalariesTab()


@pytest.mark.django_db
def test_the_tab_is_not_published_even_for_a_player_who_has_salaries(jugador: Player) -> None:
    """El apagado, fijado por un test.

    Es lo que impide que vuelva sin que nadie lo decida: si alguien descomenta la línea de `REGISTRY`
    sin haber revisado la cobertura, este test se cae y le cuenta por qué estaba apagado.
    """
    _salario(jugador, 2024, "NYY", 31_000_000)

    assert [tab.key for tab in tabs_for(jugador) if tab.key == "salarios"] == []


@pytest.mark.django_db
def test_the_profile_page_shows_no_salary_tab(jugador: Player) -> None:
    """Y no se cuela por otro lado: ni la pestaña ni el panel llegan al HTML."""
    _salario(jugador, 2024, "NYY", 31_000_000)

    cuerpo = Client().get(f"/jugador/{jugador.slug}/").content.decode()

    assert "tab-salarios" not in cuerpo
    assert "$31,000,000" not in cuerpo


@pytest.mark.django_db
def test_it_would_come_after_puestos_when_it_returns(jugador: Player) -> None:
    """El orden que pidió el dueño, listo para cuando se reactive."""
    from dglweb.profiles.tabs import PuestosTab

    assert SalariesTab().base_order > PuestosTab().base_order


@pytest.mark.django_db
def test_it_would_only_apply_to_a_player_with_salaries(jugador: Player) -> None:
    """La regla que gobierna al tab cuando vuelva: sin dato no aparece, aunque esté registrado."""
    assert SalariesTab().applies_to(jugador) is False

    _salario(jugador, 2024, "NYY", 31_000_000)

    assert SalariesTab().applies_to(jugador) is True


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
def test_the_template_still_renders_with_its_caveat_footer(jugador: Player) -> None:
    """El template se sigue probando aunque el tab no se publique: si no, se podre esperando.

    Y el footer se prueba porque es condición para reactivarlo — cuando el dato mejore seguirá siendo
    una recopilación propia, no una cifra oficial.
    """
    from django.template.loader import render_to_string

    _salario(jugador, 2024, "NYY", 31_000_000)
    tab = SalariesTab()

    html = render_to_string(tab.template, {"tab": {"data": tab.context(jugador)}})

    assert "$31,000,000" in html
    assert "incompleta" in html  # la advertencia de precisión
