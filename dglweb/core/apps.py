from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dglweb.core"

    def ready(self) -> None:
        """Registra las comprobaciones de arranque. El porqué está en `core/checks.py`."""
        from dglweb.core import checks  # noqa: F401 — se registra al importarse
