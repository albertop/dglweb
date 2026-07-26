"""parity_career: flags in-house/proxy career disagreements, loop-safe (option b)."""

from typing import Any

import pytest
from django.core.management import call_command

from dglweb.players.models import Player
from dglweb.stats.career_parity import check_career_parity
from dglweb.stats.models import BattingCareer, CareerLevel, CareerParityIssue, IngestRun
from tests.test_players import _other_player


class FakeClient:
    """Returns a canned proxy career line per statsapi group (proxy field names)."""

    def __init__(self, stats: dict[str, dict[str, Any]]) -> None:
        self.stats = stats

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        stat = self.stats.get((params or {}).get("group", ""), {})
        return {"stats": [{"splits": [{"stat": stat}]}]}

    def close(self) -> None:
        pass


def _total(pid: int, **stats: int) -> Player:
    player = Player.objects.create(**_other_player(player_id=pid, dgl_id=f"p{pid}"))
    BattingCareer.objects.create(player=player, level=CareerLevel.TOTAL, **stats)
    return player


@pytest.mark.django_db
def test_matching_totals_leave_no_issue() -> None:
    _total(1, g=100, hr=40)
    client = FakeClient({"hitting": {"G": 100, "HR": 40}})

    result = check_career_parity(client)

    assert result == {"checked": 1, "unresolved": 0}
    assert not CareerParityIssue.objects.exists()


@pytest.mark.django_db
def test_a_mismatch_is_recorded_with_the_diff() -> None:
    _total(1, g=100, hr=40)
    client = FakeClient({"hitting": {"G": 100, "HR": 50}})  # proxy has 50 HR, we have 40

    check_career_parity(client)

    issue = CareerParityIssue.objects.get(group="batting")
    assert "hr: nuestro=40 proxy=50" in issue.detail
    assert issue.status == CareerParityIssue.Status.UNRESOLVED


@pytest.mark.django_db
def test_the_issue_clears_itself_once_parity_passes() -> None:
    player = _total(1, g=100, hr=40)
    check_career_parity(FakeClient({"hitting": {"HR": 50}}))  # mismatch -> issue
    assert CareerParityIssue.objects.filter(player=player).exists()

    check_career_parity(FakeClient({"hitting": {"HR": 40}}))  # now matches -> issue deleted

    assert not CareerParityIssue.objects.filter(player=player).exists()


@pytest.mark.django_db
def test_a_persistent_mismatch_is_not_duplicated() -> None:
    _total(1, g=100, hr=40)
    client = FakeClient({"hitting": {"HR": 50}})

    check_career_parity(client)
    check_career_parity(client)  # re-run: still off

    assert CareerParityIssue.objects.count() == 1  # updated in place, never re-created


@pytest.mark.django_db
def test_command_turns_the_run_partial_on_a_mismatch(monkeypatch: pytest.MonkeyPatch) -> None:
    _total(1, g=100, hr=40)
    monkeypatch.setattr(
        "dglweb.stats.management.commands.parity_career.build_client",
        lambda: FakeClient({"hitting": {"HR": 50}}),
    )

    call_command("parity_career", "--force")

    run = IngestRun.objects.get(command="parity_career")
    assert run.status == IngestRun.Status.PARTIAL  # a yellow row: unresolved disparity
    assert "hr" in run.detail
