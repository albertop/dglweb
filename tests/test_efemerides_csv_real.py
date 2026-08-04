"""El CSV de verdad, si está en el disco.

Los otros tests usan filas armadas a mano, que prueban las reglas pero no prueban que el archivo QUE
EL EXPORTADOR PRODUCE pase por el motor. Son dos cosas distintas: el `.ps1` y el loader se escribieron
por separado y nada garantiza que hablen el mismo idioma hasta que el archivo real cruza entero.

Se salta solo si el CSV no está —está en `.gitignore` y no viaja al repositorio— así que en CI esto
no corre y en la máquina donde se genera, sí. Es la única forma honesta: no se puede versionar un
archivo de cinco mil filas solo para tener la prueba.
"""

from pathlib import Path

import pytest

from dglweb.stats.models import Efemeride, StaticDataset
from dglweb.stats.staticdata import engine

CSV = Path(__file__).resolve().parent.parent / "static_data" / "csv" / "dgl_efemerides.csv"

pytestmark = pytest.mark.skipif(
    not CSV.exists(),
    reason="el CSV de efemérides no está generado (se produce con exportar_efemerides.ps1)",
)


@pytest.mark.django_db
def test_the_real_csv_crosses_the_engine_whole() -> None:
    """Sin un solo problema, y con todas sus filas.

    Si esto falla después de tocar el exportador, lo que cambió es el contrato entre el `.ps1` y el
    loader — no una regla de negocio.
    """
    dataset = StaticDataset.objects.get(table="dgl_efemerides")
    loader = engine.REGISTRY["dgl_efemerides"]

    raw = engine.read(CSV.read_bytes())
    rows, problems = engine.validate(loader, raw, dataset.key_columns)

    assert problems == [], [(p.message, p.rows[:3]) for p in problems]
    assert len(rows) == len(raw)


@pytest.mark.django_db
def test_the_real_csv_lands_in_the_table_and_can_be_queried_by_day() -> None:
    """La consulta que va a hacer el sitio: un día del calendario, ordenado por importancia.

    Es lo único que el sitio necesita saber hacer, así que es lo que hay que probar de punta a punta.
    """
    dataset = StaticDataset.objects.get(table="dgl_efemerides")
    loader = engine.REGISTRY["dgl_efemerides"]
    rows, problems = engine.validate(loader, engine.read(CSV.read_bytes()), dataset.key_columns)
    assert problems == []

    engine.apply(loader, rows, dataset.key_columns, truncating=True)

    assert Efemeride.objects.count() == len(rows)

    # Un 4 de julio cualquiera: tiene que traer algo y venir ordenado de mayor a menor puntaje.
    del_dia = list(Efemeride.objects.filter(mes=7, dia=4))
    assert del_dia, "el 4 de julio no puede quedar vacío"
    assert [e.puntaje for e in del_dia] == sorted((e.puntaje for e in del_dia), reverse=True)

    # Y ninguna fila publicada puede quedar sin texto que pintar.
    assert not Efemeride.objects.filter(titular="").exists()
