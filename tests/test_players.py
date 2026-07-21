"""Tests for the DGL master table (Fase 2)."""

import json
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError

from dglweb.players.models import Player

# Minimal valid record matching the extract's 28 columns.
RECORD: dict[str, Any] = {
    "player_id": 110104,
    "dgl_id": "albagi01",
    "bbref_id": "albagi01",
    "bbref_minor_id": "alba--001gib",
    "retro_id": "albag001",
    "yahoo_id": 4197,
    "fangraphs_id": 1000100,
    "register_id": "257e59ac",
    "lastname_1": "Alba",
    "lastname_2": "Rosado",
    "firstname": "Gibson",
    "secondname": "Alberto",
    "nickname": "",
    "full_name": "Gibson Alba",
    "birth_date": "1960-01-18",
    "birth_place": "Santiago",
    "birth_province": "Santiago",
    "birth_country_code": "DO",
    "bats": "L",
    "throws": "L",
    "height": "6-1",
    "weight": 175,
    "pos": "P",
    "debut_date": "1988-04-10",
    "death_date": None,
    "sign_year": 1978,
    "sign_date": None,
    "dom_hof_year": None,
}


def _write_extract(tmp_path: Path, records: list[dict[str, Any]]) -> Path:
    path = tmp_path / "extract.json"
    path.write_text(json.dumps(records), encoding="utf-8")
    return path


def _other_player(**overrides: Any) -> dict[str, Any]:
    """A second player: the nullable unique ids must be NULL, not copies of RECORD's."""
    blanked = dict.fromkeys(["bbref_id", "bbref_minor_id", "retro_id", "yahoo_id", "fangraphs_id", "register_id"])
    return {**RECORD, **blanked, "player_id": 222222, "dgl_id": "otro01", **overrides}


@pytest.mark.django_db
def test_str_returns_full_name():
    player = Player.objects.create(**RECORD)

    assert str(player) == "Gibson Alba"


@pytest.mark.django_db
def test_player_id_is_the_primary_key():
    player = Player.objects.create(**RECORD)

    assert player.pk == 110104


@pytest.mark.django_db
def test_dgl_id_rejects_duplicates():
    Player.objects.create(**RECORD)

    # Same dgl_id, different player_id -> must violate the unique constraint.
    with pytest.raises(IntegrityError):
        Player.objects.create(**_other_player(dgl_id=RECORD["dgl_id"]))


@pytest.mark.django_db
def test_import_loads_every_record(tmp_path):
    path = _write_extract(tmp_path, [RECORD, _other_player()])

    call_command("import_dgl_master", file=str(path))

    assert Player.objects.count() == 2


@pytest.mark.django_db
def test_import_preserves_null_sentinels(tmp_path):
    # The extract already converted the source's 0 sentinels to null; they must stay null.
    record = {**RECORD, "yahoo_id": None, "fangraphs_id": None, "sign_year": None}
    path = _write_extract(tmp_path, [record])

    call_command("import_dgl_master", file=str(path))

    player = Player.objects.get(pk=RECORD["player_id"])
    assert player.yahoo_id is None
    assert player.fangraphs_id is None
    assert player.sign_year is None


@pytest.mark.django_db
def test_import_refuses_to_clobber_existing_rows_without_replace(tmp_path):
    Player.objects.create(**RECORD)
    path = _write_extract(tmp_path, [RECORD])

    with pytest.raises(CommandError, match="already has"):
        call_command("import_dgl_master", file=str(path))


@pytest.mark.django_db
def test_import_replaces_rows_when_asked(tmp_path):
    Player.objects.create(**RECORD)
    path = _write_extract(tmp_path, [{**RECORD, "full_name": "Nombre Nuevo"}])

    call_command("import_dgl_master", file=str(path), replace=True)

    assert Player.objects.get(pk=RECORD["player_id"]).full_name == "Nombre Nuevo"


@pytest.mark.django_db
def test_import_rejects_column_mismatch(tmp_path):
    path = _write_extract(tmp_path, [{"player_id": 1, "columna_rara": "x"}])

    with pytest.raises(CommandError, match="Column mismatch"):
        call_command("import_dgl_master", file=str(path))


def test_import_rejects_missing_file(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        call_command("import_dgl_master", file=str(tmp_path / "no_existe.json"))


def test_every_field_has_a_spanish_admin_label() -> None:
    """The backoffice is Spanish; Django's auto-generated labels ("Firstname") are not."""
    english_defaults = {
        f.name: f.verbose_name
        for f in Player._meta.get_fields()
        if hasattr(f, "verbose_name") and f.verbose_name == f.name.replace("_", " ")
    }

    assert english_defaults == {}, f"campos sin etiqueta en español: {sorted(english_defaults)}"
