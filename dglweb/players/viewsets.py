from wagtail.snippets.views.snippets import SnippetViewSet

from .models import Player


# Wagtail is untyped (mypy sees its bases as Any); subclassing is intentional.
class PlayerViewSet(SnippetViewSet):  # type: ignore[misc]
    """CRUD for the Dominican players master table (lives in the Backoffice menu)."""

    model = Player
    icon = "user"
    menu_label = "Jugadores"
    menu_name = "players"
    # Added to the admin via the Backoffice group (see backoffice.wagtail_hooks), not directly.
    add_to_admin_menu = False
    list_display = ["full_name", "primary_position", "birth_country", "is_active"]
    list_filter = ["is_active", "primary_position"]
    search_fields = ["full_name", "mlbam_id"]
    ordering = ["full_name"]
