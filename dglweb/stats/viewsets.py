"""Backoffice view over the ingest log — the pipeline's monitoring screen.

Read-only: these rows are written by the scrapers, not by hand, so there is no add/edit panel,
only the list and an inspect view. Registered in the Backoffice group next to the players CRUD.
"""

from collections.abc import Iterable

from django.contrib.auth.models import AbstractBaseUser, AnonymousUser
from django.utils.functional import cached_property
from wagtail.admin.ui.tables import Column
from wagtail.permissions import ModelPermissionPolicy
from wagtail.snippets.views.snippets import SnippetViewSet

from dglweb.stats.models import IngestRun

_User = AbstractBaseUser | AnonymousUser


class _ViewOnlyPermissionPolicy(ModelPermissionPolicy):  # type: ignore[misc]
    """Grants only `view` — even to superusers, so the Add/Edit/Delete controls never render.

    The model's `default_permissions = ("view",)` already hides them for regular admins, but Django
    superusers bypass every permission check; denying non-view actions here closes that gap for the
    ingest log specifically (the players CRUD keeps its normal, editable policy).
    """

    def user_has_permission(self, user: _User, action: str) -> bool:
        return action == "view" and bool(super().user_has_permission(user, action))

    def user_has_any_permission(self, user: _User, actions: Iterable[str]) -> bool:
        return self.user_has_permission(user, "view") and "view" in actions


# Wagtail ships no type stubs (see dglweb/players/viewsets.py).
class IngestRunViewSet(SnippetViewSet):  # type: ignore[misc]
    model = IngestRun

    @cached_property
    def permission_policy(self) -> _ViewOnlyPermissionPolicy:
        return _ViewOnlyPermissionPolicy(self.model)

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
