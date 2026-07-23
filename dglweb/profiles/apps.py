from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    """Public-facing player (and later leaders) pages — the data-driven frontend of Fase 4."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "dglweb.profiles"
    verbose_name = "Perfiles públicos"
