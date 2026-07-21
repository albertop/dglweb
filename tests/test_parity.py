"""Tests for the batting parity checker (Fase 3).

Parity is the safety net for porting the R pipeline: it compares what we load against
`dbo.mlbBatting` row by row. Counting stats must match exactly; sabermetrics are compared with
tolerance because MLB revises WAR/wRC+ retroactively (José Ramírez 2024 moved 6.45 -> 6.40
between the owner's run and today). A column the source has but we leave NULL is a *coverage
gap*, reported apart from a real mismatch.
"""

from typing import Any

from dglweb.stats.parity import compare_batting

KEY = {"player_id": 608070, "season": 2024, "stint": 1}


def test_identical_rows_report_no_problems() -> None:
    row = {**KEY, "g": 158, "ab": 620, "h": 173, "war": 6.4}

    report = compare_batting([row], [dict(row)])

    assert report.ok
    assert report.rows_expected == 1
    assert report.mismatches == []
    assert report.missing_rows == []


def test_a_counting_stat_must_match_exactly() -> None:
    expected = [{**KEY, "hr": 39}]
    actual = [{**KEY, "hr": 38}]

    report = compare_batting(expected, actual)

    assert not report.ok
    assert report.mismatches[0].column == "hr"
    assert (report.mismatches[0].expected, report.mismatches[0].actual) == (39, 38)


def test_sabermetrics_within_tolerance_are_accepted() -> None:
    """MLB recomputes WAR over time; 6.45 vs 6.40 is the same season, not a port bug."""
    expected = [{**KEY, "war": 6.45}]
    actual = [{**KEY, "war": 6.40}]

    report = compare_batting(expected, actual, tolerance=0.1)

    assert report.ok
    assert report.mismatches == []


def test_sabermetrics_beyond_tolerance_are_flagged() -> None:
    expected = [{**KEY, "war": 6.45}]
    actual = [{**KEY, "war": 2.10}]

    report = compare_batting(expected, actual, tolerance=0.1)

    assert not report.ok
    assert report.mismatches[0].column == "war"


def test_a_rate_stat_the_source_has_but_we_leave_null_is_a_coverage_gap() -> None:
    """Not a wrong value — a column we do not populate yet. Tracked separately."""
    expected = [{**KEY, "avg": 0.279}]
    actual = [{**KEY, "avg": None}]

    report = compare_batting(expected, actual)

    assert report.mismatches == []  # not a mismatch
    assert report.coverage_gaps["avg"] == 1
    assert not report.ok  # but the run is not clean either


def test_both_null_is_fine_not_a_gap() -> None:
    """An era with no swing data: NULL on both sides is agreement."""
    expected = [{**KEY, "total_swings": None}]
    actual = [{**KEY, "total_swings": None}]

    report = compare_batting(expected, actual)

    assert report.ok
    assert "total_swings" not in report.coverage_gaps


def test_a_row_missing_from_our_load_is_reported() -> None:
    expected = [{**KEY, "g": 158}, {**KEY, "stint": 2, "g": 40}]
    actual = [{**KEY, "g": 158}]

    report = compare_batting(expected, actual)

    assert not report.ok
    assert report.missing_rows == [(608070, 2024, 2)]


def test_a_row_we_have_but_the_source_does_not_is_reported() -> None:
    expected = [{**KEY, "g": 158}]
    actual = [{**KEY, "g": 158}, {**KEY, "stint": 2, "g": 40}]

    report = compare_batting(expected, actual)

    assert not report.ok
    assert report.extra_rows == [(608070, 2024, 2)]


def test_string_context_columns_must_match() -> None:
    expected = [{**KEY, "team": "CLE", "league": "AL"}]
    actual = [{**KEY, "team": "CIN", "league": "AL"}]

    report = compare_batting(expected, actual)

    assert report.mismatches[0].column == "team"


def test_the_summary_counts_everything() -> None:
    expected: list[dict[str, Any]] = [{**KEY, "hr": 39, "avg": 0.279}, {**KEY, "stint": 2, "hr": 1}]
    actual: list[dict[str, Any]] = [{**KEY, "hr": 38, "avg": None}]

    report = compare_batting(expected, actual)

    assert report.rows_expected == 2
    assert report.rows_matched == 1  # only stint 1 lines up
    assert report.mismatches[0].column == "hr"
    assert report.coverage_gaps["avg"] == 1
    assert report.missing_rows == [(608070, 2024, 2)]


def test_a_readable_summary_line() -> None:
    report = compare_batting([{**KEY, "hr": 39, "avg": 0.279}], [{**KEY, "hr": 38, "avg": None}])

    text = report.summary()
    assert "1 discrepancias" in text
    assert "avg" in text  # coverage gaps are named so we see what is unpopulated
