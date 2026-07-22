"""Admin CRUD for the DGL master table, surfaced inside the Backoffice menu.

Registered by `dglweb.backoffice.wagtail_hooks` as the first item of the Backoffice group.
"""

from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.snippets.views.snippets import SnippetViewSet

from dglweb.players.models import Player


# Wagtail ships no type stubs, so its classes are `Any` to mypy; strict mode forbids
# subclassing Any. Relaxed locally (documented in docs/library-guidelines.md).
class PlayerViewSet(SnippetViewSet):  # type: ignore[misc]
    model = Player
    icon = "user"
    menu_label = "Jugadores (DGL master)"
    menu_name = "players"
    list_display = ("full_name", "pos", "bats", "throws", "debut_date", "player_id")
    list_filter = ("pos", "bats", "throws")
    search_fields = ("full_name", "lastname_1", "lastname_2", "firstname", "nickname", "dgl_id")
    list_per_page = 50
    ordering = ("full_name",)
    add_to_admin_menu = False  # it lives under the Backoffice group

    panels = (
        MultiFieldPanel(
            [FieldPanel("player_id"), FieldPanel("dgl_id")],
            heading="Identidad",
        ),
        MultiFieldPanel(
            [
                FieldPanel("firstname"),
                FieldPanel("secondname"),
                FieldPanel("lastname_1"),
                FieldPanel("lastname_2"),
                FieldPanel("nickname"),
                FieldPanel("full_name"),
            ],
            heading="Nombres",
        ),
        MultiFieldPanel(
            [
                FieldPanel("birth_date"),
                FieldPanel("birth_place"),
                FieldPanel("birth_province"),
                FieldPanel("birth_country_code"),
            ],
            heading="Nacimiento",
        ),
        MultiFieldPanel(
            [
                FieldPanel("bats"),
                FieldPanel("throws"),
                FieldPanel("height"),
                FieldPanel("weight"),
                FieldPanel("pos"),
            ],
            heading="Físico y juego",
        ),
        MultiFieldPanel(
            [
                FieldPanel("debut_date"),
                FieldPanel("death_date"),
                FieldPanel("sign_year"),
                FieldPanel("sign_date"),
                FieldPanel("dom_hof_year"),
                FieldPanel("hof_year"),
            ],
            heading="Carrera",
        ),
        MultiFieldPanel(
            [
                FieldPanel("bbref_id"),
                FieldPanel("bbref_minor_id"),
                FieldPanel("retro_id"),
                FieldPanel("yahoo_id"),
                FieldPanel("fangraphs_id"),
                FieldPanel("register_id"),
            ],
            heading="IDs externos",
        ),
    )
