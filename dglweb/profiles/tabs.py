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
from dglweb.stats import career_totals, leaders, qualifier
from dglweb.stats.derive import FIRST_STATCAST_SEASON, UNDERTYPED_STATCAST_SEASONS, batted_ball_coefficients
from dglweb.stats.leagues import COMBINED_LEAGUE, COMBINED_TEAM
from dglweb.stats.models import (
    Batting,
    BattingCareer,
    BattingPost,
    CareerLevel,
    Fielding,
    FieldingCareer,
    FieldingPost,
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


def _leaderships(player: Player, group: str, *, postseason: bool = False) -> tuple[set[tuple[int, str]], set[str]]:
    """Where this player is the #1 leader: {(season, column)} for the season and {column} for career.

    Batting/pitching are position-agnostic (their leaders carry `fielding_pos=NULL`) — position is
    only a fielding dimension. `postseason` picks the regular-season boards (False) or the October
    ones (True); they live in the same table split by `Leader.postseason`. Drives the in-table
    highlight (wine = season leader, blue = career).
    """
    marks = Leader.objects.filter(
        player=player, rank=1, metric__stat_group=group, postseason=postseason
    ).select_related("metric")
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
        # `exclude_zeros` ("Excluir ceros" en el Backoffice) marca las métricas donde un cero no es
        # un valor sino una ausencia: HLD de un abridor, SV de quien nunca cerró. El motor de líderes
        # ya lo respetaba; sin esto, la página pintaba la columna entera de Pedro como su mejor marca
        # en holds — un logro que nadie consiguió porque nadie lo intentó.
        drop_zeros = metric is not None and metric.exclude_zeros
        for row in seasons:
            value = getattr(row, column)
            if value is None or not _had_the_chance(group, column, row):
                continue
            if drop_zeros and value == 0:
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
    for season, season_group in groupby(rows, key=lambda row: row.season):
        season_rows = list(season_group)
        lines += [{"kind": "line", "row": row} for row in season_rows]
        if len(season_rows) > 1:  # one round is already its own subtotal — printing it twice is noise
            subtotal = _post_subtotal(model, group, season_rows)
            subtotal.season = season  # `aggregate_lines` drops the key columns; the postseason
            subtotal.round = "Tot"  # leadership overlay needs the season back on the aggregate row
            lines.append({"kind": "season", "row": subtotal})

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
                if season != row.season:
                    continue
                # Una celda puede ser las dos cosas. El color se lo queda el liderazgo —es la
                # información más fuerte— y la itálica agrega la segunda sin pelear por el mismo
                # canal: lideró entre dominicanos ESA temporada y además es su propia mejor marca.
                classes[column] = f"{classes[column]} lead-personal" if column in classes else "lead-best"
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
# Their `direction` stays as it is: the engine still needs an order to rank by. Contrast with
# Contact% and Whiff%, which DO have a clear sporting direction (set per group, mirrored for
# pitching) and keep their highlight.
# PU% se movió aquí (decisión del dueño): es reparto de batazos como las otras cuatro, no una virtud.
# Antes se leía como que una palomita era un out casi automático — mala para el bateador, buena para
# el lanzador— y quedaba con direcciones opuestas por grupo; ahora no juzga en ninguno de los dos.
_DESCRIPTIVE_COLUMNS: frozenset[str] = frozenset({"gb_pct", "fb_pct", "ld_pct", "gb_fb", "pu_pct"})


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
    post_season_leads, post_career_leads = _leaderships(player, group, postseason=True)
    if not _is_his_trade(group, player):
        # A pitcher's batting line and a position player's pitching line are incidental: they are
        # ranked against people whose job that is, so a "leader" badge claims something false. The
        # career GB/FB board for BATTING is topped by three pitchers. Nobody here is Ohtani — every
        # Dominican with numbers in both tables is a starting pitcher from the pre-DH National
        # League, and the most batting any of them did is Marichal's 1 339 PA over 16 seasons.
        # The personal best survives: it compares him only with himself. Same for October.
        season_leads, career_leads = set(), set()
        post_season_leads, post_career_leads = set(), set()
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
    # Postseason leadership overlay: the wine mark lives on the aggregate the board ranks — a whole
    # October per season — never on a PARTIAL round. That aggregate is the "Tot" subtotal for a
    # multi-round October; for a season the player played in a single round, that lone line already IS
    # his whole October, so it carries the mark itself (review v4 DEV-02, option A). Blue (career)
    # goes on the grand total below. Rates have October boards too now, but the page shows no
    # personal-best on postseason, only the leadership overlay.
    seasons_with_subtotal = {entry["row"].season for entry in post_lines if entry["kind"] == "season"}
    for entry in post_lines:
        row = entry["row"]
        is_october_aggregate = entry["kind"] == "season" or (
            entry["kind"] == "line" and row.season not in seasons_with_subtotal
        )
        entry["leads"] = (
            {column: "lead-season" for season, column in post_season_leads if season == row.season}
            if is_october_aggregate
            else {}
        )
    for entry in post_totals:
        if entry["kind"] == "total":
            entry["leads"] = {column: "lead-career" for column in post_career_leads}
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
        "has_personal_leads": any("lead-personal" in css for _, leads in rows for css in leads.values()),
        "has_post_season_leads": bool(post_season_leads),
        "has_post_career_leads": bool(post_career_leads),
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
        # Los paneles Statcast arrancan en 1989, así que a quien ya jugaba antes le cubren solo parte
        # de la carrera. Antes el total se escondía entero para no publicar una suma que se leyera
        # como "toda su carrera"; ahora se publica con el número de temporadas que SÍ cubre y un
        # asterisco, que dice lo mismo sin quitarle al lector un dato que existe.
        "statcast_seasons": len(statcast_seasons),
        "statcast_partial": bool(statcast_seasons) and len(statcast_seasons) != len(seasons),
        # El desglose por equipo/liga sigue escondido cuando la cobertura es parcial: un equipo donde
        # solo jugó antes de 1989 daría una fila entera de rayas.
        "statcast_full": bool(statcast_seasons) and len(statcast_seasons) == len(seasons),
        # Las temporadas de este jugador que pasan el piso pero llegan sin los hits tipificados. Se
        # nombran una por una en el pie: decir "la cobertura varía" no le sirve a nadie para saber
        # cuáles de SUS filas mirar con reservas.
        "undertyped": [row.season for row in statcast_seasons if row.season in UNDERTYPED_STATCAST_SEASONS],
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


def _fielding_leaderships(player: Player) -> tuple[set[tuple[int, str, str]], set[tuple[str, str]]]:
    """Fielding leaders are per position: {(season, pos, column)} and {(pos, column)} for career.

    Unlike batting/pitching (`fielding_pos=NULL`), a fielding board is scoped to a position — "most
    putouts at 1B", not "most putouts". So a mark is keyed by its position and only lights the row
    for that position.
    """
    marks = Leader.objects.filter(player=player, rank=1, metric__stat_group="fielding").select_related("metric")
    season = {
        (row.season, row.fielding_pos, row.metric.column)
        for row in marks
        if row.board == Leader.Board.BEST_SEASON and row.season is not None and row.fielding_pos
    }
    career = {
        (row.fielding_pos, row.metric.column)
        for row in marks
        if row.board == Leader.Board.BEST_CAREER and row.fielding_pos
    }
    return season, career


_FIELDING_TABLES: dict[str, list[columns.Column]] = {
    "standard": columns.FIELDING_STANDARD,
    "advanced": columns.FIELDING_ADVANCED,
    "catcher": columns.FIELDING_CATCHER,
}


# En cualquier total single-line de fildeo que sume MÁS DE UNA posición, ninguna tasa tiene sentido:
# un Fld% o un rango que mezcla receptor y jardinero no significa nada, y el UZR está calibrado por
# posición. Se blanquean todos los FloatField (las tasas), dejando solo los conteos acumulados. Con
# una sola posición el total ES esa posición, así que el valor sí vale y no se toca.
_FIELDING_RATE_COLUMNS: frozenset[str] = frozenset(
    field.name for field in Fielding._meta.fields if isinstance(field, models.FloatField)
)


def _blank_rates(cols: list[columns.Column], cells: list[dict[str, str]]) -> None:
    for col, cell in zip(cols, cells, strict=True):
        if col.attr in _FIELDING_RATE_COLUMNS:
            cell["text"] = "—"


def _fielding_total_cells(total: Any, multi_position: bool) -> dict[str, list[dict[str, str]]]:  # noqa: ANN401
    """Rendered cells for a grand-total line; on a multi-position sum every rate is blanked."""
    result: dict[str, list[dict[str, str]]] = {}
    for name, cols in _FIELDING_TABLES.items():
        cells = columns.cells(total, cols, {})
        if multi_position:
            _blank_rates(cols, cells)
        result[name] = cells
    return result


def _fielding_context(player: Player) -> dict[str, Any]:
    """Fielding is per POSITION, so it does not fit `_group_context`. A line is one (season, pos);
    highlights, personal bests and career leaderships are all scoped to the position — comparing a
    catcher's putouts against a first baseman's would be meaningless. DH is dropped (no defence)."""
    catalog = _catalog("fielding")
    defaults, overrides = _qualifier_context()
    lines = list(Fielding.objects.filter(player=player).position_totals().exclude(pos="DH").order_by("season", "-gp"))
    season_leads, career_leads = _fielding_leaderships(player)

    # Personal bests within each position, never across them.
    by_pos: dict[str, list[Any]] = defaultdict(list)
    for row in lines:
        by_pos[row.pos].append(row)
    multi_position = len(by_pos) > 1  # un total que suma >1 posición no puede mostrar tasas
    best: set[tuple[int, str, str]] = set()
    for pos, pos_lines in by_pos.items():
        for season, column in _personal_bests(Fielding, "fielding", pos_lines, catalog, defaults, overrides):
            best.add((season, pos, column))

    def paint(row: Any) -> dict[str, str]:  # noqa: ANN401
        classes: dict[str, str] = {}
        for season, pos, column in season_leads:
            if season == row.season and pos == row.pos:
                classes[column] = "lead-season"
        for season, pos, column in best:
            if season == row.season and pos == row.pos:
                classes[column] = f"{classes[column]} lead-personal" if column in classes else "lead-best"
        return classes

    names = tuple(_FIELDING_TABLES)
    painted: list[dict[str, Any]] = [
        {"row": row, "leads": (cl := paint(row)), **_cells(row, cl, _FIELDING_TABLES, names)} for row in lines
    ]

    # Career: one row per position (each is its own leaderboard entity, so it takes the career mark),
    # then the grand total (a sum across positions — not a ranked line, so unmarked).
    career: list[Any] = list(FieldingCareer.objects.filter(player=player).exclude(pos="DH").order_by("sort_order"))
    total = next((line for line in career if line.level == CareerLevel.TOTAL), None)
    seasons_at = {pos: len({row.season for row in pos_lines}) for pos, pos_lines in by_pos.items()}
    totals_rows: list[dict[str, Any]] = []
    for line in career:
        if line.level != CareerLevel.POSITION:
            continue
        leads = {column: "lead-career" for pos, column in career_leads if pos == line.pos}
        totals_rows.append(
            {
                "row": line,
                "label": line.pos,
                "seasons": seasons_at.get(line.pos, 0),
                "kind": "team",
                "leads": leads,
                **_cells(line, leads, _FIELDING_TABLES, names),
            }
        )
    if total is not None:
        # La fila Total del pill Totales también es un single-line que suma posiciones: mismas tasas
        # blanqueadas si son varias.
        totals_rows.append(
            {
                "row": total,
                "label": "Total",
                "seasons": len({row.season for row in lines}),
                "kind": "total",
                "leads": {},
                **_fielding_total_cells(total, multi_position),
            }
        )

    # The Receptor tables are catcher-scoped, so their single-line total is the C-position career line
    # (catcher-only innings and a real cERA), never the multi-position grand total that blanks rates.
    catcher_career = next((line for line in career if line.level == CareerLevel.POSITION and line.pos == "C"), None)
    catcher_total: dict[str, Any] | None = None
    if catcher_career is not None:
        catcher_total = {
            "label": "Total",
            "seasons": seasons_at.get("C", 0),
            "kind": "total",
            **_cells(catcher_career, {}, _FIELDING_TABLES, ("catcher",)),
        }

    # Postseason: detail per (season, round, position), each pill/table closing with its single-line
    # total (`aggregate_lines`, same engine as batting/pitching post). The per-position subtotals live
    # in the Totales pill, and the grand total there blanks the rates like every multi-position total.
    post_table = {"standard": columns.FIELDING_STANDARD}
    round_order = {code: index for index, code in enumerate(_POST_ROUNDS)}
    post_rows: list[Any] = sorted(
        FieldingPost.objects.filter(player=player).exclude(pos="DH"),
        key=lambda line: (line.season, round_order.get(line.round, len(_POST_ROUNDS)), line.pos),
    )
    post_lines = [{"row": line, **_cells(line, {}, post_table, ("standard",))} for line in post_rows]
    post_by_pos: dict[str, list[Any]] = defaultdict(list)
    for line in post_rows:
        post_by_pos[line.pos].append(line)
    post_multi = len(post_by_pos) > 1
    post_season_count = len({line.season for line in post_rows})

    # Grand total of the whole postseason: the single-line total for the detail table, with rates
    # blanked when it sums positions.
    post_total_cells = None
    if post_rows:
        cells = columns.cells(_post_subtotal(FieldingPost, "fielding", post_rows), columns.FIELDING_STANDARD, {})
        if post_multi:
            _blank_rates(columns.FIELDING_STANDARD, cells)
        post_total_cells = {"standard": cells}

    post_totals: list[dict[str, Any]] = []
    for pos in sorted(post_by_pos, key=lambda pos: -sum(line.gp or 0 for line in post_by_pos[pos])):
        rows_at = post_by_pos[pos]
        aggregate = _post_subtotal(FieldingPost, "fielding", rows_at)
        post_totals.append(
            {
                "row": aggregate,
                "label": pos,
                "seasons": len({line.season for line in rows_at}),
                "kind": "team",
                **_cells(aggregate, {}, post_table, ("standard",)),
            }
        )
    if post_total_cells:  # the per-position table also closes with its single-line total
        post_totals.append({"label": "Total", "seasons": post_season_count, "kind": "total", **post_total_cells})

    return {
        "columns": _FIELDING_TABLES,
        "lines": painted,
        "season_count": len({row.season for row in lines}),
        "total_cells": _fielding_total_cells(total, len(by_pos) > 1) if total else None,
        "totals_rows": totals_rows,
        "has_catcher": any(row.pos == "C" for row in lines),
        "catcher_total": catcher_total,
        "post_lines": post_lines,
        "post_total_cells": post_total_cells,
        "post_season_count": post_season_count,
        "post_totals": post_totals,
        "has_season_leads": bool(season_leads),
        "has_career_leads": bool(career_leads),
        "has_personal_leads": any("lead-personal" in css for entry in painted for css in entry["leads"].values()),
    }


class FieldingTab(PlayerTab):
    key = "fielding"
    label = "Fildeo"
    template = "profiles/tabs/fielding.html"
    base_order = 30

    def applies_to(self, player: Player) -> bool:
        # Needs an actual defensive line, not just a career row: a pure DH has a FieldingCareer total
        # but nothing to show once DH is dropped.
        return Fielding.objects.filter(player=player).exclude(pos="DH").exists()

    def context(self, player: Player) -> dict[str, Any]:
        return _fielding_context(player)


_PUESTOS_TOP_N = 10  # season cells: only a top-10 finish shows
_PUESTOS_CAREER_TOP_N = 25  # the "De por vida" column reaches further — top 25
# The ranking direction shown next to each metric: + = more is better, - = fewer/lower is better.
# It is how the board is sorted, so it explains what "puesto 1" means for that metric.
_DIRECTION_SIGN: dict[str, str] = {Metric.Direction.HIGHER: "+", Metric.Direction.LOWER: "-"}


def _insert_after(columns_: list[str], anchor: str, value: str) -> list[str]:
    """A copy of `columns_` with `value` inserted right after `anchor` (or appended if absent)."""
    out = list(columns_)
    out.insert(out.index(anchor) + 1 if anchor in out else len(out), value)
    return out


def _puestos_layout(group: str) -> list[tuple[str, list[str]]]:
    """The Puestos divisions and their metric order — taken from the profile tables so the grid reads
    in the exact same order. Each division is a table pane; a column already placed in an earlier
    division is not repeated (OPS lives in Estándar, its first table). Statcast/Coeficientes drop the
    G/AB (pitching: G/IP) context prefix, already counted under Estándar. Two rankable batting metrics
    are not shown in any table: Sencillos (1B) slots between H and 2B, Boletos intencionales (IBB)
    after BB.
    """
    if group == "fielding":
        # Fildeo no tiene Statcast ni Coeficientes: los batazos (AO/GO/FH/BIP…) son del bateador y del
        # lanzador, no de la posición defensiva. Y "Receptor" es su propia división porque solo aplica
        # a C — la página de líderes la muestra cuando la posición elegida es esa.
        divisions = [
            ("Estándar", [c.attr for c in columns.FIELDING_STANDARD]),
            ("Avanzado", [c.attr for c in columns.FIELDING_ADVANCED]),
            ("Receptor", [c.attr for c in columns.FIELDING_CATCHER]),
        ]
    elif group == "batting":
        standard = [c.attr for c in columns.BATTING_STANDARD]
        standard = _insert_after(standard, "h", "x1b")  # Sencillos entre H y 2B
        standard = _insert_after(standard, "bb", "ibb")  # Boletos intencionales tras BB
        divisions = [
            ("Estándar", standard),
            ("Avanzado", [c.attr for c in columns.BATTING_ADVANCED]),
            ("Statcast", [c.attr for c in columns.BATTING_STATCAST[2:]]),
            ("Coeficientes", [c.attr for c in columns.BATTING_RATIOS[2:]]),
        ]
    else:
        divisions = [
            ("Estándar", [c.attr for c in columns.PITCHING_STANDARD]),
            ("Avanzado", [c.attr for c in columns.PITCHING_ADVANCED]),
            ("Statcast", [c.attr for c in columns.PITCHING_STATCAST[2:]]),
            ("Coeficientes", [c.attr for c in columns.PITCHING_RATIOS[2:]]),
        ]
    seen: set[str] = set()
    layout: list[tuple[str, list[str]]] = []
    for label, attrs in divisions:
        ordered: list[str] = []
        for attr in attrs:
            if attr not in seen:
                seen.add(attr)
                ordered.append(attr)
        layout.append((label, ordered))
    return layout


def _pretty_qualifier(formula: str) -> str:
    """`PA>=502` -> `PA ≥ 502`; the coefficient columns get their short label. Blank stays blank."""
    return (
        formula.replace("BALLS_IN_PLAY", "BIP")
        .replace("TOTAL_SWINGS", "swings")
        .replace(">=", " ≥ ")
        .replace("<=", " ≤ ")
        .strip()
    )


_POSITION_ORDER: dict[str, int] = {p: i for i, p in enumerate(["P", "C", "1B", "2B", "3B", "SS", "LF", "CF", "RF"])}
# La fila de la rejilla es una métrica EN una posición. La posición es None fuera de fildeo, que es
# donde el ranking no se parte por posición.
_PuestoKey = tuple[int, str | None]


def _position_order(key: _PuestoKey) -> tuple[int, int]:
    """Ordena las filas de una métrica de fildeo por posición, en el orden del scorebook."""
    return (key[0], _POSITION_ORDER.get(key[1] or "", 99))


def _puestos_grid(player: Player, group: str, *, postseason: bool) -> dict[str, Any] | None:
    """One Puestos board — Serie Regular (`postseason=False`) or Postemporada (`True`): a
    metric-by-season matrix of where the player finished among Dominicans, plus the de-por-vida
    column, grouped into the profile's table divisions. A season cell is his rank that year, blank
    unless he made the top 10; the de-por-vida column reaches the top 25. A row is any metric where he
    was top 10 in a season OR top 25 de por vida. A shared rank (dense-rank tie) is flagged with `*`.
    `None` when he has nothing to show for this board.
    """
    # Su oficio MÁS fildeo. La defensa se rankea por posición, así que la fila ya no es una métrica
    # sino una métrica EN una posición: un antesalista que también jugó el jardín tiene dos filas de
    # asistencias, con puestos distintos, y por eso la posición va en la descripción.
    groups = [group, "fielding"]
    base = Leader.objects.filter(player=player, postseason=postseason, metric__stat_group__in=groups)
    by_key: dict[_PuestoKey, dict[int, int]] = defaultdict(dict)
    seasons: set[int] = set()
    for mark in base.filter(board=Leader.Board.BEST_SEASON, rank__lte=_PUESTOS_TOP_N):
        if mark.season is None:  # a season board always carries one; guard keeps the types honest
            continue
        by_key[mark.metric_id, mark.fielding_pos][mark.season] = mark.rank
        seasons.add(mark.season)
    career_rank = {
        (mark.metric_id, mark.fielding_pos): mark.rank
        for mark in base.filter(board=Leader.Board.BEST_CAREER, rank__lte=_PUESTOS_CAREER_TOP_N)
    }

    keys = set(by_key) | set(career_rank)  # union: season top-10s and career top-25s
    if not keys:
        return None
    metrics = {m.pk: m for m in Metric.objects.filter(pk__in={pk for pk, _ in keys})}

    # A rank is shared when >1 player sits on it in that (metric, board, season, position). One
    # grouped query; the board index (metric, board, season, pos, …, rank) serves the GROUP BY.
    shared = (
        Leader.objects.filter(
            metric_id__in=metrics,
            postseason=postseason,
            board__in=(Leader.Board.BEST_SEASON, Leader.Board.BEST_CAREER),
            rank__lte=_PUESTOS_CAREER_TOP_N,  # covers both bands; season cells only read ranks ≤ 10
        )
        .values("metric_id", "board", "season", "fielding_pos", "rank")
        .annotate(n=models.Count("player_id"))
        .filter(n__gt=1)
    )
    tied = {(g["metric_id"], g["board"], g["season"], g["fielding_pos"], g["rank"]) for g in shared}

    def cell(key: _PuestoKey, board_value: str, season: int | None, rank: int | None) -> dict[str, Any]:
        metric_pk, pos = key
        return {"rank": rank, "tied": rank is not None and (metric_pk, board_value, season, pos, rank) in tied}

    ordered_seasons = sorted(seasons)

    def row(key: _PuestoKey) -> dict[str, Any]:
        metric, pos = metrics[key[0]], key[1]
        name = metric.name_es or metric.abbrev
        return {
            # La posición va en la descripción y no en una columna aparte: solo la llevan las filas de
            # fildeo, y una columna vacía en todas las demás pesaría más de lo que aclara.
            "name": f"{name} ({pos})" if pos else name,
            "abbrev": metric.abbrev,
            "direction": _DIRECTION_SIGN.get(metric.direction, ""),
            "descriptive": metric.column in _DESCRIPTIVE_COLUMNS,  # SAB-01: perfil, no "mejor/peor"
            "cells": [cell(key, Leader.Board.BEST_SEASON, s, by_key.get(key, {}).get(s)) for s in ordered_seasons],
            "career": cell(key, Leader.Board.BEST_CAREER, None, career_rank.get(key)),
        }

    # Group the player's metrics into the profile's divisions, in table order. A division with no
    # top-10 metric for this player is dropped (no empty header). Fildeo lleva sus divisiones aparte y
    # rotuladas, o su "Estándar" chocaría con el del oficio.
    by_column: dict[str, dict[str, list[_PuestoKey]]] = defaultdict(lambda: defaultdict(list))
    for key in keys:
        metric = metrics[key[0]]
        by_column[metric.stat_group][metric.column].append(key)
    placed: set[_PuestoKey] = set()
    sections: list[dict[str, Any]] = []
    for stat_group in groups:
        cols_here = by_column[stat_group]
        for label, cols in _puestos_layout(stat_group):
            # Varias posiciones en la misma métrica: una fila por posición, en el orden del scorebook.
            section_keys = [k for col in cols for k in sorted(cols_here.get(col, []), key=_position_order)]
            placed.update(section_keys)
            if section_keys:
                title = f"Fildeo · {label}" if stat_group == "fielding" else label
                sections.append({"label": title, "rows": [row(k) for k in section_keys]})
    leftover = [row(k) for k in sorted(keys - placed, key=_position_order)]
    if leftover:  # defensive: a rankable metric no table lists — never silently dropped
        sections.append({"label": "Otras", "rows": leftover})

    shown_groups = {metrics[pk].stat_group for pk, _ in keys}
    fielding_q = ("", "")
    if postseason:
        # October has no qualifier cascade; the rate boards use the fixed floors from the engine.
        season_q, career_q = leaders._POST_QUALIFIER.get(group, ("", ""))
        coef_season: list[str] = []  # no batted-ball/coefficient boards in October
        coef_career: list[str] = []
    else:
        defaults, _ = _qualifier_context()
        season_q, career_q = defaults.get(group, ("", ""))
        # Fildeo se mide en juegos EN LA POSICIÓN, no en turnos ni entradas, así que su umbral es otro
        # y va en su propia línea cuando la rejilla trae filas de defensa.
        if "fielding" in shown_groups:
            fielding_q = defaults.get("fielding", ("", ""))
        # La rejilla tiene columnas de temporada Y una de "De por vida", así que el pie muestra
        # ambos umbrales del coeficiente (400/2000…), no solo el de temporada. Emparejados para no
        # descolocar season y career cuando distintas métricas usan BIP vs swings.
        pairs = sorted({(m.qualifier_season, m.qualifier_career) for m in metrics.values() if m.qualifier_season})
        coef_season = list(dict.fromkeys(_pretty_qualifier(s) for s, _ in pairs))
        coef_career = list(dict.fromkeys(_pretty_qualifier(c) for _, c in pairs if c))
    qualifiers = {
        "season": _pretty_qualifier(season_q),
        "career": _pretty_qualifier(career_q),
        "fielding": {"season": _pretty_qualifier(fielding_q[0]), "career": _pretty_qualifier(fielding_q[1])},
        "coefficients": {"season": coef_season, "career": coef_career},
    }
    return {"seasons": ordered_seasons, "sections": sections, "qualifiers": qualifiers}


def _puestos_context(player: Player) -> dict[str, Any]:
    """The two Puestos boards: Serie Regular and Postemporada.

    El oficio es el suyo y solo el suyo —el bateo incidental de un lanzador se rankea contra gente
    cuyo trabajo es batear, así que no es su puesto— pero el FILDEO va siempre: defender es parte del
    oficio de los dos, y se rankea por posición, que es su propia comparación justa.
    Cualquiera de los dos tableros puede ser `None` si no tiene nada que mostrar.
    """
    group = "pitching" if is_pitcher(player) else "batting"
    return {
        "group": group,
        "regular": _puestos_grid(player, group, postseason=False),
        "postseason": _puestos_grid(player, group, postseason=True),
    }


class PuestosTab(PlayerTab):
    key = "puestos"
    label = "Puestos"
    template = "profiles/tabs/puestos.html"
    base_order = 40  # after Bateo/Pitcheo/Fildeo

    def applies_to(self, player: Player) -> bool:
        group = "pitching" if is_pitcher(player) else "batting"
        # A top-10 season OR a top-25 de-por-vida, regular OR October, en su oficio o en la defensa.
        return (
            Leader.objects.filter(player=player, metric__stat_group__in=[group, "fielding"])
            .filter(
                models.Q(board=Leader.Board.BEST_SEASON, rank__lte=_PUESTOS_TOP_N)
                | models.Q(board=Leader.Board.BEST_CAREER, rank__lte=_PUESTOS_CAREER_TOP_N)
            )
            .exists()
        )

    def context(self, player: Player) -> dict[str, Any]:
        return _puestos_context(player)


REGISTRY: list[PlayerTab] = [BattingTab(), PitchingTab(), FieldingTab(), PuestosTab()]  # append new tabs here


def tabs_for(player: Player) -> list[PlayerTab]:
    """The tabs that apply to a player, in that player's display order (pitchers lead with Pitcheo)."""
    return sorted((tab for tab in REGISTRY if tab.applies_to(player)), key=lambda tab: tab.order_for(player))
