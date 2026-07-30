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


# ── El texto que se comparte desde el perfil ────────────────────────────────────────────────────
#
# Es lo que decide si compartir un perfil sirve de algo. Un enlace que dice «Juan Soto» compite con
# todo lo demás en un chat; uno que dice «Juan Soto — 245 jonrones de por vida» se abre.


class _Carrera:
    """Lo mínimo de `BattingCareer` / `PitchingCareer` que mira la función."""

    def __init__(self, **kw: object) -> None:
        self.hr = self.h = self.so = 0
        self.__dict__.update(kw)


class _Jugador:
    def __init__(self, nombre: str) -> None:
        self.full_name = nombre


def test_el_texto_del_perfil_lleva_la_cifra_que_define_al_pelotero() -> None:
    from dglweb.profiles.views import texto_compartir

    texto = texto_compartir(_Jugador("Juan Soto"), _Carrera(hr=245, h=1200), None)  # type: ignore[arg-type]

    assert texto.startswith("Juan Soto")
    assert "245" in texto, "sin el número, el enlace no invita a nada"


def test_a_un_lanzador_lo_define_el_ponche_y_no_el_jonron() -> None:
    """Un lanzador con jonrones PERMITIDOS no puede salir presumiendo de ellos."""
    from dglweb.profiles.views import texto_compartir

    texto = texto_compartir(
        _Jugador("Cristian Javier"),  # type: ignore[arg-type]
        _Carrera(hr=2),  # type: ignore[arg-type]
        _Carrera(so=980),  # type: ignore[arg-type]
    )

    assert "980 ponches" in texto
    assert "jonrones" not in texto


def test_sin_datos_se_queda_solo_el_nombre_y_no_un_cero() -> None:
    """«Fulano — 0 jonrones de por vida» es peor que no decir nada.

    Pasa de verdad: hay peloteros en el maestro que debutaron y no acumularon nada, y peloteros de
    `dom_players` que aún no llegaron a las mayores.
    """
    from dglweb.profiles.views import texto_compartir

    assert texto_compartir(_Jugador("Recién Llegado"), _Carrera(), _Carrera()) == "Recién Llegado"  # type: ignore[arg-type]


def test_el_texto_del_perfil_no_arrastra_la_cola_de_seo() -> None:
    """`descripcion_social` termina en «Estadísticas completas de su carrera», que sirve para Google.

    En un mensaje de WhatsApp eso es relleno, y las dos frases se parecen lo suficiente como para que
    alguien reutilice la que no toca.
    """
    from dglweb.profiles.views import texto_compartir

    texto = texto_compartir(_Jugador("Juan Soto"), _Carrera(hr=245), None)  # type: ignore[arg-type]

    assert "Estadísticas completas" not in texto
    assert len(texto) < 80, f"demasiado largo para un mensaje: {texto!r}"
