"""Public player pages: `/jugador/<slug>/`, data-driven from our tables via the tab registry."""

from typing import Any

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from dglweb.players.models import Player
from dglweb.profiles.tabs import tabs_for
from dglweb.stats.models import BattingCareer, CareerLevel, PitchingCareer


def _player_id_from_slug(slug: str) -> int:
    """The canonical slug always ends in the MLB id (`juan-soto-120074`); read it back."""
    tail = slug.rsplit("-", 1)[-1]
    if not tail.isdigit():
        raise Http404("jugador no encontrado")
    return int(tail)


def player_detail(request: HttpRequest, slug: str) -> HttpResponse:
    player = get_object_or_404(Player, pk=_player_id_from_slug(slug))
    if slug != player.slug:
        return redirect("player_detail", slug=player.slug, permanent=True)  # canonical (SEO)

    tabs: list[dict[str, Any]] = [
        {
            "key": tab.key,
            "label": tab.label,
            "template": tab.template,
            "data": tab.context(player),
            "active": index == 0,
        }
        for index, tab in enumerate(tabs_for(player))
    ]
    context = {
        "player": player,
        "tabs": tabs,
        "is_pitcher": player.pos in {"P", "RP", "SP"},
        "bat_total": BattingCareer.objects.filter(player=player, level=CareerLevel.TOTAL).first(),
        "pit_total": PitchingCareer.objects.filter(player=player, level=CareerLevel.TOTAL).first(),
    }
    return render(request, "profiles/player_detail.html", context)
