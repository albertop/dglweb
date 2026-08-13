"""Public profile URLs. Included before Wagtail's catch-all so `/jugador/…` resolves here."""

from django.urls import URLPattern, path

from dglweb.profiles.comparaciones import comparar, generador, tarjeta_png, temporadas_de
from dglweb.profiles.leaderboards import leaders_index
from dglweb.profiles.views import player_detail, players_index, players_suggest

urlpatterns: list[URLPattern] = [
    path("jugadores/", players_index, name="players_index"),
    # El endpoint del buscador vive bajo la misma rama para que se lea como lo que es: una parte de
    # esa página, no una API pública.
    path("jugadores/buscar/", players_suggest, name="players_suggest"),
    path("jugador/<slug:slug>/", player_detail, name="player_detail"),
    path("lideres/", leaders_index, name="leaders"),
    # EL COMPARADOR. Tres rutas: el generador —donde se eligen los parámetros— y la tarjeta, que
    # tiene dos formas porque la modalidad de temporada necesita un segmento más.
    path("comparar/", generador, name="comparador"),
    # El desplegable de años se llena desde acá, igual que el buscador se llena desde
    # `players_suggest`: depende de a quién se eligió, y eso pasa en el navegador.
    path("comparar/temporadas/", temporadas_de, name="comparador_temporadas"),
    # Dos rutas para el mismo nombre: la modalidad de temporada necesita un segmento
    # más —el año de cada uno— y las otras dos no. Se declara primero la larga, o la corta se
    # tragaría `temporadas` como si fuera la modalidad completa.
    # EL PNG CUELGA DE LA MISMA RUTA con `.png` al final: compartir el enlace y compartir el fichero
    # llevan al mismo sitio. Van antes que las páginas o `tarjeta.png` se leería como un `extra`.
    path("comparar/<slug:uno>/vs/<slug:otro>/<str:modo>/<str:extra>/tarjeta.png", tarjeta_png, name="comparar_png"),
    path("comparar/<slug:uno>/vs/<slug:otro>/<str:modo>/tarjeta.png", tarjeta_png, name="comparar_png"),
    path("comparar/<slug:uno>/vs/<slug:otro>/<str:modo>/<str:extra>/", comparar, name="comparar"),
    path("comparar/<slug:uno>/vs/<slug:otro>/<str:modo>/", comparar, name="comparar"),
]
