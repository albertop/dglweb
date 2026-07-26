"""El refresco diario como una unidad — QA-01 + ARCH-01.

Lo que estos tests protegen es una sola regla, y es la razón de ser del orquestador: **los derivados
no se publican si las entradas no salieron bien.** Los liderazgos son un resultado; publicarlos
calculados sobre insumos rotos es peor que no publicarlos, porque el sitio se ve sano y miente.

Los pasos se simulan con un doble de `call_command`. No es por velocidad: correr los de verdad
probaría que `update_batting` funciona —cosa que ya prueban sus propios tests— y no lo que acá
importa, que es qué DECIDE el orquestador ante un fallo.
"""

from datetime import date
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
