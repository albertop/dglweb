"""El hueco de publicidad de las plantillas. Ver `docs/ADSERVER.md` para el montaje completo.

POR QUÉ UNA ETIQUETA Y NO EL CÓDIGO PEGADO EN CADA PLANTILLA
------------------------------------------------------------
Son TRECE huecos repartidos por seis plantillas. Pegar la etiqueta del servidor en cada uno significa
que cambiar de proveedor —o corregir un parámetro— es trece ediciones, y basta olvidar una para dejar
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

import secrets
from typing import Any

from django import template
from django.conf import settings

register = template.Library()


@register.inclusion_tag("widgets/_anuncio.html")
def anuncio(zona: int, ancho: int, alto: int, clase: str = "") -> dict[str, Any]:
    """Un hueco de publicidad. `zona` es el identificador que Revive le dio.

    Sin `ADSERVER_URL` configurado devuelve `url` vacío y la plantilla dibuja el recuadro de maqueta.
    Ese es el comportamiento correcto en desarrollo: nadie quiere contar impresiones de sí mismo
    recargando la portada, y un hueco en blanco parecería un fallo de maquetación.
    """
    origen = settings.ADSERVER_URL
    if not origen:
        return {"url": "", "ancho": ancho, "alto": alto, "clase": clase}

    # `token_hex` y no `random`: no hace falta que sea impredecible, pero el generador criptográfico
    # está en la biblioteca estándar y evita tener que explicar por qué un `random` sin sembrar es
    # suficiente. Cuesta microsegundos.
    return {
        "url": f"{origen}/www/pauta/dgl-m.php?cb={secrets.token_hex(6)}&zoneid={zona}",
        "ancho": ancho,
        "alto": alto,
        "clase": clase,
    }
