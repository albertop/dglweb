"""La validación de `StaticDataset` — que una fila describa algo que el motor pueda cumplir.

Agregar un dataset es crear una fila en el Backoffice, no tocar código. La contracara es que se
puede escribir una configuración imposible, y sin estos chequeos nada se queja hasta el día de la
carga: el peor momento, porque el CSV ya está hecho y hay alguien esperando del otro lado.
"""

import pytest
from django.core.exceptions import ValidationError

from dglweb.stats.models import StaticDataset

TABLA = "dgl_batted_ball_hits"


def _dataset(**cambios: str) -> StaticDataset:
    campos = {
        "table": TABLA,
        "powershell": "export_batted_ball_hits.ps1",
        "csv": "batted_ball_hits.csv",
        "mode": StaticDataset.Mode.TRUNCATE,
        "natural_key": "player_id,season,stat_group",
    }
    return StaticDataset(**(campos | cambios))


@pytest.mark.django_db
def test_the_real_dataset_validates() -> None:
    """La red de seguridad de los tests de abajo: si esto falla, están midiendo otra cosa."""
    _dataset().full_clean()


@pytest.mark.django_db
def test_a_table_without_a_loader_is_rejected_with_the_list_of_valid_ones() -> None:
    """Sin loader el motor no sabe leer el CSV: ni columnas, ni FKs, ni prueba de aceptación."""
    with pytest.raises(ValidationError) as error:
        _dataset(table="dgl_salarios").full_clean()

    mensaje = error.value.message_dict["table"][0]
    assert "No hay ningún loader" in mensaje
    assert TABLA in mensaje  # dice cuáles sí sirven, no solo que esa no


@pytest.mark.django_db
def test_a_natural_key_naming_columns_the_model_does_not_have_is_rejected() -> None:
    """El error clásico: copiar el nombre del CSV cuando el modelo lo llama de otra forma."""
    with pytest.raises(ValidationError) as error:
        _dataset(natural_key="mlb_id,season,stat_group").full_clean()

    assert "mlb_id" in error.value.message_dict["natural_key"][0]


@pytest.mark.django_db
def test_the_foreign_key_may_be_named_either_way() -> None:
    """El modelo la declara `player` y la columna es `player_id`; las dos son legítimas."""
    _dataset(natural_key="player,season,stat_group").full_clean()


@pytest.mark.django_db
def test_an_empty_natural_key_is_rejected_even_though_truncate_seems_not_to_need_it() -> None:
    """Con truncate igual hace falta: sin ella no hay chequeo de duplicados ni "qué desaparece"."""
    with pytest.raises(ValidationError) as error:
        _dataset(natural_key="  ,  ").full_clean()

    assert "vacía" in error.value.message_dict["natural_key"][0]


@pytest.mark.django_db
def test_upsert_without_a_unique_constraint_behind_the_key_is_rejected() -> None:
    """El modo se llama idempotente y sin la restricción no lo es.

    `update_or_create` sobre una clave que la base no protege deja convivir dos filas iguales, y a
    la carga siguiente revienta al encontrar las dos. La tabla real sí tiene la restricción, así que
    para probarlo hay que pedir un subconjunto que ninguna cubre.
    """
    with pytest.raises(ValidationError) as error:
        _dataset(mode=StaticDataset.Mode.UPSERT, natural_key="player_id,season").full_clean()

    assert "restricción de unicidad" in error.value.message_dict["mode"][0]


@pytest.mark.django_db
def test_upsert_over_the_constrained_key_is_accepted() -> None:
    """La misma clave, esta vez respaldada por `unique_batted_ball_hits`."""
    _dataset(mode=StaticDataset.Mode.UPSERT).full_clean()
