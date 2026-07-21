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
