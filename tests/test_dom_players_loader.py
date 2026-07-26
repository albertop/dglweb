"""El loader de `dom_players` — el segundo dataset de apoyo.

La validación es deliberadamente flaca: la única columna que importa es `player_id`, que tiene que
venir y ser única. Todo lo demás es descriptivo y puede faltar sin que la fila deje de servir.

Lo que sí hay que probar es la traducción, porque los tres tipos que cruzan la frontera cambian de
forma: `bit` de SQL Server llega como `True`/`False` de texto, la fecha llega con hora, y los vacíos
llegan como cadena vacía y no como NULL.
"""

from datetime import date
from typing import Any

import pytest

from dglweb.stats.models import DomPlayer, StaticDataset
from dglweb.stats.staticdata import engine

TABLA = "dom_players"


def _fila(**cambios: str) -> dict[str, str]:
    base = {
        "player_id": "660271",
        "last_name": "Ohtani",
        "first_name": "Shohei",
        "full_name": "Shohei Ohtani",
        "birth_date": "1994-07-05 00:00:00",
        "birth_place": "Oshu, Iwate",
        "bats": "L",
        "throws": "R",
        "height": "6-4",
        "weight": "210",
        "is_active": "True",
        "is_player": "True",
        "is_verified": "False",
    }
    return base | cambios


def _validar(*filas: dict[str, str]) -> tuple[list[dict[str, Any]], list[engine.Problem]]:
    return engine.validate(engine.REGISTRY[TABLA], list(filas), ["player_id"])


@pytest.mark.django_db
def test_the_registry_row_ships_with_the_migration() -> None:
    """Sin la fila del registro la tabla existe pero no hay por dónde subirle el CSV."""
    dataset = StaticDataset.objects.get(table=TABLA)

    assert (dataset.csv, dataset.mode, dataset.natural_key) == ("dom_players.csv", "truncate", "player_id")
    dataset.full_clean()  # y describe algo que el motor puede cumplir


@pytest.mark.django_db
def test_a_complete_row_crosses_the_border_with_its_types_translated() -> None:
    """Los tres tipos que cambian de forma: el `bit`, la fecha con hora y el entero."""
    filas, problemas = _validar(_fila())

    assert problemas == []
    assert filas[0]["player_id"] == 660271
    assert filas[0]["birth_date"] == date(1994, 7, 5)  # un `date`, no el texto crudo
    assert (filas[0]["is_active"], filas[0]["is_verified"]) == (True, False)
    assert filas[0]["weight"] == 210


@pytest.mark.django_db
def test_everything_except_the_id_may_be_missing() -> None:
    """Un prospecto recién cargado casi no tiene datos, y así y todo hay que poder listarlo."""
    vacia = dict.fromkeys(_fila(), "")
    vacia["player_id"] = "700001"

    filas, problemas = _validar(vacia)

    assert problemas == []
    assert filas[0]["birth_date"] is None
    assert filas[0]["weight"] is None
    assert filas[0]["is_active"] is None
    assert filas[0]["last_name"] == ""


@pytest.mark.django_db
def test_a_row_without_an_id_is_reported_and_not_silently_dropped() -> None:
    """Descartarla en silencio dejaría un CSV que parece más sano de lo que está."""
    _, problemas = _validar(_fila(), _fila(player_id=""))

    assert len(problemas) == 1
    assert "no se pudieron leer" in problemas[0].message


@pytest.mark.django_db
def test_a_repeated_id_blocks_the_load() -> None:
    """Con truncate un duplicado no pisa una fila con otra: inserta las dos."""
    _, problemas = _validar(_fila(), _fila(full_name="Otro"))

    assert any("se repite" in problema.message for problema in problemas)


@pytest.mark.django_db
def test_the_load_replaces_the_table_whole() -> None:
    """Truncate: lo que había no se conserva ni se reconcilia. Es el modo que pidió el dueño."""
    DomPlayer.objects.create(player_id=1, full_name="Viejo V")
    filas, _ = _validar(_fila())

    escritas = engine.apply(engine.REGISTRY[TABLA], filas, ["player_id"], truncating=True)

    assert escritas == 1
    assert list(DomPlayer.objects.values_list("player_id", flat=True)) == [660271]


@pytest.mark.django_db
def test_loading_it_rebuilds_nothing() -> None:
    """No alimenta ningún cálculo: no hay liderazgos ni totales que rehacer."""
    assert engine.REGISTRY[TABLA].rebuilds == ()


@pytest.mark.django_db
def test_the_comparison_does_not_add_up_the_weights() -> None:
    """El peso es un atributo del pelotero, no una medida.

    La pantalla suma cada columna numérica para que un cambio grande salte a la vista, y eso sirve
    para los conteos. Sumar el peso de 9.133 peloteros daba 1.640.576 libras: un número sin
    significado, en una fila que invitaba a interpretarlo.
    """
    filas, _ = _validar(_fila())

    comparacion = engine.compare(engine.REGISTRY[TABLA], filas, ["player_id"], [], truncating=True)

    assert [columna["name"] for columna in comparacion.columns] == []


@pytest.mark.django_db
def test_a_regional_date_is_refused_instead_of_guessed() -> None:
    """«7/6/1987» es 7 de junio o 6 de julio según quién corrió el script. No se adivina.

    `Export-Csv` escribe las fechas con el formato regional de la máquina. Elegir un orden
    corrompería en silencio la fecha de todo el que nació en día ≤ 12 — el tipo de daño que no se
    descubre nunca. El SQL las emite en ISO y esto lo exige.
    """
    _, problemas = _validar(_fila(birth_date="7/6/1987"))

    assert len(problemas) == 1
    assert "ISO" in problemas[0].rows[0]


@pytest.mark.django_db
def test_a_bad_date_is_caught_when_validating_and_never_at_write_time() -> None:
    """El bug de verdad: reventaba al CONFIRMAR, después de decir que todo estaba bien.

    La pantalla de comparación existe para que confirmar no pueda explotar. Si la conversión se deja
    para el `INSERT`, el error sale como 500 en la mitad de una carga de 9.000 filas en vez de como
    un problema con su número de línea.
    """
    filas, problemas = _validar(_fila(), _fila(player_id="700002", birth_date="31/12/1990"))

    assert problemas  # se ataja acá...
    assert [fila["player_id"] for fila in filas] == [660271]  # ...y la fila mala no llega a escribirse


@pytest.mark.django_db
def test_an_overlong_name_is_trimmed_rather_than_sinking_the_load() -> None:
    """Un nombre de más no puede tumbar una carga entera: la columna es de display."""
    filas, problemas = _validar(_fila(full_name="A" * 400))

    assert problemas == []
    assert len(filas[0]["full_name"]) == 120
