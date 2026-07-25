"""The dgl_metric catalog and the 3-level qualifier cascade: models, generators, Backoffice forms."""

import pytest
from django.core.management import call_command
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from wagtail.snippets.models import get_snippet_models

from dglweb.stats.models import Metric, QualifierDefault, QualifierSeasonOverride
from tests.test_backoffice import admin_client  # noqa: F401 (pytest fixture)


@pytest.mark.django_db
def test_metric_natural_key_is_group_plus_column() -> None:
    Metric.objects.create(stat_group="batting", column="hr", kind=Metric.Kind.CUMULATIVE)

    with pytest.raises(IntegrityError):
        Metric.objects.create(stat_group="batting", column="hr", kind=Metric.Kind.CUMULATIVE)


@pytest.mark.django_db
def test_season_override_is_unique_per_group_and_season() -> None:
    QualifierSeasonOverride.objects.create(stat_group="batting", season=2020, qualifier_season="PA>=186")

    with pytest.raises(IntegrityError):
        QualifierSeasonOverride.objects.create(stat_group="batting", season=2020, qualifier_season="PA>=200")


# --- the generator -----------------------------------------------------------------------------


@pytest.fixture
def seeded(db: None) -> None:  # `db` is a side effect
    call_command("seed_metrics")


@pytest.mark.django_db
def test_seed_generates_the_catalog_from_our_tables(seeded: None) -> None:
    # One metric per rankable column across the three groups — a healthy count, all groups present.
    assert Metric.objects.count() > 100
    assert set(Metric.objects.values_list("stat_group", flat=True).distinct()) == {"batting", "pitching", "fielding"}


@pytest.mark.django_db
def test_seed_infers_kind_from_the_field_type(seeded: None) -> None:
    assert Metric.objects.get(stat_group="batting", column="hr").kind == Metric.Kind.CUMULATIVE  # Int
    assert Metric.objects.get(stat_group="batting", column="avg").kind == Metric.Kind.RATE  # Float


@pytest.mark.django_db
def test_seed_applies_the_leaderboard_config(seeded: None) -> None:
    hr = Metric.objects.get(stat_group="batting", column="hr")
    assert hr.direction == Metric.Direction.HIGHER
    assert hr.best_season and hr.best_career and hr.postseason and hr.is_active

    era = Metric.objects.get(stat_group="pitching", column="era")
    assert era.direction == Metric.Direction.LOWER  # lower ERA is better
    assert era.is_active


@pytest.mark.django_db
def test_seed_marks_additive_sabermetrics_as_cumulative(seeded: None) -> None:
    # SAB-03: WAR/UZR are floats but ADDITIVE — they must sum over a career, not prorate.
    assert Metric.objects.get(stat_group="batting", column="war").kind == Metric.Kind.CUMULATIVE
    assert Metric.objects.get(stat_group="fielding", column="uzr").kind == Metric.Kind.CUMULATIVE
    assert Metric.objects.get(stat_group="batting", column="woba").kind == Metric.Kind.RATE  # a true rate


def test_invalid_qualifier_formula_is_rejected() -> None:
    from django.core.exceptions import ValidationError

    from dglweb.stats.formula import validate_qualifier_formula

    validate_qualifier_formula("PA>=502")  # valid
    validate_qualifier_formula("")  # blank = no threshold, allowed
    with pytest.raises(ValidationError):
        validate_qualifier_formula("PA mayor que 502")  # typo -> rejected, not fail-open


def test_qualifies_is_fail_closed_on_an_invalid_formula() -> None:
    from dglweb.stats.qualifier import qualifies

    assert qualifies("", "batting", {"pa": 10}) is True  # blank = everyone (no threshold)
    assert qualifies("basura!!", "batting", {"pa": 10}) is False  # invalid = no one (fail-closed)


@pytest.mark.django_db
def test_seed_leaves_metric_qualifiers_blank_to_inherit_the_group_default(seeded: None) -> None:
    # Level 2 is blank by default: rate metrics inherit the group default (level 1), no duplication.
    assert Metric.objects.get(stat_group="batting", column="avg").qualifier_season == ""

    # The only exception: the batted-ball coefficients are rates over balls in play / swings, so
    # gating them on the group's PA would let an era with no batted-ball data top the board.
    own = set(Metric.objects.exclude(qualifier_season="").values_list("column", flat=True))
    assert own == {"gb_pct", "fb_pct", "ld_pct", "pu_pct", "gb_fb", "contact_pct", "whiff_pct"}
    # Atado a la constante y no al número: los pisos salen de un estudio (docs/UMBRALES_COEFICIENTES)
    # y ya se recalcularon una vez. Lo que este test cuida es que el nivel 2 se siembre, no cuánto vale.
    from dglweb.stats.management.commands.seed_metrics import _OWN_QUALIFIER

    for group, column in (("batting", "gb_pct"), ("batting", "whiff_pct"), ("pitching", "gb_pct")):
        metric = Metric.objects.get(stat_group=group, column=column)
        assert (metric.qualifier_season, metric.qualifier_career) == _OWN_QUALIFIER[group, column]


@pytest.mark.django_db
def test_seed_creates_one_group_default_per_group(seeded: None) -> None:
    assert QualifierDefault.objects.get(stat_group="batting").qualifier_season == "PA>=502"
    assert QualifierDefault.objects.get(stat_group="pitching").qualifier_season == "IP>=162"
    assert QualifierDefault.objects.get(stat_group="fielding").qualifier_season == "G>=100"
    assert QualifierDefault.objects.count() == 3


@pytest.mark.django_db
def test_seed_sets_sort_order_from_the_curated_display_order(seeded: None) -> None:
    assert Metric.objects.get(stat_group="batting", column="hr").sort_order == 13
    assert Metric.objects.get(stat_group="pitching", column="era").sort_order == 17
    assert Metric.objects.get(stat_group="pitching", column="xfip").sort_order == 900  # not curated -> last


@pytest.mark.django_db
def test_seed_excludes_keys_context_and_baseball_notation(seeded: None) -> None:
    assert not Metric.objects.filter(column__in=["season", "stint", "team", "league", "pos", "age"]).exists()
    assert not Metric.objects.filter(stat_group="pitching", column="ip").exists()  # rank outs, not ip
    assert not Metric.objects.filter(stat_group="fielding", column="innings").exists()


@pytest.mark.django_db
def test_seed_uses_judgment_for_columns_the_old_table_did_not_cover(seeded: None) -> None:
    xfip = Metric.objects.get(stat_group="pitching", column="xfip")  # not in the old dgl_stat
    assert xfip.direction == Metric.Direction.LOWER  # judgment: lower is better
    assert xfip.is_active  # curada como tablero en _ACTIVATE (owner: "actívalas todas")
    # Una columna sin config de tablero y sin curar (un componente de WAR) sigue inactiva.
    component = Metric.objects.get(stat_group="batting", column="base_running")
    assert not component.is_active and not component.best_season


@pytest.mark.django_db
def test_seed_is_idempotent_and_preserves_edits(seeded: None) -> None:
    total = Metric.objects.count()
    metric = Metric.objects.get(stat_group="batting", column="hr")
    metric.name_es = "Editado a mano"
    metric.save()

    call_command("seed_metrics")  # re-run

    assert Metric.objects.count() == total  # no duplicates
    assert Metric.objects.get(stat_group="batting", column="hr").name_es == "Editado a mano"  # edit kept


@pytest.mark.django_db
def test_reset_regenerates_from_scratch(seeded: None) -> None:
    Metric.objects.create(stat_group="batting", column="inventada", kind=Metric.Kind.CUMULATIVE)

    call_command("seed_metrics", reset=True)

    assert not Metric.objects.filter(column="inventada").exists()


# --- level 3: per-group season overrides (short seasons) ---------------------------------------


@pytest.mark.django_db
def test_override_seed_prorates_the_group_default_for_short_seasons(seeded: None) -> None:
    call_command("seed_qualifier_overrides")

    # One row per (group, season) covers every rate metric of the group.
    assert QualifierSeasonOverride.objects.get(stat_group="batting", season=2020).qualifier_season == "PA>=186"
    assert QualifierSeasonOverride.objects.get(stat_group="batting", season=1956).qualifier_season == "PA>=477"
    assert QualifierSeasonOverride.objects.get(stat_group="pitching", season=2020).qualifier_season == "IP>=60"
    assert QualifierSeasonOverride.objects.get(stat_group="fielding", season=2020).qualifier_season == "G>=37"


@pytest.mark.django_db
def test_override_seed_is_compact_and_idempotent(seeded: None) -> None:
    call_command("seed_qualifier_overrides")

    # 3 groups x 8 short seasons = 24 rows — not one per metric.
    assert QualifierSeasonOverride.objects.count() == 24

    call_command("seed_qualifier_overrides")  # re-run
    assert QualifierSeasonOverride.objects.count() == 24


@pytest.mark.django_db
def test_override_seed_covers_exactly_the_short_seasons(seeded: None) -> None:
    call_command("seed_qualifier_overrides")

    seasons = set(QualifierSeasonOverride.objects.values_list("season", flat=True).distinct())
    assert seasons == {1956, 1957, 1958, 1959, 1960, 1981, 1994, 2020}


# --- Backoffice forms --------------------------------------------------------------------------


@pytest.mark.django_db
def test_catalog_models_are_registered_as_backoffice_snippets() -> None:
    for model in (Metric, QualifierDefault, QualifierSeasonOverride):
        assert model in get_snippet_models()


@pytest.mark.django_db
def test_admin_can_open_the_editable_metric_form(admin_client: Client) -> None:  # noqa: F811
    """Unlike the read-only ingest log, the metrics catalog is fully editable."""
    add = admin_client.get(reverse("wagtailsnippets_stats_metric:add"))

    assert add.status_code == 200  # the Add form renders (editable)
    assert b"Liderazgo" in add.content  # the leaderboard panel


@pytest.mark.django_db
def test_admin_can_open_the_qualifier_forms(admin_client: Client) -> None:  # noqa: F811
    default = admin_client.get(reverse("wagtailsnippets_stats_qualifierdefault:add"))
    override = admin_client.get(reverse("wagtailsnippets_stats_qualifierseasonoverride:add"))

    assert default.status_code == 200
    assert override.status_code == 200
