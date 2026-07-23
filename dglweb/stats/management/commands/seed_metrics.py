"""Generate the `dgl_metric` catalog from our own stat tables.

One `Metric` per rankable column of Batting/Pitching/Fielding. The *shape* (group, column, kind)
is read from our models; the *leaderboard config* (direction, which boards, exclude-zeros,
postseason, active) is seeded from `_LEADERBOARD` — a one-time extract of the old site's `dgl_stat`,
baked in as a constant so nothing here depends on SQL Server. Columns the old table did not cover
fall back to judgment defaults (see `_NEGATIVE`), inactive by default.

Idempotent: `get_or_create` on (stat_group, column), so re-running never clobbers Backoffice edits.
`--reset` wipes the catalog first for a clean regeneration.
"""

from typing import Any

from django.core.management.base import BaseCommand, CommandParser
from django.db import models, transaction

from dglweb.stats import career_rate
from dglweb.stats.models import Batting, Fielding, Metric, Pitching, QualifierDefault

# (neg, best_season, worst_season, best_career, worst_career, exclude_zeros, postseason, active)
# Extracted once from albertop_DGL.dbo.dgl_stat (design reference only), keyed by (group, dgl code).
_LEADERBOARD: dict[tuple[str, str], tuple[int, ...]] = {
    ("batting", "1B"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "2B"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "3B"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "AB"): (0, 1, 1, 1, 0, 0, 1, 1),
    ("batting", "ABxHR"): (0, 1, 1, 1, 1, 0, 0, 0),
    ("batting", "ABxRBI"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "ABxSO"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "APRO"): (0, 1, 1, 0, 0, 0, 0, 1),
    ("batting", "AVG"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "BABIP"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "BB"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "BBperc"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "BR"): (0, 1, 1, 0, 0, 0, 0, 1),
    ("batting", "CS"): (1, 0, 1, 0, 1, 0, 0, 1),
    ("batting", "EBP"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "G"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "GIDP"): (1, 0, 1, 0, 1, 0, 0, 1),
    ("batting", "H"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "HBP"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "HEQO"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "HR"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "HRperc"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "IBB"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "IsoD"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "IsoP"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "OBP"): (0, 1, 1, 1, 1, 1, 1, 1),
    ("batting", "OPS"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "OPSAdj"): (0, 1, 1, 0, 0, 0, 0, 1),
    ("batting", "Outs"): (1, 0, 1, 0, 1, 1, 0, 1),
    ("batting", "PA"): (0, 1, 0, 1, 0, 0, 0, 1),
    ("batting", "PwrSpd"): (0, 1, 0, 1, 0, 0, 0, 1),
    ("batting", "R"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "RBA"): (0, 1, 1, 0, 0, 0, 0, 1),
    ("batting", "RBI"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "RCG"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "RSperc"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "SB"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "SBP"): (0, 0, 0, 1, 0, 0, 0, 1),
    ("batting", "SecA"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "SF"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "SH"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "SLG"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "SO"): (1, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "SOperc"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "SOxBB"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "TB"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("batting", "TotAvg"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "wOBA"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("batting", "WPA"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("fielding", "A"): (0, 1, 0, 1, 0, 0, 0, 1),
    ("fielding", "CS"): (0, 1, 0, 1, 0, 0, 0, 0),
    ("fielding", "DP"): (0, 1, 0, 1, 0, 0, 0, 1),
    ("fielding", "E"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("fielding", "G"): (0, 1, 1, 1, 1, 0, 0, 0),
    ("fielding", "GS"): (0, 1, 1, 1, 1, 0, 0, 0),
    ("fielding", "HEQD"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("fielding", "Inn"): (0, 1, 0, 1, 0, 0, 0, 1),
    ("fielding", "InnOuts"): (0, 1, 0, 1, 0, 0, 0, 0),
    ("fielding", "PB"): (1, 0, 1, 0, 1, 0, 0, 1),
    ("fielding", "PCT"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("fielding", "pickOffs"): (0, 0, 0, 1, 0, 0, 0, 1),
    ("fielding", "PO"): (0, 1, 0, 1, 0, 0, 0, 1),
    ("fielding", "RF"): (0, 1, 1, 1, 1, 0, 0, 1),
    ("fielding", "SB"): (0, 1, 0, 1, 0, 0, 0, 0),
    ("fielding", "WP"): (1, 0, 1, 0, 1, 0, 0, 1),
    ("fielding", "ZR"): (0, 1, 1, 1, 1, 0, 0, 0),
    ("pitching", "APR"): (0, 1, 1, 0, 0, 1, 0, 1),
    ("pitching", "BAA"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("pitching", "BB"): (1, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "BBx9"): (1, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "BFP"): (0, 1, 0, 1, 0, 0, 0, 1),
    ("pitching", "CG"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "DEC"): (0, 1, 0, 1, 0, 0, 1, 1),
    ("pitching", "ER"): (1, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "ERA"): (1, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "ERA+"): (0, 1, 1, 0, 0, 0, 0, 1),
    ("pitching", "ERC"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("pitching", "FIP"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("pitching", "G"): (0, 1, 0, 1, 0, 0, 1, 1),
    ("pitching", "GS"): (0, 1, 0, 1, 0, 0, 0, 1),
    ("pitching", "H"): (1, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "HR"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("pitching", "HRx9"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("pitching", "Hx9"): (1, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "IP"): (0, 1, 0, 1, 0, 0, 1, 1),
    ("pitching", "L"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("pitching", "PCT"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "PR"): (0, 1, 1, 0, 0, 0, 0, 1),
    ("pitching", "R"): (1, 1, 0, 1, 0, 0, 0, 1),
    ("pitching", "SCORE"): (0, 1, 1, 1, 1, 0, 0, 0),
    ("pitching", "SHO"): (0, 1, 0, 1, 0, 1, 0, 1),
    ("pitching", "SO"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "SOx9"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "SOxBB"): (0, 1, 1, 1, 1, 1, 0, 1),
    ("pitching", "SV"): (0, 1, 0, 1, 0, 0, 1, 1),
    ("pitching", "W"): (0, 1, 1, 1, 1, 0, 1, 1),
    ("pitching", "WHIP"): (1, 1, 1, 1, 1, 0, 0, 1),
    ("pitching", "wpaPitcher"): (0, 1, 1, 1, 1, 0, 0, 1),
}

# our column name -> dgl code, only where a plain upper-case/x-number normalization would not match.
_ALIAS: dict[tuple[str, str], str] = {
    ("batting", "ab_per_hr"): "ABxHR",
    ("batting", "iso"): "IsoP",
    ("batting", "total_avg"): "TotAvg",
    ("batting", "woba"): "wOBA",
    ("batting", "rc"): "RCG",
    ("batting", "bsr"): "BR",
    ("pitching", "win_pct"): "PCT",
    ("pitching", "bf"): "BFP",
    ("pitching", "so_per9"): "SOx9",
    ("pitching", "bb_per9"): "BBx9",
    ("pitching", "hr_per9"): "HRx9",
    ("pitching", "h_per9"): "Hx9",
    ("pitching", "so_to_bb"): "SOxBB",
    ("pitching", "outs"): "IP",  # innings ranked via outs
    ("fielding", "gp"): "G",
    ("fielding", "fld_pct"): "PCT",
    ("fielding", "double_plays"): "DP",
    ("fielding", "innings_outs"): "Inn",  # the active innings board (InnOuts was inactive in the source)
    ("fielding", "passed_balls"): "PB",
    ("fielding", "wild_pitches"): "WP",
    ("fielding", "pickoffs"): "pickOffs",
    ("fielding", "stolen_bases"): "SB",
    ("fielding", "caught_stealing"): "CS",
    ("fielding", "uzr"): "ZR",
    ("fielding", "rf_per_g"): "RF",
}

# Identity/context columns and baseball-notation duplicates (rank outs/innings_outs, never ip/innings).
_EXCLUDE: dict[str, frozenset[str]] = {
    "batting": frozenset({"player", "season", "stint", "team", "league", "pos", "age"}),
    "pitching": frozenset({"player", "season", "stint", "team", "league", "pos", "age", "ip"}),
    "fielding": frozenset({"player", "season", "team", "pos", "league", "age", "innings"}),
}

# Judgment: lower-is-better columns the old table did not cover.
_NEGATIVE: frozenset[tuple[str, str]] = frozenset(
    {
        ("pitching", "era_minus"),
        ("pitching", "fip_minus"),
        ("pitching", "xfip"),
        ("pitching", "bk"),
        ("pitching", "wp"),
        ("pitching", "hbp"),
        ("pitching", "bsv"),
        ("fielding", "throwing_errors"),
        ("fielding", "catcher_era"),
    }
)

# Default qualifiers per group (season, career). Owner tunes these in the Backoffice.
_QUALIFIER: dict[str, tuple[str, str]] = {
    "batting": ("PA>=502", "PA>=3000"),
    "pitching": ("IP>=162", "IP>=1000"),
    "fielding": ("G>=100", "G>=1000"),
}

# UI display order per (group, dgl code) — the old dgl_stat.Pos (extracted once). Unmatched -> last.
_SORT_ORDER: dict[tuple[str, str], int] = {
    ("batting", "G"): 6,
    ("batting", "AB"): 7,
    ("batting", "R"): 8,
    ("batting", "H"): 9,
    ("batting", "1B"): 10,
    ("batting", "2B"): 11,
    ("batting", "3B"): 12,
    ("batting", "HR"): 13,
    ("batting", "RBI"): 14,
    ("batting", "SH"): 15,
    ("batting", "SF"): 16,
    ("batting", "BB"): 16,
    ("batting", "SB"): 17,
    ("batting", "SO"): 17,
    ("batting", "CS"): 18,
    ("batting", "TB"): 19,
    ("batting", "AVG"): 20,
    ("batting", "IBB"): 20,
    ("batting", "HBP"): 21,
    ("batting", "SLG"): 21,
    ("batting", "OBP"): 22,
    ("batting", "OPS"): 23,
    ("batting", "PA"): 23,
    ("batting", "RCG"): 29,
    ("batting", "GIDP"): 30,
    ("batting", "IsoP"): 31,
    ("batting", "ABxSO"): 32,
    ("batting", "SBP"): 33,
    ("batting", "SecA"): 34,
    ("batting", "APRO"): 36,
    ("batting", "BABIP"): 37,
    ("batting", "EBP"): 38,
    ("batting", "IsoD"): 39,
    ("batting", "OPSAdj"): 40,
    ("batting", "wOBA"): 41,
    ("batting", "RBA"): 42,
    ("batting", "Outs"): 42,
    ("batting", "ABxHR"): 43,
    ("batting", "SOxBB"): 44,
    ("batting", "ABxRBI"): 45,
    ("batting", "RSperc"): 46,
    ("batting", "HRperc"): 47,
    ("batting", "BBperc"): 48,
    ("batting", "SOperc"): 49,
    ("batting", "TotAvg"): 50,
    ("batting", "PwrSpd"): 51,
    ("batting", "WPA"): 52,
    ("batting", "HEQO"): 53,
    ("batting", "BR"): 54,
    ("fielding", "G"): 8,
    ("fielding", "GS"): 9,
    ("fielding", "Inn"): 10,
    ("fielding", "InnOuts"): 10,
    ("fielding", "PO"): 11,
    ("fielding", "A"): 12,
    ("fielding", "E"): 13,
    ("fielding", "DP"): 14,
    ("fielding", "PB"): 15,
    ("fielding", "WP"): 16,
    ("fielding", "SB"): 17,
    ("fielding", "CS"): 18,
    ("fielding", "ZR"): 19,
    ("fielding", "PCT"): 20,
    ("fielding", "RF"): 21,
    ("fielding", "pickOffs"): 22,
    ("fielding", "HEQD"): 22,
    ("pitching", "G"): 6,
    ("pitching", "W"): 7,
    ("pitching", "L"): 8,
    ("pitching", "GS"): 9,
    ("pitching", "CG"): 10,
    ("pitching", "SV"): 10,
    ("pitching", "SHO"): 11,
    ("pitching", "IP"): 12,
    ("pitching", "H"): 13,
    ("pitching", "ER"): 14,
    ("pitching", "BB"): 15,
    ("pitching", "HR"): 16,
    ("pitching", "SO"): 16,
    ("pitching", "ERA"): 17,
    ("pitching", "Hx9"): 18,
    ("pitching", "BBx9"): 19,
    ("pitching", "SOx9"): 20,
    ("pitching", "HRx9"): 21,
    ("pitching", "PCT"): 21,
    ("pitching", "DEC"): 22,
    ("pitching", "WHIP"): 24,
    ("pitching", "SCORE"): 27,
    ("pitching", "SOxBB"): 28,
    ("pitching", "ERA+"): 29,
    ("pitching", "APR"): 30,
    ("pitching", "FIP"): 32,
    ("pitching", "wpaPitcher"): 33,
    ("pitching", "BAA"): 34,
    ("pitching", "ERC"): 35,
    ("pitching", "BFP"): 36,
    ("pitching", "PR"): 36,
    ("pitching", "R"): 37,
}
_SORT_LAST = 900  # columns the old table did not cover sort after the curated ones

_MODELS: dict[str, type[models.Model]] = {"batting": Batting, "pitching": Pitching, "fielding": Fielding}


def _normalize(column: str) -> str:
    """Our column name -> a dgl-style code: upper-case, with x1b/x2b/x3b -> 1B/2B/3B."""
    special = {"x1b": "1B", "x2b": "2B", "x3b": "3B"}
    return special.get(column, column.upper())


def _rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group, model in _MODELS.items():
        excluded = _EXCLUDE[group]
        for field in model._meta.fields:  # concrete fields only (the composite pk is virtual)
            if field.name in excluded:
                continue
            if isinstance(field, models.FloatField):
                # Most floats are rates, but additive sabermetrics (WAR, RAR, UZR…) are cumulative.
                kind = (
                    Metric.Kind.CUMULATIVE if (group, field.name) in career_rate.CUMULATIVE_FLOATS else Metric.Kind.RATE
                )
            elif isinstance(field, models.IntegerField):
                kind = Metric.Kind.CUMULATIVE
            else:
                continue  # CharField context columns etc. are not metrics

            code = _ALIAS.get((group, field.name)) or _normalize(field.name)
            cfg = _LEADERBOARD.get((group, code))
            if cfg:
                neg, bs, ws, bc, wc, qz, post, act = cfg
                direction = Metric.Direction.LOWER if neg else Metric.Direction.HIGHER
            else:
                bs = ws = bc = wc = qz = post = act = 0
                direction = Metric.Direction.LOWER if (group, field.name) in _NEGATIVE else Metric.Direction.HIGHER

            # No per-metric qualifier here: rate metrics inherit the group default (QualifierDefault,
            # level 1). Metric.qualifier_* is left blank as the optional level-2 override.
            # Abbrev = the English code (HR, AVG, ERA, DP, Inn…), never a Spanish one — it shows in the
            # leaders UI and the player-page rankings.
            abbrev = code

            rows.append(
                {
                    "stat_group": group,
                    "column": field.name,
                    "kind": kind,
                    "direction": direction,
                    "best_season": bool(bs),
                    "worst_season": bool(ws),
                    "best_career": bool(bc),
                    "worst_career": bool(wc),
                    "exclude_zeros": bool(qz),
                    "postseason": bool(post),
                    "abbrev": abbrev,
                    "sort_order": _SORT_ORDER.get((group, code), _SORT_LAST),
                    "is_active": bool(act),
                }
            )
    return rows


class Command(BaseCommand):
    help = "Genera el catálogo dgl_metric desde nuestras tablas de stats."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--reset", action="store_true", help="Borra el catálogo antes de regenerarlo.")

    def handle(self, *args: Any, **options: Any) -> None:
        with transaction.atomic():
            if options["reset"]:
                Metric.objects.all().delete()
                QualifierDefault.objects.all().delete()
            created = 0
            for row in _rows():
                _, was_created = Metric.objects.get_or_create(
                    stat_group=row["stat_group"], column=row["column"], defaults=row
                )
                created += was_created
            # Level 1 of the qualifier cascade: one default per group (defined once, inherited by all).
            for group, (season, career) in _QUALIFIER.items():
                QualifierDefault.objects.get_or_create(
                    stat_group=group, defaults={"qualifier_season": season, "qualifier_career": career}
                )
        total = Metric.objects.count()
        active = Metric.objects.filter(is_active=True).count()
        self.stdout.write(self.style.SUCCESS(f"{created} métricas creadas; {total} en total, {active} activas."))
