"""Páginas públicas de peloteros: el índice `/jugadores/` y el perfil `/jugador/<slug>/`."""

from typing import Any

from django.db import models
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import date as format_date

from dglweb.players import search
from dglweb.players.models import Player
from dglweb.profiles.tabs import tabs_for
from dglweb.stats.models import BattingCareer, CareerLevel, PitchingCareer

# `bats`/`throws` are plain codes with no choices on the model, so there is no get_*_display to call.
# `S` (switch) and `B` (both) are the same thing in the source; 6 players carry `B`.
_HANDS = {"R": "Der", "L": "Izq", "S": "Amb", "B": "Amb"}

# The master stores the pitcher's role in the position code; spell it out. Everything else (1B, LF,
# C, DH…) is already the code the reader expects, so it passes through untouched.
_POSITIONS = {"SP": "P-Abr", "RP": "P-Rel"}


def _birthplace(player: Player) -> str | None:
    """City and province, or just one when the record repeats it.

    384 of 984 players carry the same value in both columns (`Hato Mayor, Hato Mayor`), which reads
    like a mistake on the page.
    """
    city, province = player.birth_place, player.birth_province
    if city and province and city != province:
        return f"{city}, {province}"
    return city or province or None


def bio_lines(player: Player) -> list[list[str]]:
    """The bio under the name, as two short lines rather than one long one.

    A single line runs wide enough to push the career statboxes off the hero's right edge. So: how
    he plays first (bats, throws, height, weight), then where and when (birth, birthplace, debut,
    death). Whatever the record lacks is left out, so no dangling label or separator ever prints,
    and an empty line is dropped entirely.
    """
    play: list[str] = []
    if player.pos:
        play.append(f"Posición: {_POSITIONS.get(player.pos, player.pos)}")
    if player.bats:
        play.append(f"Batea: {_HANDS.get(player.bats, player.bats)}")
    if player.throws:
        play.append(f"Lanza: {_HANDS.get(player.throws, player.throws)}")
    if player.height:
        play.append(f"Estatura: {player.height}")
    if player.weight:
        play.append(f"Peso: {player.weight} lb")

    origin: list[str] = []
    if player.birth_date:
        origin.append(f"Nac. {format_date(player.birth_date, 'j M Y')}")
    if place := _birthplace(player):
        origin.append(place)
    if player.debut_date:
        origin.append(f"Debut {format_date(player.debut_date, 'j M Y')}")
    if player.death_date:
        origin.append(f"Falleció {format_date(player.death_date, 'j M Y')}")

    return [line for line in (play, origin) if line]


def _player_id_from_slug(slug: str) -> int:
    """The canonical slug always ends in the MLB id (`juan-soto-120074`); read it back."""
    tail = slug.rsplit("-", 1)[-1]
    if not tail.isdigit():
        raise Http404("jugador no encontrado")
    return int(tail)


def player_detail(request: HttpRequest, slug: str) -> HttpResponse:
    # `Player.objects` y no `Player`: un jugador dado de baja tiene que dar 404, no página.
    # Sacarlo de las listas no alcanza — el enlace directo sobrevive en Google y en cualquier chat.
    player = get_object_or_404(Player.objects, pk=_player_id_from_slug(slug))
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
        "bio": bio_lines(player),
        "tabs": tabs,
        "is_pitcher": player.pos in {"P", "RP", "SP"},
        "bat_total": BattingCareer.objects.filter(player=player, level=CareerLevel.TOTAL).first(),
        "pit_total": PitchingCareer.objects.filter(player=player, level=CareerLevel.TOTAL).first(),
    }
    return render(request, "profiles/player_detail.html", context)


def _latest_full_season() -> int | None:
    """La última temporada que tiene bateo Y pitcheo cargados.

    Se toma el mínimo de los dos máximos a propósito: si un oficio ya se refrescó hoy y el otro no,
    la última temporada "completa" es la del que va atrás. Mostrar la del que va adelante daría una
    lista a medias que parecería la plantilla entera.
    """
    from dglweb.stats.models import Batting, Pitching

    ultimas = [modelo.objects.aggregate(m=models.Max("season"))["m"] for modelo in (Batting, Pitching)]
    return min(ultimas) if all(u is not None for u in ultimas) else None


def players_index(request: HttpRequest) -> HttpResponse:
    """El índice de jugadores: buscador y la plantilla dominicana de la última temporada.

    El buscador funciona SIN JavaScript: el formulario hace un GET normal y esta vista devuelve los
    resultados ya renderizados. El JS de la plantilla solo adelanta ese mismo trabajo mientras se
    escribe. Si falla el script, o alguien llega con él desactivado, la página sigue sirviendo.
    """
    consulta = (request.GET.get("q") or "").strip()
    temporada = _latest_full_season()
    activos: list[Player] = []
    if temporada is not None:
        activos = list(
            Player.objects.filter(
                models.Q(batting_seasons__season=temporada) | models.Q(pitching_seasons__season=temporada)
            )
            .distinct()
            .order_by("full_name")
        )

    return render(
        request,
        "profiles/players_index.html",
        {
            "consulta": consulta,
            "resultados": search.buscar(consulta, limite=50) if consulta else [],
            "min_caracteres": search.MIN_CARACTERES,
            "temporada": temporada,
            "activos": activos,
        },
    )


def players_suggest(request: HttpRequest) -> JsonResponse:
    """El endpoint que consume el buscador mientras se escribe. JSON, sin plantilla."""
    sugerencias = search.buscar(request.GET.get("q") or "")
    return JsonResponse({"results": [s.to_dict() for s in sugerencias]})
