"""Public player pages: the tab registry (ordering, pitcher-first), the view, the slug, the filters."""

import pytest
from django.test import Client
from django.urls import reverse

from dglweb.players.models import Player
from dglweb.profiles.tabs import tabs_for
from dglweb.profiles.templatetags.stats_extras import num, rate
from dglweb.stats.models import Batting, BattingCareer, CareerLevel, FieldingCareer, PitchingCareer
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
