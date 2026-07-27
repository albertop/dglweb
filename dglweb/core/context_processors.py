"""Lo que necesita el armazón del sitio —`base.html`— y por lo tanto TODAS las páginas.

Va acá y no en cada vista por una razón práctica: el cintillo vive en la cabecera, así que pedírselo
a cada vista obligaría a que la de líderes, la del perfil y la del buscador sepan de algo que no les
incumbe. Y bastaría olvidarse en una para que el cintillo desapareciera ahí sin motivo aparente, que
es el tipo de fallo que nadie reporta porque parece intencional.
"""

from typing import Any

from django.core.cache import cache
from django.http import HttpRequest

# Un cuarto de hora. La fuente la refresca un job cada hora, así que un cuarto de hora de retraso es
# invisible y ahorra la consulta en cada visita del sitio entero. Más corto no gana nada; más largo
# haría que un movimiento recién traído tardara en salir.
SEGUNDOS = 15 * 60
CLAVE = "cintillo:movimientos"


def cintillo(request: HttpRequest) -> dict[str, Any]:
    """`movimientos` — los últimos movimientos de roster, para la cintilla de la cabecera."""
    from dglweb.stats import roster_moves

    movimientos = cache.get(CLAVE)
    if movimientos is None:
        movimientos = roster_moves.portada()
        cache.set(CLAVE, movimientos, SEGUNDOS)
    return {"movimientos": movimientos}


def paginas_legales(request: HttpRequest) -> dict[str, Any]:
    """`legal_paginas` — los tres documentos legales, para la columna del pie.

    Es una constante del código, así que no toca la base ni la caché: sale del mismo diccionario que
    usan la vista y las pruebas. Ese es todo el punto — el pie no puede enlazar a un documento que
    no existe, ni dejar uno sin enlazar, porque las dos listas son la misma lista.
    """
    from dglweb.core import legal

    return {"legal_paginas": legal.PAGINAS}
