"""Backoffice view over the ingest log — the pipeline's monitoring screen.

Read-only: these rows are written by the scrapers, not by hand, so there is no add/edit panel,
only the list and an inspect view. Registered in the Backoffice group next to the players CRUD.
"""

from wagtail.admin.ui.tables import Column
from wagtail.snippets.views.snippets import SnippetViewSet

from dglweb.stats.models import IngestRun


# Wagtail ships no type stubs (see dglweb/players/viewsets.py).
class IngestRunViewSet(SnippetViewSet):  # type: ignore[misc]
    model = IngestRun
    icon = "history"
    menu_label = "Ejecuciones"
    menu_name = "ingest_runs"
    # `duration` is a model property, so it has no verbose_name; label the column explicitly.
    list_display = (
        "command",
        "scope",
        "status",
        "started_at",
        "rows_affected",
        Column("duration", label="Duración"),
    )
    list_filter = ("status", "command")
    ordering = ("-started_at",)
    list_per_page = 50
    add_to_admin_menu = False  # it lives under the Backoffice group
    inspect_view_enabled = True  # click a run to read its detail / error
