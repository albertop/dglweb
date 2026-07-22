"""The stat tables key on their natural key (composite PK), not a surrogate `id`.

Checked at the database level via introspection, so the assertions survive any change in Django's
`CompositePrimaryKey` API: what matters is the physical table — no `id` column, the primary key
IS the natural key, and the natural-key columns lead the table (the owner's requirement).
"""

import pytest
from django.db import connection

from dglweb.players.models import Player
from dglweb.stats.loader import save_batting_rows
from dglweb.stats.models import Batting
from tests.test_players import RECORD

# table -> natural-key columns, in order: they must BE the primary key and LEAD the table.
NATURAL_KEYS: dict[str, list[str]] = {
    "mlb_batting": ["player_id", "season", "stint"],
    "mlb_pitching": ["player_id", "season", "stint"],
    "mlb_fielding": ["player_id", "season", "team", "pos"],
    "mlb_batting_post": ["player_id", "season", "round"],
    "mlb_pitching_post": ["player_id", "season", "round"],
    "mlb_fielding_post": ["player_id", "season", "round", "pos"],
}


def _columns(table: str) -> list[str]:
    with connection.cursor() as cursor:
        return [col.name for col in connection.introspection.get_table_description(cursor, table)]


def _pk_columns(table: str) -> list[str]:
    with connection.cursor() as cursor:
        constraints = connection.introspection.get_constraints(cursor, table)
    for constraint in constraints.values():
        if constraint.get("primary_key"):
            return list(constraint["columns"])
    return []


@pytest.mark.django_db
@pytest.mark.parametrize(("table", "key"), NATURAL_KEYS.items())
def test_primary_key_is_the_natural_key(table: str, key: list[str]) -> None:
    assert _pk_columns(table) == key


@pytest.mark.django_db
@pytest.mark.parametrize(("table", "key"), NATURAL_KEYS.items())
def test_no_surrogate_id_column(table: str, key: list[str]) -> None:
    assert "id" not in _columns(table)


@pytest.mark.django_db
@pytest.mark.parametrize(("table", "key"), NATURAL_KEYS.items())
def test_natural_key_leads_the_table(table: str, key: list[str]) -> None:
    assert _columns(table)[: len(key)] == key


@pytest.mark.django_db
def test_upsert_is_idempotent_under_the_composite_pk() -> None:
    """The risky part: bulk_create(update_conflicts=...) must land on the composite PK's index."""
    player = Player.objects.create(**RECORD)
    save_batting_rows([{"player": player, "season": 2004, "stint": 1, "g": 100}])
    save_batting_rows([{"player": player, "season": 2004, "stint": 1, "g": 156}])  # same key

    assert Batting.objects.count() == 1
    assert Batting.objects.get().g == 156
