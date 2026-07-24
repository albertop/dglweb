"""Derived batting rate stats.

Two families, with **different provenance** — keep them apart when auditing:

* **Groups 1-2 (fifteen): ported from `mlbstats`.** Straight from the R source the owner provided,
  and every formula was checked against all 120 929 rows of `dbo.mlbBatting`: where the source has
  a real value, they match to the float (0 divergences).
* **Group 3 (seven): defined here.** The batted-ball profile and swing coefficients (GB/FB/LD/PU%,
  GB/FB, Contact%, Whiff%). They have no `mlbstats` counterpart, so there is nothing to verify
  them against — they are our definitions, agreed with the owner. Whiff is over **swings** (not
  pitches). A batted ball's type is its outs plus its hits, and the four types share
  `balls_in_play`. These only carry meaning for a season that clears the PA qualifier, which is
  enforced upstream by making them `PRO` metrics (the qualifier cascade gates every rate).

The only differences from the source are rows it stores as 0 — old eras missing an input, or a
zero denominator (a pitcher's 0 AB) — where we return NULL instead, the same NULL-over-0 choice
made everywhere in this project. A missing input propagates to NULL naturally, so an era without
sacrifice flies yields no OBP.

Two subtleties the source verification pinned down:

* **SLG and ISO come from the hit components** (`X1B+2·X2B+3·X3B+4·HR`), but **BsR, EqA, RC and
  TotalAVG use the stored `tb`** — exactly as the R script passes its arguments. This reproduces
  a real inconsistency in the source: 28 old rows have a `tb` that disagrees with the components
  by one, and the two families of metrics follow different values there. GPA sits in the first
  group (it is `1.8·OBP + SLG/4`).
* **Denominator zero means NULL, not 0** — see above.
"""

from typing import Any

# Batted-ball data only becomes usable in 1989. Measured over our own rows, as the share of each
# season's `balls_in_play` that actually carries a type (ground/fly/line/pop, outs + hits):
#
#     <=1970   0%          no batted-ball data at all
#     1971-87  15-36%      `balls_in_play` is recorded but almost nothing is classified
#     1988     65%         still a third missing
#     1989-90  94% / 90%
#     1991+    98-100%
#
# The gap is in the NUMERATOR, so a volume threshold cannot catch it: Rico Carty cleared 2 507
# balls in play with 19% of them classified and came out "leading" PU% at 1.3%. Only a season floor
# fixes it, so the Statcast counts and the coefficients start in 1989 — earlier seasons neither
# appear on the player page nor feed a leaderboard.
#
# Known exception left in place by decision: 2000 and 2001 sit at ~67% (their *_hits are missing).
# They are after the floor, so their ratios are understated; see docs/MEJORAS_FUTURAS.md.
FIRST_STATCAST_SEASON = 1989


def _sum(*values: int | None) -> int | None:
    known = [v for v in values if v is not None]
    return sum(known) if len(known) == len(values) else None


def _div(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def _times(value: int | None, factor: int) -> int | None:
    return None if value is None else value * factor


def _neg(value: int | None) -> int | None:
    return None if value is None else -value


def derived_rates(c: dict[str, Any]) -> dict[str, Any]:
    """Compute all twenty-two derived columns from a row's counting stats (our column names)."""
    h, ab, bb, hbp, sf = c.get("h"), c.get("ab"), c.get("bb"), c.get("hbp"), c.get("sf")
    so, hr, x2b, x3b, x1b = c.get("so"), c.get("hr"), c.get("x2b"), c.get("x3b"), c.get("x1b")

    total_bases = _sum(x1b, _times(x2b, 2), _times(x3b, 3), _times(hr, 4))
    extra_bases = _sum(x2b, _times(x3b, 2), _times(hr, 3))

    obp = _div(_sum(h, bb, hbp), _sum(ab, bb, hbp, sf))
    slg = _div(total_bases, ab)

    return {
        "avg": _div(h, ab),
        "obp": obp,
        "slg": slg,
        "ops": None if obp is None or slg is None else obp + slg,
        "babip": _div(_sum(h, _neg(hr)), _sum(ab, _neg(so), _neg(hr), sf)),
        "iso": _div(extra_bases, ab),
        "ab_per_hr": _div(ab, hr),
        "bb_per_so": _div(bb, so),
        "pa_per_so": _div(c.get("pa"), so),
        "runs_produced": _sum(c.get("r"), c.get("rbi"), _neg(hr)),
        # Group 2 — the exotic mlbstats formulas. These take the stored `tb` (except GPA).
        "gross_prod_avg": None if obp is None or slg is None else 1.8 * obp + slg / 4,
        "bsr": _bsr(h, bb, hr, c.get("tb"), ab),
        "eq_avg": _eq_avg(h, c.get("tb"), bb, hbp, c.get("sb"), c.get("sh"), sf, ab, c.get("cs")),
        "rc": _rc3(
            h,
            bb,
            c.get("ibb"),
            c.get("tb"),
            ab,
            c.get("cs"),
            c.get("sb"),
            hbp,
            c.get("gidp"),
            c.get("sh"),
            sf,
        ),
        "total_avg": _total_avg(c.get("tb"), hbp, bb, c.get("sb"), ab, h, c.get("cs"), c.get("gidp")),
        # Group 3 — batted-ball profile and swing coefficients (ours, not mlbstats).
        **batted_ball_coefficients(c),
    }


def batted_ball_coefficients(c: dict[str, Any]) -> dict[str, Any]:
    """Group 3 on its own, because pitching needs the very same numbers.

    The arithmetic does not care who is at bat: for a hitter these are the balls he put in play,
    for a pitcher the balls put in play against him, and both models carry the same column names.
    A batted ball's type is its outs plus its hits, and the four types share `balls_in_play`;
    whiff is over swings (owner decision). NULL-over-0 as everywhere else in this module.
    """
    ground = _sum(c.get("ground_outs"), c.get("ground_hits"))
    fly = _sum(c.get("fly_outs"), c.get("fly_hits"))
    line = _sum(c.get("line_outs"), c.get("line_hits"))
    pop = _sum(c.get("pop_outs"), c.get("pop_hits"))
    bip, swings, misses = c.get("balls_in_play"), c.get("total_swings"), c.get("swing_and_misses")
    return {
        "gb_pct": _div(ground, bip),
        "fb_pct": _div(fly, bip),
        "ld_pct": _div(line, bip),
        "pu_pct": _div(pop, bip),
        "gb_fb": _div(ground, fly),
        "contact_pct": _div(_sum(swings, _neg(misses)), swings),
        "whiff_pct": _div(misses, swings),
    }


def _bsr(h: int | None, bb: int | None, hr: int | None, tb: int | None, ab: int | None) -> float | None:
    if h is None or bb is None or hr is None or tb is None or ab is None:
        return None
    core = (1.4 * tb - 0.6 * h - 3 * hr + 0.1 * bb) * 1.02
    denominator = core + (ab - h)
    return None if denominator == 0 else ((h + bb - hr) * core) / denominator + hr


def _eq_avg(
    h: int | None,
    tb: int | None,
    bb: int | None,
    hbp: int | None,
    sb: int | None,
    sh: int | None,
    sf: int | None,
    ab: int | None,
    cs: int | None,
) -> float | None:
    if None in (h, tb, bb, hbp, sb, sh, sf, ab, cs):
        return None
    # Narrowed by the guard above; the ignore keeps the arithmetic readable rather than
    # repeating nine `is not None` checks inline.
    denominator = ab + bb + hbp + sh + sf + cs + sb / 3  # type: ignore[operator]
    if denominator == 0:
        return None
    return (h + tb + 1.5 * (bb + hbp) + sb + sh + sf) / denominator  # type: ignore[operator]


def _rc3(
    h: int | None,
    bb: int | None,
    ibb: int | None,
    tb: int | None,
    ab: int | None,
    cs: int | None,
    sb: int | None,
    hbp: int | None,
    gidp: int | None,
    sh: int | None,
    sf: int | None,
) -> float | None:
    if None in (h, bb, ibb, tb, ab, cs, sb, hbp, gidp, sh, sf):
        return None
    denominator = ab + bb + hbp + sh + sf  # type: ignore[operator]
    if denominator == 0:
        return None
    numerator = (h + bb - cs + hbp - gidp) * (tb + 0.26 * (bb - ibb + hbp)) + 0.52 * (sh + sf + sb)  # type: ignore[operator]
    return numerator / denominator


def _total_avg(
    tb: int | None,
    hbp: int | None,
    bb: int | None,
    sb: int | None,
    ab: int | None,
    h: int | None,
    cs: int | None,
    gidp: int | None,
) -> float | None:
    if None in (tb, hbp, bb, sb, ab, h, cs, gidp):
        return None
    denominator = ab - h + cs + gidp  # type: ignore[operator]
    if denominator == 0:
        return None
    return (tb + hbp + bb + sb) / denominator  # type: ignore[operator]
