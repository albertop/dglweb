"""La puerta que decide si un job del scheduler corre hoy.

El scheduler despierta los doce meses del año, pero la pelota se juega en siete. Fuera de temporada
cada job era un viaje al proxy para traer lo mismo que ayer, y una reconstrucción de 400.000
liderazgos idéntica a la del día anterior.

Lo que estos tests cuidan no es tanto que se salte —eso es fácil— sino los dos bordes donde saltarse
de más cuesta caro: el último día de la temporada, cuyos juegos se raspan al día SIGUIENTE, y el caso
de que nadie haya marcado la temporada nueva.
"""

from datetime import date

import pytest
from django.core.management import call_command

from dglweb.stats import season_window
from dglweb.stats.models import IngestRun, SeasonDates


@pytest.fixture
def temporada(db: None) -> SeasonDates:
    """2026: del 25 de marzo al 31 de octubre, marcada como en curso."""
    return SeasonDates.objects.create(
        season=2026,
        sports_id=season_window.MLB,
        season_start_date=date(2026, 3, 25),
        season_end_date=date(2026, 10, 31),
        is_active=True,
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("dia", "corre"),
    [
        (date(2026, 3, 24), False),  # víspera
        (date(2026, 3, 25), True),  # día inaugural
        (date(2026, 7, 26), True),  # mitad de temporada
        (date(2026, 10, 31), True),  # último día
        (date(2026, 11, 2), True),  # dentro de la gracia: los juegos del cierre se raspan después
        (date(2026, 11, 4), False),  # pasada la gracia
    ],
)
def test_the_window_opens_and_closes_where_the_season_does(temporada: SeasonDates, dia: date, corre: bool) -> None:
    assert season_window.evaluate(on=dia).corre is corre


@pytest.mark.django_db
def test_the_last_day_of_the_season_is_still_scraped_the_morning_after(temporada: SeasonDates) -> None:
    """El borde que la especificación literal se comía.

    Los juegos del 31 de octubre se raspan el 1 de noviembre por la mañana. Con la ventana cerrada
    exactamente en `season_end_date`, el job del día siguiente ya estaría fuera y el último juego de
    la Serie Mundial no entraría nunca.
    """
    dia_despues = date(2026, 11, 1)

    assert dia_despues > temporada.season_end_date
    assert season_window.evaluate(on=dia_despues).corre is True


@pytest.mark.django_db
def test_nobody_marked_the_new_season_says_so_instead_of_going_quiet(temporada: SeasonDates) -> None:
    """El fallo que más caro sale: el sitio deja de actualizarse y se descubre por una queja.

    No alcanza con no correr — el motivo tiene que decir que falta marcar la temporada, que es una
    acción concreta, y no confundirse con «estamos en invierno», que no requiere hacer nada.
    """
    SeasonDates.objects.update(is_active=False)

    ventana = season_window.evaluate(on=date(2026, 7, 26))

    assert ventana.corre is False
    assert "Calendario de temporadas" in ventana.motivo  # dice dónde arreglarlo


@pytest.mark.django_db
def test_another_sport_has_its_own_window(temporada: SeasonDates) -> None:
    """Hoy todos los jobs son de MLB, pero la clave lleva el deporte para no migrarla después."""
    assert season_window.evaluate(on=date(2026, 7, 26), sports_id=2).corre is False
    assert season_window.evaluate(on=date(2026, 7, 26), sports_id=season_window.MLB).corre is True


# ── El salto queda anotado ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_a_skipped_job_leaves_a_row_that_explains_itself(temporada: SeasonDates) -> None:
    """Sin la fila, «¿por qué no se actualizó?» se contesta entrando al servidor a leer logs."""
    SeasonDates.objects.update(is_active=False)

    saltado = season_window.skip("update_batting")

    assert saltado is True
    fila = IngestRun.objects.get(command="update_batting")
    assert fila.status == IngestRun.Status.SKIPPED
    assert fila.rows_affected == 0
    assert "temporada" in fila.detail.lower()  # el motivo, no solo el hecho


@pytest.mark.django_db
def test_in_season_nothing_is_logged_and_the_job_proceeds(temporada: SeasonDates) -> None:
    assert season_window.skip("update_batting") is False
    assert IngestRun.objects.count() == 0


# ── Los comandos de verdad ──────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_daily_job_does_no_work_out_of_season(temporada: SeasonDates) -> None:
    """De punta a punta: `build_leaders` fuera de temporada no toca la tabla ni sale a la red.

    Se elige este comando porque es el más caro —reescribe 400.000 filas— y porque no necesita el
    proxy: si la guarda fallara, el test se caería por la escritura y no por un timeout de red.
    """
    SeasonDates.objects.update(is_active=False)

    call_command("build_leaders")

    assert IngestRun.objects.filter(command="build_leaders", status=IngestRun.Status.SKIPPED).exists()
    assert not IngestRun.objects.filter(command="build_leaders", status=IngestRun.Status.SUCCESS).exists()


@pytest.mark.django_db
def test_the_same_job_runs_when_the_season_is_open(temporada: SeasonDates) -> None:
    """La otra mitad: con temporada abierta el comando hace su trabajo y se registra como siempre."""
    call_command("build_leaders")

    assert IngestRun.objects.filter(command="build_leaders", status=IngestRun.Status.SUCCESS).exists()
    assert not IngestRun.objects.filter(status=IngestRun.Status.SKIPPED).exists()


@pytest.mark.django_db
def test_log_pruning_is_not_gated_by_the_season(temporada: SeasonDates) -> None:
    """La excepción deliberada: podar el log es mantenimiento, no pelota.

    Si se apagara fuera de temporada, el log crecería sin podar durante los cuatro meses en que más
    filas de salto se escriben — justo al revés de lo que hace falta.
    """
    SeasonDates.objects.update(is_active=False)

    call_command("prune_ingest_log")

    assert not IngestRun.objects.filter(command="prune_ingest_log", status=IngestRun.Status.SKIPPED).exists()


@pytest.mark.django_db
def test_work_triggered_by_a_person_ignores_the_season_gate(temporada: SeasonDates) -> None:
    """La puerta es para el RELOJ, no para las acciones.

    Cargar datos de apoyo dispara la reconstrucción de lo derivado (ARCH-01), y el dato histórico se
    carga justamente en invierno. Si la puerta también aplicara ahí, la carga entraría y los
    liderazgos seguirían viejos hasta marzo, que es exactamente el fallo que ARCH-01 vino a matar.
    """
    from dglweb.stats import rebuilds

    SeasonDates.objects.update(is_active=False)

    rebuilds.run(rebuilds.DERIVED)

    assert not IngestRun.objects.filter(status=IngestRun.Status.SKIPPED).exists()
    hechos = set(IngestRun.objects.filter(status=IngestRun.Status.SUCCESS).values_list("command", flat=True))
    assert hechos == set(rebuilds.DERIVED)


# ── La ventana corta de octubre ─────────────────────────────────────────────────────────────────


@pytest.fixture
def con_postemporada(temporada: SeasonDates) -> SeasonDates:
    """La misma 2026, con su octubre: regular hasta el 27/9, postemporada desde el 30/9."""
    temporada.reg_season_end_date = date(2026, 9, 27)
    temporada.post_season_start_date = date(2026, 9, 30)
    temporada.save()
    return temporada


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("dia", "regular", "octubre"),
    [
        (date(2026, 3, 25), True, False),  # día inaugural: solo la regular
        (date(2026, 7, 26), True, False),  # mitad de temporada: octubre todavía no
        (date(2026, 9, 29), True, False),  # entre el fin de la regular y el inicio de la post
        (date(2026, 9, 30), True, True),  # arranca octubre
        (date(2026, 11, 2), True, True),  # gracia final: las dos siguen
        (date(2026, 11, 4), False, False),  # cerrado
    ],
)
def test_the_october_jobs_have_a_shorter_window(
    con_postemporada: SeasonDates, dia: date, regular: bool, octubre: bool
) -> None:
    """Lo que esto ahorra: de marzo a septiembre los tres jobs de octubre ya no salen a buscar nada."""
    assert season_window.evaluate(on=dia).corre is regular
    assert season_window.evaluate(on=dia, postseason=True).corre is octubre


@pytest.mark.django_db
def test_without_a_postseason_date_it_falls_back_to_the_end_of_the_regular_season(
    con_postemporada: SeasonDates,
) -> None:
    """MLB publica esa fecha tarde, así que falta a menudo. La postemporada empieza justo después.

    La regla es degradar hacia CORRER: una llamada de más al proxy no cuesta nada, que a nadie se le
    ocurra llenar la fecha y la Serie Mundial no se raspe nunca, sí.
    """
    con_postemporada.post_season_start_date = None
    con_postemporada.save()

    assert season_window.evaluate(on=date(2026, 9, 26), postseason=True).corre is False
    assert season_window.evaluate(on=date(2026, 9, 28), postseason=True).corre is True


@pytest.mark.django_db
def test_with_neither_date_the_october_jobs_behave_as_before_instead_of_going_silent(
    temporada: SeasonDates,
) -> None:
    """El último respaldo. Sin ninguna de las dos fechas se vuelve al comportamiento de siempre."""
    assert temporada.post_season_start_date is None
    assert temporada.reg_season_end_date is None

    assert season_window.evaluate(on=date(2026, 7, 26), postseason=True).corre is True


@pytest.mark.django_db
def test_the_skip_says_which_date_it_used(con_postemporada: SeasonDates) -> None:
    """Si se cayó al respaldo tiene que verse en el log, no adivinarse."""
    con_postemporada.post_season_start_date = None
    con_postemporada.save()

    motivo = season_window.evaluate(on=date(2026, 7, 26), postseason=True).motivo

    assert "sin fecha propia" in motivo


@pytest.mark.django_db
def test_the_october_command_skips_in_july_but_the_daily_one_does_not(con_postemporada: SeasonDates) -> None:
    """De punta a punta, con los comandos de verdad y la temporada real abierta."""
    from unittest.mock import patch

    with patch("dglweb.stats.season_window.timezone.localdate", return_value=date(2026, 7, 26)):
        call_command("update_batting_post")

    saltados = list(IngestRun.objects.filter(status=IngestRun.Status.SKIPPED).values_list("command", flat=True))
    assert saltados == ["update_batting_post"]
