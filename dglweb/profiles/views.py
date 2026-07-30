"""Páginas públicas de peloteros: el índice `/jugadores/` y el perfil `/jugador/<slug>/`."""

from typing import Any

from django.db import models
from django.http import Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.defaultfilters import date as format_date

from dglweb.players import mugshots, positions, search
from dglweb.players.models import Player
from dglweb.profiles.tabs import tabs_for
from dglweb.stats.models import BattingCareer, CareerLevel, PitchingCareer

# `bats`/`throws` are plain codes with no choices on the model, so there is no get_*_display to call.
# `S` (switch) and `B` (both) are the same thing in the source; 6 players carry `B`.
_HANDS = {"R": "Der", "L": "Izq", "S": "Amb", "B": "Amb"}


# The master stores the pitcher's role in the position code; spell it out. Everything else (1B, LF,
# C, DH…) is already the code the reader expects, so it passes through untouched.
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
        play.append(f"Posición: {positions.como_se_lee(player.pos)}")
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
    bateo = BattingCareer.objects.filter(player=player, level=CareerLevel.TOTAL).first()
    pitcheo = PitchingCareer.objects.filter(player=player, level=CareerLevel.TOTAL).first()
    context = {
        "player": player,
        # El retrato grande, no el de los widgets: acá se ve a 96px y en pantalla de retina el de
        # 120 se vería lavado. Vacío si no lo hay —un tercio de las fichas, ver `mugshots`— y ahí la
        # plantilla no dibuja nada: se pregunta acá y no con `onerror` para que el nombre nazca en su
        # sitio en vez de saltar 120px cuando vuelva el 404.
        "foto": mugshots.url(player.player_id, mugshots.GRANDE)
        if mugshots.existe(player.player_id, mugshots.GRANDE)
        else "",
        "bio": bio_lines(player),
        "tabs": tabs,
        "is_pitcher": player.pos in {"P", "RP", "SP"},
        "bat_total": bateo,
        "pit_total": pitcheo,
    }
    context["descripcion_social"] = descripcion_social(player)
    return render(request, "profiles/player_detail.html", context)


def descripcion_social(player: Player) -> str:
    """La frase que sale bajo el titular en Google y en la tarjeta de WhatsApp.

        Bryan Abreu
        Lanzador relevista. Debutó en 2019.
        dominicanosengrandesligas.com

    POR QUÉ NO SE DEJA VACÍA. Sin ella, Google recorta la primera frase que encuentre en la página —
    que acá es la fila de datos biográficos— y publica «Posición: P-ABR · Batea: Derecho · Estatura:
    6-0». Es cierto y no dice nada.

    CÓMO LLEGÓ A SER TAN CORTA (decisión del dueño, 2026-07-30). Empezó siendo esto:

        Bryan Abreu, lanzador relevista dominicano, en Grandes Ligas desde 2019.
        496 ponches de por vida. Estadísticas completas de su carrera.

    y se le quitó, por este orden, todo lo que repetía algo que la tarjeta ya dice:

    * **El nombre** — es el TÍTULO, justo encima.
    * **La cifra de carrera** — se elegía por una regla fija: ponches si es lanzador, jonrones si no.
      Eso no resume a un pelotero concreto: a un relevista lo definía por un total que a nadie le dice
      nada, y a un joven por una cifra pequeña que parece un desaire.
    * **«Estadísticas completas de su carrera»** — relleno de palabras clave.
    * **«dominicano»** — está en el nombre del sitio.
    * **«Grandes Ligas»** — está en el nombre del sitio y en el dominio que la tarjeta imprime debajo.
    * **El pueblo natal** — llegó a estar y también se fue, por simplificar.

    Y «Debutó en» y no «desde»: con un retirado, «desde 1997» suena a que sigue jugando.

    LO QUE SE ACEPTA A CAMBIO: la frase ya no distingue una ficha de otra. Dos relevistas que debutaron
    el mismo año tienen la misma descripción, y eso a Google le sabe a contenido duplicado. Es el precio
    de la brevedad y está tomado a conciencia — lo que de verdad distingue cada página en una búsqueda
    es el `<title>`, que sí lleva el nombre.
    """
    from dglweb.players import positions

    oficio = positions.nombre_largo(player.pos) or "Pelotero"
    frase = oficio[0].upper() + oficio[1:] + "."
    if player.debut_date:
        frase += f" Debutó en {player.debut_date.year}."
    return frase


def _latest_full_season() -> int | None:
    """La última temporada que tienen cargados los TRES oficios.

    El mínimo de los máximos, a propósito: si uno ya se refrescó hoy y otro no, la última temporada
    "completa" es la del que va atrás. Mostrar la del que va adelante daría una lista a medias con
    pinta de plantilla entera. Los tres jobs corren seguidos a las 6:00, 6:15 y 6:30, así que un
    desfase dura minutos.

    Una tabla VACÍA no cuenta: no dice nada sobre cuál es la última temporada, solo que ese oficio
    nunca se importó. Incluirla en el mínimo dejaría la sección entera en blanco por algo que no es
    un problema de esta página — el guardián existe para atajar una carga a medias, no una ausencia.
    """
    from dglweb.stats.models import Batting, Fielding, Pitching

    ultimas = [modelo.objects.aggregate(m=models.Max("season"))["m"] for modelo in (Batting, Pitching, Fielding)]
    cargadas = [u for u in ultimas if u is not None]
    return min(cargadas) if cargadas else None


def players_index(request: HttpRequest) -> HttpResponse:
    """El índice de jugadores: buscador y la plantilla dominicana de la última temporada.

    El buscador funciona SIN JavaScript: el formulario hace un GET normal y esta vista devuelve los
    resultados ya renderizados. El JS de la plantilla solo adelanta ese mismo trabajo mientras se
    escribe. Si falla el script, o alguien llega con él desactivado, la página sigue sirviendo.
    """
    consulta = (request.GET.get("q") or "").strip()
    # Sin límite: esta ES la lista completa, la que promete el «ver todos» del desplegable. Recortar
    # acá también dejaría al usuario sin ningún lugar donde ver el resto.
    hallazgo = search.buscar(consulta, limite=None) if consulta else None
    temporada = _latest_full_season()
    activos: list[Player] = []
    if temporada is not None:
        activos = list(
            # Los TRES oficios. Fildeo va porque «ver acción» no siempre deja línea de bateo ni de
            # pitcheo: un sustituto defensivo puede entrar solo a defender. Hoy no suma a nadie —los
            # que fildearon tienen todos línea de bateo— pero la red queda puesta para el día que sí.
            Player.objects.filter(
                models.Q(batting_seasons__season=temporada)
                | models.Q(pitching_seasons__season=temporada)
                | models.Q(fielding_seasons__season=temporada)
            )
            .distinct()
            # Quién llegó este año. Se marca con asterisco: en una lista de 132 nombres, el que acaba
            # de debutar es la única noticia, y sin señal se pierde entre los veteranos.
            .annotate(
                debutante=models.ExpressionWrapper(
                    models.Q(debut_date__year=temporada), output_field=models.BooleanField()
                )
            )
            # Por apellido, como se lista a los peloteros en cualquier registro de béisbol — aunque lo
            # que se muestre sea el nombre completo. La fecha de debut desempata a los homónimos, que
            # acá son un caso real: pone primero al que llegó antes. Los que no la tienen van al final
            # en vez de al principio, que es lo que haría Postgres con los NULL en orden ascendente.
            .order_by("lastname_1", "firstname", models.F("debut_date").asc(nulls_last=True))
        )

    return render(
        request,
        "profiles/players_index.html",
        {
            "consulta": consulta,
            "resultados": hallazgo.items if hallazgo else [],
            "min_caracteres": search.MIN_CARACTERES,
            "temporada": temporada,
            "activos": activos,
            # Cuántos hay que buscar. `Player.objects` ya excluye a los deshabilitados, así que el
            # número que se anuncia es exactamente el que el buscador puede encontrar — prometer más
            # de lo que se entrega es peor que no prometer nada.
            "total_jugadores": Player.objects.count(),
        },
    )


def players_suggest(request: HttpRequest) -> JsonResponse:
    """El endpoint que consume el buscador mientras se escribe. JSON, sin plantilla.

    Devuelve también `hidden`: cuántos encajaron y no caben en la lista. Sin ese número el
    desplegable recorta en silencio y quien busca «jose» —sesenta y ocho coincidencias— concluye que
    los otros cincuenta y ocho no están en la base.
    """
    hallazgo = search.buscar(request.GET.get("q") or "")
    return JsonResponse(
        {
            "results": [s.to_dict() for s in hallazgo.items],
            "total": hallazgo.total,
            "hidden": hallazgo.ocultos,
        }
    )
