"""Load AI output from the fixture and re-apply verified extractions. Makes no Claude request."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.dateparse import parse_datetime

from ai.models import Insight
from ai.services.generate import reproject_extraction
from catalog.models import Investigation


class Command(BaseCommand):
    help = "Import backend/fixtures/ai_output.json. Rows already present are skipped."

    def add_arguments(self, parser):
        parser.add_argument("--fixture", type=Path, default=settings.BASE_DIR / "fixtures" / "ai_output.json")

    @transaction.atomic
    def handle(self, *args, fixture: Path, **options):
        if not fixture.exists():
            self.stdout.write("No AI fixture found; nothing imported")
            return
        created = 0
        for row in json.loads(fixture.read_text(encoding="utf-8")):
            row = dict(row)
            psi_id, generated_at = row.pop("psi_id"), parse_datetime(row.pop("generated_at"))
            investigation = Investigation.objects.filter(psi_id=psi_id).first() if psi_id else None
            if psi_id and investigation is None:
                continue
            same = {"investigation": investigation, "type": row["type"], "target": row["target"]}
            if Insight.objects.filter(
                **same, input_hash=row["input_hash"], prompt_version=row["prompt_version"]
            ).exists():
                continue
            Insight.objects.filter(**same, is_current=True).update(is_current=False)
            insight = Insight.objects.create(investigation=investigation, **row)
            Insight.objects.filter(pk=insight.pk).update(generated_at=generated_at)
            created += 1
        applied = sum(reproject_extraction(item) for item in Investigation.objects.all())
        self.stdout.write(f"{created} AI rows imported, {applied} extractions applied")
