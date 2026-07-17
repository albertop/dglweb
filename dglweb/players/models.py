from django.db import models


class Player(models.Model):
    """Master table of Dominican MLB players — the SINGLE source of truth for the site's
    "Dominican" filter.

    Being present in this table IS what makes a player "Dominican" for the site. It is
    curated by administrators (CRUD in the Backoffice). MLB's ``birth_country`` is only an
    INPUT/seed used to help populate the list — it is NOT the rule (edge cases like a
    US-born player of Dominican descent are decided by the admin, not by birth country).
    """

    class Bats(models.TextChoices):
        LEFT = "L", "Zurdo"
        RIGHT = "R", "Derecho"
        SWITCH = "S", "Ambidiestro"

    class Throws(models.TextChoices):
        LEFT = "L", "Zurdo"
        RIGHT = "R", "Derecho"

    # MLBAM id: the join key to MLB data (proxy + scrapers). Unique and stable.
    mlbam_id = models.PositiveIntegerField(unique=True, verbose_name="MLBAM ID")
    full_name = models.CharField(max_length=120, verbose_name="Nombre completo")
    primary_position = models.CharField(max_length=40, blank=True, verbose_name="Posición")
    bats = models.CharField(max_length=1, choices=Bats.choices, blank=True, verbose_name="Batea")
    throws = models.CharField(max_length=1, choices=Throws.choices, blank=True, verbose_name="Lanza")
    birth_date = models.DateField(null=True, blank=True, verbose_name="Nacimiento")
    birth_city = models.CharField(max_length=120, blank=True, verbose_name="Ciudad natal")
    # INPUT/seed only (from MLB). NOT the rule for "is Dominican" — the table itself is.
    birth_country = models.CharField(max_length=80, blank=True, verbose_name="País (MLB, informativo)")
    debut_date = models.DateField(null=True, blank=True, verbose_name="Debut")
    is_active = models.BooleanField(default=True, verbose_name="Activo")
    notes = models.TextField(blank=True, verbose_name="Notas", help_text="Justificación de casos borde, etc.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("full_name",)
        verbose_name = "Jugador"
        verbose_name_plural = "Jugadores"

    def __str__(self) -> str:
        return self.full_name
