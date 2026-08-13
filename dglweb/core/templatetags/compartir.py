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

EL «vía @…» APUNTA A LA CUENTA DEL SITIO, NUNCA A UNA PERSONA
-------------------------------------------------------------
Estuvo sin `via=` mientras el sitio no tenía cuenta. Se propuso poner la personal del dueño —trae
seguidores desde el primer día— y se descartó: él no trabaja en el ambiente deportivo y no quiere su
usuario repetido en cada tuit que comparta un lector.

Con `@dglmlb` (2026-07-30) el parámetro pasa a tener sentido, porque atribuye al SITIO. Sale de
`settings.X_USUARIO`, así que si algún día cambia la cuenta no hay que buscarlo por las plantillas.
"""

from typing import Any
from urllib.parse import quote

from django import template
from django.conf import settings
from django.http import HttpRequest

register = template.Library()


@register.inclusion_tag("widgets/_compartir.html", takes_context=True)
def compartir(
    context: dict[str, Any],
    url: str,
    titulo: str,
    clase: str = "",
    que: str = "",
    redes: bool = True,
    descarga: str = "",
) -> dict[str, Any]:
    """Los botones para compartir `url`, que puede venir relativa.

    `titulo` es lo que se escribe en el mensaje. En un artículo, su titular; en un perfil debería ser
    algo con datos —«Juan Soto — 2026: .285, 32 HR»— porque un enlace con números se abre y uno
    genérico se ignora.

    `que` NOMBRA LO QUE SE COMPARTE PARA QUIEN NO VE LA PANTALLA
    ------------------------------------------------------------
    Sale en el `aria-label` del grupo: «Compartir este artículo», «Compartir este perfil». Sin nombre,
    un lector de pantalla anuncia cinco enlaces sueltos —«WhatsApp», «X», «Facebook»…— sin decir para
    qué están ahí ni qué se llevaría cada uno.

    Estuvo fijo en «Compartir este artículo» y se copió tal cual al perfil de jugador y a líderes, así
    que esas dos páginas anunciaban un artículo que no existe. Vacío por defecto —queda «Compartir»,
    que es cierto en todas partes— porque la penalización de olvidarlo tiene que ser un nombre pobre y
    no uno FALSO: lo pobre se nota al leerlo, lo falso solo lo nota quien depende de ello.
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
        # Sin arroba: X la añade solo. Con ella, el tuit sale con «vía @@dglmlb».
        "x_via": settings.X_USUARIO,
        "url_url": quote(url, safe=""),
        "texto_url": quote(titulo, safe=""),
        "clase": clase,
        "etiqueta": f"Compartir {que}".strip(),
        # LOS TRES BOTONES DE RED SON OPCIONALES desde la tarjeta del comparador (dueño, 2026-08-13):
        # allí «Compartir…» manda el FICHERO —la imagen entera— y WhatsApp, X y Facebook mandan el
        # enlace, que la red dibuja como una tarjetita pequeña. Teniendo lo primero, lo segundo es una
        # versión peor de lo mismo. En un artículo no hay fichero que mandar y los tres siguen siendo
        # el camino, así que el valor por defecto no cambia.
        "redes": redes,
        # La URL de descarga, si quien llama tiene un archivo que ofrecer. Vacía en todo lo demás.
        "descarga": descarga,
    }
