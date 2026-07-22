"""Fetch one season of fielding from the proxy and shape it into `Fielding` rows.

Fielding is per **position**, so it does not fit the shared `_download.py` (which is per team).
Its own shape, verified against the proxy:

* The bulk `/stats?group=fielding` returns one split per **(player, position)** — the season
  total at that position, tagged with the last team and a `numTeams`.
* A position played with one team → that single row is the total (`team` = the real team).
* A position played with several teams → the bulk row is the combined total (`team=XXX`), and a
  per-player call supplies the per-team breakdown.
* `UZR` comes from the fielding sabermetrics, keyed by (player, position); it lands only on each
  position's season-total row, never on the per-team split rows — as in the source.

Keyed by (player, season, team, pos); there is no `stint`.
"""

from typing import Any

from dglweb.mlb.client import MlbProxyClient
from dglweb.stats._download import BULK_LIMIT, fetch_team_codes
from dglweb.stats.fielding_mapping import map_fielding
from dglweb.stats.leagues import COMBINED_LEAGUE, COMBINED_TEAM, league_code


def _bulk(client: MlbProxyClient, stat_type: str, season: int) -> dict[int, list[dict[str, Any]]]:
    """Fielding is multi-row per player (one per position), so group the splits by player."""
    payload = client.get(
        "/api/v1/stats",
        {"stats": stat_type, "group": "fielding", "season": season, "playerPool": "All", "limit": BULK_LIMIT},
    )
    stats = payload.get("stats") or []
    splits = stats[0].get("splits") or [] if stats else []
    by_player: dict[int, list[dict[str, Any]]] = {}
    for split in splits:
        player_id = (split.get("player") or {}).get("id")
        if player_id is not None:
            by_player.setdefault(player_id, []).append(split)
    return by_player


def _pos(split: dict[str, Any]) -> str | None:
    return (split.get("position") or {}).get("abbreviation")


def _stat(split: dict[str, Any] | None) -> dict[str, Any]:
    return (split or {}).get("stat") or {}


def _team_code(split: dict[str, Any], codes: dict[int, str]) -> str | None:
    team_id = (split.get("team") or {}).get("id")
    return codes.get(team_id) if isinstance(team_id, int) else None


def _per_team_splits(client: MlbProxyClient, player_id: int, season: int) -> list[dict[str, Any]]:
    """Per (position, team) splits from the per-player call; the no-team combined rows are dropped."""
    payload = client.get(
        f"/api/v1/people/{player_id}",
        {
            "sportId": 1,
            "hydrate": (
                f"stats(group=[fielding],gameType=[R],type=[season],"
                f"startDate=01/01/{season},endDate=12/31/{season},season={season})"
            ),
        },
    )
    people = payload.get("people") or []
    stats = people[0].get("stats") if people else None
    splits = list((stats or [{}])[0].get("splits") or []) if stats else []
    return [s for s in splits if s.get("team")]


def _row(
    *, player_id: int, season: int, team: str, league: str, pos: str, stat: dict[str, Any], uzr: float | None
) -> dict[str, Any]:
    return {
        "player_id": player_id,
        "season": season,
        "team": team,
        "league": league,
        "pos": pos,
        **map_fielding(stat),
        "uzr": uzr,
    }


def fetch_season(client: MlbProxyClient, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
    """Every fielding row of `season` for the given players, ready for `Fielding(**row)`."""
    codes = fetch_team_codes(client, season)
    bulk = _bulk(client, "season", season)
    uzr = {
        ((split.get("player") or {}).get("id"), _pos(split)): _stat(split).get("UZR")
        for splits in _bulk(client, "sabermetrics", season).values()
        for split in splits
    }

    rows: list[dict[str, Any]] = []
    for player_id in sorted(player_ids & bulk.keys()):
        positions = bulk[player_id]
        traded = any((sp.get("numTeams") or 1) > 1 for sp in positions)
        per_team = _per_team_splits(client, player_id, season) if traded else []

        for split in positions:
            pos = _pos(split)
            if pos is None:
                continue
            position_uzr = uzr.get((player_id, pos))

            if (split.get("numTeams") or 1) > 1:
                rows.append(
                    _row(
                        player_id=player_id,
                        season=season,
                        team=COMBINED_TEAM,
                        league=COMBINED_LEAGUE,
                        pos=pos,
                        stat=_stat(split),
                        uzr=position_uzr,
                    )
                )
                for team_split in per_team:
                    if _pos(team_split) != pos:
                        continue
                    code = _team_code(team_split, codes)
                    if code:
                        rows.append(
                            _row(
                                player_id=player_id,
                                season=season,
                                team=code,
                                league=league_code(team_split.get("league")),
                                pos=pos,
                                stat=_stat(team_split),
                                uzr=None,
                            )
                        )
            else:
                code = _team_code(split, codes)
                if code:
                    rows.append(
                        _row(
                            player_id=player_id,
                            season=season,
                            team=code,
                            league=league_code(split.get("league")),
                            pos=pos,
                            stat=_stat(split),
                            uzr=position_uzr,
                        )
                    )
    return rows
