"""Los movimientos de roster: a quién se guarda, cómo se dice en español, y qué NO se publica.

La regla que gobierna el módulo es una: **el sitio nunca enseña inglés**. Una frase que ningún patrón
reconozca, o una plantilla a la que le falte una pieza, se queda fuera del cintillo. Es preferible un
movimiento menos que una línea rota en la cabecera de todas las páginas.

Los patrones se prueban contra frases REALES de MLB, copiadas del feed. Inventarlas sería probar que
nuestras regex se entienden a sí mismas.
"""

from datetime import date
from typing import TYPE_CHECKING, Any, cast

import pytest
from django.test import Client

from dglweb.players.models import Player
from dglweb.stats import roster_moves
from dglweb.stats.models import RosterMove

if TYPE_CHECKING:
    from dglweb.mlb.client import MlbProxyClient
from tests.test_players import _other_player


def _fila(descripcion: str, **campos: object) -> dict[str, object]:
    """Una fila del feed con la forma que manda MLB."""
    base: dict[str, object] = {
        "id": 900001,
        "person": {"id": 665742, "fullName": "Juan Soto"},
        "date": "2026-07-20",
        "typeCode": "SC",
        "typeDesc": "Status Change",
        "description": descripcion,
        "toTeam": {"id": 121, "name": "New York Mets"},
    }
    return base | campos


class _ClienteFalso:
    """Un cliente del proxy que devuelve lo que se le diga. Sin red: lo que se prueba acá es cómo
    reacciona el parser a un payload roto, no que httpx funcione."""

    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def get(self, ruta: str, params: dict[str, object] | None = None) -> Any:
        return self._payload


# ── El español ──────────────────────────────────────────────────────────────────────────────────


# Cada caso trae SUS equipos, y en el sentido en que los manda MLB: comprobado contra el feed, en un
# «optioned to Syracuse» el destino va en `toTeam` y el club grande en `fromTeam`, y en un «recalled
# from Syracuse» es al revés. Poner los mismos equipos para todos los casos habría hecho pasar un
# test que no probaba la dirección — que es justo la mitad de lo que estas plantillas tienen que
# acertar.
@pytest.mark.parametrize(
    ("descripcion", "desde", "hasta", "esperado"),
    [
        # Las más frecuentes del feed, medidas sobre un mes.
        (
            "New York Mets optioned RHP Juan Soto to Syracuse Mets.",
            "New York Mets",
            "Syracuse Mets",
            "Juan Soto fue enviado a Syracuse Mets",
        ),
        (
            "New York Mets recalled RHP Juan Soto from Syracuse Mets.",
            "Syracuse Mets",
            "New York Mets",
            "Juan Soto fue llamado desde Syracuse Mets",
        ),
        (
            "New York Mets placed LF Juan Soto on the 10-day injured list.",
            "",
            "New York Mets",
            "Juan Soto fue puesto en la lista de lesionados de 10 días",
        ),
        (
            "New York Mets activated LF Juan Soto from the 10-day injured list.",
            "",
            "New York Mets",
            "Juan Soto volvió de la lista de lesionados",
        ),
        (
            "New York Mets designated RF Juan Soto for assignment.",
            "",
            "New York Mets",
            "New York Mets designó a Juan Soto para asignación",
        ),
        # El traspaso entre listas: el número que importa es el SEGUNDO, el de la lista a la que pasa.
        (
            "New York Mets transferred CF Juan Soto from the 10-day injured list to the 60-day injured list. "
            "Left hand fractures.",
            "",
            "New York Mets",
            "Juan Soto pasó a la lista de lesionados de 60 días",
        ),
    ],
)
def test_the_sentence_comes_out_in_spanish(descripcion: str, desde: str, hasta: str, esperado: str) -> None:
    fila = _fila(descripcion, toTeam={"name": hasta}, fromTeam={"name": desde} if desde else None)

    assert roster_moves.traducir(fila) == esperado


def test_the_specific_pattern_wins_over_the_generic_one() -> None:
    """El orden de la lista es funcional, no cosmético.

    «activated from the 10-day injured list» también encaja con el genérico «activated», y si ganara
    el genérico se perdería justo lo que hace noticia: que volvió de una lesión.
    """
    generico = roster_moves.traducir(_fila("New York Mets activated LF Juan Soto."))
    especifico = roster_moves.traducir(_fila("New York Mets activated LF Juan Soto from the 10-day injured list."))

    assert generico == "New York Mets activó a Juan Soto"
    assert especifico == "Juan Soto volvió de la lista de lesionados"


def test_the_position_does_not_multiply_the_patterns() -> None:
    """MLB mete la posición en la frase; con 14 posiciones serían 14 variantes de cada patrón."""
    for posicion in ("RHP", "LHP", "SS", "C", "DH"):
        frase = f"New York Mets designated {posicion} Juan Soto for assignment."
        assert roster_moves.traducir(_fila(frase)) == "New York Mets designó a Juan Soto para asignación"


# ── Lo que NO se publica ────────────────────────────────────────────────────────────────────────


def test_a_sentence_no_pattern_recognises_is_not_published() -> None:
    """Devuelve vacío, y el cintillo salta esas filas. Una línea en inglés dentro de una cintilla en
    español no se lee como un dato: se lee como un error."""
    assert roster_moves.traducir(_fila("New York Mets did something entirely new with Juan Soto.")) == ""


def test_a_template_missing_a_piece_publishes_nothing_instead_of_a_broken_sentence() -> None:
    """El fallo real que destapó esto, y la razón de que exista la comprobación.

    El patrón de «designated for assignment» rellenaba con `fromTeam`, que en ESE tipo MLB no manda.
    El cintillo mostró « designó a Steward Berroa para asignación» — sin sujeto y empezando por un
    espacio. Ahora, si a la plantilla le falta una pieza, no sale nada.
    """
    sin_equipo = _fila("Somebody designated RF Juan Soto for assignment.", toTeam=None, fromTeam=None)

    assert roster_moves.traducir(sin_equipo) == ""


def test_no_translation_ever_starts_with_a_space_or_has_a_hole() -> None:
    """La forma general del fallo anterior, sobre TODOS los patrones del repertorio."""
    for _, plantilla in roster_moves.PATRONES:
        # Cada plantilla se rellena con piezas de verdad; ninguna puede quedar con un hueco.
        relleno = plantilla.format(jugador="X", desde="A", hasta="B", equipo="C", n="10", n2="60")
        assert relleno == relleno.strip()
        assert "  " not in relleno


# ── A quién se guarda ───────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_only_dominicans_are_kept() -> None:
    """El universo es `dgl_master` más `dom_players`, nunca el `birthCountry` del feed."""
    Player.objects.create(**_other_player(player_id=665742, dgl_id="s01", full_name="Juan Soto", pos="LF"))

    assert 665742 in roster_moves.universo()
    assert 111222333 not in roster_moves.universo()


@pytest.mark.django_db
def test_saving_twice_does_not_duplicate() -> None:
    """Es lo que permite que la corrida horaria pida siempre los últimos dos días.

    Sin esto, el horario del job pasaría a ser un problema de correctitud y no de latencia: una
    corrida repetida ensuciaría el cintillo con la misma noticia tres veces.
    """
    movimiento = roster_moves.Movimiento(
        transaction_id=900001,
        mlb_id=665742,
        nombre="Juan Soto",
        fecha=date(2026, 7, 20),
        type_code="SC",
        type_desc="Status Change",
        desde="",
        hasta="New York Mets",
        descripcion="New York Mets activated LF Juan Soto.",
        texto="New York Mets activó a Juan Soto",
    )

    roster_moves.guardar([movimiento])
    roster_moves.guardar([movimiento])

    assert RosterMove.objects.count() == 1


@pytest.mark.django_db
def test_a_player_without_a_profile_is_still_saved() -> None:
    """Hay dominicanos en `dom_players` que aún no llegaron a las mayores y no tienen ficha.

    Se guardan igual —el dato es bueno y algún día puede servir— aunque al cintillo NO vayan: eso lo
    filtra `portada()`. Guardar y mostrar son decisiones distintas.
    """
    movimiento = roster_moves.Movimiento(
        transaction_id=900002,
        mlb_id=999888,  # no está en `dgl_master`
        nombre="Un Prospecto",
        fecha=date(2026, 7, 20),
        type_code="SFA",
        type_desc="Signed as Free Agent",
        desde="",
        hasta="Miami Marlins",
        descripcion="Miami Marlins signed free agent RHP Un Prospecto to a minor league contract.",
        texto="Miami Marlins firmó a Un Prospecto a contrato de ligas menores",
    )

    roster_moves.guardar([movimiento])

    guardado = RosterMove.objects.get(transaction_id=900002)
    assert guardado.player is None
    assert guardado.nombre == "Un Prospecto"


@pytest.mark.django_db
def test_the_ticker_leaves_out_what_could_not_be_translated() -> None:
    """La regla del módulo, comprobada en la consulta que alimenta la pantalla."""
    from django.utils import timezone

    hoy = timezone.localdate()
    Player.objects.create(**_other_player(player_id=665742, dgl_id="s01", full_name="Juan Soto", pos="LF"))
    for numero, texto in enumerate(["Algo pasó en español", ""]):
        RosterMove.objects.create(
            transaction_id=900010 + numero,
            mlb_id=665742,
            player_id=665742,
            nombre="Juan Soto",
            fecha=hoy,
            type_code="SC",
            type_desc="Status Change",
            descripcion="algo en inglés",
            texto=texto,
        )

    assert [m.texto for m in roster_moves.portada()] == ["Algo pasó en español"]


@pytest.mark.django_db
def test_the_ticker_does_not_show_stale_moves() -> None:
    """Una semana hacia atrás. En invierno hay días sin nada, y con dos días la cintilla
    desaparecería media temporada; con un mes mostraría noticias viejas como si fueran de hoy."""
    from datetime import timedelta

    from django.utils import timezone

    Player.objects.create(**_other_player(player_id=665742, dgl_id="s01", full_name="Juan Soto", pos="LF"))
    RosterMove.objects.create(
        transaction_id=900020,
        mlb_id=665742,
        player_id=665742,
        nombre="Juan Soto",
        fecha=timezone.localdate() - timedelta(days=roster_moves.VENTANA_CINTILLO + 1),
        type_code="SC",
        type_desc="Status Change",
        descripcion="viejo",
        texto="Esto es de hace rato",
    )

    assert roster_moves.portada() == []


@pytest.mark.django_db
def test_the_ticker_leaves_out_the_minor_leaguers() -> None:
    """Decisión del dueño: al cintillo solo van los que tienen ficha en `dgl_master`.

    Este sitio es de dominicanos en GRANDES LIGAS. Con los de `dom_players` dentro, la cintilla se
    llenaba de «firmó a X a contrato de ligas menores» — muchachos que todavía no llegaron y que no
    son lo que viene a leer quien entra. Se siguen GUARDANDO; simplemente no se muestran.
    """
    from django.utils import timezone

    hoy = timezone.localdate()
    Player.objects.create(**_other_player(player_id=665742, dgl_id="s01", full_name="Juan Soto", pos="LF"))
    for numero, (mlb_id, quien) in enumerate([(665742, "Juan Soto"), (999888, "Un Prospecto")]):
        RosterMove.objects.create(
            transaction_id=900030 + numero,
            mlb_id=mlb_id,
            player_id=665742 if mlb_id == 665742 else None,
            nombre=quien,
            fecha=hoy,
            type_code="SC",
            type_desc="Status Change",
            descripcion="algo",
            texto=f"{quien} se movió",
        )

    assert [m.nombre for m in roster_moves.portada()] == ["Juan Soto"]


@pytest.mark.django_db
def test_with_nothing_to_show_the_ticker_is_not_drawn(client: Client) -> None:
    """Sin movimientos no hay cintilla: una franja vacía ocupa sitio para no decir nada.

    Se comprueba en la página y no en la consulta, porque el que decide es el `{% if %}` de
    `base.html` — y ahí es donde alguien podría quitarlo sin darse cuenta.
    """
    from django.core.cache import cache

    cache.clear()
    contenido = client.get("/").content

    assert RosterMove.objects.count() == 0
    assert b"dgl-cintillo" not in contenido


# ── FE-01: el cintillo y el teclado ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_duplicated_strip_is_out_of_the_tab_order(client: Client) -> None:
    """La copia lleva `aria-hidden` Y `inert`, y lo segundo es lo que faltaba.

    `aria-hidden` saca los enlaces del árbol de accesibilidad pero NO del orden de tabulación: el
    lector de pantalla los ignora y la tecla Tab los recorre igual. Quien navega con teclado caía en
    una segunda tanda de enlaces duplicados —invisibles para su lector— dentro de una tira en
    movimiento. La copia existe solo para que el ciclo de la animación empalme; nadie tiene que poder
    llegar a ella.
    """
    from django.core.cache import cache
    from django.utils import timezone

    Player.objects.create(**_other_player(player_id=665742, dgl_id="s01", full_name="Juan Soto", pos="LF"))
    RosterMove.objects.create(
        transaction_id=900100,
        mlb_id=665742,
        player_id=665742,
        nombre="Juan Soto",
        fecha=timezone.localdate(),
        type_code="SC",
        type_desc="Status Change",
        descripcion="algo",
        texto="Juan Soto volvió de la lista de lesionados",
    )
    cache.clear()

    contenido = client.get("/").content.decode()
    copias = contenido.count('aria-hidden="true" inert')

    listas = contenido.count('class="dgl-cintillo-lista"')

    assert listas == 2, "la tira lleva la lista dos veces para que el ciclo empalme"
    # Exactamente UNA de las dos es inerte: la otra es la que recorre el teclado y lee el lector.
    assert copias == 1, "la copia del cintillo tiene que ser inerte, no solo aria-hidden"


# ── QA-02: contratos ajenos rotos ───────────────────────────────────────────────────────────────
#
# El feed es de MLB, no nuestro. Una fila con un `id` de letras o una fecha con hora pegada aborta
# `int()` o `date.fromisoformat()`, y sin aislarla **se pierde la corrida entera**: el cintillo se
# queda con lo de ayer y nadie sabe por qué. Lo que se prueba es que la fila mala se salte y las
# buenas lleguen.


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("rota", "por_que"),
    [
        ({"id": "abc"}, "id con letras"),
        ({"id": None}, "id nulo"),
        ({"date": ""}, "fecha vacía"),
        ({"date": "no-es-fecha"}, "fecha ilegible"),
        ({"person": None}, "sin persona"),
        ({"person": {"id": "x", "fullName": "Raro"}}, "id de persona con letras"),
    ],
)
def test_a_broken_row_is_skipped_and_the_good_ones_survive(
    monkeypatch: pytest.MonkeyPatch, rota: dict[str, object], por_que: str
) -> None:
    """Una fila podrida no puede llevarse por delante a las demás."""
    buena = {
        "id": 900201,
        "person": {"id": 665742, "fullName": "Juan Soto"},
        "date": "2026-07-20",
        "typeCode": "SC",
        "typeDesc": "Status Change",
        "description": "New York Mets activated LF Juan Soto.",
        "toTeam": {"name": "New York Mets"},
    }
    mala = {**buena, "id": 900202, **rota}

    monkeypatch.setattr(roster_moves, "universo", lambda: {665742})
    cliente = _ClienteFalso({"transactions": [mala, buena]})

    movimientos = roster_moves.traer(cast("MlbProxyClient", cliente), date(2026, 7, 20))

    assert [m.transaction_id for m in movimientos] == [900201], f"se perdió la buena con «{por_que}»"


@pytest.mark.django_db
def test_a_date_with_a_timestamp_is_accepted() -> None:
    """MLB manda solo la fecha, pero es su contrato y puede cambiarlo sin avisarnos. Recortar a diez
    caracteres cuesta nada y evita perder la fila el día que le peguen la hora."""
    fila = {
        "id": 900203,
        "person": {"id": 665742, "fullName": "Juan Soto"},
        "date": "2026-07-20T00:00:00Z",
        "typeCode": "SC",
        "typeDesc": "Status Change",
        "description": "New York Mets activated LF Juan Soto.",
        "toTeam": {"name": "New York Mets"},
    }

    movimiento = roster_moves._movimiento(fila)

    assert movimiento is not None
    assert movimiento.fecha == date(2026, 7, 20)


@pytest.mark.django_db
def test_a_payload_that_is_not_a_list_does_not_explode(monkeypatch: pytest.MonkeyPatch) -> None:
    """`transactions` podría no venir, venir a nulo o venir como diccionario. Ninguna de las tres
    puede tumbar el job: son formas de que el contrato ajeno cambie."""
    monkeypatch.setattr(roster_moves, "universo", lambda: {665742})

    for payload in ({}, {"transactions": None}, {"transactions": {"raro": 1}}, {"transactions": ["texto suelto"]}):
        falso = cast("MlbProxyClient", _ClienteFalso(payload))
        assert roster_moves.traer(falso, date(2026, 7, 20)) == []
