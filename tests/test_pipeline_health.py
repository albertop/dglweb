"""`/health/pipeline` — el semáforo que mira un monitor externo.

Existe por el incidente: el scheduler estuvo días sin correr y el log se veía limpio, porque una
AUSENCIA no deja fila que consultar. Un job interno que revisara «¿corrió el pipeline?» habría
corrido en el mismo scheduler roto, así que la vigilancia tiene que vivir afuera — y lo único que
necesita de nosotros es un 200 o un 503.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from django.core.cache import cache
from django.db.utils import OperationalError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from dglweb.core.views import HORARIOS
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


def _horario(comando: str, hace_horas: float = 1, estado: str = IngestRun.Status.SUCCESS) -> IngestRun:
    """Una corrida de un job HORARIO. Los alimenta la portada, así que el semáforo los vigila con su
    propio umbral — tres horas, no las treinta del refresco diario."""
    momento = timezone.now() - timedelta(hours=hace_horas)
    return IngestRun.objects.create(
        command=comando, scope="2026-07-27", status=estado, started_at=momento, finished_at=momento
    )


def _todo_sano(estado: str = IngestRun.Status.SUCCESS) -> None:
    """El pipeline entero al día: el refresco diario y los dos jobs horarios.

    Existe porque desde el v8 «sano» dejó de significar solo «corrió el refresco»: con los líderes o
    el cintillo congelados, la portada enseña dato viejo con cara de fresco y el semáforo tiene que
    encenderse igual.
    """
    _refresco(estado)
    for comando in HORARIOS:
        _horario(comando)


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
    _todo_sano()

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
    _todo_sano()

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


# ── QA-01 + ARCH-01: los jobs horarios ──────────────────────────────────────────────────────────
#
# El semáforo miraba solo el refresco diario. Un `build_mlb_leaders` o un `update_roster_moves`
# fallando seis horas dejaba la portada con líderes viejos y el cintillo congelado, y el monitor en
# verde. Es peor que un 503: un módulo «vivo» que enseña dato de ayer no parece roto, parece que no
# pasó nada.


@pytest.mark.django_db
@pytest.mark.parametrize("comando", HORARIOS)
def test_a_stale_hourly_job_turns_the_light_red(temporada: SeasonDates, comando: str) -> None:
    """Aunque el refresco diario esté impecable."""
    _refresco(IngestRun.Status.SUCCESS)
    for otro in HORARIOS:
        # Todos al día menos el que se prueba, que lleva un día entero sin correr.
        _horario(otro, hace_horas=24 if otro == comando else 1)

    respuesta = _pedir()

    assert respuesta.status_code == 503, f"{comando} atrasado tiene que encender el semáforo"


@pytest.mark.django_db
@pytest.mark.parametrize("comando", HORARIOS)
def test_an_hourly_job_that_only_fails_is_as_bad_as_one_that_does_not_run(
    temporada: SeasonDates, comando: str
) -> None:
    """Se exige una corrida BUENA, no una corrida cualquiera.

    Un job que arranca cada hora y revienta cada hora deja filas recientes en el log; si el semáforo
    solo mirara que existan, estaría verde mientras nada se actualiza.
    """
    _refresco(IngestRun.Status.SUCCESS)
    for otro in HORARIOS:
        _horario(otro, estado=IngestRun.Status.FAILED if otro == comando else IngestRun.Status.SUCCESS)

    assert _pedir().status_code == 503


@pytest.mark.django_db
def test_the_hourly_threshold_is_shorter_than_the_daily_one(temporada: SeasonDates, settings: Any) -> None:
    """Dos relojes distintos porque son dos problemas distintos.

    Con el umbral del diario —treinta horas— un cintillo congelado tardaría más de un día en avisar,
    y para entonces la portada lleva un día entero mintiendo.
    """
    assert settings.PIPELINE_HOURLY_STALE_HOURS < settings.PIPELINE_STALE_HOURS

    _refresco(IngestRun.Status.SUCCESS)
    for comando in HORARIOS:
        # Cuatro horas: dentro del margen del diario, fuera del margen horario.
        _horario(comando, hace_horas=4)

    assert _pedir().status_code == 503


@pytest.mark.django_db
def test_out_of_season_the_hourly_jobs_do_not_raise_an_alarm(temporada: SeasonDates) -> None:
    """En invierno no hay líderes que recalcular ni movimientos que traer. Un 503 diario durante
    cinco meses enseña a ignorar la alerta, que es la peor manera de tener una."""
    SeasonDates.objects.update(is_active=False)

    assert _pedir().status_code == 200


# ── SEC-01: la respuesta anónima se cachea ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_anonymous_answer_is_cached_and_stops_hitting_the_database(temporada: SeasonDates) -> None:
    """El endpoint es público a propósito, así que cualquiera puede pedirlo en bucle.

    Con la caché, la segunda petición no consulta nada: solo devuelve lo guardado.
    """
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    _todo_sano()
    cache.clear()

    _pedir()  # la primera llena la caché
    with CaptureQueriesContext(connection) as capturadas:
        segunda = _pedir()

    assert segunda.status_code == 200
    assert len(capturadas) == 0, "la respuesta cacheada no debería tocar la base"


@pytest.mark.django_db
def test_the_detailed_answer_is_never_served_from_cache(temporada: SeasonDates, settings: Any) -> None:
    """Quien pide el detalle es una persona mirando qué se rompió: necesita el estado de AHORA.

    Y al revés importa igual: una respuesta detallada no puede quedar guardada donde la recoja el
    siguiente anónimo.
    """
    _todo_sano()
    cache.clear()

    _pedir_con_token(settings)
    guardado = cache.get("health:pipeline")

    assert guardado is None, "el detalle no se cachea, ni para sí mismo ni para el anónimo siguiente"


@pytest.mark.django_db
def test_a_cached_healthy_light_does_not_leak_detail(temporada: SeasonDates) -> None:
    """Lo cacheado es el semáforo, no el cuerpo: si guardáramos la respuesta entera, el detalle del
    primer consultante autorizado se le serviría al siguiente anónimo."""
    _todo_sano()
    cache.clear()

    _pedir()
    cuerpo = _pedir().json()

    assert cuerpo == {"status": "ok"}


# ── /ready — readiness, que no es lo mismo que liveness ──────────────────────────────────────────


@pytest.mark.django_db
def test_ready_responde_ok_con_la_base_al_dia(client: Client) -> None:
    respuesta = client.get("/ready")
    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


@pytest.mark.django_db
def test_ready_avisa_de_las_migraciones_que_faltan(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """El fallo que se gana el endpoint: imagen nueva y `migrate` que no corrió.

    No se ve desde fuera. La base contesta, el proceso arranca, la portada carga — y revienta la
    primera página que toque la columna nueva. Un `SELECT 1` diría que todo está bien, y por eso el
    readiness mira el grafo de migraciones y no solo la conexión.

    Y las NOMBRA: «faltan 3 migraciones» manda a buscar cuáles, y saberlo es la mitad del arreglo.
    """
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.migration import Migration

    falsa = Migration("0042_inventada", "articles")
    monkeypatch.setattr(MigrationExecutor, "migration_plan", lambda self, targets, clean_start=False: [(falsa, False)])

    respuesta = client.get("/ready")

    assert respuesta.status_code == 503
    assert respuesta.json()["faltan"] == ["articles.0042_inventada"]


@pytest.mark.django_db
def test_ready_devuelve_503_si_la_base_no_contesta(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un proceso arriba con la base caída devuelve 500 en todas las páginas: no está listo."""
    from django.db import connections

    def revienta(self: object) -> None:
        raise OperationalError("connection refused")

    monkeypatch.setattr(type(connections["default"]), "cursor", revienta)

    respuesta = client.get("/ready")

    assert respuesta.status_code == 503
    assert "connection refused" in respuesta.json()["detalle"]


@pytest.mark.django_db
def test_health_no_toca_la_base(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """La otra mitad del acuerdo, y la razón de que sean dos endpoints.

    `/health` lo mira el healthcheck del contenedor. Si consultara la base, un parpadeo de Postgres
    reiniciaría un proceso web sano — empeorar una caída de la base tirando además la aplicación.
    Con la base rota a propósito, este tiene que seguir diciendo que sí.
    """
    from django.db import connections

    def revienta(self: object) -> None:
        raise OperationalError("connection refused")

    monkeypatch.setattr(type(connections["default"]), "cursor", revienta)

    assert client.get("/health").status_code == 200
