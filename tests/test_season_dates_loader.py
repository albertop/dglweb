"""El calendario de temporadas — el primer dataset de apoyo por UPSERT y con CRUD.

Las dos cosas van juntas y cambian lo que hay que probar. Se edita a mano en el Backoffice, así que
la carga no puede truncar (borraría esas correcciones); y como el upsert no borra nada, una fila mala
se queda para siempre en vez de desaparecer en la carga siguiente. De ahí que la validación sea más
estricta acá que en los datasets que se reemplazan enteros.
"""

from datetime import date
from typing import Any

import pytest
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError

from dglweb.stats.models import SeasonDates, StaticDataset
from dglweb.stats.staticdata import engine

TABLA = "seasons_dates"
CLAVE = ["season", "sports_id"]


def _fila(**cambios: str) -> dict[str, str]:
    base = {
        "season": "2024",
        "sports_id": "1",
        "season_start_date": "2024-03-20",
        "reg_season_end_date": "2024-09-29",
        "all_star_game_date": "2024-07-16",
        "post_season_start_date": "2024-10-01",
        "season_end_date": "2024-10-30",
        "is_active": "False",
    }
    return base | cambios


def _validar(*filas: dict[str, str]) -> tuple[list[dict[str, Any]], list[engine.Problem]]:
    return engine.validate(engine.REGISTRY[TABLA], list(filas), CLAVE)


@pytest.mark.django_db
def test_the_registry_row_ships_with_the_migration_and_is_an_upsert() -> None:
    """El modo no es un detalle: truncate borraría lo que se corrige a mano en el Backoffice."""
    dataset = StaticDataset.objects.get(table=TABLA)

    assert (dataset.csv, dataset.mode, dataset.natural_key) == ("seasons_dates.csv", "upsert", "season,sports_id")
    dataset.full_clean()  # y ARCH-04 exige que exista la restricción de unicidad que lo respalda


@pytest.mark.django_db
def test_a_complete_row_crosses_with_its_dates_and_flag_translated() -> None:
    filas, problemas = _validar(_fila())

    assert problemas == []
    assert filas[0]["season"] == 2024
    assert filas[0]["season_start_date"] == date(2024, 3, 20)
    assert filas[0]["is_active"] is False


@pytest.mark.django_db
def test_the_three_optional_dates_may_be_empty() -> None:
    """Una temporada en curso todavía no tiene fecha de postemporada, y no todos los años hay ASG."""
    filas, problemas = _validar(_fila(all_star_game_date="", post_season_start_date="", reg_season_end_date=""))

    assert problemas == []
    assert filas[0]["all_star_game_date"] is None


@pytest.mark.django_db
@pytest.mark.parametrize("obligatoria", ["season_start_date", "season_end_date"])
def test_the_two_mandatory_dates_are_enforced(obligatoria: str) -> None:
    """Una temporada es el intervalo entre esas dos: sin ellas la fila no dice nada."""
    _, problemas = _validar(_fila(**{obligatoria: ""}))

    assert len(problemas) == 1
    assert obligatoria in problemas[0].rows[0]


@pytest.mark.django_db
def test_the_season_defaults_to_mlb_when_the_sport_is_missing() -> None:
    """La fuente distingue ligas, pero hoy solo se carga MLB: vacío es «la de siempre», no «ninguna»."""
    filas, problemas = _validar(_fila(sports_id=""))

    assert problemas == []
    assert filas[0]["sports_id"] == SeasonDates.MLB


@pytest.mark.django_db
def test_dates_out_of_order_block_the_load() -> None:
    """Una fecha traspuesta no se ve mirando la fila: todas son plausibles por separado.

    Y con upsert se queda para siempre, porque nada la borra. Acá el Juego de Estrellas cae DESPUÉS
    del fin de la serie regular, que es imposible.
    """
    _, problemas = _validar(_fila(all_star_game_date="2024-10-20"))

    assert len(problemas) == 1
    assert "fuera de orden" in problemas[0].message
    assert "Juego de Estrellas" in problemas[0].rows[0]


@pytest.mark.django_db
def test_two_seasons_marked_as_current_block_the_load() -> None:
    """Con upsert la vieja no se apaga sola: si entran dos encendidas, quedan dos encendidas."""
    _, problemas = _validar(_fila(season="2024", is_active="True"), _fila(season="2025", is_active="True"))

    assert len(problemas) == 1
    assert "solo puede haber una" in problemas[0].message


@pytest.mark.django_db
def test_an_incoming_current_season_clashes_with_the_one_already_stored() -> None:
    """El caso real, y el que faltaba: el CSV está bien y aun así la tabla acaba mal.

    Mirar solo el archivo alcanza con truncate, donde la carga reemplaza la tabla entera. Con upsert
    la activa vieja **sobrevive si el CSV no la trae**, que es justo lo que hace el export normal del
    año siguiente: trae 2026 y no vuelve a mencionar 2025.
    """
    SeasonDates.objects.create(
        season=2025, sports_id=1, season_start_date=date(2025, 3, 27), season_end_date=date(2025, 11, 1), is_active=True
    )

    _, problemas = _validar(_fila(season="2026", is_active="True"))

    assert len(problemas) == 1
    assert "ya hay otra" in problemas[0].message
    assert problemas[0].rows == ["2025 (deporte 1)"]


@pytest.mark.django_db
def test_replacing_the_current_season_in_the_same_file_is_fine() -> None:
    """La forma correcta de pasar de año: el CSV trae las dos, la vieja apagada.

    Sin esta prueba, el aviso de arriba podría estar bloqueando también la carga buena — y un
    validador que no deja hacer lo correcto se termina desactivando.
    """
    SeasonDates.objects.create(
        season=2025, sports_id=1, season_start_date=date(2025, 3, 27), season_end_date=date(2025, 11, 1), is_active=True
    )

    _, problemas = _validar(_fila(season="2025", is_active="False"), _fila(season="2026", is_active="True"))

    assert problemas == []


@pytest.mark.django_db
def test_the_database_refuses_two_current_seasons() -> None:
    """La última red, por debajo del CSV y del Backoffice.

    Es una regla del dominio y no una validación de formulario: `season_window` la consulta para
    decidir si el pipeline corre hoy, y con dos activas elegía por `order_by("-season")` — o sea que
    no se rompía, hacía algo peor, que es correr según una temporada que nadie eligió.
    """
    SeasonDates.objects.create(
        season=2025, sports_id=1, season_start_date=date(2025, 3, 27), season_end_date=date(2025, 11, 1), is_active=True
    )

    with pytest.raises(IntegrityError):
        SeasonDates.objects.create(
            season=2026,
            sports_id=1,
            season_start_date=date(2026, 3, 26),
            season_end_date=date(2026, 11, 1),
            is_active=True,
        )


@pytest.mark.django_db
def test_two_sports_may_each_have_their_own_current_season() -> None:
    """La constraint es por deporte, no global: si mañana entra otra liga, tiene su propia vigente."""
    SeasonDates.objects.create(
        season=2026, sports_id=1, season_start_date=date(2026, 3, 26), season_end_date=date(2026, 11, 1), is_active=True
    )
    SeasonDates.objects.create(
        season=2026, sports_id=11, season_start_date=date(2026, 4, 1), season_end_date=date(2026, 9, 1), is_active=True
    )

    assert SeasonDates.objects.filter(is_active=True).count() == 2


@pytest.mark.django_db
def test_the_form_says_which_season_is_in_the_way() -> None:
    """`clean()` repite la regla para que el Backoffice dé un mensaje y no un `IntegrityError`.

    La base dice que la restricción se violó; no dice cuál es la fila que hay que apagar.
    """
    SeasonDates.objects.create(
        season=2025, sports_id=1, season_start_date=date(2025, 3, 27), season_end_date=date(2025, 11, 1), is_active=True
    )
    nueva = SeasonDates(
        season=2026, sports_id=1, season_start_date=date(2026, 3, 26), season_end_date=date(2026, 11, 1), is_active=True
    )

    with pytest.raises(ValidationError) as fallo:
        nueva.full_clean()

    assert "2025" in str(fallo.value)


@pytest.mark.django_db
def test_editing_the_current_season_does_not_clash_with_itself() -> None:
    """`exclude(pk=...)`: guardar la fila que YA es la activa no puede chocar consigo misma."""
    activa = SeasonDates.objects.create(
        season=2026, sports_id=1, season_start_date=date(2026, 3, 26), season_end_date=date(2026, 11, 1), is_active=True
    )

    activa.all_star_game_date = date(2026, 7, 14)
    activa.full_clean()  # no debe levantar
    activa.save()

    assert SeasonDates.objects.get(pk=activa.pk).all_star_game_date == date(2026, 7, 14)


@pytest.mark.django_db
def test_the_upsert_updates_in_place_and_leaves_the_rest_alone() -> None:
    """La razón de ser del modo: lo que no viene en el CSV sobrevive.

    Acá 2023 se editó a mano y no viene en el CSV; 2024 sí viene y se corrige. Con truncate 2023
    desaparecería, que es exactamente lo que no puede pasar en una tabla que se edita.
    """
    SeasonDates.objects.create(
        season=2023, sports_id=1, season_start_date=date(2023, 3, 30), season_end_date=date(2023, 11, 1)
    )
    SeasonDates.objects.create(
        season=2024, sports_id=1, season_start_date=date(2024, 1, 1), season_end_date=date(2024, 1, 2)
    )
    filas, _ = _validar(_fila())

    engine.apply(engine.REGISTRY[TABLA], filas, CLAVE, truncating=False)

    assert SeasonDates.objects.count() == 2  # 2023 sigue ahí
    assert SeasonDates.objects.get(season=2024).season_start_date == date(2024, 3, 20)  # 2024 corregida


@pytest.mark.django_db
def test_the_backoffice_form_rejects_the_same_bad_order_as_the_import() -> None:
    """La regla vive en el modelo, así que vale para las dos puertas: el CSV y la edición a mano."""
    fila = SeasonDates(
        season=2024,
        sports_id=1,
        season_start_date=date(2024, 3, 20),
        post_season_start_date=date(2024, 2, 1),  # antes de que empiece la temporada
        season_end_date=date(2024, 10, 30),
    )

    with pytest.raises(ValidationError) as error:
        fila.full_clean()

    assert "post_season_start_date" in error.value.message_dict


@pytest.mark.django_db
def test_loading_it_rebuilds_nothing() -> None:
    assert engine.REGISTRY[TABLA].rebuilds == ()
