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
    assert esperado in [s.name for s in search.buscar(escrito).items]


@pytest.mark.django_db
def test_the_search_ignores_the_disabled_player(plantel: dict[str, Player]) -> None:
    """`Player.objects` y no `todos`: dado de baja significa que no se puede encontrar."""
    plantel["soto"].hidden = True
    plantel["soto"].disabled_reason = "Inscrito por error."
    plantel["soto"].save()

    assert search.buscar("soto").items == []


# ── El orden, que es lo que hace útil una lista de diez ─────────────────────────────────────────


@pytest.mark.django_db
def test_starting_the_name_and_starting_a_surname_count_the_same(db: None) -> None:
    """El caso que lo motivó: buscando «so», Elías Sosa (1972) antes que Sócrates Brito (2015).

    Separarlos ponía a Sócrates arriba solo por ser su nombre de pila el que empieza con «so», y para
    quien busca los dos encajan exactamente igual de bien. En el mismo escalón decide el debut.
    """
    from datetime import date

    _jugador(1, "Sócrates Brito")
    Player.objects.filter(pk=1).update(debut_date=date(2015, 9, 8))
    _jugador(2, "Elías Sosa")
    Player.objects.filter(pk=2).update(debut_date=date(1972, 9, 8))

    assert [s.name for s in search.buscar("so").items] == ["Elías Sosa", "Sócrates Brito"]


@pytest.mark.django_db
def test_a_match_buried_mid_word_still_goes_last(db: None) -> None:
    """El escalón que sobrevive, y el único que hacía falta.

    «AlfonSO Vargas» coincide con «so» sin que nadie lo estuviera buscando por eso: sin este corte le
    ganaría a un Soto de verdad con solo haber debutado antes, y acá debutó veinte años antes.
    """
    from datetime import date

    _jugador(1, "Alfonso Vargas")
    Player.objects.filter(pk=1).update(debut_date=date(1980, 4, 1))
    _jugador(2, "Juan Soto")
    Player.objects.filter(pk=2).update(debut_date=date(2018, 5, 20))

    assert [s.name for s in search.buscar("so").items] == ["Juan Soto", "Alfonso Vargas"]


@pytest.mark.django_db
def test_one_letter_returns_nothing_instead_of_half_the_master(plantel: dict[str, Player]) -> None:
    """Con una sola letra la lista deja de ser una sugerencia y pasa a ser un volcado."""
    assert search.buscar("a").items == []
    assert search.buscar("").items == []


@pytest.mark.django_db
def test_the_span_is_what_tells_two_namesakes_apart(plantel: dict[str, Player]) -> None:
    """«Abraham Núñez» y «Abraham O. Núñez» existen los dos: sin el rango no hay cómo elegir."""
    Batting.objects.create(player=plantel["nunez"], season=1997, stint=1)
    Batting.objects.create(player=plantel["nunez"], season=2008, stint=1)
    Pitching.objects.create(player=plantel["nunez_o"], season=2002, stint=1)

    tramos = {s.name: s.span for s in search.buscar("nunez").items}

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
    """El menú y el pie llevan a la página nueva."""
    cuerpo = Client().get("/").content.decode()

    assert cuerpo.count(f'href="{reverse("players_index")}"') >= 2  # el nav y el pie


@pytest.mark.django_db
def test_the_active_list_is_ordered_by_surname(db: None) -> None:
    """La lista de activos va por apellido; el orden por debut es solo del buscador."""
    from datetime import date

    def _activo(pid: int, nombre: str, apellido: str, debut: date | None) -> Player:
        jugador = Player.objects.create(
            **_other_player(
                player_id=pid,
                dgl_id=f"a{pid}",
                full_name=f"{nombre} {apellido}",
                firstname=nombre,
                lastname_1=apellido,
                debut_date=debut,
            )
        )
        Batting.objects.create(player=jugador, season=2026, stint=1)
        Pitching.objects.create(player=jugador, season=2026, stint=1)
        return jugador

    # Dos Peña con el mismo nombre de pila: los desempata el debut, primero el que llegó antes.
    _activo(1, "Carlos", "Peña", date(2001, 9, 5))
    _activo(2, "Carlos", "Peña", date(2015, 4, 7))
    _activo(3, "Adrián", "Beltré", date(1998, 6, 24))
    _activo(4, "Ana", "Zapata", None)  # sin debut: al final de los suyos, no al principio
    _activo(5, "Wily", "Peña", date(2002, 5, 1))

    cuerpo = Client().get(reverse("players_index")).content.decode()
    posiciones = {pid: cuerpo.find(f"-{pid}/") for pid in (1, 2, 3, 4, 5)}

    # Beltré, Peña C.(1998), Peña C.(2015), Peña W., Zapata
    assert sorted(posiciones, key=lambda pid: posiciones[pid]) == [3, 1, 2, 5, 4]


@pytest.mark.django_db
def test_this_season_debutants_are_flagged_and_the_footnote_explains_it(db: None) -> None:
    """En una lista de 132 nombres, el que acaba de llegar es la única noticia.

    «Debutante» es haber debutado en la temporada que se está mostrando, no ser nuevo en la lista: un
    veterano que volvió de una lesión también aparece por primera vez en el año y no es lo mismo.
    """
    from datetime import date

    novato = Player.objects.create(
        **_other_player(player_id=1, dgl_id="n1", full_name="Novato N", lastname_1="N", debut_date=date(2026, 5, 25))
    )
    veterano = Player.objects.create(
        **_other_player(player_id=2, dgl_id="v2", full_name="Veterano V", lastname_1="V", debut_date=date(2018, 4, 1))
    )
    for jugador in (novato, veterano):
        Batting.objects.create(player=jugador, season=2026, stint=1)
        Pitching.objects.create(player=jugador, season=2026, stint=1)

    cuerpo = Client().get(reverse("players_index")).content.decode()

    assert 'Novato N</a><span\n        class="dgl-debut"' in cuerpo or "dgl-debut" in cuerpo
    assert cuerpo.count('class="dgl-debut"') == 2  # el asterisco del novato + el de la nota al pie
    assert "Debutó en Grandes Ligas en 2026" in cuerpo
    # El veterano no lo lleva: su nombre no va seguido del asterisco.
    assert "Veterano V</a>" in cuerpo and 'Veterano V</a><span\n        class="dgl-debut"' not in cuerpo


@pytest.mark.django_db
def test_a_player_who_only_took_the_field_is_still_active(db: None) -> None:
    """«Ver acción» no siempre deja línea de bateo: un sustituto defensivo puede entrar solo a defender.

    Hoy en la base no hay ninguno —todos los que fildearon tienen también línea de bateo— pero la
    consulta lo contempla, que es lo que este test protege de una simplificación futura.
    """
    from dglweb.stats.models import Fielding

    solo_guante = Player.objects.create(
        **_other_player(player_id=1, dgl_id="g1", full_name="Solo Guante", lastname_1="Guante", pos="2B")
    )
    Fielding.objects.create(player=solo_guante, season=2026, pos="2B", gp=1)
    # Otro jugador con las tres tablas, para que 2026 sea "temporada completa".
    otro = Player.objects.create(**_other_player(player_id=2, dgl_id="o2", full_name="Otro O", lastname_1="O"))
    Batting.objects.create(player=otro, season=2026, stint=1)
    Pitching.objects.create(player=otro, season=2026, stint=1)
    Fielding.objects.create(player=otro, season=2026, pos="P", gp=1)

    cuerpo = Client().get(reverse("players_index")).content.decode()

    assert "Solo Guante" in cuerpo


@pytest.mark.django_db
def test_within_a_tier_the_results_go_by_debut(db: None) -> None:
    """Dentro del mismo escalón decide el debut, no el apellido.

    Los tres son «apellido que empieza con pe», o sea el mismo escalón: ahí gana el que llegó antes.
    """
    from datetime import date

    def _p(pid: int, nombre: str, debut: date) -> None:
        Player.objects.create(**_other_player(player_id=pid, dgl_id=f"p{pid}", full_name=nombre, debut_date=debut))

    _p(1, "Zoilo Peña", date(2010, 4, 1))
    _p(2, "Aaron Perdomo", date(1990, 5, 5))  # alfabéticamente primero, pero manda su debut
    _p(3, "Bruno Peña", date(1995, 6, 2))

    assert [s.name for s in search.buscar("pe").items] == ["Aaron Perdomo", "Bruno Peña", "Zoilo Peña"]


@pytest.mark.django_db
def test_the_search_says_how_many_it_left_out(db: None) -> None:
    """El fallo que reportó el dueño: buscar «carlos» y no ver al segundo Carlos Martínez.

    Con 22 coincidencias y un desplegable de 20, el que cae en el puesto 22 no aparece — y sin un
    aviso, quien busca concluye que no está en la base. Recortar en silencio es el peor fallo posible
    de un buscador, porque se confunde con «no existe».
    """
    for pid in range(1, 26):
        Player.objects.create(**_other_player(player_id=pid, dgl_id=f"c{pid}", full_name=f"Carlos Apellido{pid:02d}"))

    hallazgo = search.buscar("carlos")

    assert len(hallazgo.items) == search.LIMITE_SUGERENCIAS
    assert hallazgo.total == 25
    assert hallazgo.ocultos == 25 - search.LIMITE_SUGERENCIAS


@pytest.mark.django_db
def test_the_results_page_holds_everything_the_dropdown_could_not(db: None) -> None:
    """El desplegable manda acá con su «ver todos», así que acá no puede faltar nadie."""
    for pid in range(1, 26):
        Player.objects.create(**_other_player(player_id=pid, dgl_id=f"c{pid}", full_name=f"Carlos Apellido{pid:02d}"))

    cuerpo = Client().get(reverse("players_index"), {"q": "carlos"}).content.decode()

    assert "25 jugadores" in cuerpo
    assert "Carlos Apellido25" in cuerpo  # el que el desplegable dejaba fuera


@pytest.mark.django_db
def test_the_endpoint_reports_the_hidden_count(db: None) -> None:
    for pid in range(1, 26):
        Player.objects.create(**_other_player(player_id=pid, dgl_id=f"c{pid}", full_name=f"Carlos Apellido{pid:02d}"))

    datos = Client().get(reverse("players_suggest"), {"q": "carlos"}).json()

    assert datos["total"] == 25
    assert datos["hidden"] == 25 - search.LIMITE_SUGERENCIAS


@pytest.mark.django_db
def test_the_server_rendered_results_are_wired_to_the_box_that_can_stale_them(plantel: dict[str, Player]) -> None:
    """La sección la pintó el servidor para UNA consulta; al tocar la caja deja de ser cierta.

    Esconderla es cosa del JS, pero el cableado que se lo permite sí se puede fijar acá: sin el
    `data-resultados` apuntando a la sección, el script no tiene a qué agarrarse y el encabezado se
    queda mintiendo mientras el usuario escribe otra cosa.
    """
    cuerpo = Client().get(reverse("players_index"), {"q": "beltre"}).content.decode()

    assert 'data-resultados="resultados-busqueda"' in cuerpo
    assert 'id="resultados-busqueda"' in cuerpo
