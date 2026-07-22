"""Tests for the parity_batting command wiring (Fase 3).

The comparison core is covered in test_parity; here we check the command reads the extract,
applies the source renames, and fails loudly on a real difference. The network is stubbed.
"""

import json
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from dglweb.players.models import Player
from tests.test_players import RECORD

PID = RECORD["player_id"]


def _extract(tmp_path: Path, rows: list[dict[str, Any]]) -> str:
    path = tmp_path / "extract.json"
    path.write_text(json.dumps(rows), encoding="utf-8")
    return str(path)


@pytest.fixture
def player(db: None) -> Player:
    return Player.objects.create(**RECORD)


@pytest.fixture
def fetched(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def fake_fetch(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        return [r for r in rows if r["season"] == season]

    monkeypatch.setattr("dglweb.stats.management.commands.parity_batting.fetch_season", fake_fetch)
    return rows


@pytest.mark.django_db
def test_reports_ok_when_the_port_matches(player: Player, fetched: list[dict[str, Any]], tmp_path: Path) -> None:
    # Source columns keep their original casing; the command lowercases and renames them.
    source = {"player_id": PID, "season": 2024, "stint": 1, "G": 150, "HR": 20, "wRCPlus": 130}
    fetched.append({"player_id": PID, "season": 2024, "stint": 1, "g": 150, "hr": 20, "w_rc_plus": 130})

    call_command("parity_batting", "--expected", _extract(tmp_path, [source]))


@pytest.mark.django_db
def test_raises_on_a_counting_mismatch(player: Player, fetched: list[dict[str, Any]], tmp_path: Path) -> None:
    source = {"player_id": PID, "season": 2024, "stint": 1, "HR": 20}
    fetched.append({"player_id": PID, "season": 2024, "stint": 1, "hr": 19})

    with pytest.raises(CommandError, match="diferencias"):
        call_command("parity_batting", "--expected", _extract(tmp_path, [source]))


@pytest.mark.django_db
def test_the_renamed_columns_line_up(player: Player, fetched: list[dict[str, Any]], tmp_path: Path) -> None:
    """ABpHR -> ab_per_hr etc.; a rename slip would show up as a phantom coverage gap."""
    source = {"player_id": PID, "season": 2024, "stint": 1, "ABpHR": 15.0, "CatcherInt": 0}
    fetched.append({"player_id": PID, "season": 2024, "stint": 1, "ab_per_hr": 15.0, "catcher_int": 0})

    call_command("parity_batting", "--expected", _extract(tmp_path, [source]))


@pytest.mark.django_db
def test_a_missing_extract_file_is_a_clear_error(player: Player, fetched: list[dict[str, Any]]) -> None:
    with pytest.raises(CommandError, match="no existe"):
        call_command("parity_batting", "--expected", "/nope/missing.json")


@pytest.mark.django_db
def test_refuses_with_an_empty_master_table(fetched: list[dict[str, Any]], tmp_path: Path) -> None:
    source = {"player_id": PID, "season": 2024, "stint": 1, "HR": 20}

    with pytest.raises(CommandError, match="dgl_master"):
        call_command("parity_batting", "--expected", _extract(tmp_path, [source]))


# --- parity_pitching ------------------------------------------------------------------


@pytest.fixture
def fetched_pitching(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def fake_fetch(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        return [r for r in rows if r["season"] == season]

    monkeypatch.setattr("dglweb.stats.management.commands.parity_pitching.fetch_season", fake_fetch)
    return rows


@pytest.mark.django_db
def test_parity_pitching_ok(player: Player, fetched_pitching: list[dict[str, Any]], tmp_path: Path) -> None:
    source = {"player_id": PID, "season": 2008, "stint": 1, "so": 47, "era": 3.47}
    fetched_pitching.append({"player_id": PID, "season": 2008, "stint": 1, "so": 47, "era": 3.47})

    call_command("parity_pitching", "--expected", _extract(tmp_path, [source]))


@pytest.mark.django_db
def test_parity_pitching_raises_on_mismatch(
    player: Player, fetched_pitching: list[dict[str, Any]], tmp_path: Path
) -> None:
    source = {"player_id": PID, "season": 2008, "stint": 1, "so": 47}
    fetched_pitching.append({"player_id": PID, "season": 2008, "stint": 1, "so": 40})

    with pytest.raises(CommandError, match="diferencias"):
        call_command("parity_pitching", "--expected", _extract(tmp_path, [source]))


@pytest.mark.django_db
def test_parity_pitching_missing_file(player: Player, fetched_pitching: list[dict[str, Any]]) -> None:
    with pytest.raises(CommandError, match="no existe"):
        call_command("parity_pitching", "--expected", "/nope/missing.json")


@pytest.mark.django_db
def test_parity_pitching_empty_master(fetched_pitching: list[dict[str, Any]], tmp_path: Path) -> None:
    source = {"player_id": PID, "season": 2008, "stint": 1, "so": 47}

    with pytest.raises(CommandError, match="dgl_master"):
        call_command("parity_pitching", "--expected", _extract(tmp_path, [source]))


# --- parity_fielding (keyed by player, season, team, pos) ------------------------------


@pytest.fixture
def fetched_fielding(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def fake_fetch(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        return [r for r in rows if r["season"] == season]

    monkeypatch.setattr("dglweb.stats.management.commands.parity_fielding.fetch_season", fake_fetch)
    return rows


def _fld(**kw: Any) -> dict[str, Any]:
    return {"player_id": PID, "season": 2006, "team": "SLN", "pos": "2B", **kw}


@pytest.mark.django_db
def test_parity_fielding_ok(player: Player, fetched_fielding: list[dict[str, Any]], tmp_path: Path) -> None:
    fetched_fielding.append(_fld(po=69, a=94))

    call_command("parity_fielding", "--expected", _extract(tmp_path, [_fld(po=69, a=94)]))


@pytest.mark.django_db
def test_parity_fielding_raises_on_mismatch(
    player: Player, fetched_fielding: list[dict[str, Any]], tmp_path: Path
) -> None:
    fetched_fielding.append(_fld(po=70))

    with pytest.raises(CommandError, match="diferencias"):
        call_command("parity_fielding", "--expected", _extract(tmp_path, [_fld(po=69)]))


@pytest.mark.django_db
def test_parity_fielding_reports_a_missing_row_by_position_key(
    player: Player, fetched_fielding: list[dict[str, Any]], tmp_path: Path
) -> None:
    # Source has an SS line the port did not produce -> missing by (player, season, team, pos).
    fetched_fielding.append(_fld(pos="2B", po=69))

    with pytest.raises(CommandError, match="diferencias"):
        call_command("parity_fielding", "--expected", _extract(tmp_path, [_fld(pos="2B", po=69), _fld(pos="SS", po=9)]))


@pytest.mark.django_db
def test_parity_fielding_missing_file(player: Player, fetched_fielding: list[dict[str, Any]]) -> None:
    with pytest.raises(CommandError, match="no existe"):
        call_command("parity_fielding", "--expected", "/nope/missing.json")


# --- parity_batting_post (keyed by player, season, round) -----------------------------


@pytest.fixture
def fetched_post(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def fake_fetch(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        return [r for r in rows if r["season"] == season]

    monkeypatch.setattr("dglweb.stats.management.commands.parity_batting_post.fetch_season", fake_fetch)
    return rows


@pytest.mark.django_db
def test_parity_batting_post_ok(player: Player, fetched_post: list[dict[str, Any]], tmp_path: Path) -> None:
    # The post extract is aliased to our field names already (no rename in the command).
    source = {"player_id": PID, "season": 2013, "round": "WS", "h": 11, "hr": 2}
    fetched_post.append({"player_id": PID, "season": 2013, "round": "WS", "h": 11, "hr": 2})

    call_command("parity_batting_post", "--expected", _extract(tmp_path, [source]))


@pytest.mark.django_db
def test_parity_batting_post_raises_on_mismatch(
    player: Player, fetched_post: list[dict[str, Any]], tmp_path: Path
) -> None:
    source = {"player_id": PID, "season": 2013, "round": "WS", "h": 11}
    fetched_post.append({"player_id": PID, "season": 2013, "round": "WS", "h": 10})

    with pytest.raises(CommandError, match="diferencias"):
        call_command("parity_batting_post", "--expected", _extract(tmp_path, [source]))


@pytest.mark.django_db
def test_parity_batting_post_reports_a_missing_round(
    player: Player, fetched_post: list[dict[str, Any]], tmp_path: Path
) -> None:
    # Source has a DS row the port did not produce -> missing by (player, season, round).
    fetched_post.append({"player_id": PID, "season": 2013, "round": "WS", "h": 11})

    with pytest.raises(CommandError, match="diferencias"):
        call_command(
            "parity_batting_post",
            "--expected",
            _extract(
                tmp_path,
                [
                    {"player_id": PID, "season": 2013, "round": "WS", "h": 11},
                    {"player_id": PID, "season": 2013, "round": "DS", "h": 5},
                ],
            ),
        )


# --- parity_pitching_post -------------------------------------------------------------


@pytest.fixture
def fetched_pitching_post(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def fake_fetch(client: object, season: int, player_ids: set[int]) -> list[dict[str, Any]]:
        return [r for r in rows if r["season"] == season]

    monkeypatch.setattr("dglweb.stats.management.commands.parity_pitching_post.fetch_season", fake_fetch)
    return rows


@pytest.mark.django_db
def test_parity_pitching_post_ok(player: Player, fetched_pitching_post: list[dict[str, Any]], tmp_path: Path) -> None:
    source = {"player_id": PID, "season": 2013, "round": "WS", "so": 7, "sv": 3}
    fetched_pitching_post.append({"player_id": PID, "season": 2013, "round": "WS", "so": 7, "sv": 3})

    call_command("parity_pitching_post", "--expected", _extract(tmp_path, [source]))


@pytest.mark.django_db
def test_parity_pitching_post_raises_on_mismatch(
    player: Player, fetched_pitching_post: list[dict[str, Any]], tmp_path: Path
) -> None:
    source = {"player_id": PID, "season": 2013, "round": "WS", "so": 7}
    fetched_pitching_post.append({"player_id": PID, "season": 2013, "round": "WS", "so": 6})

    with pytest.raises(CommandError, match="diferencias"):
        call_command("parity_pitching_post", "--expected", _extract(tmp_path, [source]))
