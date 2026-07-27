from django.apps import AppConfig


class ArticlesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "dglweb.articles"
    verbose_name = "Artículos"

    def ready(self) -> None:
        """Engancha la invalidación de la URL cacheada del índice. Ver el módulo de contexto."""
        from dglweb.articles.context_processors import conectar_senales

        conectar_senales()
