"""Foundation smoke tests (Fase 1)."""

import pytest
from django.conf import settings
from django.test import Client


@pytest.mark.django_db
def test_home_returns_200_when_requested():
    client = Client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"Dominicanos en Grandes Ligas" in response.content


@pytest.mark.django_db
def test_home_has_no_fake_live_data():
    client = Client()

    response = client.get("/")

    # The live ticker must not ship hardcoded fake "EN VIVO" data to staging/prod.
    assert b"EN VIVO" not in response.content


def test_health_returns_ok_when_requested():
    client = Client()

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_static_url_is_absolute():
    # Must start with "/" so assets resolve from the site root on nested paths.
    assert settings.STATIC_URL.startswith("/")


@pytest.mark.django_db
def test_home_shows_the_articles_section_once_there_are_articles():
    """Hasta la Fase 5 la sección estaba siempre, porque las tarjetas eran de muestra.

    Ahora sale del contenido publicado, así que el test tiene que publicar algo. La otra mitad —qué
    pasa cuando no hay nada— está en el test siguiente.
    """
    from tests.test_articles import _articulo, _indice_de_articulos

    indice = _indice_de_articulos()
    for numero in range(2):
        _articulo(indice, f"Un articulo {numero}")

    response = Client().get("/")

    assert "Últimos artículos".encode() in response.content
    assert b"Un articulo 0" in response.content


@pytest.mark.django_db
def test_home_leaves_the_articles_section_out_when_there_is_nothing_published():
    """Media portada de huecos grises se lee como un sitio roto.

    Y el visitante no tiene por qué enterarse de que el CMS está recién estrenado: mejor una portada
    más corta que una con el esqueleto de una sección vacía.
    """
    response = Client().get("/")

    assert "Últimos artículos".encode() not in response.content
    assert b"Ver m" not in response.content  # tampoco el enlace al índice


@pytest.mark.django_db
def test_the_widget_zone_shows_the_stored_standouts(db):
    """La franja de arriba es dato real, no la maqueta: si hay jornada guardada, sale la jornada."""
    from datetime import date

    from dglweb.players.models import Player
    from dglweb.stats.models import DailyStandout
    from tests.test_players import _other_player

    jugador = Player.objects.create(**_other_player(full_name="Rafael Devers"))
    DailyStandout.objects.create(
        fecha=date(2026, 7, 25),
        grupo=DailyStandout.Grupo.BATEO,
        player=jugador,
        team="SFN",
        linea="3-4, 2B, HR, 4 RBI",
        valor=2.35,
    )

    body = Client().get("/").content

    assert b"Destacados del" in body
    assert b"3-4, 2B, HR, 4 RBI" in body


@pytest.mark.django_db
def test_an_empty_widget_zone_is_left_out_instead_of_drawn_hollow():
    """Un panel vacío se lee como un sitio roto; que no esté se lee como que hoy no hubo nada."""
    body = Client().get("/").content

    assert b"Destacados de la jornada" not in body


@pytest.mark.django_db
def test_cms_admin_redirects_to_login_when_anonymous():
    client = Client()

    response = client.get("/cms/")

    assert response.status_code == 302
    assert "/cms/login" in response.headers["Location"]


@pytest.mark.django_db
def test_articles_index_answers():
    """El enlace del menú ya la promete; un menú que lleva a un 404 es peor que uno que no lleva."""
    response = Client().get("/articulos/")

    assert response.status_code == 200
    assert "Artículos".encode() in response.content
