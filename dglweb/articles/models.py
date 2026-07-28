"""Los artículos, como páginas de Wagtail.

DOS NIVELES Y NO UNO
--------------------
`ArticleIndexPage` es `/articulos/` y `ArticlePage` cuelga de ella, así que cada artículo queda en
`/articulos/<slug>/` sin que nadie escriba una ruta. Es la forma en que Wagtail sirve páginas y la
que hace que el editor pueda mover, renombrar y despublicar sin tocar `urls.py` — que era justo el
punto de meter un CMS.

CATEGORÍA ÚNICA, HASHTAGS LIBRES
--------------------------------
Decisión del dueño y la estructura la respeta: la categoría es una clave foránea —una sola, y es el
kicker rojo de la tarjeta— y los hashtags son un `taggit` sin límite. Son dos cosas distintas aunque
las dos «etiqueten»: la categoría dice DÓNDE vive el artículo y sirve para navegar; el hashtag dice
DE QUÉ habla y sirve para relacionar.

Y desde el 2026-07-27 la categoría es OBLIGATORIA. La razón no es de forma: sin ella, el artículo no
aparece bajo ningún filtro del índice — solo se llega desde la lista general, así que se publica y se
pierde.

LO QUE NO SE LE PIDE AL EDITOR
------------------------------
El tiempo de lectura se calcula contando palabras, no se teclea: nadie acierta a ojo y es el tipo de
dato que se queda viejo en cuanto se edita un párrafo.
"""

from typing import Any

from django.core.paginator import Page as Page_
from django.db import models
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import strip_tags
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import ItemBase, TagBase
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.query import PageQuerySet
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from dglweb.articles.blocks import CuerpoStreamBlock

# Palabras por minuto para el tiempo de lectura. 200 es el número que usa casi todo el mundo para
# prosa en español; con tablas y gráficos el artículo se lee más lento, pero redondear hacia arriba
# ya lo compensa.
PALABRAS_POR_MINUTO = 200

# El reparto del índice, en el orden en que se leen. La suma —seis— es lo que se ve al abrir.
#
# Vive acá y no en la plantilla porque son cortes de una lista, y hacerlos con `forloop.counter` en el
# HTML obliga a leer varias condiciones para saber qué sale dónde. Acá cada hueco tiene nombre.
#
# Hubo una fila más, a todo el ancho, cerrando lo visible: nueve artículos de entrada. El dueño la
# quitó porque la página se veía cargada, y tiene razón — lo que hace útil un índice es que se
# abarque de un vistazo, no que quepa todo.
DESTACADO = 1  # el grande de arriba, con la banda ancha
RETICULA = 4  # las dos filas de dos que van debajo del destacado
LATERAL = 1  # el que va bajo el panel de «Lo más reciente», en la columna estrecha
INICIALES = DESTACADO + RETICULA + LATERAL

# Cuántos artículos por página. Doce: en la primera son los seis huecos con nombre de arriba más una
# fila de seis; en las demás, doce en retícula.
#
# ESTO SUSTITUYE AL BOTÓN «Ver más artículos», que destapaba con JavaScript artículos ya dibujados y
# escondidos. Aquello tenía dos problemas que la paginación resuelve de una vez: la página traía
# hasta 24 artículos aunque se leyeran seis —y con cientos publicados habría traído cientos— y el
# botón quedaba muerto sin JavaScript. Ahora cada página trae lo suyo y los enlaces son enlaces.
POR_PAGINA = 12


@register_snippet
# El `ignore` es por Wagtail y no por este código: `ArticlePage` hereda de `Page`, que para mypy es
# `Any` porque Wagtail no publica tipos, así que django-stubs no puede resolver el `articulos` que
# esa relación deja de este lado. La relación existe y funciona; lo que no se puede es tiparla.
class Categoria(models.Model):  # type: ignore[django-manager-missing]
    """Dónde vive el artículo. Una por artículo — ver la cabecera.

    Es un snippet y no una lista fija en el código: cambiar el reparto de secciones de un sitio
    editorial es una decisión del que escribe, no un despliegue.
    """

    nombre = models.CharField(max_length=40, unique=True)
    slug = models.SlugField(max_length=40, unique=True, help_text="Lo que sale en la URL del filtro.")
    orden = models.PositiveSmallIntegerField(
        default=100, help_text="De menor a mayor, así se ordenan las pestañas del índice."
    )

    panels = [FieldPanel("nombre"), FieldPanel("slug"), FieldPanel("orden")]

    class Meta:
        ordering = ["orden", "nombre"]
        verbose_name = "categoría"
        verbose_name_plural = "categorías"

    def __str__(self) -> str:
        return self.nombre


class Hashtag(TagBase):
    """Un `taggit` propio y no el genérico compartido con el resto del sitio.

    Los tags genéricos de Wagtail los usan también las imágenes y los documentos; mezclarlos haría
    que el autocompletado del editor ofrezca el nombre de un archivo como si fuera un tema.
    """

    class Meta:
        verbose_name = "hashtag"
        verbose_name_plural = "hashtags"


class HashtagDeArticulo(ItemBase):
    """La fila que une un artículo con un hashtag.

    El `related_name` es `hashtags_relacion` y no `hashtags` a propósito: el nombre bonito se lo
    queda el `ClusterTaggableManager` de `ArticlePage`, que es por donde se lee y se escribe.
    """

    tag = models.ForeignKey(Hashtag, related_name="articulos", on_delete=models.CASCADE)
    content_object = ParentalKey("articles.ArticlePage", related_name="hashtags_relacion", on_delete=models.CASCADE)


def _paginar(articulos: QuerySet["ArticlePage"] | Any, pedida: str | None) -> "Page_[Any]":  # noqa: ANN401
    # El `Any` es porque la búsqueda de Wagtail NO devuelve un queryset sino un `SearchResults`, y
    # los dos sirven para paginar. Escribir solo uno de los dos tipos sería mentir sobre lo que entra.
    """La página pedida, o la primera si el número no vale.

    Un `?pagina=abc` o un `?pagina=999` vienen de la URL, así que los escribe cualquiera: se cae a la
    primera en vez de reventar con un 500. Una página que no existe no es un error del sitio.
    """
    from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

    paginador = Paginator(articulos, POR_PAGINA)
    try:
        return paginador.page(pedida or 1)
    except (PageNotAnInteger, EmptyPage):
        return paginador.page(1)


def para_tarjetas(articulos: "PageQuerySet[ArticlePage]") -> "PageQuerySet[ArticlePage]":
    """Lo que `_tarjeta.html` necesita, traído de una vez. ÚSALO en todo listado de artículos.

    POR QUÉ EXISTE
    --------------
    La tarjeta es una sola plantilla compartida por la portada, el índice, la búsqueda y el panel de
    recientes — pero cada uno armaba su consulta por su cuenta, y todos se quedaban en
    `select_related("categoria")`. La tarjeta además lee `articulo.imagen` y `articulo.hashtags.all`,
    así que cada una disparaba lo suyo.

    Medido en `/articulos/` antes de esto: **40 consultas, de ellas 15 a `articles_hashtag` y 11 a
    `wagtailimages_image`** — una por tarjeta. Con 12 por página no dolía; crece lineal, y los
    artículos semilla vienen en camino.

    El problema de fondo no era el número: era que **compartían plantilla sin compartir política de
    carga**. Esa asimetría es donde nacen los N+1, porque el que añade una relación a la tarjeta no
    tiene forma de saber qué consultas hay que tocar. Ahora hay una sola, y este docstring es donde
    se entera.

    Del review v9 (DEV-03/QA-03/ARCH-01). `tests/test_articles.py` fija un presupuesto de consultas
    para que volver a romperlo sea ruidoso.

    Y EL `public()`, QUE NO ES CARGA SINO PERMISO
    ---------------------------------------------
    Vive acá por el mismo motivo que lo demás: es una política que los cuatro listados comparten y
    que ninguno debería tener que acordarse de aplicar. Ponerla en cada sitio es dejar tres sitios
    donde se puede olvidar, y el olvido no se ve — la página sale bien, solo que enseñando de más.

    En Wagtail `live()` significa PUBLICADO EN EL ÁRBOL, no «visible para cualquiera». Si el día de
    mañana marcas un artículo como restringido para un embargo, Wagtail protege el detalle —pide la
    clave— pero la portada y el índice seguirían enseñando titular, entradilla, imagen, categoría y
    etiquetas en la tarjeta. O sea, la primicia entera menos el cuerpo. Comprobado con una
    `PageViewRestriction` de verdad antes de escribir esto (SEC-01 del review v10).

    Que el propio mapa del sitio de Wagtail llame a `public()` y nuestras vistas no era la señal: no
    es una precaución nuestra, es cómo se consulta el árbol de páginas cuando hay público delante.

    No cuesta nada, y eso también está medido: la portada hace las mismas 2 consultas con `public()`
    y sin él.
    """
    return articulos.public().select_related("categoria", "imagen").prefetch_related("hashtags")


def _arrastre(consulta: str, categoria: str) -> str:
    """Lo que los enlaces de paginación tienen que llevarse consigo, ya como `&clave=valor`.

    Sin esto, pasar a la página dos devolvería el índice entero: la búsqueda y la categoría se
    perderían y la persona acabaría en un sitio que no pidió.
    """
    from urllib.parse import urlencode

    partes = {clave: valor for clave, valor in (("q", consulta), ("categoria", categoria)) if valor}
    return f"&{urlencode(partes)}" if partes else ""


class ArticleIndexPage(Page):
    """`/articulos/`. Lista lo publicado y filtra por categoría."""

    entradilla = models.CharField(
        max_length=200,
        blank=True,
        help_text="La línea que va bajo el título de la página.",
    )

    content_panels = [*Page.content_panels, FieldPanel("entradilla")]
    # Solo artículos debajo: una página suelta acá dentro saldría en la retícula sin kicker ni fecha.
    subpage_types = ["articles.ArticlePage"]
    max_count = 1  # hay un solo índice; dos competirían por la misma URL en el menú

    class Meta:
        verbose_name = "índice de artículos"

    def articulos(self) -> models.QuerySet["ArticlePage"]:
        """Lo publicado, del más nuevo al más viejo.

        `live()` y no `all()`: un borrador visible desde la portada es la manera más rápida de
        publicar sin querer algo a medio escribir.
        """
        return (
            para_tarjetas(ArticlePage.objects.child_of(self).live())
            # El `pk` desempata: dos artículos del mismo día tienen orden.
            # `-fijado` primero: en Postgres `True` va antes que `False`. Cambiar SOLO acá hace que
            # el artículo fijado encabece la portada Y el índice, porque los dos toman el primero de
            # esta misma lista. El panel «Lo más reciente» NO usa este orden — ver `get_context`.
            .order_by("-fijado", "-fecha", "-pk")
        )

    def get_context(
        self,
        request: HttpRequest,
        *args: Any,  # noqa: ANN401 — la firma es la de Wagtail
        **kwargs: Any,  # noqa: ANN401
    ) -> dict[str, Any]:
        contexto = super().get_context(request, *args, **kwargs)
        articulos = self.articulos()

        # El filtro va por querystring y no por una URL propia por categoría: son excluyentes y se
        # navegan como pestañas, así que `?categoria=defensa` dice exactamente lo que pasa y no
        # obliga a inventar una ruta por cada categoría que el editor cree mañana.
        elegida = request.GET.get("categoria", "")
        if elegida:
            articulos = articulos.filter(categoria__slug=elegida)

        # Las pestañas y la elegida se ponen ANTES de cualquier retorno: la cabecera de la página es
        # la misma se busque o no. Estaban después, y buscar dejaba la fila de categorías vacía —
        # solo «Todos»— porque el retorno temprano de la búsqueda se las saltaba.
        contexto["categorias"] = Categoria.objects.all()
        contexto["elegida"] = elegida

        # LA BÚSQUEDA. Cuando hay consulta, la página deja de ser un índice y pasa a ser una lista de
        # resultados: sin destacado, sin panel y sin tandas escondidas. Un «destacado» entre
        # resultados de búsqueda no significa nada —lo que ordena acá es la relevancia, no la fecha—
        # y el panel de recientes competiría con lo que la persona vino a buscar.
        consulta = request.GET.get("q", "").strip()
        contexto["consulta"] = consulta
        if consulta:
            # La búsqueda de Wagtail: indexa título, entradilla y cuerpo, y ordena por relevancia. La
            # configuración de Postgres que usa entiende español y no exige tildes — ver la migración
            # `0005_busqueda_en_espanol`.
            # El `ignore` es de tipos, no de lógica: `search()` lo añade Wagtail al queryset de
            # `Page` y django-stubs no lo ve porque Wagtail no publica tipos.
            articulos = articulos.search(consulta)  # type: ignore[attr-defined]

        pagina = _paginar(articulos, request.GET.get("pagina"))
        contexto["pagina"] = pagina
        # El enlace de la página siguiente tiene que llevarse la búsqueda y la categoría, o pasar a la
        # dos devolvería el índice entero y la persona perdería lo que estaba mirando.
        contexto["arrastre"] = _arrastre(consulta, elegida)

        if consulta:
            # Los resultados también van paginados: una búsqueda amplia sobre cien artículos no puede
            # devolverlos todos de golpe. `cuantos` es el TOTAL y no lo de esta página — quien busca
            # quiere saber cuántos hay, no cuántos le cupieron.
            contexto["resultados"] = list(pagina.object_list)
            contexto["cuantos"] = pagina.paginator.count
            contexto["destacado"] = None
            return contexto

        # Los seis huecos con nombre SOLO en la primera página. En la dos, un «destacado» sería el
        # séptimo artículo más reciente puesto en grande, que no significa nada; y el panel de
        # recientes repetiría lo que la persona acaba de dejar atrás.
        en_pagina = list(pagina.object_list)
        if pagina.number == 1:
            contexto["destacado"] = en_pagina[0] if en_pagina else None
            contexto["reticula"] = en_pagina[DESTACADO : DESTACADO + RETICULA]
            contexto["lateral"] = en_pagina[DESTACADO + RETICULA : INICIALES]
            contexto["resto"] = en_pagina[INICIALES:]
            # Para el panel de la derecha. Sale de lo publicado sin filtrar: si filtrara con la
            # retícula repetiría exactamente lo mismo dos veces en la misma pantalla.
            # Cronológico de verdad, sin el fijado arriba: el panel se llama «Lo más reciente» y un
            # artículo de hace tres semanas encabezándolo sería mentira. El fijado ya manda en la
            # retícula de al lado, que es donde esa decisión editorial tiene sentido.
            contexto["recientes"] = self.articulos().order_by("-fecha", "-pk")[:10]
        else:
            contexto["destacado"] = None
            contexto["resto"] = en_pagina
        return contexto


class ArticlePage(Page):
    """Un artículo."""

    entradilla = models.TextField(
        max_length=400,
        help_text="El resumen que sale en las tarjetas y en los buscadores. Obligatorio.",
    )
    imagen = models.ForeignKey(
        "wagtailimages.Image",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
        help_text="La de la tarjeta y la cabecera. Sin ella la tarjeta sale solo con texto.",
    )
    # OBLIGATORIA desde el 2026-07-27, por decisión del dueño. La razón es concreta: un artículo sin
    # categoría **no aparece bajo ningún filtro del índice** — solo se llega a él desde la lista
    # general, así que se publica y se pierde. Lo destapó el review v8 (DEV-03).
    #
    # `PROTECT` y no `SET_NULL`, que era lo que había: sin nulos, `SET_NULL` ni siquiera es legal, y
    # además la semántica correcta es esa. Borrar una categoría con artículos dentro tiene que
    # fallar y obligar a reasignarlos, no dejarlos huérfanos en silencio.
    categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        related_name="articulos",
        verbose_name="categoría",
    )
    hashtags = ClusterTaggableManager(through=HashtagDeArticulo, blank=True)
    autor = models.CharField(max_length=80, blank=True, help_text="Como se firma: «A. Perdomo».")
    # Fijar un artículo arriba, en la portada y en el índice, sin depender de su fecha.
    #
    # POR QUÉ GANA EL MÁS RECIENTE DE LOS FIJADOS, y no «solo uno puede estarlo». Decisión del dueño
    # (2026-07-28): así marcar uno nuevo desplaza al viejo por sí solo, sin que el sistema desmarque
    # nada a espaldas del editor. Guardar un artículo NO puede modificar otro que nadie estaba
    # editando — en una redacción con varias manos, eso es de lo que más confunde.
    #
    # El precio de esa decisión es olvidarse: un fijado de hace meses sigue arriba porque nadie lo
    # quitó. No hay caducidad automática a propósito, para no añadir una regla más; queda en la
    # disciplina de quien publica.
    fijado = models.BooleanField(
        "fijado arriba",
        default=False,
        help_text=(
            "Lo pone de primero en la portada y en el índice, sin importar su fecha. Si hay varios "
            "fijados manda el más reciente, así que para cambiarlo basta con marcar el nuevo."
        ),
    )
    fecha = models.DateField("fecha de publicación")
    cuerpo = StreamField(CuerpoStreamBlock(), blank=True)

    content_panels = [
        *Page.content_panels,
        MultiFieldPanel(
            [FieldPanel("entradilla"), FieldPanel("imagen")],
            heading="La tarjeta",
        ),
        MultiFieldPanel(
            [
                FieldPanel("categoria"),
                FieldPanel("hashtags"),
                FieldPanel("autor"),
                FieldPanel("fecha"),
                FieldPanel("fijado"),
            ],
            heading="Ficha",
        ),
        FieldPanel("cuerpo"),
    ]
    # `entradilla` con `boost`: es la frase que resume el artículo, así que pesa más que un párrafo
    # cualquiera del cuerpo.
    search_fields = [
        *Page.search_fields,
        index.SearchField("entradilla", boost=2),
        index.SearchField("cuerpo"),
        # Declarada para poder FILTRAR por categoría dentro de una búsqueda. No es indexación de
        # texto —nadie busca «defensa» esperando la categoría— sino la condición del `WHERE`: sin
        # esto, buscar dentro de una categoría revienta con «Cannot filter search results with field
        # slug», y el buscador y las pestañas dejarían de poder combinarse.
        index.RelatedFields("categoria", [index.FilterField("slug")]),
    ]
    parent_page_types = ["articles.ArticleIndexPage"]
    subpage_types: list[str] = []  # un artículo no tiene hijos

    class Meta:
        verbose_name = "artículo"
        verbose_name_plural = "artículos"

    @property
    def minutos(self) -> int:
        """Cuánto se tarda en leerlo. Calculado, nunca tecleado — ver la cabecera del módulo.

        Cuenta la entradilla y el cuerpo, y redondea hacia arriba: nunca dice «0 min», que es lo que
        daría un apunte de tres líneas y se lee como un error.
        """
        texto = f"{self.entradilla} {strip_tags(str(self.cuerpo))}"
        palabras = len(texto.split())
        return max(1, -(-palabras // PALABRAS_POR_MINUTO))
