"""Tests for the derived rate stats (Fase 3).

Two families, matching `derive.py`:

* **The fifteen from `mlbstats`.** Every counting input and every golden result below is the REAL
  José Ramírez 2024 line, read from `dbo.mlbBatting` — so these are parity checks against the
  source, not self-consistent arithmetic. Each formula was also verified against all 120 929
  source rows (0 divergences on non-zero values).
* **The seven batted-ball / swing coefficients.** Ours, so there is no source to check against;
  their tests assert the agreed definitions and the NULL-over-0 rule instead.
"""

import pytest

from dglweb.stats.derive import derived_rates

# José Ramírez, CLE, 2024 — the exact counting line from dbo.mlbBatting.
JR = {
    "h": 173,
    "ab": 620,
    "bb": 54,
    "hbp": 1,
    "sf": 6,
    "so": 82,
    "x1b": 93,
    "x2b": 39,
    "x3b": 2,
    "hr": 39,
    "pa": 682,
    "r": 114,
    "rbi": 118,
    "tb": 333,
    "cs": 7,
    "sb": 41,
    "sh": 0,
    "ibb": 12,
    "gidp": 9,
}

# The rate/sabermetric values the source stores for that same line.
GOLDEN = {
    "avg": 0.27903226,
    "obp": 0.33480176,
    "slg": 0.5370968,
    "ops": 0.87189853,
    "babip": 0.26534653,
    "iso": 0.25806451,
    "ab_per_hr": 15.897436,
    "bb_per_so": 0.65853661,
    "pa_per_so": 8.3170729,
    "runs_produced": 193,
    "bsr": 107.42959,
    "eq_avg": 0.90570068,
    "gross_prod_avg": 0.73691738,
    "rc": 107.1815,
    "total_avg": 0.92656589,
}


@pytest.mark.parametrize("metric", sorted(GOLDEN))
def test_matches_the_source_value(metric: str) -> None:
    got = derived_rates(JR)[metric]
    assert got == pytest.approx(GOLDEN[metric], rel=1e-4)


def test_runs_produced_is_an_integer() -> None:
    rp = derived_rates(JR)["runs_produced"]
    assert rp == 193
    assert isinstance(rp, int)


def test_slugging_uses_the_hit_components_not_stored_tb() -> None:
    """The 28 source rows where TB was off by one proved SLG follows the components."""
    row = {**JR, "tb": 999}  # a wrong stored tb must not touch SLG
    assert derived_rates(row)["slg"] == pytest.approx(GOLDEN["slg"], rel=1e-6)


def test_bsr_uses_stored_tb_not_the_components() -> None:
    """BsR/EqA/RC/TA take the stored tb — the other half of the source's own inconsistency."""
    row = {**JR, "tb": 300}  # BsR must move with the stored tb
    assert derived_rates(row)["bsr"] != pytest.approx(GOLDEN["bsr"], rel=1e-4)


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


def test_exotic_metrics_null_when_an_input_is_missing() -> None:
    """These take many inputs; any missing one (an old era) yields NULL, not a partial number."""
    rates = derived_rates({"h": 100, "ab": 400, "bb": 30, "tb": 160})  # no cs, sb, hbp, ...

    assert rates["bsr"] is None  # hr missing
    assert rates["eq_avg"] is None
    assert rates["rc"] is None
    assert rates["total_avg"] is None


_COEFFICIENTS = ("gb_pct", "fb_pct", "ld_pct", "pu_pct", "gb_fb", "contact_pct", "whiff_pct")


def test_batted_ball_coefficients() -> None:
    """A batted ball's type = its outs + its hits; the four types share `balls_in_play`."""
    rates = derived_rates(
        {
            "ground_outs": 10,
            "ground_hits": 5,  # GB = 15
            "fly_outs": 8,
            "fly_hits": 2,  # FB = 10
            "line_outs": 3,
            "line_hits": 4,  # LD = 7
            "pop_outs": 1,
            "pop_hits": 0,  # PU = 1
            "balls_in_play": 33,  # 15 + 10 + 7 + 1
            "total_swings": 100,
            "swing_and_misses": 20,
        }
    )

    assert rates["gb_pct"] == pytest.approx(15 / 33)
    assert rates["fb_pct"] == pytest.approx(10 / 33)
    assert rates["ld_pct"] == pytest.approx(7 / 33)
    assert rates["pu_pct"] == pytest.approx(1 / 33)
    assert rates["gb_fb"] == pytest.approx(1.5)  # 15 / 10
    assert rates["contact_pct"] == pytest.approx(0.8)  # (100 - 20) / 100
    assert rates["whiff_pct"] == pytest.approx(0.2)  # 20 / 100, whiff over swings


def test_batted_ball_coefficients_null_when_inputs_missing() -> None:
    """Same NULL-over-0 rule as the rest: no batted-ball data -> NULL, never a fake 0."""
    rates = derived_rates({})

    assert all(rates[c] is None for c in _COEFFICIENTS)


def test_batted_ball_coefficients_null_when_denominator_is_zero() -> None:
    """A line with the inputs present but no balls in play / no swings -> NULL, not a crash."""
    rates = derived_rates(
        dict.fromkeys(
            [
                "ground_outs",
                "ground_hits",
                "fly_outs",
                "fly_hits",
                "line_outs",
                "line_hits",
                "pop_outs",
                "pop_hits",
                "balls_in_play",
                "total_swings",
                "swing_and_misses",
            ],
            0,
        )
    )

    assert all(rates[c] is None for c in _COEFFICIENTS)


def test_exotic_metrics_null_when_their_denominator_is_zero() -> None:
    """A line with every input present but the divisor working out to zero -> NULL, not a crash."""
    # ab=h=cs=gidp=0 zeroes ta's denominator; the all-zero line zeroes the others too.
    zero = dict.fromkeys(["h", "bb", "hr", "tb", "ab", "hbp", "sb", "sh", "sf", "cs", "ibb", "gidp"], 0)
    rates = derived_rates(zero)

    assert rates["bsr"] is None
    assert rates["eq_avg"] is None
    assert rates["rc"] is None
    assert rates["total_avg"] is None
