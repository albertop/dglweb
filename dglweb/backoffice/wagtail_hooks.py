"""Backoffice = the admin section for administrators, inside the Wagtail admin.

This is the EXTENSIBLE home for all admin tools. The Dominican players CRUD is the first;
future tools (data sources, scraper status, ads, …) are added to `items` below — no
restructuring needed.
"""

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSetGroup

from dglweb.players.viewsets import PlayerViewSet


class BackofficeViewSetGroup(SnippetViewSetGroup):  # type: ignore[misc]
    menu_label = "Backoffice"
    menu_icon = "cogs"
    menu_name = "backoffice"
    # Add future backoffice CRUDs/tools here.
    items = (PlayerViewSet,)


register_snippet(BackofficeViewSetGroup)
