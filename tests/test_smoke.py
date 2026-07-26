"""Foundation smoke tests (Fase 1)."""

import pytest
from django.conf import settings
from django.test import Client
from django.urls import reverse


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
def test_home_shows_only_what_is_actually_published():
    """La portada no puede afirmar nada que no tengamos (FE-01).

    Este test verificaba lo contrario: exigía los módulos «Destacados de la jornada» y «Líderes
    dominicanos · 2026», que eran maquetado con líneas de juego y totales de jonrones INVENTADOS
    sobre peloteros reales. En un sitio de estadísticas eso no es andamiaje, y un test que lo exigía
    lo convertía en requisito. Ahora fija lo contrario: que la portada ofrezca lo que sí existe.
    """
    client = Client()

    response = client.get("/")

    body = response.content.decode()
    assert response.status_code == 200
    assert "<h1" in body  # la portada no tenía encabezado principal: el título era un <a class="h3">
    assert reverse("leaders") in body  # lo único publicado hoy, y el enlace funciona
    assert 'href="#"' not in body


@pytest.mark.django_db
def test_cms_admin_redirects_to_login_when_anonymous():
    client = Client()

    response = client.get("/cms/")

    assert response.status_code == 302
    assert "/cms/login" in response.headers["Location"]
