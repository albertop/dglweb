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


def analitica(request: HttpRequest) -> dict[str, Any]:
    """`analitica` — el origen y el identificador de Umami, o `None` si no hay analítica configurada.

    Un diccionario y no dos variables sueltas para que la plantilla no pueda dibujar media etiqueta:
    con el origen puesto y el identificador vacío, Umami carga y no cuenta nada. O están los dos o no
    está ninguno, y eso se decide acá y no en un `{% if %}` con dos condiciones.

    NO TOCA NADA: son dos ajustes leídos de memoria. Va de procesador de contexto y no de etiqueta de
    plantilla porque el script vive en `base.html`, o sea en todas las páginas, y una etiqueta habría
    que cargarla igual en todas.
    """
    from django.conf import settings

    if not (settings.ANALITICA_URL and settings.ANALITICA_ID):
        return {"analitica": None}
    return {"analitica": {"url": settings.ANALITICA_URL, "id": settings.ANALITICA_ID}}


def anuncios(request: HttpRequest) -> dict[str, Any]:
    """`anuncios_visibles` — si hoy se dibujan los huecos de publicidad.

    Va de procesador de contexto y no de etiqueta por dos motivos. Uno: lo necesitan las plantillas
    de los marcos, que se incluyen desde seis páginas distintas, y una etiqueta habría que cargarla
    en las seis. Dos, y este es el que importa: **la portada cambia de rejilla** cuando no hay
    publicidad —el carril de 300x600 desaparece y los artículos pasan a tres columnas— así que la
    bandera no la consulta solo el hueco, la consulta el layout.

    NO CONFUNDIR CON `ADSERVER_URL`, que dice DÓNDE está Revive. Esta dice si se enseña. El porqué de
    que sean dos ajustes y no uno está escrito en `config/settings/base.py`.
    """
    from django.conf import settings

    return {"anuncios_visibles": bool(settings.ANUNCIOS_VISIBLES)}


def redes(request: HttpRequest) -> dict[str, Any]:
    """`X_USUARIO`, la cuenta del sitio en X. La usan el pie y la tarjeta social, o sea todas las páginas.

    Va acá y no en cada vista por lo mismo que el resto de este módulo: `base.html` lo necesita en
    todas, y depender de que cada vista se acuerde de ponerlo es dejar el pie a medias en la que se
    olvide.

    Vacío si no está configurado, y entonces las plantillas no dibujan ni el enlace ni el
    `twitter:site`. Eso es lo correcto: un enlace a una cuenta que no existe es peor que ningún enlace.
    """
    # El import va dentro, como en `analitica`: este módulo lo carga Django al construir el motor de
    # plantillas, y a nivel de módulo tocaría los ajustes antes de que estén listos.
    from django.conf import settings

    return {"X_USUARIO": settings.X_USUARIO}
