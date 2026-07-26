"""`/health/pipeline` — el semáforo que mira un monitor externo.

Existe por el incidente: el scheduler estuvo días sin correr y el log se veía limpio, porque una
AUSENCIA no deja fila que consultar. Un job interno que revisara «¿corrió el pipeline?» habría
corrido en el mismo scheduler roto, así que la vigilancia tiene que vivir afuera — y lo único que
necesita de nosotros es un 200 o un 503.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from dglweb.stats.models import IngestRun, SeasonDates
from dglweb.stats.season_window import MLB


@pytest.fixture
def temporada(db: None) -> SeasonDates:
    return SeasonDates.objects.create(
        season=2026,
        sports_id=MLB,
        season_start_date=date(2026, 1, 1),
        season_end_date=date(2026, 12, 31),
        is_active=True,
    )


def _refresco(estado: str, hace_horas: float = 1, detalle: str = "") -> IngestRun:
    momento = timezone.now() - timedelta(hours=hace_horas)
    return IngestRun.objects.create(
        command="refresh_daily",
        scope="2026-07-26",
        status=estado,
        started_at=momento,
        finished_at=momento,
        rows_affected=417470,
        detail=detalle,
    )


def _pedir() -> Any:
    return Client().get(reverse("pipeline_health"))


@pytest.mark.django_db
def test_a_healthy_refresh_answers_200(temporada: SeasonDates) -> None:
    _refresco(IngestRun.Status.SUCCESS)

    respuesta = _pedir()

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"


@pytest.mark.django_db
def test_no_refresh_at_all_answers_503(temporada: SeasonDates) -> None:
    """El modo de fallo que ninguna alerta interna puede detectar: no hay nada que consultar."""
    respuesta = _pedir()

    assert respuesta.status_code == 503
    assert "scheduler" in respuesta.json()["detalle"]


@pytest.mark.django_db
def test_a_stale_refresh_answers_503(temporada: SeasonDates, settings: Any) -> None:
    """Corrió, pero hace demasiado. Es el mismo síntoma que no haber corrido nunca."""
    _refresco(IngestRun.Status.SUCCESS, hace_horas=settings.PIPELINE_STALE_HOURS + 1)

    assert _pedir().status_code == 503


@pytest.mark.django_db
def test_a_refresh_that_finished_partial_answers_503(temporada: SeasonDates) -> None:
    """El otro modo de fallo: corrió y algo salió mal. El detalle lleva los pasos, para el correo."""
    _refresco(IngestRun.Status.PARTIAL, detalle="update_fielding: failed (0 filas)")

    respuesta = _pedir()

    assert respuesta.status_code == 503
    assert respuesta.json()["pasos"] == ["update_fielding: failed (0 filas)"]


@pytest.mark.django_db
def test_out_of_season_is_healthy_and_not_an_alert(temporada: SeasonDates) -> None:
    """Un 503 diario durante los cinco meses de invierno enseña a ignorar la alerta.

    Y una alerta que se ignora es peor que ninguna, porque da la sensación de estar vigilando.
    """
    SeasonDates.objects.update(is_active=False)

    respuesta = _pedir()

    assert respuesta.status_code == 200
    assert "Fuera de temporada" in respuesta.json()["detalle"]


@pytest.mark.django_db
def test_the_liveness_probe_stays_independent(temporada: SeasonDates) -> None:
    """`/health` no puede depender de esto: es el healthcheck del contenedor.

    Si el liveness mirara el estado del pipeline, un refresco fallido reiniciaría un proceso web que
    está perfectamente sano — y perder el sitio por un dato viejo es cambiar un problema por otro peor.
    """
    assert _pedir().status_code == 503  # el pipeline está mal…

    assert Client().get("/health").status_code == 200  # …y el contenedor sigue vivo
