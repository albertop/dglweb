"""Rebuild the precomputed leaderboards (`dgl_leader`) from our stat tables.

Runs in the scheduler after the daily stat refresh. One full rebuild; the read side just reads.
"""

from typing import Any

from django.core.management.base import BaseCommand

from dglweb.stats.leaders import build_leaders
from dglweb.stats.runlog import record_run


class Command(BaseCommand):
    help = "Reconstruye los liderazgos (dgl_leader) desde nuestras tablas de stats."

    def handle(self, *args: Any, **options: Any) -> None:
        with record_run("build_leaders", "all") as run:
            result = build_leaders(note=self.stdout.write)
            run.add_rows(result["written"])
        self.stdout.write(self.style.SUCCESS(f"Líderes reconstruidos: {result['written']} filas."))
