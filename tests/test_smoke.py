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
def test_home_renders_landing_modules_when_requested():
    client = Client()

    response = client.get("/")

    body = response.content
    assert b"Destacados de la jornada" in body
    assert "Líderes dominicanos".encode() in body


@pytest.mark.django_db
def test_cms_admin_redirects_to_login_when_anonymous():
    client = Client()

    response = client.get("/cms/")

    assert response.status_code == 302
    assert "/cms/login" in response.headers["Location"]
