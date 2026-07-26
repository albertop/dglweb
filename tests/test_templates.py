"""Trampas de las plantillas que no se ven revisando el código, solo mirando la página.

Django no avisa de ninguna de estas: renderiza feliz y el error sale impreso en la pantalla del
lector, que es el peor sitio donde enterarse.
"""

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
CARPETAS = ("templates", "dglweb")


def _plantillas() -> list[Path]:
    return sorted(p for carpeta in CARPETAS for p in (RAIZ / carpeta).rglob("*.html"))


def test_there_are_templates_to_check() -> None:
    """Si la búsqueda deja de encontrar plantillas, el test de abajo pasaría por vacío y no por bueno."""
    assert len(_plantillas()) > 5


@pytest.mark.parametrize("plantilla", _plantillas(), ids=lambda p: str(p.relative_to(RAIZ)))
def test_short_comments_never_span_more_than_one_line(plantilla: Path) -> None:
    """`{# … #}` es de UNA línea. Uno de dos líneas no se comenta: se imprime como texto.

    Pasó dos veces en este proyecto, las dos con el mismo desenlace: un párrafo explicando una
    decisión de diseño, publicado encima de un anuncio en la portada. Django no se queja porque para
    él eso no es un comentario abierto, es texto que empieza con `{#`.

    Para varias líneas está `{% comment %}`.
    """
    culpables = [
        f"{plantilla.relative_to(RAIZ)}:{n}"
        for n, linea in enumerate(plantilla.read_text(encoding="utf-8").splitlines(), 1)
        if "{#" in linea and "#}" not in linea
    ]

    assert not culpables, f"comentario `{{# #}}` sin cerrar en su línea (usa {{% comment %}}): {culpables}"
