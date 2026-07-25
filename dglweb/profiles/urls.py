"""Public profile URLs. Included before Wagtail's catch-all so `/jugador/…` resolves here."""

from django.urls import URLPattern, path

from dglweb.profiles.leaderboards import leaders_index
from dglweb.profiles.views import player_detail

urlpatterns: list[URLPattern] = [
    path("jugador/<slug:slug>/", player_detail, name="player_detail"),
    path("lideres/", leaders_index, name="leaders"),
]
