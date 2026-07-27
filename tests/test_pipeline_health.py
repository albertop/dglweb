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


TOKEN = "el-token-del-monitor"


def _pedir() -> Any:
    """Una consulta anónima, como la del monitor de uptime. Recibe el semáforo y nada más."""
    return Client().get(reverse("pipeline_health"))


def _pedir_con_token(settings: Any, token: str = TOKEN) -> Any:
    """Una consulta autorizada, que sí recibe el detalle."""
    settings.PIPELINE_HEALTH_TOKEN = TOKEN
    return Client().get(reverse("pipeline_health"), headers={"x-monitor-token": token})


@pytest.mark.django_db
def test_a_healthy_refresh_answers_200(temporada: SeasonDates) -> None:
    _refresco(IngestRun.Status.SUCCESS)

    respuesta = _pedir()

    assert respuesta.status_code == 200
    assert respuesta.json()["status"] == "ok"


@pytest.mark.django_db
def test_no_refresh_at_all_answers_503(temporada: SeasonDates, settings: Any) -> None:
    """El modo de fallo que ninguna alerta interna puede detectar: no hay nada que consultar."""
    respuesta = _pedir_con_token(settings)

    assert respuesta.status_code == 503
    assert "scheduler" in respuesta.json()["detalle"]


@pytest.mark.django_db
def test_a_stale_refresh_answers_503(temporada: SeasonDates, settings: Any) -> None:
    """Corrió, pero hace demasiado. Es el mismo síntoma que no haber corrido nunca."""
    _refresco(IngestRun.Status.SUCCESS, hace_horas=settings.PIPELINE_STALE_HOURS + 1)

    assert _pedir().status_code == 503


@pytest.mark.django_db
def test_a_refresh_that_finished_partial_answers_503(temporada: SeasonDates, settings: Any) -> None:
    """El otro modo de fallo: corrió y algo salió mal. El detalle lleva los pasos, para el correo."""
    _refresco(IngestRun.Status.PARTIAL, detalle="update_fielding: failed (0 filas)")

    respuesta = _pedir_con_token(settings)

    assert respuesta.status_code == 503
    assert respuesta.json()["pasos"] == ["update_fielding: failed (0 filas)"]


@pytest.mark.django_db
def test_out_of_season_is_healthy_and_not_an_alert(temporada: SeasonDates, settings: Any) -> None:
    """Un 503 diario durante los cinco meses de invierno enseña a ignorar la alerta.

    Y una alerta que se ignora es peor que ninguna, porque da la sensación de estar vigilando.
    """
    SeasonDates.objects.update(is_active=False)

    respuesta = _pedir_con_token(settings)

    assert respuesta.status_code == 200
    assert "Fuera de temporada" in respuesta.json()["detalle"]


# ── Quién ve el detalle ─────────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_an_anonymous_caller_gets_the_light_but_not_the_reasons(temporada: SeasonDates) -> None:
    """El semáforo es público; el detalle no.

    Consultado cada minuto por un tercero, el cuerpo viejo enseñaba qué comandos existen, cuál falló
    y con qué texto de error — y de paso, justo cuándo el sitio está sirviendo datos viejos.
    """
    _refresco(IngestRun.Status.PARTIAL, detalle="update_fielding: failed (0 filas)")

    respuesta = _pedir()

    assert respuesta.status_code == 503  # el monitor sigue enterándose
    assert respuesta.json() == {"status": "error"}  # y nadie más se entera de nada


@pytest.mark.django_db
def test_the_healthy_answer_also_hides_its_numbers(temporada: SeasonDates) -> None:
    """En verde tampoco: las filas escritas y las horas desde el refresco son telemetría."""
    _refresco(IngestRun.Status.SUCCESS)

    assert _pedir().json() == {"status": "ok"}


@pytest.mark.django_db
def test_the_right_token_opens_the_detail(temporada: SeasonDates, settings: Any) -> None:
    _refresco(IngestRun.Status.PARTIAL, detalle="update_fielding: failed (0 filas)")

    cuerpo = _pedir_con_token(settings).json()

    assert cuerpo["pasos"] == ["update_fielding: failed (0 filas)"]


@pytest.mark.django_db
def test_a_wrong_token_is_treated_as_anonymous(temporada: SeasonDates, settings: Any) -> None:
    _refresco(IngestRun.Status.PARTIAL, detalle="update_fielding: failed (0 filas)")

    respuesta = _pedir_con_token(settings, token="el-token-equivocado")

    assert respuesta.status_code == 503
    assert respuesta.json() == {"status": "error"}


@pytest.mark.django_db
def test_without_a_token_configured_nobody_anonymous_sees_detail(temporada: SeasonDates, settings: Any) -> None:
    """El default seguro: sin token puesto, un despiste de configuración no abre la puerta.

    Al revés —tratar «sin token» como «sin restricción»— es el fallo clásico: el sitio sale a
    producción sin la variable y el recorte no protege nada.
    """
    settings.PIPELINE_HEALTH_TOKEN = ""
    _refresco(IngestRun.Status.PARTIAL, detalle="update_fielding: failed (0 filas)")

    respuesta = Client().get(reverse("pipeline_health"), headers={"x-monitor-token": ""})

    assert respuesta.json() == {"status": "error"}


@pytest.mark.django_db
def test_the_backoffice_staff_sees_the_detail_by_their_session(temporada: SeasonDates) -> None:
    """Quien puede entrar al Backoffice ya ve el log de ingesta entero: no hay nada que ocultarle."""
    from django.contrib.auth import get_user_model

    usuario = get_user_model().objects.create_user(username="editora", password="x", is_staff=True)
    _refresco(IngestRun.Status.PARTIAL, detalle="update_fielding: failed (0 filas)")

    cliente = Client()
    cliente.force_login(usuario)
    cuerpo = cliente.get(reverse("pipeline_health")).json()

    assert cuerpo["pasos"] == ["update_fielding: failed (0 filas)"]


@pytest.mark.django_db
def test_the_liveness_probe_stays_independent(temporada: SeasonDates) -> None:
    """`/health` no puede depender de esto: es el healthcheck del contenedor.

    Si el liveness mirara el estado del pipeline, un refresco fallido reiniciaría un proceso web que
    está perfectamente sano — y perder el sitio por un dato viejo es cambiar un problema por otro peor.
    """
    assert _pedir().status_code == 503  # el pipeline está mal…

    assert Client().get("/health").status_code == 200  # …y el contenedor sigue vivo
