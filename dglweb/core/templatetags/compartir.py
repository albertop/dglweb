"""Los botones de compartir.

POR QUÉ UNA ETIQUETA Y NO EL HTML PEGADO EN CADA PLANTILLA
-----------------------------------------------------------
Van a estar en el artículo (dos veces), y después en el perfil de jugador y en líderes. Cada sitio
necesita su propia URL y su propio texto, así que pegar cuatro enlaces a mano en cada uno es cinco
oportunidades de escapar mal una URL o de olvidar un `rel="noopener"`.

LA URL SE CONSTRUYE ABSOLUTA Y AQUÍ
------------------------------------
Las redes necesitan la dirección completa, con esquema y dominio. Si la plantilla pasara `page.url`
—que en Wagtail es relativa— se compartiría `/articulos/algo/`, que no lleva a ninguna parte.

Y se usa el HOST DE LA PETICIÓN, igual que hacen el canonical y el Open Graph. Desde el 2026-07-29 el
`www` redirige al apex en nginx, así que ese host solo puede ser uno.

EL TEXTO NO LLEVA «vía @…»
---------------------------
El sitio no tiene cuentas propias (decisión del dueño, 2026-07-29). Atribuir a una cuenta inexistente
—o peor, a la de la agencia— sería meter ruido en el mensaje que escribe otra persona.
"""

from typing import Any
from urllib.parse import quote

from django import template
from django.http import HttpRequest

register = template.Library()


@register.inclusion_tag("widgets/_compartir.html", takes_context=True)
def compartir(context: dict[str, Any], url: str, titulo: str, clase: str = "") -> dict[str, Any]:
    """Los botones para compartir `url`, que puede venir relativa.

    `titulo` es lo que se escribe en el mensaje. En un artículo, su titular; en un perfil debería ser
    algo con datos —«Juan Soto — 2026: .285, 32 HR»— porque un enlace con números se abre y uno
    genérico se ignora.
    """
    peticion: HttpRequest | None = context.get("request")
    if peticion is not None and url.startswith("/"):
        url = f"{peticion.scheme}://{peticion.get_host()}{url}"

    # `quote` y no `urlencode`: estas URLs van dentro del `href` de la plantilla, que ya escapa el
    # HTML. Codificar dos veces convertiría los `%20` en `%2520` y el mensaje llegaría con la basura
    # a la vista.
    return {
        "url": url,
        "titulo": titulo,
        "url_url": quote(url, safe=""),
        "texto_url": quote(titulo, safe=""),
        "clase": clase,
    }
