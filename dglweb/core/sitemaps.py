"""El mapa del sitio: qué páginas se le anuncian a Google.

POR QUÉ HACE FALTA. El sitio tiene ~970 fichas de jugador, y sin mapa Google las descubre siguiendo
enlaces desde el índice. Funciona, pero tarda semanas y no hay forma de saber si llegó a todas. Con
el mapa se anuncian de una vez.

LO QUE NO ENTRA, Y ES LA MITAD DEL TRABAJO
-------------------------------------------
La página de LÍDERES acepta métrica, alcance y temporada por la URL: 146 x 2 x 72 son ~21.000
combinaciones de la misma página. Meterlas sería invitar a Google a gastarse el presupuesto de
rastreo ahí en vez de en las fichas, que son el contenido de verdad. Va la URL desnuda y nada más.

Tampoco entran el buscador ni los filtros del índice de artículos: son formas de ordenar contenido
que ya está en el mapa por su cuenta.
"""

from typing import Any

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from dglweb.players.models import Player


class Jugadores(Sitemap):  # type: ignore[type-arg]
    """Las ~970 fichas. El grueso del sitio y lo que de verdad se quiere indexado."""

    changefreq = "weekly"
    priority = 0.8
    protocol = "https"
    limit = 2000  # caben todas en un solo archivo

    def items(self) -> Any:  # noqa: ANN401 — devuelve un QuerySet; Django no lo tipa mejor
        # `Player.objects` y no `Player.todos`: el manager por defecto excluye a los dados de baja, y
        # anunciar en el mapa una URL que devuelve 404 es la forma más rápida de que Google deje de
        # fiarse del mapa entero.
        return Player.objects.all().order_by("player_id")

    def location(self, item: Player) -> str:
        return reverse("player_detail", args=[item.slug])


class Portada(Sitemap):  # type: ignore[type-arg]
    """Las tres que cambian a diario y son la puerta de entrada."""

    changefreq = "daily"
    priority = 1.0
    protocol = "https"

    def items(self) -> list[str]:
        return ["home", "leaders", "players_index"]

    def location(self, item: str) -> str:
        return reverse(item)


class Legales(Sitemap):  # type: ignore[type-arg]
    """Privacidad, términos, cookies y contacto.

    Prioridad baja pero VAN: un anunciante o un revisor de AdSense las busca, y que estén en el mapa
    es parte de que el sitio se vea completo.
    """

    changefreq = "yearly"
    priority = 0.3
    protocol = "https"

    def items(self) -> list[str]:
        return ["contacto", "privacidad", "terminos", "cookies"]

    def location(self, item: str) -> str:
        return reverse("contacto") if item == "contacto" else reverse("legal", args=[item])
