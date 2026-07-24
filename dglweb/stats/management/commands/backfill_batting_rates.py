"""Recompute the derived batting rate columns in place, from each row's stored counts.

The ingest computes these on the way in (`batting_source` / `batting_post_source` both apply
`derive.derived_rates`), so rows already in the table keep whatever the formulas produced the day
they were written. Whenever `derive.py` gains a column or a formula changes, this re-derives every
existing row **without touching the proxy** — no network, no re-ingest, no risk of a source drift
sneaking in with the fix.

Idempotent: it is a pure function of columns already stored, so running it twice changes nothing.
"""

from collections.abc import Callable
from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import models, transaction

from dglweb.stats.derive import batted_ball_coefficients, derived_rates
from dglweb.stats.models import Batting, BattingPost, Pitching, PitchingPost

# name -> (model, the function that derives its columns). Pitching only re-derives the batted-ball
# coefficients: its other rates (ERA, WHIP, FIP…) come mapped from the source, and running the
# batting formulas over a pitcher's line would overwrite them with nonsense.
_MODELS: dict[str, tuple[type[models.Model], Callable[[dict[str, Any]], dict[str, Any]]]] = {
    "batting": (Batting, derived_rates),
    "post": (BattingPost, derived_rates),
    "pitching": (Pitching, batted_ball_coefficients),
    "pitching_post": (PitchingPost, batted_ball_coefficients),
}
_BATCH = 1000


def _counts(row: models.Model) -> dict[str, Any]:
    """Every non-relational column of the row — the formulas pick what they need by name."""
    return {field.name: getattr(row, field.name) for field in row._meta.fields if not field.is_relation}


def backfill(model: type[models.Model], derive: Callable[[dict[str, Any]], dict[str, Any]]) -> int:
    """Re-derive every row of a model. Returns the number of rows written."""
    columns = list(derive({}))  # the derived column names, straight from the single source
    written = 0
    with transaction.atomic():
        buffer: list[models.Model] = []
        for row in model._default_manager.iterator(chunk_size=_BATCH):
            for column, value in derive(_counts(row)).items():
                setattr(row, column, value)
            buffer.append(row)
            if len(buffer) >= _BATCH:
                model._default_manager.bulk_update(buffer, columns)
                written += len(buffer)
                buffer = []
        if buffer:
            model._default_manager.bulk_update(buffer, columns)
            written += len(buffer)
    return written


class Command(BaseCommand):
    help = "Recalcula las tasas derivadas (derive.py) sobre las filas ya almacenadas."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--only", choices=sorted(_MODELS), help="Recalcula solo una tabla (por defecto, todas).")

    def handle(self, *args: Any, **options: Any) -> None:
        targets = [options["only"]] if options["only"] else sorted(_MODELS)
        for name in targets:
            model, derive = _MODELS[name]
            written = backfill(model, derive)
            self.stdout.write(self.style.SUCCESS(f"{name}: {written} filas recalculadas."))
