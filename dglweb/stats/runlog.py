"""Record each scraper run to the ingest log.

`record_run` wraps a command so every execution leaves an `IngestRun` row: a RUNNING row on
entry (a hung run is visible), closed out to SUCCESS / PARTIAL / FAILED on exit. This is the
observability that makes scheduling safe — a silent failure becomes a red row in the backoffice
instead of nothing at all.
"""

import traceback
from collections.abc import Iterator
from contextlib import contextmanager

from django.utils import timezone

from dglweb.stats.models import IngestRun

# The traceback is kept (it is what makes a failed scrape diagnosable), but bounded so a nightly
# failure cannot grow the row without limit. Head + tail keeps both the message and where it broke.
_MAX_DETAIL = 12_000
_TRUNCATED = "\n…(traceback truncado)…\n"


def _bounded(text: str) -> str:
    if len(text) <= _MAX_DETAIL:
        return text
    keep = (_MAX_DETAIL - len(_TRUNCATED)) // 2
    return text[:keep] + _TRUNCATED + text[-keep:]


class RunHandle:
    """Handed to the command body to report progress; `record_run` turns it into the final row."""

    def __init__(self) -> None:
        self.rows = 0
        self._notes: list[str] = []
        self._failures: list[str] = []

    def add_rows(self, n: int) -> None:
        self.rows += n

    def note(self, message: str) -> None:
        self._notes.append(message)

    def fail(self, item: str) -> None:
        """Record that one unit of work (e.g. a season) failed without sinking the whole run."""
        self._failures.append(item)

    @property
    def failed_any(self) -> bool:
        return bool(self._failures)

    def detail(self) -> str:
        parts = list(self._notes)
        if self._failures:
            parts.append("Fallaron: " + ", ".join(self._failures))
        return "\n".join(parts)


@contextmanager
def record_run(command: str, scope: str) -> Iterator[RunHandle]:
    run = IngestRun.objects.create(
        command=command,
        scope=scope,
        status=IngestRun.Status.RUNNING,
        started_at=timezone.now(),
    )
    handle = RunHandle()
    try:
        yield handle
    except Exception as exc:
        run.status = IngestRun.Status.FAILED
        run.detail = _bounded(f"{exc}\n\n{traceback.format_exc()}")
        raise
    else:
        run.status = IngestRun.Status.PARTIAL if handle.failed_any else IngestRun.Status.SUCCESS
        run.detail = handle.detail()
    finally:
        run.rows_affected = handle.rows
        run.finished_at = timezone.now()
        run.save()
