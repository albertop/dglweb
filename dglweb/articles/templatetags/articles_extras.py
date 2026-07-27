"""Filtros de plantilla de los artículos.

Hoy solo uno, y existe por un fallo real: el texto enriquecido de Wagtail **no filtra el esquema de
los enlaces**. Un `<a href="javascript:alert(1)">` escrito en el cuerpo llegaba tal cual a la página.

Lo descubrió un test que se escribió para congelar el comportamiento seguro y resultó que no lo era
(SEC-03 del review v8). Wagtail lo deja pasar a propósito: su reescritor de enlaces solo reconoce
`http`, `https`, `mailto` y las anclas, y **lo que no reconoce lo deja intacto** —para no romper cosas
como `<a name="…">`—. Correcto de su parte; el filtro nos toca a nosotros.
"""

from django import template
from django.utils.safestring import SafeString, mark_safe

register = template.Library()

# Lo que puede llevar un `href` del cuerpo de un artículo. Todo lo demás se descarta.
#
# Es una lista blanca y no una negra a propósito: `javascript:` es el que todo el mundo recuerda, pero
# están también `data:`, `vbscript:` y los que inventen mañana. Con lista negra hay que acertar a
# todos; con lista blanca hay que acertar a los cinco que sí queremos.
ESQUEMAS = ("http", "https", "mailto", "tel")


def _es_seguro(href: str) -> bool:
    """Un enlace relativo o de esquema conocido. Ver la lista blanca de arriba."""
    limpio = href.strip().lower()
    if not limpio:
        return False
    # Relativo o ancla: no hay esquema que validar.
    if limpio.startswith(("/", "#", "?")):
        return True
    if ":" not in limpio.split("/")[0]:
        return True
    return limpio.split(":", 1)[0] in ESQUEMAS


@register.filter
def enlaces_seguros(html: str) -> SafeString:
    """Quita el `href` de todo enlace con un esquema que no esté en la lista blanca.

    Se quita el atributo y NO el enlace entero: el texto que escribió el redactor se queda en la
    página. Si alguien pega algo raro, se pierde el enlace, no el párrafo.

    Se parsea en vez de usar una expresión regular porque las regex sobre HTML se saltan con
    entidades —`java&#115;cript:`— y con espacios raros. BeautifulSoup ya viene con Wagtail, así que
    no suma dependencia.
    """
    from bs4 import BeautifulSoup

    sopa = BeautifulSoup(str(html), "html.parser")
    tocado = False
    for etiqueta in sopa.find_all("a", href=True):
        if not _es_seguro(str(etiqueta["href"])):
            del etiqueta["href"]
            tocado = True
    # `mark_safe` sobre lo que ya venía marcado y acabamos de limpiar: sin esto el HTML del cuerpo
    # saldría escapado y el artículo se leería con las etiquetas a la vista.
    return mark_safe(str(sopa)) if tocado else mark_safe(str(html))
