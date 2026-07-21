"""Derived batting rate stats — the group-1 metrics the R pipeline computes with `mlbstats`.

Ported straight from the owner's script and verified against every row of `dbo.mlbBatting`:
where the source has a real value, these match to the float. The only divergences are rows the
source stores as 0 — old eras missing an input, or a zero denominator (a pitcher's 0 AB) —
where we return NULL instead, the same NULL-over-0 choice made everywhere in this project. A
missing input propagates to NULL naturally, so an era without sacrifice flies yields no OBP.

Two subtleties the source verification pinned down:

* **SLG/ISO come from the hit components**, not the stored `TB`: 28 old rows have a `TB` that
  disagrees with `X1B+2·X2B+3·X3B+4·HR` by one, and the source rate follows the components.
* **Denominator zero means NULL, not 0** — see above.
"""

from typing import Any


def _sum(*values: int | None) -> int | None:
    known = [v for v in values if v is not None]
    return sum(known) if len(known) == len(values) else None


def _div(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return numerator / denominator


def derived_rates(c: dict[str, Any]) -> dict[str, Any]:
    """Compute the ten rate columns from a row's counting stats (our column names)."""
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
    }


def _times(value: int | None, factor: int) -> int | None:
    return None if value is None else value * factor


def _neg(value: int | None) -> int | None:
    return None if value is None else -value
