"""La URL del índice de artículos, disponible en toda plantilla.

La usan el menú y el pie, que están en `base.html` y por lo tanto en TODAS las páginas. Antes era un
`{% url 'articles' %}` contra una ruta fija de Django; desde que la página la sirve Wagtail, la ruta
la decide el editor y hay que preguntársela al árbol.

POR QUÉ UN PROCESADOR DE CONTEXTO Y NO `{% slugurl %}`
------------------------------------------------------
Wagtail trae `{% slugurl 'articulos' %}`, que hace exactamente esto. El problema es que son dos usos
por página —menú y pie— y cada uno cobra su consulta, en todas las páginas del sitio. Acá se resuelve
una vez por petición y además se cachea, así que el coste normal es cero consultas.

Y se guarda en caché por su ID, no por su URL: si el editor mueve la página, `Page.url` lo refleja
solo. El ID es lo único que no cambia.
"""

from typing import Any

from django.core.cache import cache
from django.http import HttpRequest

# Un día. La página índice se mueve una vez cada nunca; lo que se evita con esto es una consulta por
# visita en un sitio entero, y el precio de equivocarse es un menú desactualizado hasta mañana.
SEGUNDOS = 60 * 60 * 24
CLAVE = "articles:indice"


def indice(request: HttpRequest) -> dict[str, Any]:
    """`indice_articulos` — la URL de `/articulos/`, o vacío si todavía no existe la página.

    Vacío y no un `#`: la plantilla esconde el enlace, porque un menú que lleva a ninguna parte es
    peor que un menú con un elemento menos.
    """
    from dglweb.articles.models import ArticleIndexPage

    url = cache.get(CLAVE)
    if url is None:
        pagina = ArticleIndexPage.objects.live().first()
        url = pagina.url if pagina else ""
        cache.set(CLAVE, url, SEGUNDOS)
    return {"indice_articulos": url}
