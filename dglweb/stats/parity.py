"""Compare loaded batting against the source table, row by row.

This is the safety net promised when we chose to port the R pipeline instead of keeping it: it
proves the port reproduces `dbo.mlbBatting` and, just as importantly, tells us which columns it
does not yet fill. Three outcomes per cell, kept apart on purpose:

* **mismatch** — both sides have a value and they disagree (exactly for counts, within
  tolerance for sabermetrics). This is a real bug in the port.
* **coverage gap** — the source has a value, we stored NULL. Not a wrong number; a column we do
  not compute yet (the R-only rate metrics: RC, EqA, BsR, ...).
* **agreement** — equal, or NULL on both sides (an era MLB never recorded).

Sabermetrics get a tolerance because MLB recomputes WAR/wRC+ retroactively, so an old extract
drifts from today's proxy without either being wrong.

Column kinds come from the model itself (FloatField -> approximate, integer -> exact), so this
stays in step with `Batting` instead of repeating its column list.
"""

from dataclasses import dataclass, field
from typing import Any

from django.db import models

from dglweb.stats.models import Batting

_KEY_FIELDS = ("player_id", "season", "stint")

Key = tuple[int, int, int]

# `pos` is not compared: we deliberately store the season position while the source stores the
# player's primary one, so it diverges by design for traded players and outfielders. Comparing
# it would drown real mismatches in expected noise.
_UNCOMPARED = {"pos"}


def _column_kinds() -> tuple[frozenset[str], frozenset[str]]:
    exact: set[str] = set()
    approx: set[str] = set()
    for f in Batting._meta.fields:
        name = "player_id" if f.name == "player" else f.name
        if name in {"id", *_KEY_FIELDS, *_UNCOMPARED}:
            continue
        if isinstance(f, models.FloatField):
            approx.add(name)
        else:  # PositiveSmallIntegerField (counts) and CharField (team/league)
            exact.add(name)
    return frozenset(exact), frozenset(approx)


EXACT_COLUMNS, APPROX_COLUMNS = _column_kinds()


@dataclass(frozen=True)
class Mismatch:
    key: Key
    column: str
    expected: Any
    actual: Any


@dataclass
class ParityReport:
    rows_expected: int = 0
    rows_actual: int = 0
    rows_matched: int = 0
    mismatches: list[Mismatch] = field(default_factory=list)
    coverage_gaps: dict[str, int] = field(default_factory=dict)
    missing_rows: list[Key] = field(default_factory=list)
    extra_rows: list[Key] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (self.mismatches or self.missing_rows or self.extra_rows or self.coverage_gaps)

    def summary(self) -> str:
        gap_cols = ", ".join(f"{col}({n})" for col, n in sorted(self.coverage_gaps.items()))
        parts = [
            f"{self.rows_matched}/{self.rows_expected} filas casadas",
            f"{len(self.mismatches)} discrepancias",
            f"{len(self.missing_rows)} faltantes",
            f"{len(self.extra_rows)} sobrantes",
        ]
        if gap_cols:
            parts.append(f"columnas sin poblar: {gap_cols}")
        return " | ".join(parts)


def _key(row: dict[str, Any]) -> Key:
    return (int(row["player_id"]), int(row["season"]), int(row["stint"]))


def _approx_equal(a: float, b: float, tolerance: float) -> bool:
    return abs(a - b) <= tolerance


def compare_batting(
    expected: list[dict[str, Any]],
    actual: list[dict[str, Any]],
    *,
    tolerance: float = 0.05,
) -> ParityReport:
    """Compare two row sets keyed by (player_id, season, stint)."""
    report = ParityReport(rows_expected=len(expected), rows_actual=len(actual))
    actual_by_key = {_key(row): row for row in actual}
    expected_keys = set()

    for exp in expected:
        key = _key(exp)
        expected_keys.add(key)
        act = actual_by_key.get(key)
        if act is None:
            report.missing_rows.append(key)
            continue

        report.rows_matched += 1
        _compare_row(key, exp, act, tolerance, report)

    report.extra_rows.extend(k for k in actual_by_key if k not in expected_keys)
    report.missing_rows.sort()
    report.extra_rows.sort()
    return report


def _compare_row(
    key: Key,
    exp: dict[str, Any],
    act: dict[str, Any],
    tolerance: float,
    report: ParityReport,
) -> None:
    for column in EXACT_COLUMNS | APPROX_COLUMNS:
        if column not in exp:
            continue
        want = exp[column]
        got = act.get(column)

        if want is None:
            continue  # source has nothing to check against
        if got is None:
            report.coverage_gaps[column] = report.coverage_gaps.get(column, 0) + 1
            continue

        if column in APPROX_COLUMNS:
            if not _approx_equal(float(want), float(got), tolerance):
                report.mismatches.append(Mismatch(key, column, want, got))
        elif want != got:
            report.mismatches.append(Mismatch(key, column, want, got))
