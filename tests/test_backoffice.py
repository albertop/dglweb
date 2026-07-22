"""Tests for the Backoffice admin section (Fase 2)."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone
from wagtail.snippets.models import get_snippet_models

from dglweb.players.models import Player
from dglweb.stats.models import IngestRun
from tests.test_players import RECORD

LIST_URL_NAME = "wagtailsnippets_players_player:list"
RUNS_URL_NAME = "wagtailsnippets_stats_ingestrun:list"


@pytest.fixture
def admin_client(db: None) -> Client:  # pytest-django's `db` fixture is a side effect, not a value
    get_user_model().objects.create_superuser("admin", "admin@example.com", "pw-for-tests")
    client = Client()
    client.login(username="admin", password="pw-for-tests")
    return client


def test_player_is_registered_as_a_backoffice_snippet():
    # Registration is what puts the CRUD in the Wagtail admin.
    assert Player in get_snippet_models()


@pytest.mark.django_db
def test_player_list_requires_authentication():
    response = Client().get(reverse(LIST_URL_NAME))

    assert response.status_code == 302
    assert "/cms/login" in response.headers["Location"]


@pytest.mark.django_db
def test_admin_can_open_the_player_list(admin_client):
    response = admin_client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 200


@pytest.mark.django_db
def test_player_list_shows_existing_players(admin_client):
    Player.objects.create(**RECORD)

    response = admin_client.get(reverse(LIST_URL_NAME))

    assert b"Gibson Alba" in response.content


@pytest.mark.django_db
def test_admin_can_open_the_edit_form(admin_client):
    Player.objects.create(**RECORD)

    response = admin_client.get(reverse("wagtailsnippets_players_player:edit", args=[RECORD["player_id"]]))

    assert response.status_code == 200
    # The form is grouped into sections; check one heading and one external-id field.
    assert b"IDs externos" in response.content
    assert b"bbref_id" in response.content
    # The Cooperstown HoF year is editable in the form (its field and Spanish label render).
    assert b"hof_year" in response.content
    assert b"Cooperstown" in response.content


@pytest.mark.django_db
def test_ingest_run_is_registered_as_a_backoffice_snippet():
    assert IngestRun in get_snippet_models()


@pytest.mark.django_db
def test_run_list_requires_authentication():
    response = Client().get(reverse(RUNS_URL_NAME))

    assert response.status_code == 302
    assert "/cms/login" in response.headers["Location"]


@pytest.mark.django_db
def test_admin_sees_the_runs_with_their_status(admin_client):
    IngestRun.objects.create(
        command="import_batting",
        scope="2024",
        status=IngestRun.Status.SUCCESS,
        started_at=timezone.now(),
        rows_affected=106,
    )

    response = admin_client.get(reverse(RUNS_URL_NAME))

    assert response.status_code == 200
    assert b"import_batting" in response.content
    assert b"2024" in response.content


@pytest.mark.django_db
def test_the_runs_view_is_read_only_even_for_a_superuser(admin_client):
    """The ingest log is machine-written; the Add view is blocked even for superusers."""
    response = admin_client.get(reverse("wagtailsnippets_stats_ingestrun:add"))

    # Wagtail denies the action (redirect to the admin home, not a 200 add form).
    assert response.status_code == 302


@pytest.mark.django_db
def test_the_players_crud_stays_editable_for_a_superuser(admin_client):
    """The read-only policy is scoped to the ingest log — the players CRUD is still editable."""
    response = admin_client.get(reverse("wagtailsnippets_players_player:add"))

    assert response.status_code == 200
