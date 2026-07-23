"""Public profile URLs. Included before Wagtail's catch-all so `/jugador/…` resolves here."""

from django.urls import URLPattern, path

from dglweb.profiles.views import player_detail

urlpatterns: list[URLPattern] = [
    path("jugador/<slug:slug>/", player_detail, name="player_detail"),
]
