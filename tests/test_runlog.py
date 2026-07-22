"""Tests for the ingest run log (Fase 3).

`record_run` is what makes a scheduled scraper safe: every run leaves a row saying when it ran,
how it went, and why — so a scraper failing silently for weeks is visible instead of invisible.
"""

import pytest

from dglweb.stats.models import IngestRun
from dglweb.stats.runlog import record_run


@pytest.mark.django_db
def test_a_successful_run_is_recorded() -> None:
    with record_run("import_batting", "2024") as run:
        run.add_rows(106)
        run.note("2024: 106 filas")

    saved = IngestRun.objects.get()
    assert saved.command == "import_batting"
    assert saved.scope == "2024"
    assert saved.status == IngestRun.Status.SUCCESS
    assert saved.rows_affected == 106
    assert "106 filas" in saved.detail
    assert saved.finished_at is not None


@pytest.mark.django_db
def test_rows_accumulate_across_calls() -> None:
    with record_run("import_batting", "1988-1990") as run:
        run.add_rows(10)
        run.add_rows(5)

    assert IngestRun.objects.get().rows_affected == 15


@pytest.mark.django_db
def test_a_partial_run_is_flagged() -> None:
    """Some seasons loaded, some failed — not a clean success, not a total failure."""
    with record_run("import_batting", "1988-1990") as run:
        run.add_rows(20)
        run.fail("1989")

    saved = IngestRun.objects.get()
    assert saved.status == IngestRun.Status.PARTIAL
    assert "1989" in saved.detail


@pytest.mark.django_db
def test_an_exception_is_recorded_as_failed_and_re_raised() -> None:
    with pytest.raises(ValueError, match="boom"), record_run("import_batting", "2024") as run:
        run.add_rows(3)
        raise ValueError("boom")

    saved = IngestRun.objects.get()
    assert saved.status == IngestRun.Status.FAILED
    assert "boom" in saved.detail
    assert saved.rows_affected == 3  # whatever it managed before dying
    assert saved.finished_at is not None


@pytest.mark.django_db
def test_the_run_is_visible_while_it_is_still_going() -> None:
    """A row is written on entry, so a hung run does not look like it never started."""
    with record_run("import_batting", "2024"):
        live = IngestRun.objects.get()
        assert live.status == IngestRun.Status.RUNNING
        assert live.finished_at is None


@pytest.mark.django_db
def test_duration_is_available_after_a_run() -> None:
    with record_run("import_batting", "2024"):
        pass

    assert IngestRun.objects.get().duration is not None
