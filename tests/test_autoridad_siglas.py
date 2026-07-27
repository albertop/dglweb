"""Las siglas del sitio van en inglés. Nunca en español.

Es la regla 2 de `docs/AUTORIDAD.md`, y vale «ni en la portada, ni en los perfiles, ni en las tablas
del Backoffice, ni en los nombres visibles de los modelos».

Este test existe porque los `verbose_name` de los modelos se le habían escapado a esa regla: la parte
que ve el lector ya decía `RBI` y `HBP`, y el metadata seguía diciendo `CI` y `GP`. No se veía en
ninguna pantalla —esas tablas no tienen CRUD— y por eso duró: nadie mira lo que nadie muestra. Pero
cualquier admin genérico, export o formulario futuro las habría sacado a la luz sin que nadie lo
decidiera (DEV-03 + SAB-02 del review v7).
"""

from pathlib import Path

import pytest
from django.apps import apps

# Lo que la autoridad prohíbe, con su sigla correcta al lado. Se escriben las dos para que el mensaje
# del fallo diga qué poner, no solo qué está mal.
PROHIBIDAS: dict[str, str] = {
    "J": "G",
    "AP": "PA",
    "C": "R",
    "BR": "SB",
    "AR": "CS",
    "P": "SO",
    "BBI": "IBB",
    "BBNI": "NIBB",
    "GP": "HBP",
    "TS": "SH",
    "ES": "SF",
    "DEB": "LOB",
    "CP": "RP",
    "BB/P": "BB/SO",
    "AP/P": "PA/SO",
    # Las de la tabla de `AUTORIDAD.md` que ya no aparecían, para que tampoco vuelvan.
    "CI": "RBI",
    "CA": "R",
    "CL": "ER",
    "VB": "AB",
    "AVE": "AVG",
}


def _campos_de_stats() -> list[tuple[str, str, str]]:
    """(modelo, campo, verbose_name) de todo lo que vive en `stats`."""
    return [
        (modelo.__name__, campo.name, str(campo.verbose_name))
        for modelo in apps.get_app_config("stats").get_models()
        for campo in modelo._meta.fields
    ]


def test_there_are_fields_to_check() -> None:
    """Si la introspección deja de encontrar campos, el test de abajo pasaría por vacío."""
    assert len(_campos_de_stats()) > 100


@pytest.mark.parametrize("prohibida", sorted(PROHIBIDAS))
def test_no_spanish_abbreviation_survives_in_the_models(prohibida: str) -> None:
    culpables = [
        f"{modelo}.{campo} dice «{etiqueta}» (debería ser «{PROHIBIDAS[prohibida]}»)"
        for modelo, campo, etiqueta in _campos_de_stats()
        if etiqueta == prohibida
    ]

    assert not culpables, f"siglas en español en los modelos: {culpables}"


def test_the_authority_document_still_says_this() -> None:
    """El test no puede ser la única fuente de la regla: si el documento cambia, esto se revisa.

    Sin este anclaje, un test así se vuelve una regla huérfana que nadie sabe de dónde salió — y la
    siguiente persona la borra por molesta en vez de discutirla con el dueño.
    """
    autoridad = (Path(__file__).resolve().parent.parent / "docs" / "AUTORIDAD.md").read_text(encoding="utf-8")

    assert "en inglés, nunca en español" in autoridad
    assert "los nombres visibles de los modelos" in autoridad
