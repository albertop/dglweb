from django.apps import AppConfig


class ProfilesConfig(AppConfig):
    """Public-facing player (and later leaders) pages — the data-driven frontend of Fase 4."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "dglweb.profiles"
    verbose_name = "Perfiles públicos"

    def ready(self) -> None:
        """Engancha la invalidación de las cachés de métricas y umbrales.

        Va en `ready()` y no al importar el módulo porque las señales necesitan los modelos ya
        cargados. Sin esto, el dueño cambiaría un umbral en el Backoffice y el sitio seguiría
        publicando el viejo hasta 24 horas — una caché sin invalidación no es una optimización, es un
        fallo con retraso.
        """
        from dglweb.profiles.metric_layout import conectar_senales

        conectar_senales()
