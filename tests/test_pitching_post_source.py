"""Tests for the postseason pitching download (Fase 3)."""

from typing import Any

from dglweb.stats.pitching_post_source import fetch_season

TEAMS = {"teams": [{"id": 111, "teamCode": "bos", "name": "Boston Red Sox"}]}
AL = {"id": 103, "name": "AL"}
KOJI = 493200  # Koji Uehara stand-in id; any Dominican closer would do


def _split(**kwargs: Any) -> dict[str, Any]:
    return {"season": "2013", **kwargs}


def _bulk(*splits: dict[str, Any]) -> dict[str, Any]:
    return {"stats": [{"splits": list(splits)}]}


class FakeClient:
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


RESPONSES = {
    ("season", "W"): _bulk(
        _split(
            stat={
                "G": 5,
                "IP": "6.0",
                "ERA": "0.00",
                "K": 7,
                "H": 3,
                "BB": 0,
                "SV": 3,
                "BF": 20,
                "HBP": 0,
                "SH": 0,
                "SF": 0,
                "CI": 0,
            },
            team={"id": 111},
            league=AL,
            player={"id": KOJI},
            position={"abbreviation": "P"},
        )
    ),
    ("seasonAdvanced", "W"): _bulk(_split(stat={"Kp9": "10.5", "Swings": 90}, player={"id": KOJI})),
}


def test_one_row_per_round_pitched() -> None:
    rows = fetch_season(FakeClient(RESPONSES), 2013, {KOJI})  # type: ignore[arg-type]

    assert len(rows) == 1
    ws = rows[0]
    assert (ws["round"], ws["team"], ws["league"]) == ("WS", "BOS", "AL")
    assert (ws["so"], ws["sv"], ws["era"]) == (7, 3, 0.0)  # K->so, ERA parsed to float


def test_derived_and_advanced_reused_from_regular_pitching() -> None:
    ws = fetch_season(FakeClient(RESPONSES), 2013, {KOJI})[0]  # type: ignore[arg-type]

    assert ws["so_per9"] == 10.5  # advanced
    assert ws["baa"] == 3 / (20 - 0 - 0 - 0 - 0 - 0)  # BAA = H / (BF - BB - HBP - SH - SF - CI)
    assert ws["total_swings"] == 90


def test_the_postseason_extras_are_dropped() -> None:
    """age/ab/sh_fail/sh_missed are regular-season extras the post source does not carry."""
    ws = fetch_season(FakeClient(RESPONSES), 2013, {KOJI})[0]  # type: ignore[arg-type]

    assert "age" not in ws
    assert "ab" not in ws
    assert "sh_fail" not in ws


def test_all_four_rounds_are_queried() -> None:
    client = FakeClient(RESPONSES)

    fetch_season(client, 2013, {KOJI})  # type: ignore[arg-type]

    assert set(client.game_types) == {"D", "F", "L", "W"}
