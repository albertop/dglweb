"""`/health/pipeline` — el semáforo que mira un monitor externo.

Existe por el incidente: el scheduler estuvo días sin correr y el log se veía limpio, porque una
AUSENCIA no deja fila que consultar. Un job interno que revisara «¿corrió el pipeline?» habría
corrido en el mismo scheduler roto, así que la vigilancia tiene que vivir afuera — y lo único que
necesita de nosotros es un 200 o un 503.
"""

from datetime import date, timedelta
from typing import Any

import pytest
from django.conf import settings
from django.core.cache import cache
from django.db.utils import OperationalError
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from dglweb.core.views import HORARIOS
from dglweb.stats.jobs import SIN_VIGILAR, Vigilado
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


def _horario(job: Vigilado, hace_horas: float = 1, estado: str = IngestRun.Status.SUCCESS) -> IngestRun:
    """Una corrida de un job HORARIO. Los alimenta la portada, así que el semáforo los vigila con su
    propio umbral — tres horas, no las treinta del refresco diario.

    El `scope` lleva el alcance del job, y no es adorno: `build_daily_standouts` corre en dos modos
    con el mismo nombre de comando, y lo único que los distingue es ese sufijo. Un ayudante que lo
    escribiera fijo haría pasar las corridas del refresco diario por corridas del job horario — que
    es exactamente el fallo que el alcance viene a cerrar.
    """
    momento = timezone.now() - timedelta(hours=hace_horas)
    return IngestRun.objects.create(
        command=job.comando,
        scope=f"2026-07-27 {job.alcance}".strip(),
        status=estado,
        started_at=momento,
        finished_at=momento,
    )


def _todo_sano(estado: str = IngestRun.Status.SUCCESS) -> None:
    """El pipeline entero al día: el refresco diario y los dos jobs horarios.

    Existe porque desde el v8 «sano» dejó de significar solo «corrió el refresco»: con los líderes o
    el cintillo congelados, la portada enseña dato viejo con cara de fresco y el semáforo tiene que
    encenderse igual.
    """
    _refresco(estado)
    for job in HORARIOS:
        _horario(job)


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
@pytest.mark.parametrize("job", HORARIOS, ids=lambda j: j.comando)
def test_a_stale_hourly_job_turns_the_light_red(temporada: SeasonDates, job: Vigilado) -> None:
    """Aunque el refresco diario esté impecable."""
    _refresco(IngestRun.Status.SUCCESS)
    for otro in HORARIOS:
        # Todos al día menos el que se prueba, que lleva un día entero sin correr.
        _horario(otro, hace_horas=24 if otro == job else 1)

    respuesta = _pedir()

    assert respuesta.status_code == 503, f"{job.comando} atrasado tiene que encender el semáforo"


@pytest.mark.django_db
@pytest.mark.parametrize("job", HORARIOS, ids=lambda j: j.comando)
def test_an_hourly_job_that_only_fails_is_as_bad_as_one_that_does_not_run(
    temporada: SeasonDates, job: Vigilado
) -> None:
    """Se exige una corrida BUENA, no una corrida cualquiera.

    Un job que arranca cada hora y revienta cada hora deja filas recientes en el log; si el semáforo
    solo mirara que existan, estaría verde mientras nada se actualiza.
    """
    _refresco(IngestRun.Status.SUCCESS)
    for otro in HORARIOS:
        _horario(otro, estado=IngestRun.Status.FAILED if otro == job else IngestRun.Status.SUCCESS)

    assert _pedir().status_code == 503


@pytest.mark.django_db
def test_the_hourly_threshold_is_shorter_than_the_daily_one(temporada: SeasonDates, settings: Any) -> None:
    """Dos relojes distintos porque son dos problemas distintos.

    Con el umbral del diario —treinta horas— un cintillo congelado tardaría más de un día en avisar,
    y para entonces la portada lleva un día entero mintiendo.
    """
    assert settings.PIPELINE_HOURLY_STALE_HOURS < settings.PIPELINE_STALE_HOURS

    _refresco(IngestRun.Status.SUCCESS)
    for job in HORARIOS:
        # Cuatro horas: dentro del margen del diario, fuera del margen horario.
        _horario(job, hace_horas=4)

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

    CUÁNTAS faltan es público —es el semáforo, y no dice nada que el 503 no diga ya—; CUÁLES es
    detalle y va detrás del guardia: los nombres cuentan qué apps corren dentro y a qué ritmo se
    despliega. Cambió con SEC-01 del review v9; antes salían para cualquiera.
    """
    from django.db.migrations.executor import MigrationExecutor
    from django.db.migrations.migration import Migration

    falsa = Migration("0042_inventada", "articles")
    monkeypatch.setattr(MigrationExecutor, "migration_plan", lambda self, targets, clean_start=False: [(falsa, False)])

    respuesta = client.get("/ready")

    assert respuesta.status_code == 503
    assert respuesta.json() == {"status": "migraciones pendientes", "pendientes": 1}
    assert "0042_inventada" not in respuesta.content.decode(), "los nombres son detalle"


@pytest.mark.django_db
def test_ready_devuelve_503_si_la_base_no_contesta(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """Un proceso arriba con la base caída devuelve 500 en todas las páginas: no está listo."""
    from django.db import connections

    def revienta(self: object) -> None:
        raise OperationalError("connection refused")

    monkeypatch.setattr(type(connections["default"]), "cursor", revienta)

    respuesta = client.get("/ready")

    assert respuesta.status_code == 503
    # Solo el semáforo: el porqué va a los logs y al operador con token. Ver SEC-01 del review v9.
    assert respuesta.json() == {"status": "error"}


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


# ── `/ready`: el semáforo es público, el diagnóstico no (SEC-01 del review v9) ───────────────────


@pytest.mark.django_db
def test_ready_no_le_cuenta_a_nadie_por_que_fallo(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """El mensaje de un fallo de conexión trae host, puerto, usuario y nombre de base.

    O sea el mapa de la infraestructura, servido a quien golpee la URL justo durante una caída — que
    es cuando menos se está mirando. El semáforo (503) basta para un monitor o un balanceador.
    """

    def revienta(*_: object, **__: object) -> None:
        raise OperationalError('connection to server at "10.0.0.39", port 5432 failed: timeout')

    monkeypatch.setattr("django.db.backends.utils.CursorWrapper.execute", revienta)

    respuesta = client.get("/ready")

    assert respuesta.status_code == 503
    cuerpo = respuesta.json()
    assert cuerpo == {"status": "error"}, "no puede salir nada más que el semáforo"
    assert "10.0.0.39" not in respuesta.content.decode()


@pytest.mark.django_db
def test_ready_si_le_cuenta_al_que_trae_el_token(client: Client, monkeypatch: pytest.MonkeyPatch) -> None:
    """El mismo guardia que `/health/pipeline`, que existía desde el día anterior y este endpoint no
    aplicó. Para el operador el detalle es la mitad del arreglo."""

    def revienta(*_: object, **__: object) -> None:
        raise OperationalError("no se pudo conectar")

    monkeypatch.setattr("django.db.backends.utils.CursorWrapper.execute", revienta)
    monkeypatch.setattr(settings, "PIPELINE_HEALTH_TOKEN", "un-token")

    respuesta = client.get("/ready", headers={"X-Monitor-Token": "un-token"})

    assert respuesta.status_code == 503
    assert "no se pudo conectar" in respuesta.json()["detalle"]


# ── El calendario y la lista vigilada, atados (DEV-01 del review v10) ───────────────────────────


def _jobs_del_calendario() -> dict[str, str]:
    """Los jobs HORARIOS que hay en `ofelia/config.ini`, leídos del archivo de verdad.

    Se lee el archivo que usa producción y no una copia: una copia sería una tercera lista que
    también se puede quedar vieja, y el problema que esto resuelve es justamente ese.

    El horario de Ofelia trae SEIS campos —el primero son segundos— así que la hora es el tercero.
    «Cada hora» es tenerlo en `*`.
    """
    import configparser
    from pathlib import Path

    config = configparser.ConfigParser()
    # `read` no falla si el archivo no está, y un test que pasa porque no leyó nada es peor que uno
    # que falla; de ahí el `read_text` explícito.
    ruta = Path(settings.BASE_DIR) / "ofelia" / "config.ini"
    config.read_string(ruta.read_text(encoding="utf-8"))

    horarios = {}
    for seccion in config.sections():
        if not seccion.startswith("job-exec"):
            continue
        campos = config[seccion]["schedule"].split()
        if len(campos) == 6 and campos[2] == "*":
            # `python manage.py build_daily_standouts --fecha-hoy` -> `build_daily_standouts`
            horarios[seccion] = config[seccion]["command"].split()[2]
    return horarios


def test_todo_job_horario_del_calendario_esta_vigilado() -> None:
    """La prueba que convierte dos listas en una sola.

    El fallo real: entró `daily-standouts-hourly` al calendario y `HORARIOS` se quedó con dos
    comandos. Ninguna prueba lo vio porque todas se parametrizaban desde `HORARIOS` — o sea, desde la
    misma lista incompleta que usaba producción. Verde para siempre, vigilando de menos.

    Por eso ESTA no sale de `HORARIOS`: sale del calendario, que es el que manda.
    """
    del_calendario = set(_jobs_del_calendario().values())
    vigilados = {job.comando for job in HORARIOS} | set(SIN_VIGILAR)

    assert del_calendario, "no se leyó ningún job horario del calendario; la prueba no está probando nada"
    assert del_calendario <= vigilados, (
        f"jobs horarios sin vigilar: {sorted(del_calendario - vigilados)}. "
        "Agrégalos a HORARIOS en stats/jobs.py, o a SIN_VIGILAR con el motivo."
    )


def test_no_se_vigila_un_job_que_ya_no_corre() -> None:
    """El descuadre contrario, que no rompe nada pero avisa de un rojo permanente.

    Un comando vigilado que ya nadie ejecuta no tiene corridas buenas nunca, así que el semáforo se
    queda en 503 para siempre y la alerta se vuelve ruido.
    """
    sobran = ({job.comando for job in HORARIOS} | set(SIN_VIGILAR)) - set(_jobs_del_calendario().values())

    assert not sobran, f"vigilados pero fuera del calendario: {sorted(sobran)}"


def test_los_estados_sanos_existen_de_verdad() -> None:
    """`stats/jobs.py` no importa los modelos —a propósito, para poder leerse desde donde sea— así
    que los estados van como texto. Esto es lo que impide que un typo pase por «sano»: un estado que
    no existe no lo tiene ninguna fila, y el job quedaría en rojo permanente."""
    validos = set(IngestRun.Status.values)

    for job in HORARIOS:
        assert set(job.sanos) <= validos, f"{job.comando} declara estados que no existen: {job.sanos}"


def test_solo_los_destacados_aceptan_un_salto_como_sano() -> None:
    """El permiso es de UNO, y conviene que ampliarlo cueste tocar este test.

    `SKIPPED` cuenta como sano en `build_daily_standouts` porque «ningún juego ha terminado todavía»
    es la respuesta correcta a media mañana. En los otros dos un salto significa que el job decidió
    no trabajar, y eso sí hay que mirarlo.
    """
    con_permiso = {job.comando for job in HORARIOS if IngestRun.Status.SKIPPED in job.sanos}

    assert con_permiso == {"build_daily_standouts"}


# ── `/health/proxy`: ¿puede el sitio hablar con el proxy? (2026-07-29) ──────────────────────────
#
# Nace del incidente: el proxy de dev llevaba horas caído —cinco reinicios del servidor sin política
# que lo levantara— y el fallo apareció en el correo del refresco de la mañana. Un monitor lo habría
# dicho a los cinco minutos.


def _proxy(monkeypatch: pytest.MonkeyPatch, *, respuesta: Any = None, error: Exception | None = None) -> None:
    """Sustituye la llamada al proxy. En los tests no se sale a la red."""
    import httpx

    def falso(url: str, timeout: float = 0) -> Any:
        if error is not None:
            raise error
        return respuesta

    monkeypatch.setattr(httpx, "get", falso)


class _Respuesta:
    def __init__(self, codigo: int, cuerpo: dict[str, Any] | None = None) -> None:
        self.status_code = codigo
        self._cuerpo = cuerpo or {}

    def json(self) -> dict[str, Any]:
        return self._cuerpo


@pytest.mark.django_db
def test_con_el_proxy_vivo_el_semaforo_esta_verde(monkeypatch: pytest.MonkeyPatch) -> None:
    _proxy(monkeypatch, respuesta=_Respuesta(200, {"status": "alive", "version": "1.2026.12"}))

    respuesta = Client().get(reverse("proxy_health"))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


@pytest.mark.django_db
def test_si_el_proxy_no_responde_el_semaforo_se_pone_rojo(monkeypatch: pytest.MonkeyPatch) -> None:
    """El caso real del 2026-07-29: el contenedor parado y nada escuchando en el puerto."""
    import httpx

    _proxy(monkeypatch, error=httpx.ConnectError("Connection refused"))

    assert Client().get(reverse("proxy_health")).status_code == 503


@pytest.mark.django_db
def test_un_proxy_que_contesta_mal_tambien_cuenta_como_roto(monkeypatch: pytest.MonkeyPatch) -> None:
    """Responder no es estar sano: un 502 del propio proxy es tan inútil como no responder."""
    _proxy(monkeypatch, respuesta=_Respuesta(502))

    assert Client().get(reverse("proxy_health")).status_code == 503


@pytest.mark.django_db
def test_el_detalle_no_es_para_cualquiera(monkeypatch: pytest.MonkeyPatch, settings: Any) -> None:
    """Mismo trato que `/health/pipeline`: el semáforo es público, el detalle no.

    El detalle lleva la URL interna del proxy — nombre de contenedor y puerto — que es
    reconocimiento operativo gratis para quien pregunte cada minuto.
    """
    import httpx

    _proxy(monkeypatch, error=httpx.ConnectError("Connection refused"))

    anonimo = Client().get(reverse("proxy_health"))
    assert anonimo.json() == {"status": "error"}

    settings.PIPELINE_HEALTH_TOKEN = TOKEN
    con_token = Client().get(reverse("proxy_health"), headers={"x-monitor-token": TOKEN})
    assert "No se pudo alcanzar el proxy" in con_token.json()["detalle"]


@pytest.mark.django_db
def test_se_pregunta_por_live_y_no_por_health(monkeypatch: pytest.MonkeyPatch) -> None:
    """`/health` del proxy va a la API de MLB en CADA llamada.

    Un monitor cada minuto serían 1.440 peticiones diarias a MLB solo para saber si un contenedor
    está vivo — y encima se pondría rojo durante un corte de MLB, que ni podemos arreglar ni tiene
    que despertar a nadie. `/live` no sale a la red.
    """
    import httpx

    pedidas: list[str] = []

    def falso(url: str, timeout: float = 0) -> Any:
        pedidas.append(url)
        return _Respuesta(200, {"status": "alive"})

    monkeypatch.setattr(httpx, "get", falso)
    Client().get(reverse("proxy_health"))

    assert pedidas and pedidas[0].endswith("/live"), pedidas


# ── `/health/adserver`: ¿entrega anuncios Revive? (2026-07-29) ──────────────────────────────────
#
# VA AL REVÉS QUE EL DE ARRIBA, y esa es toda la gracia. Al proxy de MLB lo consume EL SITIO desde el
# servidor, así que ahí lo que importa es el camino interno. A Revive lo consume **el navegador del
# visitante**, dentro de un `iframe`. Un monitor que preguntara por la red de Docker podría estar
# verde con el certificado caducado o el subdominio mal apuntado, y ningún visitante vería un
# anuncio.


class _Texto:
    """Una respuesta con cuerpo de texto — la entrega de Revive es JavaScript, no JSON."""

    def __init__(self, codigo: int, cuerpo: str = "") -> None:
        self.status_code = codigo
        self.text = cuerpo


# Lo que devuelve Revive de verdad, recortado. Medido contra producción: 395 bytes que empiezan así
# incluso cuando NO hay campaña que entregar.
ENTREGA = "var OX_3ce35e19 = '';\nOX_3ce35e19 += \"<\"+\"div id='beacon_833e8a3d15'\""


@pytest.mark.django_db
def test_con_revive_entregando_el_semaforo_esta_verde(monkeypatch: pytest.MonkeyPatch) -> None:
    _proxy(monkeypatch, respuesta=_Texto(200, ENTREGA))
    monkeypatch.setattr(settings, "ADSERVER_URL", "https://promo.example.test")

    respuesta = Client().get(reverse("adserver_health"))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "ok"}


@pytest.mark.django_db
def test_sin_campana_vendida_sigue_verde(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un hueco sin nada que entregar NO es una avería, y no puede sonar de madrugada.

    Revive responde 200 con `var OX_… = ''` cuando no tiene banner para esa zona. Es el estado normal
    de un sitio que arranca sin anunciantes, y confundirlo con una caída convertiría el monitor en
    ruido que nadie mira.
    """
    _proxy(monkeypatch, respuesta=_Texto(200, "var OX_3ce35e19 = '';\n"))
    monkeypatch.setattr(settings, "ADSERVER_URL", "https://promo.example.test")

    assert Client().get(reverse("adserver_health")).status_code == 200


@pytest.mark.django_db
def test_un_200_que_no_es_la_entrega_cuenta_como_roto(monkeypatch: pytest.MonkeyPatch) -> None:
    """LA PRUEBA QUE JUSTIFICA MIRAR EL CUERPO Y NO SOLO EL CÓDIGO.

    Este montaje ya se rompió así: el instalador de Revive pidiendo configuración, y una página de
    error de nginx. Las dos responden **200**. Un monitor que solo mirara el código estaría verde con
    el adserver sin servir un anuncio.
    """
    _proxy(monkeypatch, respuesta=_Texto(200, "<html><body>Revive Adserver Installer</body></html>"))
    monkeypatch.setattr(settings, "ADSERVER_URL", "https://promo.example.test")

    assert Client().get(reverse("adserver_health")).status_code == 503


@pytest.mark.django_db
def test_si_revive_no_responde_el_semaforo_se_pone_rojo(monkeypatch: pytest.MonkeyPatch) -> None:
    import httpx

    _proxy(monkeypatch, error=httpx.ConnectError("Connection refused"))
    monkeypatch.setattr(settings, "ADSERVER_URL", "https://promo.example.test")

    assert Client().get(reverse("adserver_health")).status_code == 503


@pytest.mark.django_db
def test_fuera_de_produccion_sin_adserver_no_es_un_fallo(monkeypatch: pytest.MonkeyPatch) -> None:
    """En desarrollo los anuncios están apagados y eso es lo normal, no una avería."""
    monkeypatch.setattr(settings, "ADSERVER_URL", "")

    respuesta = Client().get(reverse("adserver_health"))

    assert respuesta.status_code == 200
    assert respuesta.json() == {"status": "apagado"}


@pytest.mark.django_db
def test_en_produccion_sin_adserver_si_es_un_fallo(monkeypatch: pytest.MonkeyPatch) -> None:
    """EL FALLO SILENCIOSO DE ESTE MONTAJE, y la razón de que este endpoint exista.

    `ADSERVER_URL` se declara en Portainer en DOS sitios: la sustitución `${...}` del compose y el
    bloque `environment:`. Si falta en el segundo, el contenedor arranca sin ella, la portada carga
    perfecta, y **los huecos de anuncio salen en blanco sin un solo error en ningún registro**. Es
    exactamente el tipo de fallo que este proyecto lleva todo el mes persiguiendo: la configuración
    se ve bien, nada se queja, y se descubre semanas después.
    """
    monkeypatch.setattr(settings, "ADSERVER_URL", "")
    # Así es como `notify.entorno()` distingue los dos entornos: por el módulo de settings y no por
    # una variable propia, precisamente porque una variable se puede olvidar y el módulo no.
    monkeypatch.setenv("DJANGO_SETTINGS_MODULE", "config.settings.prod")

    assert Client().get(reverse("adserver_health")).status_code == 503
