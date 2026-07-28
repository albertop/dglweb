"""El refresco diario como una unidad — QA-01 + ARCH-01.

Lo que estos tests protegen es una sola regla, y es la razón de ser del orquestador: **los derivados
no se publican si las entradas no salieron bien.** Los liderazgos son un resultado; publicarlos
calculados sobre insumos rotos es peor que no publicarlos, porque el sitio se ve sano y miente.

Los pasos se simulan con un doble de `call_command`. No es por velocidad: correr los de verdad
probaría que `update_batting` funciona —cosa que ya prueban sus propios tests— y no lo que acá
importa, que es qué DECIDE el orquestador ante un fallo.
"""

from datetime import date
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.utils import timezone

from dglweb.stats import pipeline
from dglweb.stats.models import IngestRun, SeasonDates
from dglweb.stats.season_window import MLB


@pytest.fixture
def temporada(db: None) -> SeasonDates:
    """2026 abierta de par en par: regular en curso y postemporada ya empezada."""
    return SeasonDates.objects.create(
        season=2026,
        sports_id=MLB,
        season_start_date=date(2026, 1, 1),
        reg_season_end_date=date(2026, 12, 20),
        post_season_start_date=date(2026, 1, 2),
        season_end_date=date(2026, 12, 31),
        is_active=True,
    )


@pytest.fixture
def falso_call_command(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Sustituye cada paso por una fila en el log, con el estado que el test pida.

    Devuelve un dict de control: `estados` decide qué escribe cada comando, y `corridos` registra el
    orden real en que se llamaron — que es la mitad de lo que hay que verificar.
    """
    control: dict[str, Any] = {"estados": {}, "corridos": []}

    def falso(comando: str, *args: Any, **kwargs: Any) -> None:
        control["corridos"].append(comando)
        if comando in pipeline.MANTENIMIENTO:
            return  # el mantenimiento no registra corrida propia en este doble
        estado = control["estados"].get(comando, IngestRun.Status.SUCCESS)
        ahora = timezone.now()
        IngestRun.objects.create(
            command=comando,
            scope="test",
            status=estado,
            started_at=ahora,
            finished_at=ahora,
            rows_affected=10,
            detail="" if estado == IngestRun.Status.SUCCESS else "algo salió mal",
        )

    monkeypatch.setattr(pipeline, "call_command", falso)
    return control


# ── La regla que da sentido al orquestador ──────────────────────────────────────────────────────


@pytest.mark.django_db
def test_with_every_input_healthy_the_derived_tables_are_rebuilt(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    resultado = pipeline.run_daily()

    assert resultado.derivados_publicados is True
    cola = [*pipeline.DERIVADOS, *pipeline.PORTADA, *pipeline.AVISOS]
    assert falso_call_command["corridos"][-len(cola) :] == cola


@pytest.mark.django_db
def test_a_failed_input_stops_the_rebuild_instead_of_publishing_mixed_data(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    """El caso del finding: `build_leaders` corría a las 7:30 aunque el fildeo hubiera fallado.

    Sin reconstruir, el sitio sigue mostrando los liderazgos de ayer — viejos, pero coherentes. Con
    reconstruir, muestra unos nuevos calculados sobre bateo de hoy y fildeo de ayer, y no hay forma
    de que el lector lo sepa.
    """
    falso_call_command["estados"]["update_fielding"] = IngestRun.Status.FAILED

    resultado = pipeline.run_daily()

    assert resultado.derivados_publicados is False
    assert not set(pipeline.DERIVADOS) & set(falso_call_command["corridos"])
    assert [p.comando for p in resultado.fallidos] == ["update_fielding"]


@pytest.mark.django_db
def test_a_partial_input_also_stops_the_rebuild(temporada: SeasonDates, falso_call_command: dict[str, Any]) -> None:
    """PARTIAL no es éxito: un refresco a medias produce derivados a medias, que es el mismo daño."""
    falso_call_command["estados"]["update_batting"] = IngestRun.Status.PARTIAL

    assert pipeline.run_daily().derivados_publicados is False


@pytest.mark.django_db
def test_publishing_with_broken_inputs_takes_an_explicit_flag(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    """Se puede publicar parcial, pero hay que pedirlo — nunca es lo que pasa por defecto."""
    falso_call_command["estados"]["update_fielding"] = IngestRun.Status.FAILED

    resultado = pipeline.run_daily(publicar_parcial=True)

    assert resultado.derivados_publicados is True
    assert resultado.fallidos  # sigue reportándose como día con fallos


@pytest.mark.django_db
def test_all_inputs_are_attempted_even_after_the_first_failure(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    """Abortar en el primer error dejaría sin saber si el problema es uno o son tres."""
    falso_call_command["estados"]["update_batting"] = IngestRun.Status.FAILED
    falso_call_command["estados"]["update_pitching"] = IngestRun.Status.FAILED

    resultado = pipeline.run_daily()

    assert set(pipeline.ENTRADAS) <= set(falso_call_command["corridos"])
    assert len(resultado.fallidos) == 2


@pytest.mark.django_db
def test_a_step_that_leaves_no_row_counts_as_failed(temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch) -> None:
    """De un paso del que no sabemos nada no se puede asumir que salió bien.

    Es exactamente lo que pasó en producción: Ofelia no lograba arrancar los jobs, no había filas, y
    el log limpio se leía como «todo en orden».
    """
    monkeypatch.setattr(pipeline, "call_command", lambda *a, **k: None)

    resultado = pipeline.run_daily()

    assert resultado.derivados_publicados is False
    assert all("no dejó fila" in p.error for p in resultado.fallidos)


# ── La ventana de temporada, evaluada una sola vez ──────────────────────────────────────────────


@pytest.mark.django_db
def test_out_of_season_the_whole_pipeline_skips_with_a_single_row(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    """Una fila `skipped`, no once. En invierno, once por día convierten el log en ruido."""
    SeasonDates.objects.update(is_active=False)

    pipeline.run_and_record()

    saltados = IngestRun.objects.filter(status=IngestRun.Status.SKIPPED)
    assert [f.command for f in saltados] == ["refresh_daily"]


@pytest.mark.django_db
def test_out_of_season_run_daily_runs_nothing_and_says_why(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    """El corte está en `run_daily`, no solo en el envoltorio que registra.

    Importa porque `run_daily` también se llama directo —desde un shell, o desde otro comando— y ahí
    no hay `run_and_record` que lo frene antes. Sin el corte propio, correría los once pasos en
    enero.
    """
    SeasonDates.objects.update(is_active=False)

    resultado = pipeline.run_daily()

    assert resultado.motivo_salto
    assert resultado.pasos == []
    assert falso_call_command["corridos"] == []


@pytest.mark.django_db
def test_the_october_steps_wait_for_october(temporada: SeasonDates, falso_call_command: dict[str, Any]) -> None:
    """Regular abierta y postemporada todavía no: los tres `*_post` no se corren."""
    SeasonDates.objects.update(post_season_start_date=date(2026, 12, 15))

    pipeline.run_daily()

    assert not set(pipeline.ENTRADAS_POST) & set(falso_call_command["corridos"])
    assert set(pipeline.ENTRADAS) <= set(falso_call_command["corridos"])


@pytest.mark.django_db
def test_log_pruning_runs_even_out_of_season(temporada: SeasonDates, falso_call_command: dict[str, Any]) -> None:
    """Podar es higiene, no pelota. Y va al final, para incluir lo que este refresco acaba de escribir."""
    SeasonDates.objects.update(is_active=False)

    pipeline.run_and_record()

    assert falso_call_command["corridos"] == list(pipeline.MANTENIMIENTO)


# ── La fila agregada, que es la entidad que no existía ──────────────────────────────────────────


@pytest.mark.django_db
def test_the_day_gets_one_row_that_says_how_it_went(temporada: SeasonDates, falso_call_command: dict[str, Any]) -> None:
    """`IngestRun` daba observabilidad por comando; faltaba «el refresco del 26 de julio»."""
    pipeline.run_and_record()

    fila = IngestRun.objects.get(command="refresh_daily")
    assert fila.status == IngestRun.Status.SUCCESS
    etapas = (pipeline.ENTRADAS, pipeline.ENTRADAS_POST, pipeline.DERIVADOS, pipeline.PORTADA, pipeline.AVISOS)
    assert fila.rows_affected == 10 * sum(len(etapa) for etapa in etapas)
    assert "update_batting" in fila.detail and "build_leaders" in fila.detail


@pytest.mark.django_db
def test_a_day_with_failures_is_marked_partial_and_names_them(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    """Que se vea rojo en el Backoffice sin abrir el detalle es la mitad del valor."""
    falso_call_command["estados"]["update_fielding"] = IngestRun.Status.FAILED

    pipeline.run_and_record()

    fila = IngestRun.objects.get(command="refresh_daily")
    assert fila.status == IngestRun.Status.PARTIAL
    assert "update_fielding" in fila.detail
    assert "Derivados NO reconstruidos" in fila.detail


@pytest.mark.django_db
def test_the_command_runs_end_to_end(temporada: SeasonDates, falso_call_command: dict[str, Any]) -> None:
    """El comando de verdad, con su parseo de argumentos."""
    call_command("refresh_daily")

    assert IngestRun.objects.filter(command="refresh_daily", status=IngestRun.Status.SUCCESS).exists()


@pytest.mark.django_db
def test_the_aggregate_row_opens_before_the_work_not_after(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    """Registrarla al final daba 0s de duración para hora y media de trabajo.

    Y peor: los pasos quedaban FUERA de la ventana temporal de su propia corrida, así que «qué pasó
    en el refresco de hoy» no se podía contestar por fechas. `record_run` existe justamente para que
    una corrida en curso —o colgada— se vea mientras pasa.
    """
    marcas: list[str] = []

    def espiar(comando: str, *args: Any, **kwargs: Any) -> None:
        fila = IngestRun.objects.filter(command="refresh_daily").first()
        marcas.append(f"{comando}:{fila.status if fila else 'sin-fila'}")

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(pipeline, "call_command", espiar)
    try:
        pipeline.run_and_record()
    finally:
        monkeypatch.undo()

    # Mientras corría el primer paso, la fila del día ya existía y estaba en curso.
    assert marcas[0] == f"{pipeline.ENTRADAS[0]}:{IngestRun.Status.RUNNING}"


# ── El paso que revienta ────────────────────────────────────────────────────────────────────────
#
# Distinto del paso que falla ordenadamente: acá el comando lanza una excepción y nunca vuelve. Si
# `_correr` la dejara propagar, el primer error abortaría el refresco entero y los seis pasos que
# vienen detrás no se intentarían — que es justo lo contrario de la regla de este módulo.


@pytest.mark.django_db
def test_a_step_that_explodes_does_not_take_the_refresh_down_with_it(
    temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch
) -> None:
    """La excepción de un paso es un dato del refresco, no una interrupción.

    Y el mensaje de la excepción tiene que sobrevivir al reporte: sin él, el paso queda como «no dejó
    fila en el log», que manda a buscar un problema de registro cuando lo que hubo fue un error.
    """
    revienta = pipeline.ENTRADAS[1]

    def falso(comando: str, *args: Any, **kwargs: Any) -> None:
        if comando == revienta:
            raise RuntimeError("el proxy contestó 500")

    monkeypatch.setattr(pipeline, "call_command", falso)
    lineas: list[str] = []

    resultado = pipeline.run_daily(note=lineas.append)

    reventado = next(p for p in resultado.pasos if p.comando == revienta)
    assert reventado.estado == IngestRun.Status.FAILED
    assert "RuntimeError: el proxy contestó 500" in reventado.error
    # Y sale marcado en el log del scheduler mientras pasa, no solo en el resumen del final.
    assert any(f"✗ {revienta}" in linea for linea in lineas)
    # Y lo que importa de verdad: los pasos posteriores igual se intentaron.
    assert [p.comando for p in resultado.pasos] == [
        *pipeline.ENTRADAS,
        *pipeline.ENTRADAS_POST,
        *pipeline.PORTADA,
        *pipeline.AVISOS,
    ]


@pytest.mark.django_db
def test_when_the_step_logged_its_own_error_the_exception_does_not_overwrite_it(
    temporada: SeasonDates, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El comando sabe mejor que nosotros por qué falló.

    Si alcanzó a escribir su fila con el detalle —«el equipo BOS no existe en 1899»— ese texto es más
    útil que el `RuntimeError` genérico con el que terminó reventando, así que se respeta.
    """
    revienta = pipeline.ENTRADAS[0]

    def falso(comando: str, *args: Any, **kwargs: Any) -> None:
        if comando != revienta:
            return
        ahora = timezone.now()
        IngestRun.objects.create(
            command=comando,
            scope="test",
            status=IngestRun.Status.PARTIAL,
            started_at=ahora,
            finished_at=ahora,
            detail="el equipo BOS no existe en 1899",
        )
        raise RuntimeError("y después reventó")

    monkeypatch.setattr(pipeline, "call_command", falso)

    paso = next(p for p in pipeline.run_daily().pasos if p.comando == revienta)

    assert paso.error == "el equipo BOS no existe en 1899"
    assert paso.estado == IngestRun.Status.FAILED  # el estado sí lo pisa: reventar es fallar


# ── Lo que el scheduler ve por consola ──────────────────────────────────────────────────────────
#
# El comando manda esto al log del contenedor. Es lo único que queda de un refresco que salió mal a
# las 4:30 de la mañana si nadie abre el Backoffice, así que el fallo tiene que verse ahí.


@pytest.mark.django_db
def test_the_command_prints_the_failed_steps_to_stderr(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    """Por `stderr` y no por `stdout`: un log que mezcla el resumen bueno con el malo se lee igual."""
    falso_call_command["estados"]["update_fielding"] = IngestRun.Status.FAILED
    salida, errores = StringIO(), StringIO()

    call_command("refresh_daily", stdout=salida, stderr=errores)

    assert "Refresco con fallos" in errores.getvalue()
    assert "update_fielding" in errores.getvalue()  # cuál falló, no solo que hubo fallos
    assert "Refresco completo" not in salida.getvalue()


@pytest.mark.django_db
def test_the_command_says_it_did_not_run_instead_of_reporting_zero_steps(
    temporada: SeasonDates, falso_call_command: dict[str, Any]
) -> None:
    """Fuera de temporada, «0/0 pasos · 0 filas» se lee como un refresco que corrió y no encontró nada."""
    SeasonDates.objects.update(is_active=False)
    salida = StringIO()

    call_command("refresh_daily", stdout=salida)

    assert "Sin correr" in salida.getvalue()
    assert "pasos" not in salida.getvalue()


def test_todos_los_pasos_del_refresco_aceptan_lo_que_el_pipeline_les_pasa() -> None:
    """El fallo del 2026-07-28, convertido en prueba.

    `build_team_games` se sumó a las ENTRADAS sin declarar `--force`, y el pipeline llama a TODOS sus
    pasos con esa bandera. El `call_command` reventó con `TypeError` antes de ejecutar nada.

    Y el daño no se quedó en ese paso: al ser una entrada, su fallo dejó los derivados sin
    reconstruir y el sitio publicó los liderazgos de ayer. O sea que un argumento que falta en un
    comando nuevo apaga la actualización del sitio entero.

    Esta prueba recorre los pasos de verdad —no una lista copiada— y comprueba que cada uno declara
    lo que se le va a pasar. Es barata y cierra la clase entera de fallo, no solo este caso.
    """
    from django.core.management import get_commands, load_command_class

    from dglweb.stats import pipeline

    # Los que pasan por `_correr`, que es quien añade `--force`. `MANTENIMIENTO` queda FUERA a
    # propósito: se invoca con `call_command(comando)` a secas porque corre también fuera de
    # temporada, así que no necesita la bandera ni debe exigirla. Lo descubrió esta misma prueba, que
    # en su primera versión lo incluía y señalaba a `prune_ingest_log` como roto sin estarlo.
    pasos = [
        *pipeline.ENTRADAS,
        *pipeline.ENTRADAS_POST,
        *pipeline.DERIVADOS,
        *pipeline.PORTADA,
        *pipeline.AVISOS,
    ]
    comandos = get_commands()
    sin_force = []
    for nombre in pasos:
        assert nombre in comandos, f"{nombre} no existe como comando"
        parser = load_command_class(comandos[nombre], nombre).create_parser("manage.py", nombre)
        opciones = {accion.dest for accion in parser._actions}
        if "force" not in opciones:
            sin_force.append(nombre)

    assert not sin_force, f"el pipeline los llama con --force y no lo declaran: {sin_force}"
