from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ingestion.loader import load_fixture


class Command(BaseCommand):
    help = "Load the PSI seed fixture: investigations, publications, files, documents and test runs."

    def add_arguments(self, parser):
        parser.add_argument("--fixture", type=Path, default=settings.BASE_DIR / "fixtures" / "psi_seed.json")

    def handle(self, *args, fixture: Path, **options):
        run = load_fixture(fixture)
        self.stdout.write(self.style.SUCCESS(f"Loaded {run.counts}"))
        for error in run.errors:
            self.stdout.write(self.style.WARNING(error))
