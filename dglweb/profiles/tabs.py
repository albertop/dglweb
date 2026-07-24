"""The player-page tab registry — the extensibility seam.

A tab is a small object: what it is (`key`, `label`, `template`), whether a given player has data
for it (`applies_to`), where it sits in the tab bar for that player (`order_for` — pitchers lead
with Pitcheo), and the data its partial renders (`context`). Adding a new tab (Splits, Premios,
Game Logs…) is a new subclass + a template partial + one line in `REGISTRY`; the page shell, the
URL and the other tabs are untouched.
"""

from collections import defaultdict
from collections.abc import Sequence
from itertools import groupby
from typing import Any

from django.db import models

from dglweb.players.models import Player
from dglweb.profiles import columns
from dglweb.stats import career_totals, qualifier
from dglweb.stats.derive import FIRST_STATCAST_SEASON, batted_ball_coefficients
from dglweb.stats.leagues import COMBINED_LEAGUE, COMBINED_TEAM
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    BattingPost,
    CareerLevel,
    Fielding,
    FieldingCareer,
    Leader,
    Metric,
    Pitching,
    PitchingCareer,
    PitchingPost,
    QualifierDefault,
    QualifierSeasonOverride,
)

_PITCHER_POSITIONS = {"P", "RP", "SP"}  # the master's pitcher codes (starter / reliever / generic)


def is_pitcher(player: Player) -> bool:
    return player.pos in _PITCHER_POSITIONS


def _leaderships(player: Player, group: str) -> tuple[set[tuple[int, str]], set[str]]:
    """Where this player is the #1 leader: {(season, column)} for the season and {column} for career.

    Batting/pitching are position-agnostic (their leaders carry `fielding_pos=NULL`) — position is
    only a fielding dimension. Drives the in-table highlight (wine = season leader, blue = career).
    """
    marks = Leader.objects.filter(player=player, rank=1, metric__stat_group=group).select_related("metric")
    season = {
        (row.season, row.metric.column)
        for row in marks
        if row.board == Leader.Board.BEST_SEASON and row.season is not None
    }
    career = {row.metric.column for row in marks if row.board == Leader.Board.BEST_CAREER}
    return season, career


_NOT_A_STAT = {"season", "stint", "age"}


def _catalog(group: str) -> dict[str, Metric]:
    """{column: Metric} for a stat group — gives each column its ranking direction (`+`/`-`)."""
    return {metric.column: metric for metric in Metric.objects.filter(stat_group=group)}


def _qualifier_context() -> tuple[qualifier.Defaults, qualifier.Overrides]:
    """The qualifier cascade lookups (group defaults + per-season overrides), preloaded once."""
    defaults = {d.stat_group: (d.qualifier_season, d.qualifier_career) for d in QualifierDefault.objects.all()}
    overrides = {(o.stat_group, o.season): o.qualifier_season for o in QualifierSeasonOverride.objects.all()}
    return defaults, overrides


def _qualifier_row(row: models.Model) -> dict[str, Any]:
    """The columns the cascade evaluates: PA (batting), IP←outs (pitching), G←gp (fielding)."""
    return {"pa": getattr(row, "pa", None), "outs": getattr(row, "outs", None), "gp": getattr(row, "gp", None)}


# A floor value is only an achievement when there was a chance to fail. "Never caught stealing" says
# nothing about a player who never ran, so CS=0 counts as a personal best only for a season with at
# least one steal. Display-only: CS feeds no "best" leaderboard, so the engine is untouched.
_NEEDS_OPPORTUNITY: dict[tuple[str, str], str] = {("batting", "cs"): "sb"}


def _had_the_chance(group: str, column: str, row: models.Model) -> bool:
    """False when the column's companion says the player never put himself at risk that season."""
    companion = _NEEDS_OPPORTUNITY.get((group, column))
    return companion is None or bool(getattr(row, companion, None))


def _personal_bests(
    model: type[models.Model],
    group: str,
    seasons: list[Any],
    catalog: dict[str, Metric],
    defaults: qualifier.Defaults,
    overrides: qualifier.Overrides,
) -> set[tuple[int, str]]:
    """Per numeric column, the season(s) holding the player's own career-best.

    "Best" follows the metric's direction: the maximum for `+` (higher is better), the minimum for
    `-` (lower is better: SO, CS, GIDP…). But the extreme only counts among seasons that clear the
    qualifier when a small sample could fake it — i.e. for any rate (PRO: AVG, BABIP, wOBA…, in
    either direction) and for the minimum of a count (`-`). A `+` count (or an accumulating float
    like WAR) can't be faked by few PA, so its maximum is taken over all seasons. Columns absent
    from the catalog have no known kind/direction, so they keep the plain maximum.
    """
    stat_columns = [
        field.name
        for field in model._meta.fields
        if isinstance(field, models.IntegerField | models.FloatField) and field.name not in _NOT_A_STAT
    ]
    best: set[tuple[int, str]] = set()
    for column in stat_columns:
        if column in _DESCRIPTIVE_COLUMNS:
            continue  # a style has no "best" — see _DESCRIPTIVE_COLUMNS
        metric = catalog.get(column)
        lower_is_better = metric is not None and metric.direction == Metric.Direction.LOWER
        # Rates distort in small samples either way; the min of a "lower is better" count is trivially
        # tiny in a short season. Both must clear the qualifier. A "+" count / accumulating float cannot.
        needs_qualifier = lower_is_better or (metric is not None and metric.kind == Metric.Kind.RATE)
        candidates: list[tuple[int, float]] = []
        for row in seasons:
            value = getattr(row, column)
            if value is None or not _had_the_chance(group, column, row):
                continue
            if needs_qualifier and metric is not None:
                formula = qualifier.resolve_season(metric, row.season, defaults, overrides)
                if not qualifier.qualifies(formula, group, _qualifier_row(row)):
                    continue
            candidates.append((row.season, value))
        if not candidates:
            continue
        target = min(v for _, v in candidates) if lower_is_better else max(v for _, v in candidates)
        best |= {(season, column) for season, value in candidates if value == target}
    return best


def _seasons_played(model: type[models.Model], player: Player) -> tuple[dict[str, int], dict[str, int]]:
    """How many distinct seasons the player spent with each team, and in each league.

    Counted from the per-team lines, not the season totals: a season split between two clubs counts
    once for **each** of them, so the team counts can add up to more than his career total. The
    combined sentinels (`XXX` team / `XX` league) are bookkeeping rows, never a real club, so they
    are skipped — otherwise a traded season would invent a third "team".
    """
    by_team: dict[str, set[int]] = defaultdict(set)
    by_league: dict[str, set[int]] = defaultdict(set)
    rows = model._default_manager.filter(player=player).values_list("season", "team", "league")
    for season, team, league in rows:
        if team and team != COMBINED_TEAM:
            by_team[team].add(season)
        if league and league != COMBINED_LEAGUE:
            by_league[league].add(season)
    return {t: len(s) for t, s in by_team.items()}, {lg: len(s) for lg, s in by_league.items()}


def _totals_rows(
    career: list[Any],
    total: models.Model | None,
    seasons: int,
    model: type[models.Model],
    player: Player,
    total_leads: dict[str, str],
) -> list[dict[str, Any]]:
    """The `Totales` pane: a line per team, then per league, then the career total last — each
    labelled with how many seasons it covers.

    Only the career line carries highlights: `dgl_leader` ranks whole careers, so a team or league
    subtotal is not a leaderboard entry and must not be painted as one.
    """
    by_team, by_league = _seasons_played(model, player)
    rows = [
        {"row": row, "label": row.team, "seasons": by_team.get(row.team, 0), "kind": "team", "leads": {}}
        for row in career
        if row.level == CareerLevel.TEAM
    ]
    rows += [
        {
            "row": row,
            "label": f"Liga {row.league}",
            "seasons": by_league.get(row.league, 0),
            "kind": "league",
            "leads": {},
        }
        for row in career
        if row.level == CareerLevel.LEAGUE
    ]
    if total is not None:
        rows.append({"row": total, "label": "Total", "seasons": seasons, "kind": "total", "leads": total_leads})
    return rows


# The MLB bracket, in the order it is played. `round` sorts alphabetically otherwise (DS, LCS, WC,
# WS), which would print the Wild Card after the League Championship.
_POST_ROUNDS = ("WC", "DS", "LCS", "WS")


def _post_subtotal(model: type[models.Model], group: str, rows: list[Any]) -> Any:  # noqa: ANN401
    """An unsaved line standing for a set of postseason rows, so templates read it like any other."""
    return model(**career_totals.aggregate_lines(group, model, rows))


def _postseason(
    model: type[models.Model], group: str, player: Player
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """(detail lines with a per-season subtotal, per-round subtotals plus the grand total).

    Computed per request rather than materialized: postseason feeds no leaderboard yet, so the
    player page is its only consumer and a stored table could only drift. Rates come from
    `aggregate_lines`, i.e. recomputed from the summed components.
    """
    order = {code: index for index, code in enumerate(_POST_ROUNDS)}
    rows: list[Any] = sorted(
        model._default_manager.filter(player=player),
        key=lambda row: (row.season, order.get(row.round, len(_POST_ROUNDS))),
    )

    lines: list[dict[str, Any]] = []
    for _, season_group in groupby(rows, key=lambda row: row.season):
        season_rows = list(season_group)
        lines += [{"kind": "line", "row": row} for row in season_rows]
        if len(season_rows) > 1:  # one round is already its own subtotal — printing it twice is noise
            lines.append({"kind": "season", "row": _post_subtotal(model, group, season_rows)})

    totals: list[dict[str, Any]] = []
    for code in _POST_ROUNDS:
        in_round = [row for row in rows if row.round == code]
        if in_round:
            totals.append(
                {
                    "kind": "round",
                    "label": code,
                    "row": _post_subtotal(model, group, in_round),
                    "seasons": len({row.season for row in in_round}),
                }
            )
    if rows:
        totals.append(
            {
                "kind": "total",
                "label": "Total",
                "row": _post_subtotal(model, group, rows),
                "seasons": len({row.season for row in rows}),
            }
        )
    return lines, totals


def _row_key(row: models.Model) -> tuple[Any, Any]:
    """A row's identity within one player's history: (season, stint). Fielding has no stint."""
    return getattr(row, "season", None), getattr(row, "stint", None)


def _season_highlights(
    rows: list[Any],
    season_leads: set[tuple[int, str]],
    best: set[tuple[int, str]],
    total_keys: set[tuple[Any, Any]],
) -> list[tuple[Any, dict[str, str]]]:
    """(row, {column: css class}). Priority: season leader (wine) > personal career-best (dark).

    `rows` may hold the per-team splits of a traded season as well as that season's combined line.
    Only the combined line is marked: a leaderboard entry and a personal best are properties of the
    **whole season**, so painting half of it would claim the player led on 24 games' worth of work.
    """
    highlighted = []
    for row in rows:
        classes: dict[str, str] = {}
        if _row_key(row) in total_keys:
            for season, column in season_leads:
                if season == row.season:
                    classes[column] = "lead-season"
            for season, column in best:
                if season == row.season and column not in classes:
                    classes[column] = "lead-best"
        highlighted.append((row, classes))
    return highlighted


class PlayerTab:
    """Base tab. Subclasses set the class attrs and implement `applies_to`/`context`."""

    key: str = ""
    label: str = ""
    template: str = ""
    base_order: int = 0

    def applies_to(self, player: Player) -> bool:
        raise NotImplementedError

    def order_for(self, player: Player) -> int:
        return self.base_order

    def context(self, player: Player) -> dict[str, Any]:
        return {}


_COEFFICIENT_COLUMNS: frozenset[str] = frozenset(batted_ball_coefficients({}))

# Which column list each pane renders. Same keys for both groups, so `_group_context` stays generic.
_BATTING_TABLES: dict[str, list[columns.Column]] = {
    "standard": columns.BATTING_STANDARD,
    "advanced": columns.BATTING_ADVANCED,
    "statcast": columns.BATTING_STATCAST,
    "ratios": columns.BATTING_RATIOS,
}
_PITCHING_TABLES: dict[str, list[columns.Column]] = {
    "standard": columns.PITCHING_STANDARD,
    "advanced": columns.PITCHING_ADVANCED,
    "statcast": columns.PITCHING_STATCAST,
    "ratios": columns.PITCHING_RATIOS,
}

# Descriptive metrics: they measure a STYLE, not an achievement. A career-high GB% does not say the
# player got better at anything — his batted-ball profile simply moved, and whether that helps him
# depends on speed, power, park and era. Painting that extreme with the same badge as a career-high
# HR invites a false reading, so these get no personal-best mark.
# Their `direction` stays as it is: the engine still needs an order to rank by. Contrast with PU%,
# Contact% and Whiff%, which DO have a clear sporting direction (set per group, mirrored for
# pitching) and keep their highlight.
_DESCRIPTIVE_COLUMNS: frozenset[str] = frozenset({"gb_pct", "fb_pct", "ld_pct", "gb_fb"})


def _cells(
    row: Any,  # noqa: ANN401
    leads: dict[str, str],
    tables: dict[str, list[columns.Column]],
    names: Sequence[str],
) -> dict[str, list[dict[str, str]]]:
    """The rendered cells of `row` for each named table."""
    return {name: columns.cells(row, tables[name], leads) for name in names}


def _is_his_trade(group: str, player: Player) -> bool:
    """Whether this stat group is what the player is actually paid to do."""
    return is_pitcher(player) if group == "pitching" else not is_pitcher(player)


def _group_context(
    group: str,
    model: type[models.Model],
    career_model: type[models.Model],
    post_model: type[models.Model],
    player: Player,
    tables: dict[str, list[columns.Column]],
) -> dict[str, Any]:
    """Everything a batting or pitching pane needs.

    Both groups have the same shape — season lines with their per-team splits, career subtotals,
    postseason, Statcast — so they share the assembly and only differ in their templates' columns.
    Fielding does not fit here: its lines are per position, not per stint.
    """
    # Two row sets: `seasons` is one line per season (the combined line for a traded year) and
    # drives every calculation; `lines` also lists the per-team splits, and is what the table
    # shows — a traded year prints each club, then that season's combined line.
    rows_qs = model._default_manager.filter(player=player)
    seasons = list(rows_qs.season_totals().order_by("season"))  # type: ignore[attr-defined]
    lines = list(rows_qs.order_by("season", "stint"))
    total_keys = {_row_key(row) for row in seasons}
    season_leads, career_leads = _leaderships(player, group)
    if not _is_his_trade(group, player):
        # A pitcher's batting line and a position player's pitching line are incidental: they are
        # ranked against people whose job that is, so a "leader" badge claims something false. The
        # career GB/FB board for BATTING is topped by three pitchers. Nobody here is Ohtani — every
        # Dominican with numbers in both tables is a starting pitcher from the pre-DH National
        # League, and the most batting any of them did is Marichal's 1 339 PA over 16 seasons.
        # The personal best survives: it compares him only with himself.
        season_leads, career_leads = set(), set()
    defaults, overrides = _qualifier_context()
    catalog = _catalog(group)
    best = _personal_bests(model, group, seasons, catalog, defaults, overrides)
    career: list[Any] = list(career_model._default_manager.filter(player=player).order_by("sort_order"))
    total = next((row for row in career if row.level == CareerLevel.TOTAL), None)
    rows = _season_highlights(lines, season_leads, best, total_keys)
    total_leads = {col: "lead-career" for col in career_leads}  # blue on the career row
    # The Statcast panes start in 1989: before that the batted-ball types were barely recorded
    # (see derive.FIRST_STATCAST_SEASON for the season-by-season coverage). A player who retired
    # earlier gets no panes at all, and no row of pure `—` is ever printed.
    # Coverage is judged on the season lines, never on the row count: a traded year contributes
    # several rows but is still one season.
    statcast_rows = [(row, leads) for row, leads in rows if row.season >= FIRST_STATCAST_SEASON]
    statcast_seasons = [row for row in seasons if row.season >= FIRST_STATCAST_SEASON]
    post_lines, post_totals = _postseason(post_model, group, player)
    totals = _totals_rows(career, total, len(seasons), model, player, total_leads)

    # Every line carries its cells already rendered, one list per table. The column specs in
    # `profiles/columns.py` are the single definition: header, season line, career total, postseason
    # and per-team subtotal all read the same list, so none of them can drift from the others.
    def painted(source: list[tuple[Any, dict[str, str]]], *names: str) -> list[dict[str, Any]]:
        return [{"row": row, "leads": leads, **_cells(row, leads, tables, names)} for row, leads in source]

    def labelled(entries: list[dict[str, Any]], *names: str) -> list[dict[str, Any]]:
        return [{**entry, **_cells(entry["row"], entry.get("leads") or {}, tables, names)} for entry in entries]

    every = tuple(tables)
    return {
        "columns": tables,
        "lines": painted(rows, "standard", "advanced"),
        "statcast_lines": painted(statcast_rows, "statcast", "ratios"),
        "total_cells": _cells(total, total_leads, tables, every) if total else None,
        "totals_rows": labelled(totals, *every),
        "post_cells": labelled(post_lines, "standard"),
        "post_total_cells": labelled(post_totals, "standard"),
        "season_count": len(seasons),  # seasons, not rows: a traded year prints several lines
        "total": total,
        "totals": totals,
        # Los datos crudos detrás de las celdas: (fila, {columna: clase}) y las marcas de carrera.
        "rows": rows,
        "total_leads": total_leads,
        "post": post_lines,
        "post_totals": post_totals,
        # What the legend is allowed to name: only the marks this player actually carries.
        "has_season_leads": bool(season_leads),
        "has_career_leads": bool(career_leads),
        "statcast_rows": statcast_rows,
        "has_statcast": bool(statcast_rows),
        # Read back from `dgl_metric`, never hardcoded in the caption: the thresholds are tunable in
        # the Backoffice, and a note that repeated them would start lying the day someone tunes one.
        "coefficient_qualifiers": sorted(
            {
                metric.qualifier_season
                for column, metric in catalog.items()
                if column in _COEFFICIENT_COLUMNS and metric.qualifier_season
            }
        ),
        # Only total a Statcast pane when it covers every season the player has: a career line
        # summed over fewer seasons than the table lists would misread as his whole career.
        "statcast_full": bool(statcast_seasons) and len(statcast_seasons) == len(seasons),
    }


class BattingTab(PlayerTab):
    key = "batting"
    label = "Bateo"
    template = "profiles/tabs/batting.html"
    base_order = 10

    def applies_to(self, player: Player) -> bool:
        return BattingCareer.objects.filter(player=player).exists()

    def order_for(self, player: Player) -> int:
        return 20 if is_pitcher(player) else 10  # pitchers push Bateo below Pitcheo

    def context(self, player: Player) -> dict[str, Any]:
        return _group_context("batting", Batting, BattingCareer, BattingPost, player, _BATTING_TABLES)


class PitchingTab(PlayerTab):
    key = "pitching"
    label = "Pitcheo"
    template = "profiles/tabs/pitching.html"
    base_order = 20

    def applies_to(self, player: Player) -> bool:
        return PitchingCareer.objects.filter(player=player).exists()

    def order_for(self, player: Player) -> int:
        return 10 if is_pitcher(player) else 20

    def context(self, player: Player) -> dict[str, Any]:
        return _group_context("pitching", Pitching, PitchingCareer, PitchingPost, player, _PITCHING_TABLES)


class FieldingTab(PlayerTab):
    key = "fielding"
    label = "Fildeo"
    template = "profiles/tabs/_soon.html"
    base_order = 30

    def applies_to(self, player: Player) -> bool:
        return FieldingCareer.objects.filter(player=player).exists()

    def context(self, player: Player) -> dict[str, Any]:
        return {"has_data": Fielding.objects.filter(player=player).exists()}


REGISTRY: list[PlayerTab] = [BattingTab(), PitchingTab(), FieldingTab()]  # append new tabs here


def tabs_for(player: Player) -> list[PlayerTab]:
    """The tabs that apply to a player, in that player's display order (pitchers lead with Pitcheo)."""
    return sorted((tab for tab in REGISTRY if tab.applies_to(player)), key=lambda tab: tab.order_for(player))
