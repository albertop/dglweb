"""The master table of Dominican players who reached MLB.

Source: DGL SQL Server `dbo.dglMaster` (migrated per the owner's mapping query).
Schema derived from the real source columns/types — nothing assumed.

**Authority rule:** being in this table is what makes a player "a Dominican MLB player".
`birth_country_code` is informational input from the source, NOT the rule.

**ETL rule — the source uses 0 as a "no value" sentinel; these are converted to NULL:**
`statsID`→`yahoo_id`, `fanGraphID`→`fangraphs_id`, `signYear`→`sign_year`,
`yearDomHof`→`dom_hof_year`. That is why `sign_year` is nullable even though the
source column is NOT NULL.

Not to be confused with `dom_players` (a separate, broader table of Dominicans in MLB *and*
the minors, refreshed once or twice per season, used to detect debuts and roster moves).
"""

from typing import TYPE_CHECKING

from django.db import models

if TYPE_CHECKING:
    from dglweb.stats.models import Batting


class Player(models.Model):
    # Reverse accessors are created at runtime by the related models, so django-stubs cannot
    # see them; declaring them here is what makes `player.batting_seasons` type-check.
    if TYPE_CHECKING:
        batting_seasons: models.Manager["Batting"]

    # --- identity / external ids -------------------------------------------------
    player_id = models.PositiveIntegerField(primary_key=True, verbose_name="MLB ID")
    dgl_id = models.CharField(max_length=10, unique=True, verbose_name="DGL ID")
    bbref_id = models.CharField(max_length=10, unique=True, null=True, blank=True, verbose_name="Baseball-Reference")
    bbref_minor_id = models.CharField(
        max_length=15, unique=True, null=True, blank=True, verbose_name="Baseball-Reference (menores)"
    )
    retro_id = models.CharField(max_length=10, unique=True, null=True, blank=True, verbose_name="Retrosheet")
    yahoo_id = models.PositiveIntegerField(unique=True, null=True, blank=True, verbose_name="Yahoo")
    fangraphs_id = models.PositiveIntegerField(unique=True, null=True, blank=True, verbose_name="FanGraphs")
    register_id = models.CharField(max_length=10, unique=True, null=True, blank=True, verbose_name="Register")

    # --- names -------------------------------------------------------------------
    lastname_1 = models.CharField(max_length=30, verbose_name="Primer apellido")
    lastname_2 = models.CharField(max_length=30, null=True, blank=True, verbose_name="Segundo apellido")
    firstname = models.CharField(max_length=30, verbose_name="Nombre")
    secondname = models.CharField(max_length=30, null=True, blank=True, verbose_name="Segundo nombre")
    nickname = models.CharField(max_length=20, null=True, blank=True, verbose_name="Apodo")
    full_name = models.CharField(max_length=50, verbose_name="Nombre completo")

    # --- birth -------------------------------------------------------------------
    birth_date = models.DateField(null=True, blank=True, verbose_name="Fecha de nacimiento")
    birth_place = models.CharField(max_length=60, null=True, blank=True, verbose_name="Lugar de nacimiento")
    birth_province = models.CharField(max_length=60, null=True, blank=True, verbose_name="Provincia")
    birth_country_code = models.CharField(max_length=2, null=True, blank=True, verbose_name="País (código)")

    # --- physical / playing ------------------------------------------------------
    bats = models.CharField(max_length=1, null=True, blank=True, verbose_name="Batea")
    throws = models.CharField(max_length=1, null=True, blank=True, verbose_name="Lanza")
    height = models.CharField(
        max_length=4, null=True, blank=True, verbose_name="Estatura", help_text="Pies-pulgadas, ej. 5-10"
    )
    weight = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Peso (lb)")
    pos = models.CharField(max_length=2, null=True, blank=True, verbose_name="Posición")

    # --- career milestones -------------------------------------------------------
    debut_date = models.DateField(null=True, blank=True, verbose_name="Fecha de debut")
    death_date = models.DateField(null=True, blank=True, verbose_name="Fecha de fallecimiento")
    # Nullable because the ETL converts the source's 0 sentinel to NULL (see module docstring).
    sign_year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="Año de firma")
    sign_date = models.DateField(null=True, blank=True, verbose_name="Fecha de firma")
    dom_hof_year = models.PositiveIntegerField(null=True, blank=True, verbose_name="Año Salón de la Fama RD")
    # Cooperstown (MLB Hall of Fame) induction year. Not in the SQL Server extract — the admin
    # fills it by hand in the backoffice, so it is not part of `import_dgl_master`'s columns.
    hof_year = models.PositiveIntegerField(null=True, blank=True, verbose_name="Año Salón de la Fama (Cooperstown)")

    class Meta:
        db_table = "dgl_master"
        ordering = ["full_name"]
        verbose_name = "jugador"
        verbose_name_plural = "jugadores"

    def __str__(self) -> str:
        return self.full_name

    @property
    def slug(self) -> str:
        """SEO slug for the public page; always ends in the MLB id so it never collides."""
        from django.utils.text import slugify

        return f"{slugify(self.full_name)}-{self.player_id}"
