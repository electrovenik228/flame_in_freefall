"""Write the current AI output to a fixture, so a fresh database gets it without new Claude requests."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from ai.models import Insight, ReviewStatus

FIELDS = ["type", "target", "content", "citations", "model", "prompt_version", "input_hash", "checks", "review_status"]


class Command(BaseCommand):
    help = "Export current, visible AI rows to backend/fixtures/ai_output.json."

    def add_arguments(self, parser):
        parser.add_argument("--out", type=Path, default=settings.BASE_DIR / "fixtures" / "ai_output.json")

    def handle(self, *args, out: Path, **options):
        rows = []
        insights = Insight.objects.filter(
            is_current=True, review_status__in=[ReviewStatus.UNREVIEWED, ReviewStatus.APPROVED]
        ).select_related("investigation")
        for insight in sorted(insights, key=lambda i: (i.investigation.psi_id if i.investigation else "", i.type)):
            row = {"psi_id": insight.investigation.psi_id if insight.investigation else None}
            row.update({field: getattr(insight, field) for field in FIELDS})
            row["generated_at"] = insight.generated_at.isoformat()
            rows.append(row)
        out.write_text(json.dumps(rows, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(rows)} AI rows written to {out}")
