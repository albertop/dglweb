"""Foundation smoke tests (Fase 1)."""

import pytest
from django.test import Client


@pytest.mark.django_db
def test_home_returns_200_when_requested():
    client = Client()

    response = client.get("/")

    assert response.status_code == 200
    assert b"Dominicanos en Grandes Ligas" in response.content


@pytest.mark.django_db
def test_home_renders_landing_modules_when_requested():
    client = Client()

    response = client.get("/")

    body = response.content
    assert b"Destacados de la jornada" in body
    assert b"L\xc3\xadderes dominicanos" in body  # "Líderes dominicanos" (utf-8)


@pytest.mark.django_db
def test_cms_admin_redirects_to_login_when_anonymous():
    client = Client()

    response = client.get("/cms/")

    assert response.status_code == 302
    assert "/cms/login" in response.headers["Location"]
