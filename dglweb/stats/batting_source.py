"""Fetch one season of batting from the proxy and shape it into `Batting` rows.

Mirrors the owner's R pipeline, because the loaded rows have to match `dbo.mlbBatting`:

1. Three bulk calls per season (`season`, `seasonAdvanced`, `sabermetrics`), filtered down to
   the master table's players. `sabermetrics` is why this goes season by season instead of
   player by player: the per-player hydrate returns nothing for it unless a season is pinned.
2. For a player who changed teams mid-season, three extra per-player calls to get the stints.

Two shapes were verified against the live proxy rather than assumed:

* **The combined row carries no `team`.** That, not its position in the list, is how it is
  identified — it happens to come first for `type=season` and last for `yearByYear`.
* **Stints arrive newest first**, so they are reversed to get the chronological order the
  source table uses (Kansas City = stint 1, Arizona = stint 2 for a player traded west).

Team codes come from `/teams` per season: the stat splits carry only a team id and the long
name, never the `KCA`/`LAN` code the source table stores.
"""

from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats.leagues import COMBINED_LEAGUE, COMBINED_TEAM, league_code, team_code
from dglweb.stats.mapping import map_advanced, map_regular, map_sabermetrics

BULK_LIMIT = 8000


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


def _bulk_by_player(client: MlbProxyClient, stat_type: str, season: int) -> dict[int, dict[str, Any]]:
    """One split per player: for a traded player this is already his combined season."""
    payload = client.get(
        "/api/v1/stats",
        {
            "stats": stat_type,
            "group": "hitting",
            "season": season,
            "playerPool": "All",
            "limit": BULK_LIMIT,
        },
    )
    by_player: dict[int, dict[str, Any]] = {}
    for split in _splits(payload):
        player_id = (split.get("player") or {}).get("id")
        if player_id is not None:
            by_player[player_id] = split
    return by_player


def _stints_by_team(client: MlbProxyClient, player_id: int, season: int, stat_type: str) -> list[dict[str, Any]]:
    """The player's per-team splits for one season, oldest first."""
    payload = client.get(
        f"/api/v1/people/{player_id}",
        {
            "sportId": 1,
            "hydrate": (
                f"stats(group=[hitting],gameType=[R],type=[{stat_type}],"
                f"startDate=01/01/{season},endDate=12/31/{season},season={season})"
            ),
        },
    )
    people = payload.get("people") or []
    stats = people[0].get("stats") if people else None
    splits = list((stats or [{}])[0].get("splits") or []) if stats else []
    # No `team` means the combined row; the real stints arrive newest first.
    return list(reversed([split for split in splits if split.get("team")]))


def _stat(split: dict[str, Any] | None) -> dict[str, Any]:
    return (split or {}).get("stat") or {}


def _row(
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
        **map_regular(regular),
        **map_advanced(advanced),
        **map_sabermetrics(sabermetrics),
    }


def _team_of(split: dict[str, Any], codes: dict[int, str]) -> str | None:
    team_id = (split.get("team") or {}).get("id")
    return codes.get(team_id) if team_id is not None else None


def _by_team_id(splits: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    return {split["team"]["id"]: split for split in splits if (split.get("team") or {}).get("id")}


def _traded_player_rows(
    client: MlbProxyClient,
    *,
    player_id: int,
    season: int,
    codes: dict[int, str],
    pos: str | None,
    combined: dict[str, dict[str, Any] | None],
) -> list[dict[str, Any]]:
    """One row per team, then the combined season carrying the `XXX` sentinel."""
    stints = _stints_by_team(client, player_id, season, "season")
    advanced = _by_team_id(_stints_by_team(client, player_id, season, "seasonAdvanced"))
    sabermetrics = _by_team_id(_stints_by_team(client, player_id, season, "sabermetrics"))

    rows = []
    for number, split in enumerate(stints, start=1):
        team_id = split["team"]["id"]
        rows.append(
            _row(
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


def fetch_season(client: MlbProxyClient, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
    """Every batting row of `season` for the given players, ready for `Batting(**row)`."""
    codes = fetch_team_codes(client, season)
    regular = _bulk_by_player(client, "season", season)
    advanced = _bulk_by_player(client, "seasonAdvanced", season)
    sabermetrics = _bulk_by_player(client, "sabermetrics", season)

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
                    client,
                    player_id=player_id,
                    season=season,
                    codes=codes,
                    pos=pos,
                    combined=combined,
                )
            )
        else:
            rows.append(
                _row(
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
