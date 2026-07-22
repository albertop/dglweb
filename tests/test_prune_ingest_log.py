"""Tests for pruning the ingest log (retention window)."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from dglweb.stats.models import IngestRun


def _run(days_ago: int) -> IngestRun:
    when = timezone.now() - timedelta(days=days_ago)
    run = IngestRun.objects.create(
        command="import_batting", scope=str(days_ago), status=IngestRun.Status.SUCCESS, started_at=when
    )
    # started_at has no auto_now, but be explicit in case defaults change.
    IngestRun.objects.filter(pk=run.pk).update(started_at=when)
    return run


@pytest.mark.django_db
def test_deletes_runs_older_than_the_retention_window() -> None:
    _run(days_ago=40)
    _run(days_ago=31)
    kept = _run(days_ago=10)

    call_command("prune_ingest_log")  # default retention: 30 days

    assert list(IngestRun.objects.values_list("pk", flat=True)) == [kept.pk]


@pytest.mark.django_db
def test_keeps_runs_exactly_at_the_boundary() -> None:
    fresh = _run(days_ago=29)

    call_command("prune_ingest_log")

    assert IngestRun.objects.filter(pk=fresh.pk).exists()


@pytest.mark.django_db
def test_retention_can_be_overridden(settings: object) -> None:
    settings.INGEST_LOG_RETENTION_DAYS = 7  # type: ignore[attr-defined]
    old = _run(days_ago=10)
    kept = _run(days_ago=3)

    call_command("prune_ingest_log")

    assert list(IngestRun.objects.values_list("pk", flat=True)) == [kept.pk]
    assert not IngestRun.objects.filter(pk=old.pk).exists()


@pytest.mark.django_db
def test_the_days_flag_wins_over_the_setting() -> None:
    _run(days_ago=5)
    kept = _run(days_ago=1)

    call_command("prune_ingest_log", "--days", "2")

    assert list(IngestRun.objects.values_list("pk", flat=True)) == [kept.pk]


@pytest.mark.django_db
def test_reports_how_many_were_pruned() -> None:
    _run(days_ago=40)
    _run(days_ago=35)
    _run(days_ago=1)

    # A clean run with nothing to prune must not error either.
    call_command("prune_ingest_log", "--days", "999")
    assert IngestRun.objects.count() == 3
