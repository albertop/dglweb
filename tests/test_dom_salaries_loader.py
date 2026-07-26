"""El loader de `dom_salaries` — el tercer dataset de apoyo.

Lo que distingue a este de los otros dos es el **grano**: la clave lleva el equipo, no solo el
jugador y la temporada. Un pelotero traspasado a mitad de año cobra de dos organizaciones, así que
su temporada son dos filas legítimas; sin el equipo en la clave, la validación de duplicados las
trataría como un error y bloquearía la carga entera.
"""

from typing import Any

import pytest

from dglweb.stats.models import DomSalary, StaticDataset
from dglweb.stats.staticdata import engine

TABLA = "dom_salaries"
CLAVE = ["player_id", "season", "team_id"]


def _fila(**cambios: str) -> dict[str, str]:
    base = {
        "player_id": "120074",
        "season": "2024",
        "team_id": "WAS",
        "league_id": "NL",
        "age": "25",
        "salary": "31000000",
    }
    return base | cambios


def _validar(*filas: dict[str, str]) -> tuple[list[dict[str, Any]], list[engine.Problem]]:
    return engine.validate(engine.REGISTRY[TABLA], list(filas), CLAVE)


@pytest.mark.django_db
def test_the_registry_row_ships_with_the_migration() -> None:
    """Y describe algo que el motor puede cumplir: la clave existe en el modelo."""
    dataset = StaticDataset.objects.get(table=TABLA)

    assert (dataset.csv, dataset.mode, dataset.natural_key) == (
        "dom_salaries.csv",
        "truncate",
        "player_id,season,team_id",
    )
    dataset.full_clean()


@pytest.mark.django_db
def test_a_complete_row_keeps_the_codes_as_text_and_the_money_as_a_number() -> None:
    """`team_id` y `league_id` son códigos de DGL, no ids numéricos: no se convierten."""
    filas, problemas = _validar(_fila())

    assert problemas == []
    assert filas[0] == {
        "player_id": 120074,
        "season": 2024,
        "team_id": "WAS",
        "league_id": "NL",
        "age": 25,
        "salary": 31000000,
    }


@pytest.mark.django_db
def test_a_traded_player_is_two_rows_in_the_same_season_and_that_is_legal() -> None:
    """El caso que obliga a que el equipo esté en la clave.

    Si la clave fuera (jugador, temporada), estas dos filas se verían como un duplicado y el motor
    bloquearía la carga — perdiendo la mitad de lo que ese pelotero cobró ese año.
    """
    filas, problemas = _validar(_fila(team_id="SDP", salary="12000000"), _fila(team_id="NYY", salary="19000000"))

    assert problemas == []
    assert sum(fila["salary"] for fila in filas) == 31000000


@pytest.mark.django_db
def test_the_same_player_season_and_team_twice_blocks_the_load() -> None:
    """Dos filas del mismo trío es la vista mal armada: con truncate se insertarían las dos."""
    _, problemas = _validar(_fila(), _fila(salary="999"))

    assert any("se repite" in problema.message for problema in problemas)


@pytest.mark.django_db
@pytest.mark.parametrize("faltante", CLAVE)
def test_any_missing_key_column_is_reported_with_its_line(faltante: str) -> None:
    """Las tres son obligatorias porque las tres identifican la fila."""
    _, problemas = _validar(_fila(), _fila(**{"player_id": "700003", faltante: ""}))

    assert len(problemas) == 1
    assert faltante in problemas[0].rows[0] or "clave" in problemas[0].rows[0]


@pytest.mark.django_db
def test_the_optional_columns_may_be_empty() -> None:
    """La liga, la edad y el salario pueden faltar; el jugador cobró igual y la fila sirve."""
    filas, problemas = _validar(_fila(league_id="", age="", salary=""))

    assert problemas == []
    assert (filas[0]["league_id"], filas[0]["age"], filas[0]["salary"]) == ("", None, None)


@pytest.mark.django_db
def test_a_negative_salary_blocks_instead_of_being_written() -> None:
    """No es un dato raro, es un error de la vista o del export.

    Importa que se ataje al VALIDAR: la columna es `PositiveBigInteger`, así que dejarlo pasar sería
    un 500 a mitad de escritura en vez de un problema con su número de línea.
    """
    _, problemas = _validar(_fila(salary="-5000"))

    assert len(problemas) == 1
    assert "negativo" in problemas[0].message


@pytest.mark.django_db
def test_the_comparison_adds_up_the_payroll_but_not_the_ages() -> None:
    """El total de la nómina es la señal que delata un export corto. La suma de edades no dice nada."""
    filas, _ = _validar(_fila())

    comparacion = engine.compare(engine.REGISTRY[TABLA], filas, CLAVE, [], truncating=True)

    assert [columna["name"] for columna in comparacion.columns] == ["salary"]
    assert comparacion.columns[0]["after"] == 31000000


@pytest.mark.django_db
def test_the_load_replaces_the_table_whole() -> None:
    DomSalary.objects.create(player_id=1, season=1999, team_id="BOS", salary=100)
    filas, _ = _validar(_fila())

    escritas = engine.apply(engine.REGISTRY[TABLA], filas, CLAVE, truncating=True)

    assert escritas == 1
    assert list(DomSalary.objects.values_list("player_id", "team_id")) == [(120074, "WAS")]


@pytest.mark.django_db
def test_loading_it_rebuilds_nothing() -> None:
    """Los salarios no alimentan ningún cálculo del sitio."""
    assert engine.REGISTRY[TABLA].rebuilds == ()
