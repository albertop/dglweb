"""Public profile URLs. Included before Wagtail's catch-all so `/jugador/…` resolves here."""

from django.urls import URLPattern, path

from dglweb.profiles.leaderboards import leaders_index
from dglweb.profiles.views import player_detail, players_index, players_suggest

urlpatterns: list[URLPattern] = [
    path("jugadores/", players_index, name="players_index"),
    # El endpoint del buscador vive bajo la misma rama para que se lea como lo que es: una parte de
    # esa página, no una API pública.
    path("jugadores/buscar/", players_suggest, name="players_suggest"),
    path("jugador/<slug:slug>/", player_detail, name="player_detail"),
    path("lideres/", leaders_index, name="leaders"),
]
