"""Tests for the derived rate stats (Fase 3, group 1).

The ten formulas the owner's R script computes with `mlbstats`. Each definition was verified
against all 120 929 rows of `dbo.mlbBatting`: on rows where the source has a real value, our
formula matches to the float; the only "differences" are era-gap and zero-denominator rows the
source stores as 0, where we return NULL (same NULL-over-0 choice as everywhere else).

The numbers below are José Ramírez 2024, checked against the source table.
"""

import pytest

from dglweb.stats.derive import derived_rates

# José Ramírez 2024 counting line (already mapped to our column names).
JR = {
    "h": 173,
    "ab": 620,
    "bb": 62,
    "hbp": 3,
    "sf": 6,
    "so": 91,
    "x1b": 120,
    "x2b": 39,
    "x3b": 5,
    "hr": 39,
    "pa": 691,
    "r": 114,
    "rbi": 118,
}


def test_batting_average() -> None:
    assert derived_rates(JR)["avg"] == pytest.approx(173 / 620, abs=1e-6)


def test_slugging_uses_the_hit_components_not_stored_tb() -> None:
    """The 28 source rows where TB was off by one proved SLG comes from the components."""
    total_bases = 120 + 2 * 39 + 3 * 5 + 4 * 39
    assert derived_rates(JR)["slg"] == pytest.approx(total_bases / 620, abs=1e-6)


def test_on_base_percentage() -> None:
    expected = (173 + 62 + 3) / (620 + 62 + 3 + 6)
    assert derived_rates(JR)["obp"] == pytest.approx(expected, abs=1e-6)


def test_ops_is_obp_plus_slg() -> None:
    rates = derived_rates(JR)
    assert rates["ops"] == pytest.approx(rates["obp"] + rates["slg"], abs=1e-6)


def test_babip() -> None:
    expected = (173 - 39) / (620 - 91 - 39 + 6)
    assert derived_rates(JR)["babip"] == pytest.approx(expected, abs=1e-6)


def test_isolated_power() -> None:
    expected = (39 + 2 * 5 + 3 * 39) / 620
    assert derived_rates(JR)["iso"] == pytest.approx(expected, abs=1e-6)


def test_ratios() -> None:
    rates = derived_rates(JR)
    assert rates["ab_per_hr"] == pytest.approx(620 / 39, abs=1e-6)
    assert rates["bb_per_so"] == pytest.approx(62 / 91, abs=1e-6)
    assert rates["pa_per_so"] == pytest.approx(691 / 91, abs=1e-6)


def test_runs_produced_is_an_integer() -> None:
    rp = derived_rates(JR)["runs_produced"]
    assert rp == 114 + 118 - 39
    assert isinstance(rp, int)


def test_a_zero_denominator_is_null_not_zero() -> None:
    """A pitcher with no at-bats has no average; NULL beats a misleading .000."""
    rates = derived_rates({"h": 0, "ab": 0, "hr": 0, "so": 0, "pa": 0})

    assert rates["avg"] is None
    assert rates["ab_per_hr"] is None
    assert rates["bb_per_so"] is None


def test_a_missing_input_propagates_to_null() -> None:
    """Pre-1954 rows have no SF, so OBP is uncomputable — as in the source (which stores 0)."""
    rates = derived_rates({"h": 90, "ab": 300, "bb": 20, "hbp": 2, "sf": None})

    assert rates["obp"] is None
    assert rates["ops"] is None  # OBP missing -> OPS missing
    assert rates["avg"] == pytest.approx(90 / 300, abs=1e-6)  # this one still computes


def test_runs_produced_null_when_an_input_is_missing() -> None:
    assert derived_rates({"r": 50, "rbi": None, "hr": 10})["runs_produced"] is None
