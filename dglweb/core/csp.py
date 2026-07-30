"""La `Content-Security-Policy`: la segunda línea de defensa contra XSS.

QUÉ RESUELVE
------------
La primera línea ya está: `articles/templatetags/articles_extras.py` limpia los `href="javascript:"`
del texto enriquecido, porque el reescritor de enlaces de Wagtail solo entiende `http`, `https`,
`mailto` y `#` y deja pasar intactos los esquemas que no conoce. Esto es lo otro: si algún día se
cuela un `<script>` que no vimos venir —en el cuerpo de un artículo, en un pie de foto, en cualquier
sitio— el navegador se niega a ejecutarlo. Cubre la vulnerabilidad que no sabemos que tenemos.

POR QUÉ AHORA SALIÓ BARATO
---------------------------
Una CSS estricta se pelea con los CDN, y este sitio dejó de tenerlos: Bootstrap y las fuentes se
sirven desde `static/vendor/`. Con todo bajo el mismo origen, `'self'` alcanza para casi todo.

POR QUÉ NO ES UNA DEPENDENCIA
-----------------------------
`django-csp` hace esto y bastante más —nonces, informes, políticas por vista—. Nada de eso hace falta
acá: la política es fija y son dos cabeceras. Un middleware de treinta líneas que se lee entero en un
minuto vale más que una dependencia cuya configuración hay que ir a buscar a otra documentación.

LO QUE SÍ SE PERMITE, Y POR QUÉ
--------------------------------
- `style-src` lleva `'unsafe-inline'`. Los `style="..."` sueltos de las plantillas son una veintena y
  quitarlos es mucho ruido para poco: un estilo inyectado puede afear la página, no ejecutar código.
  `script-src` es donde está el peligro de verdad, y ese va estricto.
- `img-src` lleva `data:` por los SVG y los favicons incrustados.
- `frame-src` lleva **el servidor de anuncios y nada más**. Estuvo en `'none'` hasta que entró la
  publicidad; sigue siendo una lista de una.

EL CMS VA APARTE
----------------
El admin de Wagtail usa scripts y estilos inline por todos lados, y no es código nuestro: apretarlo
sería romperlo en cada actualización de Wagtail. Recibe una política más floja, que sigue siendo
mejor que ninguna. Nadie llega al CMS sin credenciales, así que la superficie es distinta.

LA PUBLICIDAD ENTRÓ POR LA PUERTA ESTRECHA (2026-07-28)
-------------------------------------------------------
La etiqueta que sugiere Revive es JavaScript **en línea** con `document.write`, y usarla habría
costado dos cosas caras: `'unsafe-inline'` en `script-src` —que tira abajo esta protección entera— y
permiso de ejecución para un PHP público en TODAS las páginas del sitio.

Se usa el `iframe` en su lugar. El anuncio vive en su propio documento, **el servidor de anuncios no
puede tocar el nuestro**, y la política solo tuvo que abrir `frame-src`. `script-src` sigue en
`'self'` a secas. Ver `core/templatetags/anuncios.py`.

Que haya que tocar este archivo a mano para dejar entrar a alguien es la garantía, no el estorbo.
"""

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

# LOS VIDEOS DE MLB. Es la única excepción del sitio público, y hay que declararla o el televisorcito
# de la portada abre una ventana negra: el navegador dice «Media load rejected by URL safety check» y
# ni siquiera deja un error en la consola que se entienda.
#
# Medido sobre los 42 clips guardados: los `.mp4` salen de DOS hosts —`mlb-cuts-diamond.mlb.com` y
# `bdata-producedclips.mlb.com`— y las miniaturas de `img.mlbstatic.com`. Van con comodín de
# subdominio justamente por eso: si con 42 clips ya hay dos hosts distintos para lo mismo, listarlos a
# mano garantiza que el día que MLB estrene un tercero el video deje de verse sin avisar.
#
# El comodín es barato acá: `media-src` e `img-src` no pueden ejecutar código. Lo que de verdad
# importa —`script-src`— sigue en `'self'` a secas.
VIDEO_MLB = "https://*.mlb.com"
IMAGEN_MLB = "https://*.mlbstatic.com"


def publica(analitica: str = "", anuncios: str = "", envio: str = "") -> str:
    """El sitio público. Todo del propio origen salvo los estilos inline, los videos y los anuncios.

    LA ANALÍTICA NECESITA DOS DIRECTIVAS, Y PUEDEN SER DOS ORIGENES DISTINTOS
    -------------------------------------------------------------------------
    `analitica` es de dónde se BAJA el script y va en `script-src`. `envio` es adónde ese script MANDA
    los eventos y va en `connect-src`. Con solo la primera, el script carga, no protesta y no cuenta
    ni una visita: el navegador bloquea el envío y solo queda constancia en la consola de quien mire.

    ESTO ESTUVO ROTO EN PRODUCCIÓN Y ASÍ SE ENCONTRÓ (2026-07-30). Acá se pasaba el MISMO origen a las
    dos, dando por hecho que el script envía a donde vive. Umami Cloud no hace eso: el script sale de
    `cloud.umami.is` y los eventos van a `gateway.umami.is`. Cuando cambiaron el segundo, la política
    dejó de cubrirlo y el sitio dejó de contar visitas sin que nada fallara. El mensaje era este:

        Connecting to 'https://gateway.umami.is/api/send' violates the following Content Security
        Policy directive: "connect-src 'self' https://cloud.umami.is"

    Se vio en la factura de eventos: 2 en todo el mes, los dos anteriores al cambio.

    Que sean dos parámetros y no uno derivado del otro es la lección: **de dónde viene el código y
    adónde van los datos son dos preguntas distintas**, y ningún proveedor está obligado a responder
    lo mismo a las dos.

    POR QUÉ EL COMODÍN VA EN `connect-src` Y NO EN `script-src`
    ------------------------------------------------------------
    `envio` llega como `https://*.umami.is` (ver `settings.ANALITICA_ENVIO_URL`), para que el próximo
    cambio de host del proveedor no vuelva a apagar la analítica en silencio. Es el mismo razonamiento
    que ya se aplicó a `VIDEO_MLB` acá arriba, y el que acaba de costar un mes de datos.

    Pero el comodín NO sube a `script-src`, y la diferencia es la que importa:

        script-src    decide QUÉ CÓDIGO puede ejecutarse dentro de nuestras páginas
        connect-src   decide ADÓNDE puede mandar datos el código que ya se está ejecutando

    Un comodín en el primero deja entrar código de cualquier subdominio del proveedor. En el segundo
    solo amplía el destino de un script que ya está autorizado a correr — y ese script, si algún día
    fuera malicioso, ya podría mandar a `gateway.umami.is` de todas formas. El comodín no le concede
    nada que no tuviera; le ahorra al sitio dejar de medir cada vez que el proveedor mueve un host.

    Es una función y no una constante porque los orígenes salen de `settings`, y en las pruebas hace
    falta poder pedir la política con y sin analítica sin levantar el proceso de nuevo.
    """
    extra = f" {analitica}" if analitica else ""
    # `envio` cae de vuelta en `analitica` para el caso de una instancia propia, donde el script y la
    # recolección sí comparten host. Así una Umami autoalojada no necesita configurar nada extra.
    destino = envio or analitica
    extra_envio = f" {destino}" if destino else ""
    # LOS ANUNCIOS ENTRAN POR `frame-src` Y NO POR `script-src`, y esa es la decisión de seguridad
    # más importante de todo el montaje del servidor de anuncios.
    #
    # La etiqueta clásica de Revive es JavaScript en línea, y hacerla funcionar habría exigido dos
    # cosas: `'unsafe-inline'` en `script-src` —que tira abajo la protección entera— y permiso de
    # ejecución para un PHP público en TODAS nuestras páginas. Con el `iframe`, el anuncio vive en su
    # propio documento y **el servidor de anuncios no puede tocar el nuestro**.
    #
    # `frame-src` estaba en `'none'` justamente porque el sitio no incrustaba nada. Ahora incrusta una
    # cosa, y sigue siendo una lista de una. Ver `core/templatetags/anuncios.py`.
    marcos = anuncios or "'none'"
    return (
        "default-src 'self'; "
        f"script-src 'self'{extra}; "
        "style-src 'self' 'unsafe-inline'; "
        f"img-src 'self' data: {IMAGEN_MLB}; "
        f"media-src 'self' {VIDEO_MLB}; "
        "font-src 'self'; "
        f"connect-src 'self'{extra_envio}; "
        f"frame-src {marcos}; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'"
    )


# El CMS y el admin de Django. Wagtail necesita inline en scripts y estilos, y `blob:` para las
# previsualizaciones de imagen del cargador. Lo que SÍ se conserva es lo que corta los ataques
# clásicos: nada de plugins, nada de `<base>` ajeno, y los formularios solo pueden enviar acá.
ADMINISTRACION = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'self'"
)

# Las rutas que reciben la política floja. Se comparan por prefijo contra el camino de la petición.
RUTAS_DE_ADMINISTRACION = ("/cms/", "/django-admin/", "/documents/")


class ContentSecurityPolicyMiddleware:
    """Pone la cabecera en cada respuesta. Elige la política por la ruta, no por el usuario.

    Por la RUTA a propósito: un `request.user.is_staff` haría que la misma URL respondiera con dos
    políticas distintas según quién la pida, y eso convierte cualquier fallo en algo que solo le pasa
    a una persona y no se reproduce.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        from django.conf import settings

        self.get_response = get_response
        # Se arma UNA vez, al arrancar el proceso, y no en cada respuesta: el origen de la analítica
        # sale de la configuración y la configuración no cambia mientras el proceso vive. Rearmar la
        # cadena en cada petición sería trabajo por nada en la ruta más caliente del sitio.
        hay_analitica = bool(settings.ANALITICA_ID)
        self.publica = publica(
            settings.ANALITICA_URL if hay_analitica else "",
            settings.ADSERVER_URL,
            settings.ANALITICA_ENVIO_URL if hay_analitica else "",
        )

    def __call__(self, request: HttpRequest) -> HttpResponse:
        respuesta = self.get_response(request)
        # No se pisa una cabecera ya puesta: si alguna vista necesita la suya, manda ella.
        if "Content-Security-Policy" not in respuesta:
            es_admin = request.path.startswith(RUTAS_DE_ADMINISTRACION)
            respuesta["Content-Security-Policy"] = ADMINISTRACION if es_admin else self.publica
        return respuesta
