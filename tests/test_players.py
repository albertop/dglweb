"""Fase 2 — Dominican players master table + Backoffice CRUD."""

import pytest
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from wagtail.snippets.models import get_snippet_models

from dglweb.players.models import Player


@pytest.mark.django_db
def test_str_returns_full_name():
    player = Player.objects.create(mlbam_id=665742, full_name="Juan Soto")

    assert str(player) == "Juan Soto"


@pytest.mark.django_db
def test_mlbam_id_must_be_unique():
    Player.objects.create(mlbam_id=1, full_name="Uno")

    with pytest.raises(IntegrityError):
        Player.objects.create(mlbam_id=1, full_name="Dos")


def test_player_is_registered_as_snippet():
    # The CRUD is wired into the admin (via the Backoffice group).
    assert Player in get_snippet_models()


@pytest.mark.django_db
def test_players_crud_requires_login_when_anonymous():
    client = Client()

    response = client.get(reverse("wagtailsnippets_players_player:list"))

    assert response.status_code == 302  # redirect to the CMS login


@pytest.mark.django_db
def test_admin_can_open_players_list(django_user_model):
    admin = django_user_model.objects.create_superuser("admin", "admin@example.com", "pw")
    client = Client()
    client.force_login(admin)

    response = client.get(reverse("wagtailsnippets_players_player:list"))

    assert response.status_code == 200
