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

# El sitio público. Todo del propio origen salvo los estilos inline — ver la cabecera.
PUBLICA = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
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
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        respuesta = self.get_response(request)
        # No se pisa una cabecera ya puesta: si alguna vista necesita la suya, manda ella.
        if "Content-Security-Policy" not in respuesta:
            es_admin = request.path.startswith(RUTAS_DE_ADMINISTRACION)
            respuesta["Content-Security-Policy"] = ADMINISTRACION if es_admin else PUBLICA
        return respuesta
