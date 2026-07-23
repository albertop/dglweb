"""Check the in-house career totals against the proxy's career line (flags only, never rewrites).

Scheduled weekly. Unresolved disagreements land in `CareerParityIssue` and turn the ingest run
PARTIAL (a yellow row in the Backoffice); they clear themselves once a re-backfill fixes the data.
"""

from typing import Any

from django.core.management.base import BaseCommand

from dglweb.mlb.client import build_client
from dglweb.stats.career_parity import check_career_parity
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Verifica los totales de carrera in-house contra el career del proxy (solo marca/loguea)."

    def handle(self, *args: Any, **options: Any) -> None:
        client = build_client()
        try:
            with record_run("parity_career", "all") as run:
                result = check_career_parity(client, on_mismatch=run.fail)
                run.add_rows(result["checked"])
        finally:
            client.close()
        message = f"{result['checked']} revisados; {result['unresolved']} con disparidad."
        style = self.style.WARNING if result["unresolved"] else self.style.SUCCESS
        self.stdout.write(style(message))
