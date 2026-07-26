"""Lo mínimo que un lector de pantalla necesita para navegar el sitio (FE-02).

No es una auditoría de accesibilidad completa: fija los atributos que hacen navegable la estructura
—cabecera, pestañas y pills— y que son justo los que se caen al editar plantillas sin pensar en esto.

Hay una distinción que estos tests protegen y que es fácil de romper con buena intención: en el perfil
las pestañas son pestañas de verdad (cambian de panel sin recargar) y llevan el juego completo de
`role="tab"`. En Líderes son ENLACES que recargan la página con otra selección, y ahí `role="tab"`
sería una mentira: el lector anunciaría "pestaña" y esperaría que el panel cambie en el sitio.
"""

import re

import pytest
from django.test import Client

from dglweb.players.models import Player
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    CareerLevel,
    Fielding,
    FieldingCareer,
    Leader,
    Metric,
)
from tests.test_players import _other_player


@pytest.fixture
def perfil(db: None) -> str:
    """Un perfil con DOS pestañas: hace falta más de una para que el juego de ARIA signifique algo.

    Los tabs se dibujan a partir de los totales de carrera, no de las líneas de temporada
    (`applies_to` mira `BattingCareer`/`FieldingCareer`), así que hay que sembrar los dos.
    """
    jugador = Player.objects.create(**_other_player(player_id=1, dgl_id="a01", full_name="Uno U", pos="1B"))
    Batting.objects.create(player=jugador, season=2020, stint=1, hr=30, pa=600, ab=550, h=150)
    BattingCareer.objects.create(player=jugador, level=CareerLevel.TOTAL, hr=30, pa=600, ab=550, h=150)
    Fielding.objects.create(player=jugador, season=2020, pos="1B", gp=140)
    FieldingCareer.objects.create(player=jugador, level="1B", gp=140)
    return Client().get(f"/jugador/{jugador.slug}/").content.decode()


@pytest.fixture
def lideres(db: None) -> str:
    jugador = Player.objects.create(**_other_player(player_id=2, dgl_id="b01", full_name="Dos D"))
    metrica = Metric.objects.create(
        stat_group="batting",
        column="hr",
        abbrev="HR",
        name_es="Jonrones",
        kind=Metric.Kind.CUMULATIVE,
        direction=Metric.Direction.HIGHER,
        best_career=True,
        is_active=True,
    )
    Leader.objects.create(
        metric=metrica, board=Leader.Board.BEST_CAREER, season=None, player=jugador, value=500.0, rank=1
    )
    return Client().get("/lideres/?g=batting&m=hr").content.decode()


# ── La cabecera, que estaba en cero ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_two_navigation_regions_have_distinct_names(perfil: str) -> None:
    """Un lector lista las regiones de navegación: «navegación» a secas no distingue nada."""
    assert 'aria-label="Navegación principal"' in perfil
    assert 'aria-labelledby="pie-secciones"' in perfil


@pytest.mark.django_db
def test_the_search_box_has_a_name_that_is_not_the_placeholder(perfil: str) -> None:
    """El placeholder no sirve como nombre: desaparece al escribir y varios lectores no lo leen."""
    assert '<label class="visually-hidden" for="buscar">' in perfil
    assert 'role="search"' in perfil


@pytest.mark.django_db
def test_the_hamburger_says_what_it_does_and_whether_it_is_open(perfil: str) -> None:
    boton = re.search(r"<button class=\"navbar-toggler.*?>", perfil, re.S)

    assert boton is not None
    for atributo in ('aria-label="Abrir el menú"', 'aria-expanded="false"', 'aria-controls="nav"'):
        assert atributo in boton.group(0)


# ── Las pestañas del perfil: pestañas de verdad ─────────────────────────────────────────────────


@pytest.mark.django_db
def test_every_profile_tab_is_wired_to_its_panel_in_both_directions(perfil: str) -> None:
    """`aria-controls` y `aria-labelledby` tienen que cerrar el círculo, o el par queda huérfano."""
    botones = re.findall(r'id="(tab-[\w-]+)-btn"[^>]*aria-controls="(tab-[\w-]+)"', perfil)
    assert botones, "el perfil no dibujó ninguna pestaña"

    for boton_id, panel_id in botones:
        assert f"{boton_id} " in perfil or f'{boton_id}"' in perfil
        assert re.search(rf'id="{panel_id}"[^>]*aria-labelledby="{boton_id}-btn"', perfil)


@pytest.mark.django_db
def test_each_tablist_announces_exactly_one_selected_tab(perfil: str) -> None:
    """Uno por LISTA, no uno por página: el perfil tiene la de arriba y la de pills de cada tab.

    Dos seleccionadas en la misma lista —o ninguna— es el fallo típico de mantener la clase `active` y
    el `aria-selected` por separado, cada uno con su propia condición.
    """
    listas = re.findall(r'<ul[^>]*role="tablist"[^>]*>(.*?)</ul>', perfil, re.S)
    assert len(listas) >= 2, "esperaba la lista de tabs y al menos una de pills"

    assert [lista.count('aria-selected="true"') for lista in listas] == [1] * len(listas)


@pytest.mark.django_db
def test_every_pane_of_the_inner_pills_is_a_labelled_tabpanel(perfil: str) -> None:
    """Los pills de dentro de cada tab son el otro tablist, y se olvidan más fácil que los de fuera."""
    paneles = re.findall(r'<div class="tab-pane[^>]*>', perfil)
    assert paneles

    sin_rol = [panel for panel in paneles if 'role="tabpanel"' not in panel or "aria-labelledby=" not in panel]
    assert sin_rol == []


# ── Líderes: navegación, NO pestañas ────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_leaders_selectors_are_navigation_and_not_tabs(lideres: str) -> None:
    """Recargan la página. Llamarlas pestañas prometería un cambio de panel que no ocurre."""
    assert 'role="tab"' not in lideres
    assert 'aria-label="Renglón"' in lideres
    assert 'aria-label="Grupo de estadísticas"' in lideres


@pytest.mark.django_db
def test_the_current_selection_is_announced_and_not_only_coloured(lideres: str) -> None:
    """La clase `active` es visual y no se transmite; `aria-current` es lo que se anuncia."""
    assert lideres.count('aria-current="page"') == 2  # el renglón vigente y su grupo


@pytest.mark.django_db
def test_every_dropdown_has_its_label(lideres: str) -> None:
    """Los controles navegan la página: sin nombre, el lector anuncia «lista» y nada más."""
    selects = re.findall(r'<select[^>]*id="(\w+)"', lideres)
    assert selects

    for control in selects:
        assert f'for="{control}"' in lideres


@pytest.mark.django_db
def test_each_pill_group_has_its_own_name(perfil: str) -> None:
    """Cuatro listas llamadas igual no se distinguen al navegarlas: cada una toma el nombre de su tab."""
    nombres = re.findall(r'<ul[^>]*role="tablist"[^>]*aria-label="([^"]+)"', perfil)

    assert len(nombres) == len(set(nombres))
