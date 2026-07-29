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

import re
from typing import Any

import pytest
from bs4 import BeautifulSoup
from django.conf import settings
from django.test import Client
from django.urls import reverse
from django.utils.html import escape

from dglweb.core import csp, legal

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

    EL ÚNICO TERCERO PERMITIDO ES EL DECLARADO, y esa es la forma de la excepción que importa. Desde
    el 2026-07-28 el sitio carga la analítica de visitas, así que esta prueba ya no puede exigir cero
    cargas externas. Lo que NO se hizo fue relajarla a «externas las que sean»: se comprueba contra
    `settings.ANALITICA_URL`, o sea contra el mismo ajuste que dibuja el script y que alimenta la CSP.
    El día que entre un segundo tercero —un ad server, una fuente, un chat— esto se cae y obliga a
    pasar por las páginas legales, que es exactamente para lo que existe.

    LO QUE ESTA PRUEBA NO VE, Y CONVIENE SABERLO
    --------------------------------------------
    Solo mira el HTML servido. El video de MLB no aparece acá por dos motivos a la vez: su URL viaja
    en un `data-video`, no en un `src`, y el JS se la pone al `<video>` recién al pulsar el
    televisorcito. O sea que un tercero cargado POR JAVASCRIPT es invisible para esta prueba.

    Eso no es un descuido: es el reparto de trabajo. Lo que gobierna esas cargas es la CSP, y quien
    las vigila es `test_la_csp_permite_los_videos_de_mlb`. Esta prueba cubre lo que se carga solo al
    abrir la página; aquella, lo que puede cargarse después.
    """
    sopa = BeautifulSoup(client.get(ruta).content.decode(), "html.parser")
    cargas = [etiqueta.get("src") for etiqueta in sopa.find_all(src=True)]
    # `rel="canonical"` queda FUERA, y no es una excepción de conveniencia: una canónica no se carga
    # nunca. Es una declaración para los buscadores —«esta página vive en esta dirección»— y el
    # navegador no la pide jamás. Va absoluta porque Google la exige así (desde el SEO del
    # 2026-07-28), y meterla en esta lista confundiría una etiqueta que no dispara ninguna petición
    # con las que sí.
    cargas += [
        etiqueta.get("href")
        for etiqueta in sopa.find_all("link", href=True)
        if "canonical" not in (etiqueta.get("rel") or [])
    ]
    permitido = settings.ANALITICA_URL
    for url in cargas:
        externa = str(url).startswith(("http://", "https://"))
        if externa and permitido and str(url).startswith(permitido):
            continue
        assert not externa, f"{ruta} carga {url}, que no es el tercero declarado ({permitido or 'ninguno'})"


@pytest.mark.django_db
def test_la_pagina_de_contacto_publica_el_buzon(client: Client) -> None:
    """Una página de contacto sin dirección visible es una página de contacto rota.

    El correo sale de `legal.CONTACTO`, el mismo que citan los tres documentos: una dirección que
    cambia en un sitio y se queda vieja en otros tres es exactamente el fallo que esa constante
    existe para evitar.
    """
    html = client.get(reverse("contacto")).content.decode()
    assert f"mailto:{legal.CONTACTO}" in html
    assert reverse("contacto") in client.get("/").content.decode()


@pytest.mark.django_db
def test_el_aviso_de_retrosheet_sigue_publicado(client: Client) -> None:
    """La única condición que pone Retrosheet a cambio de sus datos: que la declaración se publique.

    Estuvo en el pie de todas las páginas y hoy vive solo en los términos —decisión del dueño, ver
    `core/legal.py`—, así que esta prueba se mudó con ella. Lo que protege es lo mismo: que no
    desaparezca sin que nadie lo note, porque publicar sin ese aviso es publicar sin permiso.
    """
    html = client.get(reverse("legal", args=["terminos"])).content.decode()
    # `escape()` y no la cadena cruda: el aviso lleva comillas alrededor de «www.retrosheet.org» y
    # Django las escribe como `&quot;`. En pantalla se leen igual; en el HTML no coinciden.
    assert escape(legal.RETROSHEET) in html


def test_el_aviso_de_retrosheet_esta_palabra_por_palabra() -> None:
    """Lo que la licencia autoriza es ESE texto, no un resumen ni una traducción.

    Se comprueban las piezas que no se pueden perder al «mejorar la redacción»: que fue gratis, que
    los derechos son de ellos y la vía de contacto. Reescribirlo es publicar sin permiso.
    """
    assert legal.RETROSHEET == (
        "The information used here was obtained free of charge from and is copyrighted by "
        'Retrosheet. Interested parties may contact Retrosheet at "www.retrosheet.org".'
    )


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", PUBLICAS)
def test_el_sitio_publico_no_lleva_javascript_en_el_html(client: Client, ruta: str) -> None:
    """Lo que hace que la CSP estricta se cumpla en vez de romper la página.

    Con `script-src 'self'` el navegador NO ejecuta un `<script>` sin `src` ni un `onclick="..."`.
    El sitio tenía doce de esos, y todos se mudaron a archivos bajo `static/js/`. Esta prueba es lo
    que impide que vuelva a colarse uno: escribir `onclick=` es más rápido que abrir el `.js`, y el
    fallo no se ve al mirar la página —solo deja de funcionar el botón, en silencio.
    """
    sopa = BeautifulSoup(client.get(ruta).content.decode(), "html.parser")
    inline = [e for e in sopa.find_all("script") if not e.get("src")]
    assert not inline, f"{ruta} lleva un <script> sin src"
    for etiqueta in sopa.find_all(True):
        manejadores = [a for a in etiqueta.attrs if a.startswith("on")]
        assert not manejadores, f"{ruta} lleva {manejadores} en <{etiqueta.name}>"


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", PUBLICAS)
def test_la_csp_va_en_las_paginas_publicas(client: Client, ruta: str) -> None:
    politica = client.get(ruta).headers.get("Content-Security-Policy", "")
    assert "script-src 'self';" in politica, "el sitio público no admite scripts inline"
    assert "object-src 'none'" in politica


@pytest.mark.django_db
def test_la_csp_permite_los_videos_de_mlb(client: Client) -> None:
    """La CSP rompió el televisorcito de la portada y nadie se enteró hasta que lo pulsó una persona.

    Con `media-src` cayendo en `default-src 'self'`, el navegador rechazaba el `.mp4` de MLB con un
    «Media load rejected by URL safety check» que no deja rastro útil: la ventana se abre negra y no
    hay error en la consola que lleve a la causa.

    No lo cazó ninguna prueba porque el video se carga por JavaScript desde un `data-video` —ver
    `test_el_sitio_publico_no_pide_nada_a_terceros`—, así que la protección tiene que estar acá: en
    la propia política, que es lo que decide si esa carga se permite.
    """
    politica = client.get("/").headers["Content-Security-Policy"]
    assert f"media-src 'self' {csp.VIDEO_MLB}" in politica, "los clips no se van a poder reproducir"
    assert csp.IMAGEN_MLB in politica, "la miniatura del clip quedaría en negro"


@pytest.mark.django_db
def test_el_cms_recibe_la_politica_floja(client: Client) -> None:
    """El admin de Wagtail usa inline por todos lados y no es código nuestro; apretarlo sería
    romperlo en cada actualización. Lo que se comprueba es que igual RECIBE una política."""
    politica = client.get("/cms/").headers.get("Content-Security-Policy", "")
    assert "'unsafe-inline'" in politica and "object-src 'none'" in politica


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
        if isinstance(nodo, ast.Assign) and any(getattr(destino, "id", "") == "ACTUALIZADO" for destino in nodo.targets)
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


# ── La analítica de visitas (Umami, 2026-07-28) ─────────────────────────────────────────────────
#
# Se eligió sin cookies a propósito, así que `test_el_sitio_publico_no_pone_cookies` sigue verde y la
# política de cookies sigue siendo verdad. Lo que sí cambia es la de privacidad: la visita ahora se
# le anuncia a alguien, y estas pruebas atan el script, la CSP y el documento que lo declara.

ANALITICA = {"ANALITICA_URL": "https://cloud.umami.is", "ANALITICA_ID": "el-identificador"}


@pytest.mark.django_db
def test_sin_configurar_no_se_carga_ninguna_analitica(client: Client, settings: Any) -> None:
    """El default APAGA, y ese es el que corre en desarrollo.

    Es lo que evita que las visitas de dev ensucien las estadísticas del sitio real, y también el
    default correcto en lo legal: medir a escondidas porque nadie configuró nada sería el fallo caro.
    """
    settings.ANALITICA_URL = ""
    settings.ANALITICA_ID = ""

    assert "script.js" not in client.get("/").content.decode()


@pytest.mark.django_db
def test_con_las_dos_puestas_el_script_sale_en_todas_las_paginas(client: Client, settings: Any) -> None:
    """En `base.html` y no en la portada: si estuviera por vista, faltaría en la que nadie recordó."""
    for clave, valor in ANALITICA.items():
        setattr(settings, clave, valor)

    for ruta in PUBLICAS:
        html = client.get(ruta).content.decode()
        assert 'src="https://cloud.umami.is/script.js"' in html, ruta
        assert 'data-website-id="el-identificador"' in html, ruta


@pytest.mark.django_db
def test_a_medias_no_se_dibuja_nada(client: Client, settings: Any) -> None:
    """Con el origen puesto y el identificador vacío, Umami carga y no cuenta nada.

    Es un fallo silencioso —el script responde 200, la consola queda limpia y el panel vacío— así que
    la decisión es de todo o nada, y vive en el procesador de contexto para que la plantilla no pueda
    equivocarse.
    """
    settings.ANALITICA_URL = "https://cloud.umami.is"
    settings.ANALITICA_ID = ""

    assert "script.js" not in client.get("/").content.decode()


def test_la_csp_deja_pasar_la_analitica_en_las_dos_directivas() -> None:
    """`script-src` para poder cargarlo y `connect-src` porque después hace un POST a `/api/send`.

    Con solo la primera el script carga, no protesta y no cuenta ni una visita: el navegador bloquea
    el envío en silencio. Es el fallo más caro de diagnosticar de los dos, y por eso se prueban las
    dos y no «que el dominio aparezca en algún sitio de la política».
    """
    politica = csp.publica("https://cloud.umami.is")

    assert "script-src 'self' https://cloud.umami.is;" in politica
    assert "connect-src 'self' https://cloud.umami.is;" in politica


def test_sin_analitica_la_csp_se_queda_estricta() -> None:
    """La política de siempre tiene que sobrevivir intacta cuando no hay nada configurado."""
    politica = csp.publica()

    assert "script-src 'self';" in politica
    assert "connect-src 'self';" in politica
    assert "umami" not in politica


@pytest.mark.django_db
def test_la_privacidad_nombra_a_quien_procesa_las_visitas(client: Client, settings: Any) -> None:
    """Lo que la ley pide y lo que el código no puede inventar: el nombre de quien trata los datos.

    Va contra las constantes de `core/legal.py` y no contra un texto escrito a mano en la plantilla,
    porque el día que se cambie de herramienta hay que cambiar el documento en el mismo commit.
    """
    for clave, valor in ANALITICA.items():
        setattr(settings, clave, valor)

    html = client.get(reverse("legal", args=["privacidad"])).content.decode()

    assert legal.ANALITICA in html
    assert legal.ANALITICA_EMPRESA in html
    # Una frase que no se parte en la plantilla: la primera versión buscaba «no rastrear» y fallaba
    # por el salto de línea del HTML, no por faltar el texto.
    assert "bloqueador de rastreadores" in html, "hay que decirle a la gente cómo quedarse fuera"


@pytest.mark.django_db
def test_la_pagina_de_cookies_sigue_diciendo_que_no_hay_ninguna(client: Client, settings: Any) -> None:
    """La afirmación que sobrevivió a la analítica, y la razón de haber elegido esa herramienta.

    Se comprueba CON la analítica encendida a propósito: con ella apagada esto pasaría solo y no
    estaría probando lo que dice probar.
    """
    for clave, valor in ANALITICA.items():
        setattr(settings, clave, valor)

    respuesta = client.get(reverse("legal", args=["cookies"]))

    assert "no recibes ninguna cookie" in respuesta.content.decode()
    assert not respuesta.cookies


@pytest.mark.django_db
@pytest.mark.parametrize("ruta", PUBLICAS)
def test_con_la_analitica_encendida_sigue_sin_haber_cookies(client: Client, settings: Any, ruta: str) -> None:
    """Comprobado además leyendo `script.js` el 2026-07-28: cero `document.cookie`, cero `setItem`.

    Esta prueba solo puede vigilar NUESTRO lado —que el servidor no mande ninguna—, así que la otra
    mitad queda escrita en `core/legal.py`. Si Umami empezara a poner cookies un día, esto no se
    entera: lo que avisaría es la revisión del script, que hay que rehacer si se cambia de proveedor.
    """
    for clave, valor in ANALITICA.items():
        setattr(settings, clave, valor)

    assert not client.get(ruta).cookies


# ── El servidor de anuncios (Revive autoalojado, 2026-07-28) ────────────────────────────────────

ANUNCIOS = "https://promo.dominicanosengrandesligas.com"


def test_los_anuncios_entran_por_frame_src_y_no_por_script_src() -> None:
    """La decisión de seguridad más importante del montaje del servidor de anuncios.

    La etiqueta que sugiere Revive es JavaScript en línea, y usarla habría exigido `'unsafe-inline'`
    en `script-src` —que anula la protección entera— más permiso de ejecución para un PHP público en
    todas las páginas. Con el `iframe`, el anuncio vive en su propio documento.

    Esta prueba es lo que impide que alguien «arregle» un anuncio que no carga abriendo `script-src`,
    que es exactamente lo que uno hace cuando no sabe por qué falla.
    """
    politica = csp.publica(anuncios=ANUNCIOS)

    assert f"frame-src {ANUNCIOS};" in politica
    assert "script-src 'self';" in politica, "el servidor de anuncios NO ejecuta código en el sitio"


def test_sin_anuncios_frame_src_vuelve_a_none() -> None:
    """El sitio no incrusta nada más, así que sin publicidad la puerta queda cerrada del todo."""
    assert "frame-src 'none';" in csp.publica()


@pytest.mark.django_db
def test_sin_configurar_los_huecos_siguen_siendo_maqueta(client: Client, settings: Any) -> None:
    """El default apagado, que es el que corre en desarrollo.

    Nadie quiere contar impresiones de sí mismo recargando la portada. Y el recuadro rayado mide lo
    MISMO que el anuncio, así que el diseño se prueba con las medidas reales.
    """
    settings.ADSERVER_URL = ""

    html = client.get("/").content.decode()

    assert "Espacio publicitario" in html
    assert "dgl-ad-marco" not in html


@pytest.mark.django_db
def test_configurado_dibuja_los_marcos_con_el_cb_delante(client: Client, settings: Any) -> None:
    """`.php?zoneid=` es una regla de EasyList POR SÍ SOLA.

    Medido el 2026-07-28: con `zoneid` de primer parámetro, cualquier navegador con un bloqueador
    corta la petición **aunque la ruta esté renombrada**. Y a los clientes se les factura por
    impresiones, así que cada una bloqueada es dinero que no se cobra.

    Poniendo el anti-caché `cb` delante la regla no encaja. No es un truco: `cb` es el parámetro que
    Revive usa en sus propias etiquetas.
    """
    settings.ADSERVER_URL = ANUNCIOS

    html = client.get("/").content.decode()

    assert f'src="{ANUNCIOS}/www/pauta/dgl-m.php?cb=' in html
    assert "?zoneid=" not in html, "zoneid nunca puede ser el primer parámetro"
    assert "Espacio publicitario" not in html


def test_cada_hueco_pide_la_zona_que_le_toca(settings: Any) -> None:
    """Si dos huecos apuntaran a la misma zona, Revive contaría dos impresiones de una y ninguna de
    la otra — y el informe que se le pasa al anunciante diría que su banner salió donde no salió.

    Se prueba la ETIQUETA y no el HTML de una página: la primera versión miraba la portada y exigía
    tres zonas, pero el hueco lateral vive dentro del bloque del artículo destacado y en una base sin
    artículos no se dibuja. La prueba dependía de datos sin decirlo, que es como se consiguen fallos
    que solo aparecen en algunas ejecuciones.
    """
    from dglweb.core.templatetags.anuncios import anuncio

    settings.ADSERVER_URL = ANUNCIOS

    assert "zoneid=12" in anuncio(12, 300, 600)["url"]
    assert anuncio(1, 970, 90)["url"] != anuncio(4, 970, 90)["url"]


@pytest.mark.django_db
def test_dos_huecos_de_la_misma_pagina_no_repiten_zona(client: Client, settings: Any) -> None:
    """La cabecera y el pie de la portada son zonas distintas: la de arriba se ve sin bajar y vale
    más, así que se venden por separado.

    LOS NÚMEROS CAMBIARON EL 2026-07-29 y esta prueba fue la que lo cantó. Antes toda la web
    compartía las zonas 1 y 2, así que un anuncio vendido para la portada se entregaba también en
    artículos, en jugadores y en el perfil. Ahora cada página tiene su decena:

        1-4    portada        11-13  líderes       21-22  jugadores
        31-32  índice art.    41-42  artículo      51-52  perfil

    Acá se comprueban la 1 (arriba) y la 4 (abajo), que son las dos que existen en una base de
    pruebas vacía: las otras dos de la portada viven dentro del bloque de artículos y no se dibujan
    sin contenido publicado.
    """
    settings.ADSERVER_URL = ANUNCIOS

    zonas = re.findall(r"zoneid=(\d+)", client.get("/").content.decode())

    assert zonas == sorted(set(zonas)), f"hay una zona repetida en la portada: {zonas}"
    assert {"1", "4"} <= set(zonas), f"faltan la cabecera o el pie: {zonas}"


@pytest.mark.django_db
def test_el_marco_no_se_puede_confundir_con_contenido(client: Client, settings: Any) -> None:
    """`title="Publicidad"` es lo que oye quien navega con lector de pantalla.

    Un marco sin título se anuncia como «marco», y quien no ve la página no tiene forma de saber que
    puede saltárselo.
    """
    settings.ADSERVER_URL = ANUNCIOS

    assert 'title="Publicidad"' in client.get("/").content.decode()
