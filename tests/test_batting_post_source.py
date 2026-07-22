"""Tests for the postseason batting download (Fase 3).

Rounds map to gameTypes (DS=D, WC=F, LCS=L, WS=W). One row per player per round; no XXX, no
per-player calls. Reuses the regular-batting mapping and formulas — checked with David Ortiz's
2013 World Series line (16 AB, 11 H).
"""

from typing import Any

from dglweb.stats.batting_post_source import ROUNDS, fetch_season

TEAMS = {"teams": [{"id": 111, "teamCode": "bos", "name": "Boston Red Sox"}]}
AL = {"id": 103, "name": "AL"}


def _split(**kwargs: Any) -> dict[str, Any]:
    return {"season": "2013", **kwargs}


def _bulk(*splits: dict[str, Any]) -> dict[str, Any]:
    return {"stats": [{"splits": list(splits)}]}


class FakeClient:
    """Answers per (stats type, gameType); records the gameTypes it was asked for."""

    def __init__(self, responses: dict[tuple[str, str], dict[str, Any]]) -> None:
        self._responses = responses
        self.game_types: list[str] = []

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = params or {}
        if path == "/api/v1/teams":
            return TEAMS
        game_type = str(params.get("gameType") or "")
        self.game_types.append(game_type)
        return self._responses.get((str(params.get("stats")), game_type), {"stats": [{"splits": []}]})


ORTIZ = 120074
# Ortiz played DS, LCS and WS in 2013 (gameTypes D, L, W); not the wild card (F).
RESPONSES = {
    ("season", "D"): _bulk(
        _split(
            stat={"AB": 13, "H": 5, "HR": 2, "X2B": 2, "X3B": 0, "BB": 1, "IBB": 0},
            team={"id": 111},
            league=AL,
            player={"id": ORTIZ},
            position={"abbreviation": "DH"},
        )
    ),
    ("season", "L"): _bulk(
        _split(
            stat={"AB": 22, "H": 2, "HR": 1, "X2B": 0, "X3B": 0, "BB": 3},
            team={"id": 111},
            league=AL,
            player={"id": ORTIZ},
            position={"abbreviation": "DH"},
        )
    ),
    ("season", "W"): _bulk(
        _split(
            stat={"AB": 16, "H": 11, "HR": 2, "X2B": 2, "X3B": 0, "BB": 8, "IBB": 4},
            team={"id": 111},
            league=AL,
            player={"id": ORTIZ},
            position={"abbreviation": "DH"},
        )
    ),
    ("seasonAdvanced", "W"): _bulk(_split(stat={"Swings": 60, "SwingMiss": 5}, player={"id": ORTIZ})),
}


def test_rounds_map_to_the_documented_game_types() -> None:
    assert ROUNDS == {"DS": "D", "WC": "F", "LCS": "L", "WS": "W"}


def test_one_row_per_round_the_player_appears_in() -> None:
    rows = fetch_season(FakeClient(RESPONSES), 2013, {ORTIZ})  # type: ignore[arg-type]

    by_round = {r["round"]: r for r in rows}
    assert set(by_round) == {"DS", "LCS", "WS"}  # not WC — he did not play it
    assert (by_round["WS"]["ab"], by_round["WS"]["h"], by_round["WS"]["hr"]) == (16, 11, 2)
    assert (by_round["WS"]["team"], by_round["WS"]["league"], by_round["WS"]["pos"]) == ("BOS", "AL", "DH")


def test_derived_rates_are_computed_for_the_round() -> None:
    ws = next(r for r in fetch_season(FakeClient(RESPONSES), 2013, {ORTIZ}) if r["round"] == "WS")  # type: ignore[arg-type]

    assert ws["avg"] == 11 / 16  # .688
    assert ws["x1b"] == 11 - 2 - 0 - 2  # H - 2B - 3B - HR
    assert ws["total_swings"] == 60  # from the advanced payload


def test_all_four_rounds_are_queried() -> None:
    client = FakeClient(RESPONSES)

    fetch_season(client, 2013, {ORTIZ})  # type: ignore[arg-type]

    assert set(client.game_types) == {"D", "F", "L", "W"}


def test_players_outside_the_master_table_are_ignored() -> None:
    assert fetch_season(FakeClient(RESPONSES), 2013, {999999}) == []  # type: ignore[arg-type]
