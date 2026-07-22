"""The Backoffice: the administrators' section of the Wagtail admin.

This is the single assembly point for every admin tool the site needs. The players CRUD is
the first one; the ones that come with the scrapers (data sources, run monitoring, ads, …)
get added to `items` below — the menu structure does not have to change.

Each tool lives in its own domain app (`dglweb.<app>.viewsets`); this module only groups them.
"""

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSetGroup

from dglweb.players.viewsets import PlayerViewSet
from dglweb.stats.viewsets import IngestRunViewSet


# Wagtail ships no type stubs (see dglweb/players/viewsets.py).
class BackofficeViewSetGroup(SnippetViewSetGroup):  # type: ignore[misc]
    menu_label = "Backoffice"
    menu_icon = "cogs"
    menu_order = 800
    items = (PlayerViewSet, IngestRunViewSet)  # add future admin tools here


register_snippet(BackofficeViewSetGroup)
