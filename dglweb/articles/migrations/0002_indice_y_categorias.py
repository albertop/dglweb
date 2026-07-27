"""Crea la página `/articulos/` y siembra las categorías.

VA EN UNA MIGRACIÓN Y NO EN UN COMANDO A MANO porque sin la página índice no hay dónde colgar un
artículo: el editor abriría el CMS y no encontraría el sitio donde crearlo. Que `docker compose up`
deje el CMS utilizable es parte de que el proyecto arranque.

La página se crea a mano —campos y `path` incluidos— en vez de con `add_child()`. En una migración
solo hay modelos históricos, que no traen los métodos de treebeard; calcular el `path` acá es feo
pero es de una sola vez, y usar el modelo de verdad rompería el día que el modelo cambie.
"""

from typing import Any

from django.db import migrations

# El alfabeto y el paso con los que treebeard arma el `path`. Son los de Wagtail y no se tocan: un
# `path` con otro formato deja la página fuera del árbol sin dar error.
ALFABETO = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PASO = 4

# Las que salieron del diseño del índice. El editor puede cambiarlas, renombrarlas o agregar otras:
# son un snippet, no una lista fija. Esto es solo el punto de partida para no empezar en blanco.
CATEGORIAS = [
    ("Sabermetría", "sabermetria", 10),
    ("Statcast", "statcast", 20),
    ("Defensa", "defensa", 30),
    ("Pitcheo", "pitcheo", 40),
    ("Debutantes", "debutantes", 50),
    ("Historia", "historia", 60),
    ("Cosas raras", "cosas-raras", 70),
]


def _a_numero(trozo: str) -> int:
    valor = 0
    for letra in trozo:
        valor = valor * len(ALFABETO) + ALFABETO.index(letra)
    return valor


def _a_texto(numero: int) -> str:
    letras = ""
    while numero:
        numero, resto = divmod(numero, len(ALFABETO))
        letras = ALFABETO[resto] + letras
    return letras.rjust(PASO, ALFABETO[0])


def crear(apps: Any, schema_editor: Any) -> None:
    Page = apps.get_model("wagtailcore", "Page")
    Site = apps.get_model("wagtailcore", "Site")
    ContentType = apps.get_model("contenttypes", "ContentType")
    ArticleIndexPage = apps.get_model("articles", "ArticleIndexPage")
    Categoria = apps.get_model("articles", "Categoria")

    for nombre, slug, orden in CATEGORIAS:
        Categoria.objects.get_or_create(slug=slug, defaults={"nombre": nombre, "orden": orden})

    sitio = Site.objects.filter(is_default_site=True).first()
    if sitio is None:
        return  # sin sitio no hay árbol donde colgarla; pasa solo en bases a medio armar
    raiz = Page.objects.get(pk=sitio.root_page_id)
    if Page.objects.filter(path__startswith=raiz.path, depth=raiz.depth + 1, slug="articulos").exists():
        return

    ultimo = (
        Page.objects.filter(path__startswith=raiz.path, depth=raiz.depth + 1).order_by("-path").first()
    )
    siguiente = _a_numero(ultimo.path[-PASO:]) + 1 if ultimo else 1

    tipo, _ = ContentType.objects.get_or_create(app_label="articles", model="articleindexpage")
    indice = ArticleIndexPage(
        title="Artículos",
        draft_title="Artículos",
        slug="articulos",
        content_type=tipo,
        path=raiz.path + _a_texto(siguiente),
        depth=raiz.depth + 1,
        numchild=0,
        url_path=f"{raiz.url_path}articulos/",
        live=True,
        locale_id=raiz.locale_id,
        entradilla="Análisis, datos y contexto del béisbol dominicano en las Grandes Ligas.",
        show_in_menus=True,
    )
    indice.save()

    raiz.numchild = Page.objects.filter(path__startswith=raiz.path, depth=raiz.depth + 1).count()
    raiz.save(update_fields=["numchild"])


def deshacer(apps: Any, schema_editor: Any) -> None:
    """Solo la página. Las categorías no: para cuando alguien deshaga esto ya pueden tener artículos
    colgando, y borrarlas se los llevaría por delante."""
    Page = apps.get_model("wagtailcore", "Page")
    Page.objects.filter(slug="articulos", depth=2).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("articles", "0001_initial"),
        ("wagtailcore", "0097_baselogentry_uuid_action_timestamp_indexes"),
    ]

    operations = [migrations.RunPython(crear, deshacer)]
