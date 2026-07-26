"""El índice de jugadores: el buscador y la plantilla de la última temporada.

El requisito de fondo del buscador no es la velocidad, son los acentos: 488 de los 984 nombres del
maestro llevan tilde o eñe. Si hay que escribirlos bien, la mitad del maestro es inalcanzable para
cualquiera que no sepa dónde va la tilde o que no tenga eñe en el teclado.

Por eso la mayoría de estos tests son sobre escribir el nombre "mal" y encontrarlo igual.
"""

import pytest
from django.test import Client
from django.urls import reverse

from dglweb.players import search
from dglweb.players.models import Player
from dglweb.stats.models import Batting, Pitching
from tests.test_players import _other_player


def _jugador(pid: int, nombre: str, pos: str = "SS") -> Player:
    return Player.objects.create(**_other_player(player_id=pid, dgl_id=f"j{pid}", full_name=nombre, pos=pos))


@pytest.fixture
def plantel(db: None) -> dict[str, Player]:
    return {
        "nunez": _jugador(1, "Abraham Núñez"),
        "nunez_o": _jugador(2, "Abraham O. Núñez"),
        "beltre": _jugador(3, "Adrián Beltré", pos="3B"),
        "pena": _jugador(4, "Wily Mo Peña", pos="RF"),
        "soto": _jugador(5, "Juan Soto", pos="LF"),
    }


# ── Acentos y eñes: el corazón del asunto ───────────────────────────────────────────────────────


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("escrito", "esperado"),
    [
        ("nunez", "Abraham Núñez"),  # sin tilde y sin eñe
        ("núñez", "Abraham Núñez"),  # escrito perfecto
        ("nuñez", "Abraham Núñez"),  # con eñe pero sin tilde
        ("NUNEZ", "Abraham Núñez"),  # mayúsculas
        ("beltre", "Adrián Beltré"),
        ("adrian", "Adrián Beltré"),
        ("pena", "Wily Mo Peña"),  # la eñe, que es la que más falta en los teclados
        ("peña", "Wily Mo Peña"),
    ],
)
def test_a_name_is_found_however_it_is_typed(plantel: dict[str, Player], escrito: str, esperado: str) -> None:
    assert esperado in [s.name for s in search.buscar(escrito)]


@pytest.mark.django_db
def test_the_search_ignores_the_disabled_player(plantel: dict[str, Player]) -> None:
    """`Player.objects` y no `todos`: dado de baja significa que no se puede encontrar."""
    plantel["soto"].hidden = True
    plantel["soto"].disabled_reason = "Inscrito por error."
    plantel["soto"].save()

    assert search.buscar("soto") == []


# ── El orden, que es lo que hace útil una lista de diez ─────────────────────────────────────────


@pytest.mark.django_db
def test_the_three_tiers_of_match_come_out_in_that_order(db: None) -> None:
    """Buscando «so»: primero el que empieza así, luego el apellido, y al final el que lo esconde.

    El tercero es el que justifica los tres niveles: «Alfonso» contiene «so» a mitad de palabra, y sin
    el escalón intermedio le ganaría a un Soto de verdad.
    """
    _jugador(1, "Sócrates Brito")  # el NOMBRE empieza con «so» -> nivel 0
    _jugador(2, "Juan Soto")  # una palabra empieza con «so»  -> nivel 1
    _jugador(3, "Alfonso Vargas")  # «alfonSO», en medio      -> nivel 2

    assert [s.name for s in search.buscar("so")] == ["Sócrates Brito", "Juan Soto", "Alfonso Vargas"]


@pytest.mark.django_db
def test_a_word_starting_with_it_beats_a_match_buried_in_the_middle(db: None) -> None:
    """Buscando «ram», Ramírez tiene que ganarle a quien lo lleva escondido dentro de otra palabra."""
    _jugador(1, "Amed Rosario")  # no coincide
    _jugador(2, "Beltran Ramos")  # apellido: empieza palabra
    _jugador(3, "Juan Beltram")  # lo contiene al final, sin empezar palabra

    assert [s.name for s in search.buscar("ram")] == ["Beltran Ramos", "Juan Beltram"]


@pytest.mark.django_db
def test_one_letter_returns_nothing_instead_of_half_the_master(plantel: dict[str, Player]) -> None:
    """Con una sola letra la lista deja de ser una sugerencia y pasa a ser un volcado."""
    assert search.buscar("a") == []
    assert search.buscar("") == []


@pytest.mark.django_db
def test_the_span_is_what_tells_two_namesakes_apart(plantel: dict[str, Player]) -> None:
    """«Abraham Núñez» y «Abraham O. Núñez» existen los dos: sin el rango no hay cómo elegir."""
    Batting.objects.create(player=plantel["nunez"], season=1997, stint=1)
    Batting.objects.create(player=plantel["nunez"], season=2008, stint=1)
    Pitching.objects.create(player=plantel["nunez_o"], season=2002, stint=1)

    tramos = {s.name: s.span for s in search.buscar("nunez")}

    assert tramos["Abraham Núñez"] == "1997-2008"
    assert tramos["Abraham O. Núñez"] == "2002"  # una sola temporada no se escribe como rango


# ── La página ───────────────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_page_lists_the_players_active_in_the_latest_full_season(plantel: dict[str, Player]) -> None:
    """«Última temporada completa» es la que tienen las DOS tablas, no la más nueva de cualquiera."""
    Batting.objects.create(player=plantel["soto"], season=2026, stint=1)
    Pitching.objects.create(player=plantel["beltre"], season=2026, stint=1)
    Batting.objects.create(player=plantel["pena"], season=2019, stint=1)  # viejo: no sale

    cuerpo = Client().get(reverse("players_index")).content.decode()

    assert "Activos en 2026" in cuerpo
    assert "Juan Soto" in cuerpo and "Adrián Beltré" in cuerpo
    assert "Wily Mo Peña" not in cuerpo


@pytest.mark.django_db
def test_the_search_works_without_javascript(plantel: dict[str, Player]) -> None:
    """El formulario hace un GET normal y la vista responde renderizado. El JS solo lo adelanta."""
    cuerpo = Client().get(reverse("players_index"), {"q": "beltre"}).content.decode()

    assert "Adrián Beltré" in cuerpo
    assert "Resultados para" in cuerpo


@pytest.mark.django_db
def test_a_query_with_no_matches_says_so(plantel: dict[str, Player]) -> None:
    cuerpo = Client().get(reverse("players_index"), {"q": "zzzz"}).content.decode()

    assert "Ningún jugador coincide" in cuerpo


@pytest.mark.django_db
def test_the_suggest_endpoint_answers_json(plantel: dict[str, Player]) -> None:
    respuesta = Client().get(reverse("players_suggest"), {"q": "nunez"})

    assert respuesta.status_code == 200
    nombres = [r["name"] for r in respuesta.json()["results"]]
    assert "Abraham Núñez" in nombres
    assert all({"id", "name", "slug", "pos", "span"} == set(r) for r in respuesta.json()["results"])


@pytest.mark.django_db
def test_the_nav_link_points_at_the_page(plantel: dict[str, Player]) -> None:
    """Volvió al menú: estaba escondido desde FE-01 porque no había página a la que llevar."""
    cuerpo = Client().get("/").content.decode()

    assert f'href="{reverse("players_index")}"' in cuerpo
    assert 'href="#"' not in cuerpo
