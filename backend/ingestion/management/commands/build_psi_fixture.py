"""Build the slim, committed fixture from a raw PSI export.

The raw export is about 7 MB, nearly all of it version-diff fields. The fixture keeps
every descriptive field and every experiment table, drops the diff fields and personal
contact details, and records the checksum of the export it came from.
"""

import hashlib
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

DROP_FIELDS = {"added", "removed", "dirty", "modified", "versionMessageLocations"}
CONTACT_KEEP = ("firstName", "midInitials", "lastName", "affiliation")
RESEARCH_AREA = "Combustion Science"


class Command(BaseCommand):
    help = "Build backend/fixtures/psi_seed.json from a raw PSI export."

    def add_arguments(self, parser):
        parser.add_argument("export", type=Path)
        parser.add_argument("--out", type=Path, default=settings.BASE_DIR / "fixtures" / "psi_seed.json")

    def handle(self, *args, export: Path, out: Path, **options):
        raw_bytes = export.read_bytes()
        data = json.loads(raw_bytes)
        investigations, excluded = {}, []
        for psi_id, record in data["investigations"].items():
            if record.get("researchArea") != RESEARCH_AREA:
                excluded.append({"psi_id": psi_id, "research_area": record.get("researchArea", "")})
                continue
            slim = {key: value for key, value in record.items() if key not in DROP_FIELDS}
            slim["contacts"] = [
                {
                    **{key: contact.get(key, "") for key in CONTACT_KEEP},
                    "roles": [role.get("annotationValue", "") for role in contact.get("roles", [])],
                }
                for contact in record.get("contacts", [])
            ]
            investigations[psi_id] = slim
        fixture = {
            "source": data["source"],
            "api": data["api"],
            "retrieved_at": data["retrieved_at"],
            "licence_note": data["licence_note"],
            "export_sha256": hashlib.sha256(raw_bytes).hexdigest(),
            "seed_set": data["seed_set"],
            "missing": data["missing"],
            "excluded_not_combustion": excluded,
            "investigations": investigations,
            "experiment_tables": {k: v for k, v in data["experiment_tables"].items() if k in investigations},
        }
        out.write_text(json.dumps(fixture, ensure_ascii=False, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        self.stdout.write(f"{len(investigations)} investigations, {len(excluded)} excluded, {out.stat().st_size} bytes")
