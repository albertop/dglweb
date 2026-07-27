"""Los artículos, como páginas de Wagtail.

DOS NIVELES Y NO UNO
--------------------
`ArticleIndexPage` es `/articulos/` y `ArticlePage` cuelga de ella, así que cada artículo queda en
`/articulos/<slug>/` sin que nadie escriba una ruta. Es la forma en que Wagtail sirve páginas y la
que hace que el editor pueda mover, renombrar y despublicar sin tocar `urls.py` — que era justo el
punto de meter un CMS.

CATEGORÍA ÚNICA, HASHTAGS LIBRES
--------------------------------
Decisión del dueño y la estructura la respeta: la categoría es una clave foránea —una y solo una, y
es el kicker rojo de la tarjeta— y los hashtags son un `taggit` sin límite. Son dos cosas distintas
aunque las dos «etiqueten»: la categoría dice DÓNDE vive el artículo y sirve para navegar; el
hashtag dice DE QUÉ habla y sirve para relacionar.

LO QUE NO SE LE PIDE AL EDITOR
------------------------------
El tiempo de lectura se calcula contando palabras, no se teclea: nadie acierta a ojo y es el tipo de
dato que se queda viejo en cuanto se edita un párrafo.
"""

from typing import Any

from django.db import models
from django.http import HttpRequest
from django.utils.html import strip_tags
from modelcluster.contrib.taggit import ClusterTaggableManager
from modelcluster.fields import ParentalKey
from taggit.models import ItemBase, TagBase
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page
from wagtail.search import index
from wagtail.snippets.models import register_snippet

from dglweb.articles.blocks import CuerpoStreamBlock

# Palabras por minuto para el tiempo de lectura. 200 es el número que usa casi todo el mundo para
# prosa en español; con tablas y gráficos el artículo se lee más lento, pero redondear hacia arriba
# ya lo compensa.
PALABRAS_POR_MINUTO = 200

# Cuántos artículos por página en el índice.
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
    content_object = ParentalKey(
        "articles.ArticlePage", related_name="hashtags_relacion", on_delete=models.CASCADE
    )


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
            ArticlePage.objects.child_of(self)
            .live()
            .select_related("categoria")
            .order_by("-fecha", "-pk")  # el `pk` desempata: dos artículos del mismo día tienen orden
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

        contexto["articulos"] = articulos[:POR_PAGINA]
        contexto["categorias"] = Categoria.objects.all()
        contexto["elegida"] = elegida
        # Para el panel de la derecha. Sale de lo publicado sin filtrar: si filtrara con la retícula
        # repetiría exactamente lo mismo dos veces en la misma pantalla.
        contexto["recientes"] = self.articulos()[:10]
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
    categoria = models.ForeignKey(
        Categoria,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="articulos",
        verbose_name="categoría",
    )
    hashtags = ClusterTaggableManager(through=HashtagDeArticulo, blank=True)
    autor = models.CharField(max_length=80, blank=True, help_text="Como se firma: «A. Perdomo».")
    fecha = models.DateField("fecha de publicación")
    cuerpo = StreamField(CuerpoStreamBlock(), blank=True)

    content_panels = [
        *Page.content_panels,
        MultiFieldPanel(
            [FieldPanel("entradilla"), FieldPanel("imagen")],
            heading="La tarjeta",
        ),
        MultiFieldPanel(
            [FieldPanel("categoria"), FieldPanel("hashtags"), FieldPanel("autor"), FieldPanel("fecha")],
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
