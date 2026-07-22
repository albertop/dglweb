"""Fetch one season of postseason batting from the proxy and shape it into `BattingPost` rows.

Postseason is per **round**, not per stint, so it does not use `_download.py` (that is per team).
It is simpler: for each of the four rounds, one bulk call gives one row per player (a player is on
a single team per round — no `XXX`, no per-player detail calls). Each round is a different
`gameType`, which is also how FIX-7 (parametrise `gameType`) is answered for the postseason.

Reuses the regular-batting mapping and formulas unchanged — the columns are identical to regular
batting minus the sabermetrics block, which the postseason simply does not fetch.
"""

from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats._download import BULK_LIMIT, fetch_team_codes
from dglweb.stats.derive import derived_rates
from dglweb.stats.leagues import league_code
from dglweb.stats.mapping import map_advanced, map_regular

# Our round label -> the statsapi gameType. Verified: all four return data.
ROUNDS = {"DS": "D", "WC": "F", "LCS": "L", "WS": "W"}

# `map_regular`/`map_advanced` also emit the regular-season extras; `dbo.mlbBattingPost` has none
# of them, so they are dropped to keep the postseason table a faithful mirror of the source.
_REGULAR_EXTRAS = {"age", "roe", "gidp_opp"}


def _bulk(client: MlbProxyClient, stat_type: str, season: int, game_type: str) -> dict[int, dict[str, Any]]:
    """One split per player for a given round (gameType). Unlike the regular _download bulk, this
    passes `gameType` so the /stats endpoint returns that postseason round, not the regular season."""
    payload = client.get(
        "/api/v1/stats",
        {
            "stats": stat_type,
            "group": "hitting",
            "gameType": game_type,
            "season": season,
            "playerPool": "All",
            "limit": BULK_LIMIT,
        },
    )
    stats = payload.get("stats") or []
    splits = stats[0].get("splits") or [] if stats else []
    by_player: dict[int, dict[str, Any]] = {}
    for split in splits:
        player_id = (split.get("player") or {}).get("id")
        if player_id is not None:
            by_player[player_id] = split
    return by_player


def _stat(split: dict[str, Any] | None) -> dict[str, Any]:
    return (split or {}).get("stat") or {}


def _team_code(split: dict[str, Any], codes: dict[int, str]) -> str | None:
    team_id = (split.get("team") or {}).get("id")
    return codes.get(team_id) if isinstance(team_id, int) else None


def fetch_season(client: MlbProxyClient, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
    """Every postseason batting row of `season` for the given players (one per round played)."""
    codes = fetch_team_codes(client, season)
    rows: list[dict[str, Any]] = []

    for round_label, game_type in ROUNDS.items():
        regular = _bulk(client, "season", season, game_type)
        advanced = _bulk(client, "seasonAdvanced", season, game_type)

        for player_id in sorted(player_ids & regular.keys()):
            split = regular[player_id]
            merged = {**map_regular(_stat(split)), **map_advanced(_stat(advanced.get(player_id)))}
            counts = {key: value for key, value in merged.items() if key not in _REGULAR_EXTRAS}
            rows.append(
                {
                    "player_id": player_id,
                    "season": season,
                    "round": round_label,
                    "team": _team_code(split, codes),
                    "league": league_code(split.get("league")),
                    "pos": (split.get("position") or {}).get("abbreviation"),
                    **counts,
                    **derived_rates(counts),
                }
            )
    return rows
