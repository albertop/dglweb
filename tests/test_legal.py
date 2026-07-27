"""Las tres páginas legales, y sobre todo: que lo que dicen siga siendo verdad.

La parte fácil es comprobar que responden 200. Lo que de verdad importa acá es lo otro: un aviso
legal es una AFIRMACIÓN SOBRE EL CÓDIGO, y el código cambia. La política de cookies de este sitio
dice, con todas sus letras, que quien solo navega no recibe ninguna cookie. El día que alguien
enchufe una etiqueta de analítica o de anuncios, esa frase pasa a ser mentira — y la mentira no la
va a notar nadie mirando la pantalla, porque una cookie no se ve.

Por eso `test_el_sitio_publico_no_pone_cookies` no es una prueba de cortesía: es la que convierte el
texto en una promesa que el repositorio puede sostener. Si se cae, la respuesta correcta NO es
relajarla: es actualizar `templates/legal/cookies.html` y montar el consentimiento.
"""

import pytest
from bs4 import BeautifulSoup
from django.test import Client
from django.urls import reverse
from django.utils.html import escape

from dglweb.core import legal

# Las páginas que ve cualquiera sin identificarse. Es la lista que importa: el CMS sí pone cookies
# —sesión y CSRF— y eso está declarado en el documento como la excepción del equipo editorial.
PUBLICAS = ("/", "/jugadores/", "/lideres/", "/legal/privacidad/")


@pytest.mark.django_db
@pytest.mark.parametrize("documento", list(legal.PAGINAS))
def test_cada_documento_responde(client: Client, documento: str) -> None:
    respuesta = client.get(reverse("legal", args=[documento]))
    assert respuesta.status_code == 200
    assert legal.PAGINAS[documento] in respuesta.content.decode()


@pytest.mark.django_db
def test_un_documento_inventado_da_404(client: Client) -> None:
    """La vista sirve plantillas por nombre; sin la lista blanca, la ruta sería una invitación a
    pedir `legal/../../etc/passwd` y a ver qué contesta el cargador de plantillas."""
    assert client.get("/legal/no-existe/").status_code == 404


@pytest.mark.django_db
def test_el_pie_enlaza_los_tres(client: Client) -> None:
    """El pie sale del mismo diccionario que la vista, así que no puede quedarse corto. Esta prueba
    protege esa unión: si alguien vuelve a escribir los enlaces a mano en `base.html`, se cae."""
    html = client.get("/").content.decode()
    for documento, nombre in legal.PAGINAS.items():
        assert reverse("legal", args=[documento]) in html
        assert nombre in html


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", PUBLICAS)
def test_el_sitio_publico_no_pone_cookies(client: Client, ruta: str) -> None:
    """Lo que sostiene la política de cookies. Ver la cabecera del módulo antes de tocarla."""
    respuesta = client.get(ruta)
    assert respuesta.status_code in (200, 301, 302), ruta
    assert not respuesta.cookies, f"{ruta} devolvió cookies: {list(respuesta.cookies)}"


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", PUBLICAS)
def test_el_sitio_publico_no_pide_nada_a_terceros(client: Client, ruta: str) -> None:
    """La otra afirmación del documento: que la visita no se le anuncia a nadie más.

    Lo que se prohíbe es CARGAR de un tercero —un `<script>` de analítica, una fuente de Google, una
    etiqueta de anuncios—, no ENLAZAR a uno. La diferencia es exactamente la que importa acá: un
    `<a href>` a Retrosheet no le cuenta nada a Retrosheet hasta que alguien lo pulsa, mientras que
    un `<script src>` dispara la petición sola, con la IP del visitante, en cada visita.

    Por eso mira `src` de cualquier etiqueta y `href` SOLO de `<link>` —que es una carga— y deja en
    paz los `href` de los enlaces. Así no hay lista blanca que actualizar cada vez que el sitio
    enlace a algún sitio nuevo.
    """
    sopa = BeautifulSoup(client.get(ruta).content.decode(), "html.parser")
    cargas = [etiqueta.get("src") for etiqueta in sopa.find_all(src=True)]
    cargas += [etiqueta.get("href") for etiqueta in sopa.find_all("link", href=True)]
    for url in cargas:
        assert not str(url).startswith(("http://", "https://")), f"{ruta} carga {url}"


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", PUBLICAS)
def test_el_aviso_de_retrosheet_sale_en_todas_las_paginas(client: Client, ruta: str) -> None:
    """La única condición que pone Retrosheet a cambio de sus datos.

    Su licencia pide que la declaración aparezca «prominently», y de ahí que vaya en el pie y no
    escondida en los términos. Esta prueba es la que impide que se caiga sin que nadie lo note: un
    pie es justo el sitio del que se borran cosas al rediseñar.
    """
    # `escape()` y no la cadena cruda: el aviso lleva comillas alrededor de «www.retrosheet.org» y
    # Django las escribe como `&quot;`. En pantalla se leen igual; en el HTML no coinciden.
    assert escape(legal.RETROSHEET) in client.get(ruta).content.decode(), ruta


def test_el_aviso_de_retrosheet_esta_palabra_por_palabra() -> None:
    """Lo que la licencia autoriza es ESE texto, no un resumen ni una traducción.

    Se comprueban las piezas que no se pueden perder al «mejorar la redacción»: que fue gratis, que
    los derechos son de ellos y la vía de contacto. Reescribirlo es publicar sin permiso.
    """
    assert legal.RETROSHEET == (
        "The information used here was obtained free of charge from and is copyrighted by "
        'Retrosheet. Interested parties may contact Retrosheet at "www.retrosheet.org".'
    )


def test_la_fecha_de_actualizacion_no_se_mueve_sola() -> None:
    """`ACTUALIZADO` tiene que ser una constante escrita a mano.

    Si alguien la cambia por `date.today()`, la página diría que el aviso se revisó hoy aunque lleve
    un año igual — que es exactamente la mentira que la fecha existe para evitar.
    """
    import ast
    import inspect

    # Se mira el ÁRBOL y no el texto del módulo: la primera versión de esta prueba buscaba la cadena
    # «date.today()» y se caía con el propio comentario que explica por qué no se usa.
    arbol = ast.parse(inspect.getsource(legal))
    asignaciones = [
        nodo.value
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Assign)
        and any(getattr(destino, "id", "") == "ACTUALIZADO" for destino in nodo.targets)
    ]
    assert len(asignaciones) == 1
    valor = asignaciones[0]
    assert isinstance(valor, ast.Call), "ACTUALIZADO tiene que ser un date(a, m, d) literal"
    assert all(isinstance(arg, ast.Constant) for arg in valor.args), "la fecha se escribe a mano"


def test_los_datos_del_responsable_estan_puestos() -> None:
    """Un aviso de privacidad sin responsable identificado ni vía de contacto no cumple nada.

    No valida que sean CORRECTOS —eso solo lo sabe el dueño, y por eso están marcados con
    `# ← confirmar` en el módulo— pero sí que no queden vacíos ni con un texto de relleno.
    """
    assert legal.RESPONSABLE and "@" in legal.CONTACTO
    for valor in (legal.RESPONSABLE, legal.CONTACTO, legal.ALOJAMIENTO):
        assert "TODO" not in valor and "XXX" not in valor
