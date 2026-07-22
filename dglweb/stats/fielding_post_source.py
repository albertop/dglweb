"""Fetch one season of postseason fielding from the proxy and shape it into `FieldingPost` rows.

The simplest download of them all: per round, one bulk `season` call (group=fielding), one row per
(player, position). No per-player calls, no XXX (one team per round), no sabermetrics/UZR. Reuses
`map_fielding`; drops the columns the postseason source does not carry.
"""

from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats._download import BULK_LIMIT, fetch_team_codes
from dglweb.stats.batting_post_source import ROUNDS
from dglweb.stats.fielding_mapping import map_fielding
from dglweb.stats.leagues import league_code

# `dbo.mlbFieldingPost` has no age (extra) nor the catcher stolen-base columns nor UZR.
_DROP = {"age", "stolen_bases", "caught_stealing", "uzr"}


def _bulk(client: MlbProxyClient, season: int, game_type: str) -> dict[int, list[dict[str, Any]]]:
    """Per (player, position) splits for a round; grouped by player (a player fields many positions)."""
    payload = client.get(
        "/api/v1/stats",
        {
            "stats": "season",
            "group": "fielding",
            "gameType": game_type,
            "season": season,
            "playerPool": "All",
            "limit": BULK_LIMIT,
        },
    )
    stats = payload.get("stats") or []
    splits = stats[0].get("splits") or [] if stats else []
    by_player: dict[int, list[dict[str, Any]]] = {}
    for split in splits:
        player_id = (split.get("player") or {}).get("id")
        if player_id is not None:
            by_player.setdefault(player_id, []).append(split)
    return by_player


def _team_code(split: dict[str, Any], codes: dict[int, str]) -> str | None:
    team_id = (split.get("team") or {}).get("id")
    return codes.get(team_id) if isinstance(team_id, int) else None


def fetch_season(client: MlbProxyClient, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
    """Every postseason fielding row of `season` for the given players (one per round/position)."""
    codes = fetch_team_codes(client, season)
    rows: list[dict[str, Any]] = []

    for round_label, game_type in ROUNDS.items():
        bulk = _bulk(client, season, game_type)

        for player_id in sorted(player_ids & bulk.keys()):
            for split in bulk[player_id]:
                pos = (split.get("position") or {}).get("abbreviation")
                if pos is None:
                    continue
                mapped = {k: v for k, v in map_fielding(split.get("stat") or {}).items() if k not in _DROP}
                rows.append(
                    {
                        "player_id": player_id,
                        "season": season,
                        "round": round_label,
                        "team": _team_code(split, codes),
                        "league": league_code(split.get("league")),
                        "pos": pos,
                        **mapped,
                    }
                )
    return rows
