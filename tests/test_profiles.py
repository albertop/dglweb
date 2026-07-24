"""Public player pages: the tab registry (ordering, pitcher-first), the view, the slug, the filters."""

from datetime import date

import pytest
from django.test import Client
from django.urls import reverse

from dglweb.players.models import Player
from dglweb.profiles.tabs import (
    BattingTab,
    _catalog,
    _personal_bests,
    _qualifier_context,
    tabs_for,
)
from dglweb.profiles.templatetags.stats_extras import dec, innings, num, pct, rate
from dglweb.profiles.views import bio_lines
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    CareerLevel,
    FieldingCareer,
    Leader,
    Metric,
    PitchingCareer,
    QualifierDefault,
)
from tests.test_players import _other_player


def _player(pid: int, dgl: str, name: str, pos: str) -> Player:
    return Player.objects.create(**_other_player(player_id=pid, dgl_id=dgl, full_name=name, pos=pos))


@pytest.mark.django_db
def test_slug_always_ends_in_the_id() -> None:
    player = _player(120074, "ortiz01", "David Ortiz", "DH")
    assert player.slug == "david-ortiz-120074"


@pytest.mark.django_db
def test_tabs_order_batter_batting_first() -> None:
    player = _player(1, "a01", "Un Bateador", "LF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    FieldingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=200)

    assert [tab.key for tab in tabs_for(player)] == ["batting", "fielding"]


@pytest.mark.django_db
def test_tabs_order_pitcher_pitching_first() -> None:
    player = _player(2, "b01", "Un Lanzador", "SP")  # SP is a pitcher code
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    PitchingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    FieldingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=200)

    assert [tab.key for tab in tabs_for(player)] == ["pitching", "batting", "fielding"]


@pytest.mark.django_db
def test_tab_hidden_when_the_player_has_no_data_for_it() -> None:
    player = _player(3, "c01", "Solo Bateo", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)

    assert [tab.key for tab in tabs_for(player)] == ["batting"]  # no pitching/fielding career -> no tabs


@pytest.mark.django_db
def test_player_page_renders_the_name_and_a_stat() -> None:
    player = _player(4, "d01", "Juan Soto", "LF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300, hr=229, avg=0.288)
    Batting.objects.create(player=player, season=2024, stint=1, hr=41, avg=0.288)

    response = Client().get(reverse("player_detail", args=[player.slug]))

    assert response.status_code == 200
    assert b"Juan Soto" in response.content
    assert b"229" in response.content  # career HR statbox
    # `{# ... #}` es de UNA línea: partido en dos deja de ser comentario y se imprime en la página.
    assert b"{#" not in response.content


@pytest.mark.django_db
def test_wrong_name_slug_redirects_to_canonical() -> None:
    player = _player(5, "e01", "Manny Ramírez", "LF")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)

    response = Client().get(f"/jugador/nombre-equivocado-{player.player_id}/")

    assert response.status_code == 301
    assert response.headers["Location"] == reverse("player_detail", args=[player.slug])


@pytest.mark.django_db
def test_slug_without_a_trailing_id_is_404() -> None:
    assert Client().get("/jugador/sin-id/").status_code == 404


def test_rate_filter_drops_the_leading_zero() -> None:
    assert rate(0.288) == ".288"
    assert rate(2.5, 2) == "2.50"
    assert rate(None) == "—"
    assert num(None) == "—"
    assert num(41) == "41"


def test_num_adds_thousands_separator() -> None:
    assert num(2472) == "2,472"
    assert num(541) == "541"


@pytest.mark.django_db
def test_bio_line_lists_every_field_it_has() -> None:
    player = _player(18, "b03", "Con Todo", "1B")
    player.bats, player.throws, player.height, player.weight = "L", "R", "6-3", 230
    player.birth_date = date(1975, 11, 18)
    player.birth_place, player.birth_province = "Santo Domingo", "Distrito Nacional"
    player.debut_date, player.death_date = date(1997, 9, 2), date(2050, 1, 5)
    player.save()

    play, origin = bio_lines(player)  # dos líneas: cómo juega, y de dónde/cuándo

    assert "Batea: Izq" in play  # el modelo no tiene choices: mapeo explícito, no get_*_display
    assert "Lanza: Der" in play
    assert "Estatura: 6-3" in play and "Peso: 230 lb" in play
    assert "Santo Domingo, Distrito Nacional" in origin
    assert any(p.startswith("Debut") for p in origin)
    assert any(p.startswith("Falleció") for p in origin)


@pytest.mark.django_db
def test_bio_line_spells_out_the_pitcher_role() -> None:
    """El maestro guarda el rol en el código de posición; el resto de posiciones pasa tal cual."""
    assert "Posición: P-Abr" in bio_lines(_player(23, "r01", "Abridor", "SP"))[0]
    assert "Posición: P-Rel" in bio_lines(_player(24, "r02", "Relevista", "RP"))[0]
    assert "Posición: P" in bio_lines(_player(25, "r03", "Genérico", "P"))[0]
    assert "Posición: LF" in bio_lines(_player(26, "r04", "Jardinero", "LF"))[0]


@pytest.mark.django_db
def test_bio_line_prints_the_birthplace_once_when_city_equals_province() -> None:
    """384 de 984 jugadores repiten el valor; `Hato Mayor, Hato Mayor` se lee como un error."""
    player = _player(19, "b04", "Mismo Lugar", "1B")
    player.birth_place = player.birth_province = "Hato Mayor"
    player.birth_date = player.debut_date = player.death_date = None
    player.save()

    _, origin = bio_lines(player)

    assert origin == ["Hato Mayor"]  # una vez, no "Hato Mayor, Hato Mayor"


@pytest.mark.django_db
def test_bio_line_skips_what_the_record_lacks() -> None:
    player = _player(20, "b05", "Sin Datos", "1B")
    player.pos = None
    player.bats = player.throws = player.height = player.weight = None
    player.birth_date = player.birth_place = player.birth_province = None
    player.debut_date = player.death_date = None
    player.save()

    assert bio_lines(player) == []  # ni etiquetas huérfanas ni separadores sueltos


def test_innings_uses_baseball_notation_not_a_decimal() -> None:
    """Los 8482 outs de Pedro son 2,827.1 IP — el `.1` es UN OUT, no una décima (2,827.3)."""
    assert innings(8482) == "2,827.1"
    assert innings(8483) == "2,827.2"
    assert innings(8484) == "2,828.0"
    assert innings(None) == "—"


def test_dec_keeps_the_leading_zero_and_groups_thousands() -> None:
    assert dec(0.5) == "0.5"  # el cero inicial se queda (no es una tasa de bateo)
    assert dec(-2.34, 2) == "-2.34"
    assert dec(1536.6) == "1,536.6"  # BsR/RC/wRC de carrera pasan de mil
    assert dec(None) == "—"


def test_pct_filter_shows_percentage_number() -> None:
    assert pct(0.452) == "45.2"
    assert pct(0.2, 1) == "20.0"
    assert pct(None) == "—"


@pytest.mark.django_db
def test_a_traded_season_lists_each_club_then_the_combined_line() -> None:
    """2021 de Pujols: cada equipo sale como fila, y la combinada del año cierra la temporada."""
    player = _player(17, "x01", "Traspasado", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=2020, stint=1, team="LAN", league="NL", pa=600, hr=40)
    Batting.objects.create(player=player, season=2021, stint=1, team="LAN", league="NL", pa=204, hr=12)
    Batting.objects.create(player=player, season=2021, stint=2, team="ANA", league="AL", pa=92, hr=5)
    Batting.objects.create(player=player, season=2021, stint=3, team="XXX", league="XX", pa=296, hr=17)

    data = BattingTab().context(player)
    lines = [(row.season, row.team) for row, _ in data["rows"]]

    assert lines == [(2020, "LAN"), (2021, "LAN"), (2021, "ANA"), (2021, "XXX")]
    assert data["season_count"] == 2  # 2 temporadas aunque sean 4 filas

    # El resaltado pertenece a la temporada completa, no a media temporada: solo la combinada.
    marked = [(row.season, row.team) for row, leads in data["rows"] if leads]
    assert all(team in {"LAN", "XXX"} for _, team in marked)
    split_rows = [leads for row, leads in data["rows"] if row.season == 2021 and row.team != "XXX"]
    assert all(leads == {} for leads in split_rows)


@pytest.mark.django_db
def test_totals_pane_counts_seasons_and_ends_with_the_career_total() -> None:
    """Una temporada dividida cuenta para CADA equipo, pero una sola vez en la carrera."""
    player = _player(16, "t01", "Cambio de Equipo", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TEAM, team="MIN", sort_order=100)
    BattingCareer.objects.create(player=player, level=CareerLevel.TEAM, team="BOS", sort_order=101)
    BattingCareer.objects.create(player=player, level=CareerLevel.LEAGUE, league="AL", sort_order=200)
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=2002, stint=1, team="MIN", league="AL", pa=400)
    Batting.objects.create(player=player, season=2003, stint=1, team="MIN", league="AL", pa=200)
    Batting.objects.create(player=player, season=2003, stint=2, team="BOS", league="AL", pa=200)
    Batting.objects.create(player=player, season=2003, stint=3, team="XXX", league="AL", pa=400)  # combinada

    totals = BattingTab().context(player)["totals"]
    by_label = {row["label"]: row["seasons"] for row in totals}

    assert by_label["MIN"] == 2  # 2002 y 2003
    assert by_label["BOS"] == 1  # solo la mitad de 2003
    assert by_label["Liga AL"] == 2
    assert totals[-1]["kind"] == "total"  # el total de carrera va de último
    assert totals[-1]["seasons"] == 2  # 2003 dividida cuenta UNA vez


@pytest.mark.django_db
def test_statcast_panes_hidden_for_a_player_without_batted_ball_data() -> None:
    """Un jugador del pasado sin Statcast no debe mostrar los pills."""
    player = _player(13, "s01", "Bateo Antiguo", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=1960, stint=1, team="SFG", pa=600)

    data = BattingTab().context(player)

    assert data["has_statcast"] is False
    assert data["statcast_rows"] == []


@pytest.mark.django_db
def test_statcast_has_no_total_when_coverage_is_partial() -> None:
    """Si Statcast cubre menos temporadas que bateo, la fila total engañaría: no se pone.

    El jugador cruza el piso de 1989: su temporada de 1988 no entra a los paneles Statcast."""
    player = _player(14, "s02", "Cobertura Parcial", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=1988, stint=1, team="BOS", pa=600, balls_in_play=400)
    Batting.objects.create(player=player, season=1996, stint=1, team="BOS", pa=600, balls_in_play=400)

    data = BattingTab().context(player)

    assert data["has_statcast"] is True
    assert len(data["statcast_rows"]) == 1  # 1988 queda fuera del piso
    assert data["statcast_rows"][0][0].season == 1996
    assert data["statcast_full"] is False  # -> sin fila total


@pytest.mark.django_db
def test_statcast_totals_when_every_season_has_data() -> None:
    player = _player(15, "s03", "Cobertura Total", "1B")
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=player, season=2015, stint=1, team="BOS", pa=600, balls_in_play=400)
    Batting.objects.create(player=player, season=2016, stint=1, team="BOS", pa=600, balls_in_play=410)

    data = BattingTab().context(player)

    assert data["statcast_full"] is True


@pytest.mark.django_db
def test_personal_best_higher_is_better_is_the_season_maximum() -> None:
    player = _player(10, "h01", "Bateo HR", "1B")
    Metric.objects.create(
        stat_group="batting", column="hr", kind=Metric.Kind.CUMULATIVE, direction=Metric.Direction.HIGHER
    )
    Batting.objects.create(player=player, season=2018, stint=1, team="BOS", pa=600, hr=54)
    Batting.objects.create(player=player, season=2019, stint=1, team="BOS", pa=600, hr=30)

    seasons = list(Batting.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Batting, "batting", seasons, _catalog("batting"), *_qualifier_context())

    assert (2018, "hr") in best
    assert (2019, "hr") not in best


@pytest.mark.django_db
def test_personal_best_lower_is_better_is_the_qualified_minimum() -> None:
    """SO (menor es mejor): la mejor marca es el mínimo ENTRE temporadas calificadas por PA,
    no el conteo más pequeño de una muestra chica sin calificar, ni el máximo (que es lo peor)."""
    player = _player(11, "k01", "Bateo Ponches", "1B")
    Metric.objects.create(
        stat_group="batting", column="so", kind=Metric.Kind.CUMULATIVE, direction=Metric.Direction.LOWER
    )
    QualifierDefault.objects.create(stat_group="batting", qualifier_season="PA>=502")
    Batting.objects.create(player=player, season=2018, stint=1, team="BOS", pa=600, so=90)  # mín calificado
    Batting.objects.create(player=player, season=2019, stint=1, team="BOS", pa=600, so=145)  # el peor
    Batting.objects.create(player=player, season=2020, stint=1, team="BOS", pa=40, so=8)  # muestra chica

    seasons = list(Batting.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Batting, "batting", seasons, _catalog("batting"), *_qualifier_context())

    assert (2018, "so") in best  # el mínimo calificado es su mejor marca
    assert (2019, "so") not in best  # el máximo (peor) nunca
    assert (2020, "so") not in best  # muestra chica sin calificar no cuenta


@pytest.mark.django_db
def test_a_pitchers_batting_table_carries_no_leadership_badges() -> None:
    """Sus turnos al bate son incidentales: se ranquean contra bateadores de oficio. La mejor marca
    personal sí se queda — esa no compara con nadie."""
    pitcher = _player(22, "p02", "Un Abridor", "SP")
    BattingCareer.objects.create(player=pitcher, level=CareerLevel.TOTAL, sort_order=300)
    Batting.objects.create(player=pitcher, season=2019, stint=1, team="BOS", pa=80, hr=2)
    metric = Metric.objects.create(
        stat_group="batting", column="hr", kind=Metric.Kind.CUMULATIVE, direction=Metric.Direction.HIGHER
    )
    Leader.objects.create(metric=metric, board=Leader.Board.BEST_SEASON, season=2019, player=pitcher, value=2, rank=1)
    Leader.objects.create(metric=metric, board=Leader.Board.BEST_CAREER, player=pitcher, value=2, rank=1)

    data = BattingTab().context(pitcher)

    assert data["total_leads"] == {}  # sin azul de líder de por vida
    classes = {css for _, leads in data["rows"] for css in leads.values()}
    assert "lead-season" not in classes and "lead-career" not in classes
    assert "lead-best" in classes  # su mejor marca personal sobrevive


@pytest.mark.django_db
def test_cs_zero_is_a_personal_best_only_when_he_actually_ran() -> None:
    """No haber sido atrapado robando no dice nada si nunca intentó robar."""
    player = _player(21, "c02", "Nunca Corre", "1B")
    Metric.objects.create(
        stat_group="batting", column="cs", kind=Metric.Kind.CUMULATIVE, direction=Metric.Direction.LOWER
    )
    QualifierDefault.objects.create(stat_group="batting", qualifier_season="PA>=502")
    Batting.objects.create(player=player, season=2016, stint=1, team="BOS", pa=600, sb=0, cs=0)
    Batting.objects.create(player=player, season=2017, stint=1, team="BOS", pa=600, sb=12, cs=0)
    Batting.objects.create(player=player, season=2018, stint=1, team="BOS", pa=600, sb=5, cs=4)

    seasons = list(Batting.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Batting, "batting", seasons, _catalog("batting"), *_qualifier_context())

    assert (2017, "cs") in best  # robó 12 y nunca lo atraparon: eso sí es una marca
    assert (2016, "cs") not in best  # 0 de 0 intentos no es un logro


@pytest.mark.django_db
def test_personal_best_rate_ignores_small_sample_extreme() -> None:
    """Un rate (BABIP) se dispara en una muestra chica de 51 PA; la verdadera mejor marca es la
    temporada CALIFICADA más alta, no la muestra chica (el bug reportado en 1997 de Ortiz)."""
    player = _player(12, "b02", "Bateo BABIP", "1B")
    Metric.objects.create(
        stat_group="batting", column="babip", kind=Metric.Kind.RATE, direction=Metric.Direction.HIGHER
    )
    QualifierDefault.objects.create(stat_group="batting", qualifier_season="PA>=502")
    Batting.objects.create(player=player, season=1997, stint=1, team="MIN", pa=51, babip=0.420)  # muestra chica
    Batting.objects.create(player=player, season=2006, stint=1, team="BOS", pa=686, babip=0.350)  # máx calificado
    Batting.objects.create(player=player, season=2007, stint=1, team="BOS", pa=667, babip=0.330)

    seasons = list(Batting.objects.filter(player=player).season_totals().order_by("season"))
    best = _personal_bests(Batting, "batting", seasons, _catalog("batting"), *_qualifier_context())

    assert (1997, "babip") not in best  # muestra chica sin calificar no cuenta
    assert (2006, "babip") in best  # el máximo entre temporadas calificadas
