"""Fetch one season of postseason pitching from the proxy and shape it into `PitchingPost` rows.

Same shape as postseason batting (per round, one row per player, no stint/XXX), but the pitching
group and mapping. Reuses `pitching_mapping` and `derive_pitching` (BAA, X1B, NIBB) unchanged;
drops the regular-season extras the postseason source does not carry.
"""

from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats._download import BULK_LIMIT, fetch_team_codes
from dglweb.stats.batting_post_source import ROUNDS
from dglweb.stats.leagues import league_code
from dglweb.stats.pitching_mapping import derive_pitching, map_advanced, map_regular

# `dbo.mlbPitchingPost` has none of the regular-season extras.
_REGULAR_EXTRAS = {"age", "ab", "sh_fail", "sh_missed"}


def _bulk(client: MlbProxyClient, stat_type: str, season: int, game_type: str) -> dict[int, dict[str, Any]]:
    payload = client.get(
        "/api/v1/stats",
        {
            "stats": stat_type,
            "group": "pitching",
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
    """Every postseason pitching row of `season` for the given players (one per round pitched)."""
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
                    **derive_pitching(counts),
                }
            )
    return rows
