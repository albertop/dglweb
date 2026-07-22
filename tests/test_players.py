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
def test_import_refuses_to_clobber_existing_rows_without_a_flag(tmp_path):
    Player.objects.create(**RECORD)
    path = _write_extract(tmp_path, [RECORD])

    with pytest.raises(CommandError, match="already has"):
        call_command("import_dgl_master", file=str(path))


@pytest.mark.django_db
def test_import_upserts_rows_when_asked(tmp_path):
    Player.objects.create(**RECORD)
    path = _write_extract(tmp_path, [{**RECORD, "full_name": "Nombre Nuevo"}])

    call_command("import_dgl_master", file=str(path), upsert=True)

    assert Player.objects.get(pk=RECORD["player_id"]).full_name == "Nombre Nuevo"


@pytest.mark.django_db
def test_upsert_never_deletes_stats(tmp_path):
    """The whole point of FIX-1: a master reload must not cascade-delete the backfill."""
    from dglweb.stats.models import Batting

    player = Player.objects.create(**RECORD)
    Batting.objects.create(player=player, season=2004, stint=1, g=156)
    path = _write_extract(tmp_path, [{**RECORD, "full_name": "Nombre Nuevo"}])

    call_command("import_dgl_master", file=str(path), upsert=True)

    assert Batting.objects.count() == 1  # survived the reload


@pytest.mark.django_db
def test_delete_missing_removes_absent_players_without_stats(tmp_path):
    Player.objects.create(**RECORD)
    Player.objects.create(**_other_player())  # not in the extract below
    path = _write_extract(tmp_path, [RECORD])

    call_command("import_dgl_master", file=str(path), delete_missing=True)

    assert list(Player.objects.values_list("player_id", flat=True)) == [RECORD["player_id"]]


@pytest.mark.django_db
def test_delete_missing_refuses_to_remove_a_player_with_stats(tmp_path):
    from dglweb.stats.models import Batting

    Player.objects.create(**RECORD)
    other = Player.objects.create(**_other_player())
    Batting.objects.create(player=other, season=2010, stint=1, g=10)
    path = _write_extract(tmp_path, [RECORD])  # `other` is absent -> would be deleted

    with pytest.raises(CommandError, match="stats"):
        call_command("import_dgl_master", file=str(path), delete_missing=True)

    assert Player.objects.filter(pk=other.pk).exists()  # nothing deleted


@pytest.mark.django_db
def test_delete_missing_with_force_removes_a_player_with_stats(tmp_path):
    from dglweb.stats.models import Batting

    Player.objects.create(**RECORD)
    other = Player.objects.create(**_other_player())
    Batting.objects.create(player=other, season=2010, stint=1, g=10)
    path = _write_extract(tmp_path, [RECORD])

    call_command("import_dgl_master", file=str(path), delete_missing=True, force=True)

    assert not Player.objects.filter(pk=other.pk).exists()
    assert Batting.objects.count() == 0  # cascaded, as forced


@pytest.mark.django_db
def test_import_rejects_column_mismatch_and_names_the_row(tmp_path):
    path = _write_extract(tmp_path, [RECORD, {"player_id": 1, "columna_rara": "x"}])

    with pytest.raises(CommandError, match="Row 1: column mismatch"):
        call_command("import_dgl_master", file=str(path))


@pytest.mark.django_db
def test_import_rejects_duplicate_player_id(tmp_path):
    path = _write_extract(tmp_path, [RECORD, {**RECORD, "dgl_id": "distinto"}])

    with pytest.raises(CommandError, match="Duplicate player_id"):
        call_command("import_dgl_master", file=str(path))


@pytest.mark.django_db
def test_import_rejects_duplicate_unique_id(tmp_path):
    # Two different players sharing a bbref_id — the DB would reject it with a crude error.
    path = _write_extract(tmp_path, [RECORD, _other_player(bbref_id=RECORD["bbref_id"])])

    with pytest.raises(CommandError, match="Duplicate bbref_id"):
        call_command("import_dgl_master", file=str(path))


def test_import_rejects_missing_file(tmp_path):
    with pytest.raises(CommandError, match="not found"):
        call_command("import_dgl_master", file=str(tmp_path / "no_existe.json"))


@pytest.mark.django_db
def test_hof_year_is_an_optional_cooperstown_field() -> None:
    """New field: the Cooperstown induction year, separate from the Dominican HoF year."""
    Player.objects.create(**{**RECORD, "hof_year": 2011})

    assert Player.objects.get(pk=RECORD["player_id"]).hof_year == 2011
    assert Player._meta.get_field("hof_year").null is True


def test_hof_year_is_not_part_of_the_import_extract() -> None:
    """It is admin-edited in the backoffice, so it must not be a required extract column."""
    from dglweb.players.management.commands.import_dgl_master import EXPECTED_FIELDS

    assert "hof_year" not in EXPECTED_FIELDS


def test_every_field_has_a_spanish_admin_label() -> None:
    """The backoffice is Spanish; Django's auto-generated labels ("Firstname") are not."""
    english_defaults = {
        f.name: f.verbose_name
        for f in Player._meta.get_fields()
        if hasattr(f, "verbose_name") and f.verbose_name == f.name.replace("_", " ")
    }

    assert english_defaults == {}, f"campos sin etiqueta en español: {sorted(english_defaults)}"


@pytest.mark.django_db
def test_names_sort_the_spanish_way_not_byte_wise() -> None:
    """Guards the Postgres image: musl (alpine) collates byte-wise and buries accented names.

    Under byte ordering "Félix" lands *after* "Freddy" (É is a multibyte sequence above "r"),
    which readers would see in every sorted list on the site. glibc sorts it as a dictionary does.
    """
    Player.objects.create(**_other_player(player_id=1, dgl_id="fel01", full_name="Félix Bautista"))
    Player.objects.create(**_other_player(player_id=2, dgl_id="fre01", full_name="Freddy Peralta"))
    Player.objects.create(**_other_player(player_id=3, dgl_id="pen01", full_name="Francisco Peña"))
    Player.objects.create(**_other_player(player_id=4, dgl_id="per01", full_name="Francisco Pérez"))

    names = list(Player.objects.order_by("full_name").values_list("full_name", flat=True))

    assert names == ["Félix Bautista", "Francisco Peña", "Francisco Pérez", "Freddy Peralta"]
