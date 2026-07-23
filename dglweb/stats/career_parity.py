"""Verify the in-house career totals against the proxy's authoritative `career` line.

Option "b": this only **flags and logs** — it never rewrites data. For each player's grand total it
fetches the proxy career, maps it with the same tested mappers as the season ingest, and compares
the counting columns exactly. A survivor is recorded as a `CareerParityIssue` (created on first
mismatch, refreshed while it persists, **deleted when parity passes again**). The command closes the
ingest run PARTIAL if anything is unresolved, so it surfaces as a yellow row in the Backoffice.

Scope: batting and pitching (the per-player career). Fielding parity (per position, summed from the
proxy's position splits) is a follow-up — see docs/MEJORAS_FUTURAS.
"""

from collections.abc import Callable
from typing import Any, Protocol

from django.utils import timezone

from dglweb.stats import mapping, pitching_mapping
from dglweb.stats.models import BattingCareer, CareerLevel, CareerParityIssue, PitchingCareer


class _Client(Protocol):
    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]: ...


# group -> (career model, statsapi group, mapper, counting columns to compare exactly)
#
# `g` (games) is deliberately NOT compared: the proxy's `career` endpoint reports a games count that
# disagrees with its own `yearByYear` (it counts a pitcher's appearances in the hitting line), so our
# season-summed total is right but would look wrong. A future yearByYear-based parity can restore it
# (see docs/MEJORAS_FUTURAS). We compare the outcome stats, which do sum consistently.
_CONFIG: dict[str, tuple[Any, str, Callable[[dict[str, Any]], dict[str, Any]], list[str]]] = {
    "batting": (
        BattingCareer,
        "hitting",
        mapping.map_regular,
        [
            "pa",
            "ab",
            "r",
            "h",
            "x2b",
            "x3b",
            "hr",
            "rbi",
            "sb",
            "cs",
            "bb",
            "so",
            "ibb",
            "hbp",
            "sh",
            "sf",
            "gidp",
            "tb",
        ],
    ),
    "pitching": (
        PitchingCareer,
        "pitching",
        pitching_mapping.map_regular,
        ["w", "l", "gs", "gf", "cg", "sho", "sv", "h", "r", "er", "hr", "bb", "so", "hbp", "bf"],
    ),
}


def _to_int(value: str | int | float | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _career_stat(client: _Client, player_id: int, stat_group: str) -> dict[str, Any]:
    payload = client.get(f"/api/v1/people/{player_id}/stats", {"stats": "career", "group": stat_group})
    stats = payload.get("stats") or []
    splits = (stats[0].get("splits") if stats else []) or []
    return (splits[0].get("stat") if splits else {}) or {}


def check_career_parity(client: _Client, on_mismatch: Callable[[str], None] = lambda _: None) -> dict[str, int]:
    """Compare every grand total to the proxy; manage the markers. Returns {checked, unresolved}."""
    now = timezone.now()
    checked = unresolved = 0
    for group, (model, stat_group, mapper, columns) in _CONFIG.items():
        for total in model.objects.filter(level=CareerLevel.TOTAL).select_related("player"):
            checked += 1
            proxy = mapper(_career_stat(client, total.player_id, stat_group))
            diffs = [
                f"{column}: nuestro={getattr(total, column)} proxy={theirs}"
                for column in columns
                if (theirs := _to_int(proxy.get(column))) is not None and _to_int(getattr(total, column)) != theirs
            ]
            existing = CareerParityIssue.objects.filter(player_id=total.player_id, group=group).first()
            if not diffs:
                if existing:
                    existing.delete()  # resolved — a re-backfill fixed the season data
                continue
            unresolved += 1
            detail = "; ".join(diffs)
            if existing:
                existing.detail = detail
                existing.last_checked = now
                existing.save(update_fields=["detail", "last_checked"])
            else:
                CareerParityIssue.objects.create(
                    player_id=total.player_id, group=group, detail=detail, first_detected=now, last_checked=now
                )
            on_mismatch(f"{total.player.full_name} ({group}): {detail}")
    return {"checked": checked, "unresolved": unresolved}
