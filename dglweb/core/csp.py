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
- `frame-src` es `'none'`: hoy el sitio no incrusta ningún vídeo ni mapa. Si algún día se incrusta uno,
  esta es la línea que hay que abrir — y que falle ruidosamente es lo correcto.

EL CMS VA APARTE
----------------
El admin de Wagtail usa scripts y estilos inline por todos lados, y no es código nuestro: apretarlo
sería romperlo en cada actualización de Wagtail. Recibe una política más floja, que sigue siendo
mejor que ninguna. Nadie llega al CMS sin credenciales, así que la superficie es distinta.

CUANDO ENTRE LA PUBLICIDAD
--------------------------
Las etiquetas de un ad server cargan scripts de terceros, y con esto puesto no van a funcionar hasta
que se añada su dominio acá. Eso NO es un estorbo: es la lista, en un solo archivo, de a quién se le
permite ejecutar código en el sitio. Que haya que tocarla a mano es la garantía.
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

def publica(analitica: str = "") -> str:
    """El sitio público. Todo del propio origen salvo los estilos inline y los videos.

    `analitica` es el origen del servidor de estadísticas, o cadena vacía si no hay ninguno
    configurado. Entra en DOS directivas y las dos hacen falta: `script-src` para poder cargar
    `script.js`, y `connect-src` porque lo que ese script hace después es un `POST` a `/api/send`. Con
    solo la primera, el script carga, no protesta y no cuenta ni una visita — el navegador bloquea el
    envío en silencio, que es el fallo más caro de diagnosticar de los dos.

    Es una función y no una constante porque el origen sale de `settings`, y en las pruebas hace falta
    poder pedir la política con y sin analítica sin levantar el proceso de nuevo.
    """
    extra = f" {analitica}" if analitica else ""
    return (
        "default-src 'self'; "
        f"script-src 'self'{extra}; "
        "style-src 'self' 'unsafe-inline'; "
        f"img-src 'self' data: {IMAGEN_MLB}; "
        f"media-src 'self' {VIDEO_MLB}; "
        "font-src 'self'; "
        f"connect-src 'self'{extra}; "
        "frame-src 'none'; "
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
        self.publica = publica(settings.ANALITICA_URL if settings.ANALITICA_ID else "")

    def __call__(self, request: HttpRequest) -> HttpResponse:
        respuesta = self.get_response(request)
        # No se pisa una cabecera ya puesta: si alguna vista necesita la suya, manda ella.
        if "Content-Security-Policy" not in respuesta:
            es_admin = request.path.startswith(RUTAS_DE_ADMINISTRACION)
            respuesta["Content-Security-Policy"] = ADMINISTRACION if es_admin else self.publica
        return respuesta
