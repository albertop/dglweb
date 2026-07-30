"""Los botones de compartir de un artículo.

QUÉ SE PROTEGE, Y POR QUÉ ESTAS COSAS Y NO OTRAS
-------------------------------------------------
Un botón de compartir se rompe de formas que **no se ven mirando la pantalla**: el botón sigue ahí,
con su color y su borde, y lo que llega al otro lado es una URL relativa que no lleva a ningún sitio,
o un titular con los acentos convertidos en basura. La persona que lo pulsó no se entera, y quien
recibe el mensaje tampoco sabe qué pasó.

Por eso las pruebas miran **lo que viaja en el enlace**, no que el enlace exista.

Y hay una que no es cosmética: que NO se cargue nada de un tercero. La política de cookies de este
sitio afirma que quien solo navega no recibe ninguna cookie ni le anuncia su visita a nadie. Un widget
de compartir —AddThis, el botón oficial de X— rompería esa frase, y la rompería en silencio.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from django.test import Client

from dglweb.core.templatetags.compartir import compartir

TITULO = "¿Quién abrió la puerta? Virgil y una discusión"
RUTA = "/articulos/quien-abrio-la-puerta/"


# `testserver` y no el dominio real: es el host que `ALLOWED_HOSTS` acepta en la suite sin tener que
# tocar los ajustes. Lo que se comprueba es que la URL salga ABSOLUTA y con el host de la petición,
# no cuál es ese host.
HOST = "testserver"


def _contexto() -> dict[str, Any]:
    from django.test import RequestFactory

    return {"request": RequestFactory().get(RUTA, secure=True)}


def test_la_url_que_se_comparte_es_absoluta() -> None:
    """EL FALLO QUE NO SE VE. Wagtail da URLs relativas, y una red social no puede hacer nada con
    `/articulos/algo/`: el enlace llegaría al otro lado sin dominio y no abriría nada.

    Y el botón se vería perfecto.
    """
    datos = compartir(_contexto(), RUTA, TITULO)

    assert datos["url"].startswith("https://" + HOST + "/"), datos["url"]
    assert datos["url"].endswith(RUTA)


def test_una_url_que_ya_es_absoluta_no_se_toca() -> None:
    """El perfil y líderes podrían pasarla ya hecha; duplicar el dominio la rompería."""
    absoluta = "https://dominicanosengrandesligas.com/lideres/?board=hr"  # ya hecha: no se toca

    assert compartir(_contexto(), absoluta, TITULO)["url"] == absoluta


def test_el_titulo_viaja_entero_y_con_sus_acentos() -> None:
    """Los signos de apertura y las tildes son la mitad de un titular en español.

    Se comprueba deshaciendo la codificación: lo que importa no es cómo se escribe en la URL sino qué
    lee la persona que recibe el mensaje.
    """
    datos = compartir(_contexto(), RUTA, TITULO)

    assert unquote(datos["texto_url"]) == TITULO
    # Y que esté codificado de verdad: sin esto, un `&` o un `#` en el titular cortaría la URL.
    assert " " not in datos["texto_url"]
    assert "¿" not in datos["texto_url"]


@pytest.mark.django_db
def test_whatsapp_va_primero(client: Client) -> None:
    """No es estética: en República Dominicana es donde se comparte deporte.

    X y Facebook van detrás porque toca ponerlos, no porque vayan a mover el tráfico. Esta prueba
    existe para que nadie los reordene «como en todos los sitios».
    """
    from django.template import Context, Template

    html = Template("{% load compartir %}{% compartir url titulo %}").render(
        Context({"url": RUTA, "titulo": TITULO, **_contexto()})
    )

    orden = [html.find(f'data-red="{r}"') for r in ("whatsapp", "x", "facebook")]
    assert all(p > 0 for p in orden), "falta alguna de las tres redes"
    assert orden == sorted(orden), "WhatsApp tiene que ir primero"


def test_no_se_carga_nada_de_un_tercero() -> None:
    """LA PRUEBA QUE SOSTIENE LA POLÍTICA DE COOKIES.

    Los botones son `<a href>`: enlazan a X y a Facebook, pero no CARGAN nada de ellos. La diferencia
    es toda: un enlace no le cuenta nada a nadie hasta que alguien lo pulsa; un `<script src>` de
    AddThis o el botón oficial de X dispara la petición solo, con la IP del visitante, en cada visita.

    Si algún día alguien mete un widget «porque queda mejor», esto se cae — y hay que ir a
    `templates/legal/cookies.html` antes de relajarlo.
    """
    from django.template import Context, Template

    html = Template("{% load compartir %}{% compartir url titulo %}").render(
        Context({"url": RUTA, "titulo": TITULO, **_contexto()})
    )

    assert "<script" not in html, "los botones de compartir no pueden traer JavaScript en línea"
    for atributo in ('src="http', "src='http"):
        assert atributo not in html, "los botones de compartir no pueden cargar de un tercero"


def test_los_enlaces_no_dejan_tocar_nuestra_pagina() -> None:
    """`target="_blank"` sin `rel="noopener"` le da a la página de destino un puntero a la nuestra."""
    from django.template import Context, Template

    html = Template("{% load compartir %}{% compartir url titulo %}").render(
        Context({"url": RUTA, "titulo": TITULO, **_contexto()})
    )

    assert html.count('target="_blank"') == html.count('rel="noopener"')


def test_el_enlace_de_whatsapp_lleva_titulo_y_direccion() -> None:
    """Lo que de verdad se manda. Con solo la URL, el mensaje llega sin contexto y se abre menos."""
    from django.template import Context, Template

    html = Template("{% load compartir %}{% compartir url titulo %}").render(
        Context({"url": RUTA, "titulo": TITULO, **_contexto()})
    )

    inicio = html.index("https://wa.me/?text=")
    href = html[inicio : html.index('"', inicio)]
    texto = unquote(parse_qs(urlparse(href.replace("&amp;", "&")).query)["text"][0])

    assert TITULO in texto
    assert HOST in texto


# ── La descripción social del perfil ────────────────────────────────────────────────────────────
#
# La línea que se lee bajo el titular en Google y en la tarjeta de WhatsApp:
#
#     Bryan Abreu
#     Lanzador relevista. Debutó en 2019.
#     dominicanosengrandesligas.com


class _Jugador:
    """Lo mínimo que mira `descripcion_social`."""

    def __init__(self, pos: str = "RP", debut: object = None) -> None:
        self.pos = pos
        self.debut_date = debut


def test_la_descripcion_es_el_oficio_y_el_debut() -> None:
    import datetime as dt

    from dglweb.profiles.views import descripcion_social

    assert descripcion_social(_Jugador(debut=dt.date(2019, 4, 1))) == "Lanzador relevista. Debutó en 2019."  # type: ignore[arg-type]


def test_no_repite_nada_que_la_tarjeta_ya_diga() -> None:
    """LA PRUEBA QUE PROTEGE LA BREVEDAD, y por eso enumera lo que se quitó.

    La frase empezó siendo «Bryan Abreu, lanzador relevista dominicano, en Grandes Ligas desde 2019.
    496 ponches de por vida. Estadísticas completas de su carrera.» y se le fue quitando todo lo que
    repetía algo que la tarjeta ya dice: el nombre (es el título), «dominicano» y «Grandes Ligas» (están
    en el nombre del sitio y en el dominio), la cifra de carrera y el relleno de palabras clave.

    Cada una de esas piezas es fácil de volver a añadir «para que la descripción sea más rica».
    """
    import datetime as dt

    from dglweb.profiles.views import descripcion_social

    frase = descripcion_social(_Jugador(debut=dt.date(2019, 4, 1)))  # type: ignore[arg-type]

    for sobra in ("dominicano", "Grandes Ligas", "ponches", "jonrones", "Estadísticas completas"):
        assert sobra not in frase, f"volvió a colarse: {sobra!r}"
    assert len(frase) < 60, f"demasiado larga: {frase!r}"


def test_sin_fecha_de_debut_no_se_inventa_un_ano() -> None:
    """Pasa de verdad: los de `dom_players` que aún no llegaron a las mayores no tienen debut."""
    from dglweb.profiles.views import descripcion_social

    frase = descripcion_social(_Jugador(pos="SS"))  # type: ignore[arg-type]

    assert frase == "Campocorto."


# ── FE-01 del review v13: el grupo se llama por lo que de verdad se comparte ─────────────────────


def test_sin_decir_que_se_comparte_el_nombre_es_pobre_pero_cierto() -> None:
    """La penalización de olvidarlo tiene que ser un nombre POBRE y no uno FALSO.

    Lo pobre se nota al leerlo; lo falso solo lo nota quien depende de ello.
    """
    assert compartir(_contexto(), RUTA, TITULO)["etiqueta"] == "Compartir"


@pytest.mark.parametrize(
    ("que", "esperado"),
    [
        ("este artículo", "Compartir este artículo"),
        ("este perfil", "Compartir este perfil"),
        ("esta lista de líderes", "Compartir esta lista de líderes"),
    ],
)
def test_cada_pagina_nombra_lo_suyo(que: str, esperado: str) -> None:
    assert compartir(_contexto(), RUTA, TITULO, que=que)["etiqueta"] == esperado


# Las tres páginas que llevan los botones, y lo que cada una tiene que anunciar.
PAGINAS_QUE_COMPARTEN = [
    ("articles/article_page.html", "este artículo"),
    ("profiles/player_detail.html", "este perfil"),
    ("profiles/leaders.html", "esta lista de líderes"),
]


@pytest.mark.parametrize(("plantilla", "que"), PAGINAS_QUE_COMPARTEN)
def test_ninguna_pagina_anuncia_un_articulo_que_no_existe(plantilla: str, que: str) -> None:
    """EL FALLO QUE SOLO ENCUENTRA QUIEN NO VE LA PANTALLA, y por eso no lo encuentra nadie.

    El `aria-label` estuvo fijo en «Compartir este artículo» dentro del widget, y el widget se llevó
    tal cual al perfil de jugador y a líderes. En esas dos páginas un lector de pantalla anunciaba un
    artículo que no existe — peor que no decir nada, porque manda a buscar algo que no está.

    Se lee el archivo y no la página renderizada a propósito: el perfil necesita un jugador con
    temporadas y líderes una tabla entera, así que montarlas costaría más que lo que se comprueba, y
    lo que se comprueba —que la llamada pase su `que`— está entero en el texto.
    """
    import pathlib
    import re

    ruta = pathlib.Path(__file__).resolve().parent.parent / "templates" / plantilla
    llamadas = re.findall(r"\{% compartir [^%]*%\}", ruta.read_text(encoding="utf-8"))

    assert llamadas, f"{plantilla} ya no comparte: esta prueba dejó de comprobar nada"
    for llamada in llamadas:
        assert f'que="{que}"' in llamada, llamada
