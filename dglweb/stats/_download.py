"""Shared machinery for downloading one season of a stat group from the proxy.

Batting, pitching (and later fielding) all fetch the same way — three bulk calls per season plus
three per-player calls for anyone traded mid-season — and differ only in three things, captured
by `SportConfig`:

* **`group`** — `"hitting"` or `"pitching"`, the statsapi group.
* **`reverse_stints`** — batting numbers stints newest-first (its R script reverses), pitching
  oldest-first. Verified against the source for a traded player in each. Getting this backwards
  swaps the stint numbers of every traded player, so it is a per-sport flag, not a guess.
* **`build_stats`** — turns the three `stat` dicts of a split into the sport's columns.

The rest is identical and lives here once: the combined row is the split with no `team`; team
codes come from `/teams`; advanced and sabermetric splits are matched to the regular ones by team
id.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats.leagues import COMBINED_LEAGUE, COMBINED_TEAM, league_code, team_code

BULK_LIMIT = 8000

BuildStats = Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class SportConfig:
    group: str
    reverse_stints: bool
    build_stats: BuildStats


def fetch_team_codes(client: MlbProxyClient, season: int) -> dict[int, str]:
    """Team id -> `KCA`-style code for a season."""
    payload = client.get("/api/v1/teams", {"sportId": 1, "season": season})
    codes = {}
    for team in payload.get("teams") or []:
        code = team_code(team.get("teamCode"))
        if team.get("id") is not None and code:
            codes[team["id"]] = code
    return codes


def _splits(payload: dict[str, Any]) -> list[dict[str, Any]]:
    stats = payload.get("stats") or []
    return list(stats[0].get("splits") or []) if stats else []


def _bulk_by_player(client: MlbProxyClient, stat_type: str, season: int, group: str) -> dict[int, dict[str, Any]]:
    """One split per player: for a traded player this is already his combined season."""
    payload = client.get(
        "/api/v1/stats",
        {"stats": stat_type, "group": group, "season": season, "playerPool": "All", "limit": BULK_LIMIT},
    )
    by_player: dict[int, dict[str, Any]] = {}
    for split in _splits(payload):
        player_id = (split.get("player") or {}).get("id")
        if player_id is not None:
            by_player[player_id] = split
    return by_player


def _stints_by_team(
    client: MlbProxyClient, player_id: int, season: int, stat_type: str, config: SportConfig
) -> list[dict[str, Any]]:
    """The player's per-team splits for one season, in the sport's stint order."""
    payload = client.get(
        f"/api/v1/people/{player_id}",
        {
            "sportId": 1,
            "hydrate": (
                f"stats(group=[{config.group}],gameType=[R],type=[{stat_type}],"
                f"startDate=01/01/{season},endDate=12/31/{season},season={season})"
            ),
        },
    )
    people = payload.get("people") or []
    stats = people[0].get("stats") if people else None
    splits = list((stats or [{}])[0].get("splits") or []) if stats else []
    teams = [split for split in splits if split.get("team")]  # no `team` => the combined row
    return list(reversed(teams)) if config.reverse_stints else teams


def _stat(split: dict[str, Any] | None) -> dict[str, Any]:
    return (split or {}).get("stat") or {}


def _row(
    config: SportConfig,
    *,
    player_id: int,
    season: int,
    stint: int,
    team: str | None,
    league: str,
    pos: str | None,
    regular: dict[str, Any],
    advanced: dict[str, Any],
    sabermetrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "season": season,
        "stint": stint,
        "team": team,
        "league": league,
        "pos": pos,
        **config.build_stats(regular, advanced, sabermetrics),
    }


def _team_of(split: dict[str, Any], codes: dict[int, str]) -> str | None:
    team_id = (split.get("team") or {}).get("id")
    return codes.get(team_id) if team_id is not None else None


def _by_team_id(splits: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {split["team"]["id"]: split for split in splits if (split.get("team") or {}).get("id")}


def _traded_player_rows(
    client: MlbProxyClient,
    config: SportConfig,
    *,
    player_id: int,
    season: int,
    codes: dict[int, str],
    pos: str | None,
    combined: dict[str, dict[str, Any] | None],
) -> list[dict[str, Any]]:
    """One row per team, then the combined season carrying the `XXX` sentinel."""
    stints = _stints_by_team(client, player_id, season, "season", config)
    advanced = _by_team_id(_stints_by_team(client, player_id, season, "seasonAdvanced", config))
    sabermetrics = _by_team_id(_stints_by_team(client, player_id, season, "sabermetrics", config))

    rows = []
    for number, split in enumerate(stints, start=1):
        team_id = split["team"]["id"]
        rows.append(
            _row(
                config,
                player_id=player_id,
                season=season,
                stint=number,
                team=codes.get(team_id),
                league=league_code(split.get("league")),
                pos=pos,
                regular=_stat(split),
                advanced=_stat(advanced.get(team_id)),
                sabermetrics=_stat(sabermetrics.get(team_id)),
            )
        )

    rows.append(
        _row(
            config,
            player_id=player_id,
            season=season,
            stint=len(rows) + 1,
            team=COMBINED_TEAM,
            league=COMBINED_LEAGUE,
            pos=pos,
            regular=_stat(combined["regular"]),
            advanced=_stat(combined["advanced"]),
            sabermetrics=_stat(combined["sabermetrics"]),
        )
    )
    return rows


def fetch_season(
    client: MlbProxyClient, season: int, player_ids: set[int], config: SportConfig
) -> list[dict[str, Any]]:
    """Every row of `season` for the given players, ready for `Model(**row)`."""
    codes = fetch_team_codes(client, season)
    regular = _bulk_by_player(client, "season", season, config.group)
    advanced = _bulk_by_player(client, "seasonAdvanced", season, config.group)
    sabermetrics = _bulk_by_player(client, "sabermetrics", season, config.group)

    rows: list[dict[str, Any]] = []
    for player_id in sorted(player_ids & regular.keys()):
        split = regular[player_id]
        pos = (split.get("position") or {}).get("abbreviation")
        combined = {
            "regular": split,
            "advanced": advanced.get(player_id),
            "sabermetrics": sabermetrics.get(player_id),
        }

        if (split.get("numTeams") or 1) > 1:
            rows.extend(
                _traded_player_rows(
                    client, config, player_id=player_id, season=season, codes=codes, pos=pos, combined=combined
                )
            )
        else:
            rows.append(
                _row(
                    config,
                    player_id=player_id,
                    season=season,
                    stint=1,
                    team=_team_of(split, codes),
                    league=league_code(split.get("league")),
                    pos=pos,
                    regular=_stat(split),
                    advanced=_stat(combined["advanced"]),
                    sabermetrics=_stat(combined["sabermetrics"]),
                )
            )
    return rows
