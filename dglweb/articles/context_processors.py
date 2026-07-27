"""La URL del índice de artículos, disponible en toda plantilla.

La usan el menú y el pie, que están en `base.html` y por lo tanto en TODAS las páginas. Antes era un
`{% url 'articles' %}` contra una ruta fija de Django; desde que la página la sirve Wagtail, la ruta
la decide el editor y hay que preguntársela al árbol.

POR QUÉ UN PROCESADOR DE CONTEXTO Y NO `{% slugurl %}`
------------------------------------------------------
Wagtail trae `{% slugurl 'articulos' %}`, que hace exactamente esto. El problema es que son dos usos
por página —menú y pie— y cada uno cobra su consulta, en todas las páginas del sitio. Acá se resuelve
una vez por petición y además se cachea, así que el coste normal es cero consultas.

Lo que se guarda en caché es la URL, y por eso hace falta INVALIDARLA. El comentario que había acá
decía que se cacheaba «por su ID, no por su URL» — y era falso: el código guardaba la URL desde el
primer día. Un comentario que miente es peor que ninguno, porque manda a buscar un comportamiento que
no existe; lo destapó el review v8 (ARCH-02).

La invalidación va por señales de Wagtail: al publicar, mover o despublicar el índice, se tira la
entrada. Sin eso, el editor movía la página y el menú de TODAS las páginas apuntaba a una ruta muerta
hasta 24 horas.
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


def _olvidar(**kwargs: Any) -> None:  # noqa: ANN401 — la firma es la de las señales de Django
    """Tira la URL cacheada. La llaman las señales de Wagtail — ver abajo.

    No comprueba QUÉ página se movió: es una sola entrada de caché y recalcularla cuesta una
    consulta. Filtrar por tipo de página sería más código para ahorrar algo que no duele.
    """
    cache.delete(CLAVE)


def conectar_senales() -> None:
    """Engancha el olvido a publicar, despublicar y mover. La llama `ArticlesConfig.ready()`."""
    from wagtail.signals import page_published, page_unpublished

    page_published.connect(_olvidar, dispatch_uid="articles-indice-publicado")
    page_unpublished.connect(_olvidar, dispatch_uid="articles-indice-despublicado")
