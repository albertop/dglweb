"""El hueco de publicidad de las plantillas. Ver `docs/ADSERVER.md` para el montaje completo.

POR QUÉ UNA ETIQUETA Y NO EL CÓDIGO PEGADO EN CADA PLANTILLA
------------------------------------------------------------
Son DIECISÉIS huecos repartidos por seis plantillas —medidos en `tests/test_anuncios_apagados.py`,
que los cuenta; el «trece» que decía acá se quedó viejo—. Pegar la etiqueta del servidor en cada uno significa
que cambiar de proveedor —o corregir un parámetro— son dieciséis ediciones, y basta olvidar una para dejar
un hueco muerto que nadie nota hasta que el anunciante pregunta por sus impresiones.

POR QUÉ UN `iframe` Y NO LA ETIQUETA DE JAVASCRIPT QUE SUGIERE REVIVE
----------------------------------------------------------------------
La etiqueta clásica de Revive es JavaScript **en línea** con `document.write`. Este sitio manda
`script-src 'self'` y tiene una prueba que prohíbe los scripts en línea
(`test_el_sitio_publico_no_lleva_javascript_en_el_html`), así que **el navegador la bloquearía
entera** — y hacerla funcionar exigiría abrirle a un PHP público permiso para ejecutar código en
todas nuestras páginas.

Con `iframe` no hace falta nada de eso:

- El anuncio se dibuja en **su propio documento**, aislado del sitio.
- La CSP solo necesita `frame-src`, no `script-src`. **El servidor de anuncios nunca ejecuta código
  en nuestras páginas.**
- No bloquea el dibujado, al revés que un `<script>` síncrono.

Lo que se pierde son los formatos que se despliegan fuera de su marco. Para banners de venta directa
—que es lo que vende Adcio— no se pierde nada.

EL `cb` VA PRIMERO, Y ESO ES DINERO
------------------------------------
`.php?zoneid=` es una regla de EasyList por sí sola: una URL donde `zoneid` sea el primer parámetro la
bloquea cualquier navegador con un bloqueador puesto, **aunque la ruta esté renombrada**. Poniendo el
anti-caché `cb` delante, la regla no encaja.

No es un truco: `cb` es el parámetro que Revive usa en sus propias etiquetas para que el navegador no
cachee el anuncio. Acá simplemente va en el orden que además esquiva la regla.
"""

import json
import secrets
from typing import Any

from django import template
from django.conf import settings

register = template.Library()


def _apagado() -> dict[str, Any]:
    """El contexto de un hueco que hoy no se enseña. Las dos plantillas de marco no dibujan nada.

    `visible: False` Y NO UN `{% if %}` EN CADA PÁGINA. Son dieciséis huecos en seis plantillas: apagarlos
    desde arriba obligaría a envolver los dieciséis, y el primero que alguien añadiera nacería encendido.
    Acá la puerta es una y la cruzan todos.

    Y SE APAGA DEVOLVIENDO NADA, no escondiendo con CSS. Un marco con `display:none` se sigue pidiendo
    al servidor y cuenta la impresión, así que las estadísticas del anunciante contarían anuncios que
    nadie vio. Lo que no se dibuja no se pide.

    Los tags SIGUEN EN LAS PLANTILLAS, que es lo que pidió el dueño: la integración no se toca, solo
    deja de enseñarse. `ANUNCIOS_VISIBLES=true` la devuelve entera sin tocar una línea de HTML.
    """
    return {"visible": False}


@register.inclusion_tag("widgets/_anuncio.html")
def anuncio(zona: int, ancho: int, alto: int, clase: str = "") -> dict[str, Any]:
    """Un hueco de publicidad. `zona` es el identificador que Revive le dio.

    Sin `ADSERVER_URL` configurado devuelve `url` vacío y la plantilla dibuja el recuadro de maqueta.
    Ese es el comportamiento correcto en desarrollo: nadie quiere contar impresiones de sí mismo
    recargando la portada, y un hueco en blanco parecería un fallo de maquetación.
    """
    if not settings.ANUNCIOS_VISIBLES:
        return _apagado()
    origen = settings.ADSERVER_URL
    if not origen:
        return {"visible": True, "url": "", "ancho": ancho, "alto": alto, "clase": clase}

    # `token_hex` y no `random`: no hace falta que sea impredecible, pero el generador criptográfico
    # está en la biblioteca estándar y evita tener que explicar por qué un `random` sin sembrar es
    # suficiente. Cuesta microsegundos.
    return {
        "visible": True,
        "url": f"{origen}/www/pauta/dgl-m.php?cb={secrets.token_hex(6)}&zoneid={zona}",
        "ancho": ancho,
        "alto": alto,
        "clase": clase,
    }


# Los tres tamaños de un hueco horizontal, con la pantalla mínima a la que cada uno cabe. Sale de
# medir el `.container` de Bootstrap en el sitio real, no del manual:
#
#     pantalla      contenedor    cabe 970    cabe 728
#     >= 1200          1140          sí          sí
#     992-1199          960          NO          sí
#     768-991           720          no          no (por 8 px)
#     < 768          fluido          no          no
#
# Por eso el corte del 970 está en 1200 y no en 994: entre 992 y 1199 el contenedor mide 960 y un
# banner de 970 se saldría. Con un solo par 970/320, TODO portátil de menos de 1200 px se llevaría el
# banner de teléfono — que es la franja de los portátiles de 13 pulgadas.
#
# El tercer valor de cada fila es esa pantalla mínima.
TAMANOS_HORIZONTALES = (
    (970, 90, 1200),
    (728, 90, 992),
    (320, 50, 0),
)


@register.inclusion_tag("widgets/_anuncio_horizontal.html")
def anuncio_horizontal(z970: int, z728: int, z320: int, clase: str = "") -> dict[str, Any]:
    """Un hueco horizontal que se adapta: UN marco, y el navegador elige de qué tamaño.

    UN SOLO `iframe`, Y ESO NO ES UNA OPTIMIZACIÓN — ES LO QUE HACE HONESTAS LAS CUENTAS
    -----------------------------------------------------------------------------------
    La primera versión de esto dibujaba los TRES marcos y ocultaba dos con `display: none`, dando por
    hecho que un marco oculto no carga. **Es falso, y se comprobó en el navegador**: los tres pidieron
    su anuncio, con `loading="lazy"` puesto y todo.

    Eso habría hecho que Revive contara **tres impresiones por cada anuncio realmente visto**. El
    informe de Adcio saldría inflado al triple, con dos tercios de impresiones de anuncios que nadie
    vio. En venta directa eso no es un defecto técnico: es facturar aire.

    Así que el marco sale **sin `src`** —un `iframe` sin `src` no pide nada— y `static/js/anuncios.js`
    le pone el de la zona que corresponde al ancho disponible. Un marco, una petición, una impresión.

    QUÉ PASA SIN JAVASCRIPT: el hueco se queda vacío. Se acepta a conciencia — son cuatro gatos, y la
    alternativa era contar impresiones falsas para todos los demás.

    POR QUÉ NO SE DECIDE EN EL SERVIDOR por el `User-Agent`: el HTML pasaría a depender del
    dispositivo y dejaría de poder cachearse en un CDN. La Fase 8 del plan contempla Cloudflare, y
    esto la cerraría.

    CADA TAMAÑO NECESITA SU PROPIA ZONA EN REVIVE, y no es burocracia: Revive cuenta por zona, así que
    si los tres compartieran una, el informe no podría decir cuántas veces salió en móvil y cuántas en
    escritorio. Son formatos distintos y se venden a precios distintos.
    """
    if not settings.ANUNCIOS_VISIBLES:
        return _apagado()
    origen = settings.ADSERVER_URL
    opciones: list[dict[str, Any]] = []
    for (ancho, alto, minimo), zona in zip(TAMANOS_HORIZONTALES, (z970, z728, z320), strict=True):
        opcion: dict[str, Any] = {"min": minimo, "ancho": ancho, "alto": alto}
        if origen:
            # El `cb` delante del `zoneid` no es cosmético: ver la cabecera del módulo. Cada tamaño
            # lleva el suyo porque son zonas distintas y el navegador no debe cachear ninguna.
            opcion["url"] = f"{origen}/www/pauta/dgl-m.php?cb={secrets.token_hex(6)}&zoneid={zona}"
        opciones.append(opcion)

    # `separators` sin espacios: este JSON viaja dentro de un atributo y se repite en dos huecos por
    # página. Los espacios serían bytes que no dicen nada.
    return {
        "visible": True,
        "opciones": json.dumps(opciones, separators=(",", ":")),
        "hay_servidor": bool(origen),
        "clase": clase,
    }


@register.inclusion_tag("widgets/_anuncio_horizontal.html")
def anuncio_rango(
    zona: int, ancho: int, alto: int, minimo: int = 0, maximo: int = 0, clase: str = ""
) -> dict[str, Any]:
    """Un hueco que SOLO existe en un rango de pantallas.

    Usa la misma maquinaria que `anuncio_horizontal` —un marco sin `src` que rellena `anuncios.js`—
    pero con una sola opción y un rango acotado.

    POR QUÉ NO SE RESUELVE CON `d-none` DE BOOTSTRAP, que sería lo obvio: **un `iframe` oculto con CSS
    SÍ CARGA su documento.** Se comprobó en el navegador. Esconder el carril de 300x600 en movil dejaría
    a Revive contando una impresión que nadie vio, y el banner de 320x50 que va entre los widgets
    contaría otra en escritorio. En venta directa eso es facturar aire.

    Declarando el rango, el script no le pone `src` fuera de él — y además quita el marco del DOM, así
    que tampoco deja una franja vacía reservada por el CSS.

    Las clases de Bootstrap sí siguen haciendo falta, pero para otra cosa: evitan el salto de
    maquetación entre que el HTML se dibuja y el script decide.

        maximo=991    solo por debajo de `lg`  (móvil y tablet en vertical)
        minimo=992    solo desde `lg`          (escritorio y tablet en horizontal)
    """
    if not settings.ANUNCIOS_VISIBLES:
        return _apagado()
    origen = settings.ADSERVER_URL
    opcion: dict[str, Any] = {"min": minimo, "ancho": ancho, "alto": alto}
    if maximo:
        opcion["max"] = maximo
    if origen:
        opcion["url"] = f"{origen}/www/pauta/dgl-m.php?cb={secrets.token_hex(6)}&zoneid={zona}"
    return {
        "visible": True,
        "opciones": json.dumps([opcion], separators=(",", ":")),
        "hay_servidor": bool(origen),
        "clase": clase,
    }
