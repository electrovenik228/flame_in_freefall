"""Load the PSI fixture into the database. Safe to run again: records are updated, not duplicated."""

import hashlib
import json
from datetime import date, datetime
from pathlib import Path

from django.contrib.postgres.search import SearchVector
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.text import slugify

from catalog.models import (
    Facility,
    Investigation,
    Project,
    Publication,
    SourceDocument,
    SourceFile,
    TestRun,
    VocabularyTerm,
)
from catalog.services.conditions import recompute_ranges_from_test_runs
from ingestion.models import IngestionRun
from ingestion.parsers import PARSERS, validate

# Project groups named in section 5.1, matched on the start of the PSI acronym.
PROJECT_PREFIXES = [
    ("ACME", "ACME", "Advanced Combustion via Microgravity Experiments"),
    ("FLEX", "FLEX family", "Flame Extinguishment Experiment and its follow-on"),
    ("BASS", "BASS family", "Burning and Suppression of Solids"),
    ("SAFFIRE", "Saffire", "Spacecraft Fire Experiment"),
    ("SAME", "SAME", "Smoke and Aerosol Measurement Experiment"),
]

# Facility name, type, and the lower-case phrases that identify it in the PSI hardware text.
FACILITY_RULES = [
    ("Combustion Integrated Rack (CIR)", "ISS rack", ["combustion integrated rack"]),
    ("Microgravity Science Glovebox (MSG)", "ISS glovebox", ["microgravity science glovebox"]),
    ("Multi-user Droplet Combustion Apparatus (MDCA)", "CIR insert", ["droplet combustion app", "mdca"]),
    ("ACME insert", "CIR insert", ["acme"]),
    ("Saffire enclosure in Cygnus", "Uncrewed vehicle experiment", ["saffire", "cygnus"]),
    ("Comparative Soot Diagnostic hardware", "ISS hardware", ["soot diagnostic"]),
]

RECORD_SECTIONS = [
    ("Objective", "objective"),
    ("Approach", "approach"),
    ("Hypothesis", "hypothesis"),
    ("Research impacts", "researchImpacts"),
]


def parse_psi_date(text: str | None) -> date | None:
    try:
        return datetime.strptime((text or "").strip(), "%m-%d-%Y").date()
    except ValueError:
        return None


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def record_text(psi_id: str, record: dict) -> str:
    """Plain-text rendering of a PSI record. Field values are copied unchanged."""
    lines = [f"PSI record {psi_id}", f"Title: {record.get('title', '').strip()}"]
    for label, key in (
        ("Acronym", "investigationAcronym"),
        ("Research area", "researchArea"),
        ("Research sub-area", "subResearchArea"),
        ("Project type", "projectType"),
        ("Flight program", "flightProgram"),
        ("Start date (month-day-year)", "investigationStartDate"),
        ("End date (month-day-year)", "investigationEndDate"),
        ("Experiment hardware", "experimentHardware"),
    ):
        value = (record.get(key) or "").strip()
        if value:
            lines.append(f"{label}: {value}")
    for label, key in RECORD_SECTIONS:
        value = (record.get(key) or "").strip()
        if value:
            lines += ["", f"{label}:", value]
    return "\n".join(lines) + "\n"


def contact_rows(record: dict) -> list[dict]:
    rows = []
    for contact in record.get("contacts", []):
        name = " ".join(filter(None, [contact.get("firstName"), contact.get("midInitials"), contact.get("lastName")]))
        if name:
            rows.append(
                {"name": name, "affiliation": contact.get("affiliation", ""), "roles": contact.get("roles", [])}
            )
    return rows


def split_links(text: str | None) -> list[str]:
    return [part.strip() for part in (text or "").split(",") if part.strip().startswith("http")]


@transaction.atomic
def load_fixture(path: Path) -> IngestionRun:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    retrieved_at = parse_datetime(data["retrieved_at"])
    run = IngestionRun.objects.create(route="owner_export", source_checksum=data.get("export_sha256", ""))
    seed = set(data["seed_set"])
    counts = {"investigations": 0, "publications": 0, "source_files": 0, "documents": 0, "test_runs": 0}
    errors: list[str] = [f"{psi_id}: listed as missing from the export" for psi_id in data.get("missing", [])]
    projects = {
        prefix: Project.objects.update_or_create(name=name, defaults={"description": description})[0]
        for prefix, name, description in PROJECT_PREFIXES
    }
    facilities = {
        name: Facility.objects.update_or_create(name=name, defaults={"type": kind})[0]
        for name, kind, _ in FACILITY_RULES
    }

    for psi_id, record in data["investigations"].items():
        acronym = (record.get("investigationAcronym") or "").strip()
        project = next((p for prefix, p in projects.items() if acronym.upper().startswith(prefix)), None)
        investigation, _ = Investigation.objects.update_or_create(
            psi_id=psi_id,
            defaults={
                "acronym": acronym,
                "title": record["title"].strip(),
                "doi": record.get("doi", ""),
                "project": project,
                "research_area": record.get("researchArea", ""),
                "sub_research_area": (record.get("subResearchArea") or "").strip(),
                "project_type": record.get("projectType", ""),
                "flight_program": record.get("flightProgram", ""),
                "start_date": parse_psi_date(record.get("investigationStartDate")),
                "end_date": parse_psi_date(record.get("investigationEndDate")),
                "objectives": (record.get("objective") or "").strip(),
                "approach": (record.get("approach") or "").strip(),
                "hypothesis": (record.get("hypothesis") or "").strip(),
                "benefits": (record.get("researchImpacts") or "").strip(),
                "hardware_text": (record.get("experimentHardware") or "").strip(),
                "hardware_links": split_links(record.get("experimentHardwareLink")),
                "contacts": contact_rows(record),
                "license_name": record.get("licenseName", ""),
                "license_url": record.get("licenseLink", ""),
                "psi_url": record["psi_page"],
                "psi_version": record.get("version"),
                "total_file_size": record.get("totalFileSize"),
                "is_seed": psi_id in seed,
                "retrieved_at": retrieved_at,
            },
        )
        counts["investigations"] += 1
        hardware = investigation.hardware_text.lower()
        investigation.facilities.set(
            [facilities[name] for name, _, phrases in FACILITY_RULES if any(p in hardware for p in phrases)]
        )

        text = record_text(psi_id, record)
        SourceDocument.objects.update_or_create(
            investigation=investigation,
            kind=SourceDocument.Kind.RECORD,
            title=f"{psi_id} investigation record",
            defaults={
                "text": text,
                "url": investigation.psi_url,
                "checksum": sha256(text),
                "retrieved_at": retrieved_at,
            },
        )
        counts["documents"] += 1

        investigation.publications.all().delete()
        for item in record.get("publications", []):
            doi = (item.get("doi") or "").strip()
            Publication.objects.create(
                investigation=investigation,
                title=(item.get("title") or "").strip()[:800],
                authors=item.get("authorList", ""),
                doi=doi,
                url=f"https://doi.org/{doi}" if doi else "",
            )
            counts["publications"] += 1

        for image in record.get("images", []):
            SourceFile.objects.update_or_create(
                investigation=investigation,
                path=image["remote_path"],
                defaults={
                    "name": image["file_name"],
                    "category": "Representative image",
                    "size": image.get("file_size"),
                },
            )
            counts["source_files"] += 1

        listed = {entry["file_name"]: entry for entry in record.get("experimentalTable", [])}
        investigation.test_runs.all().delete()
        for table in data["experiment_tables"].get(psi_id, []):
            name, content = table["file_name"], table["content"]
            entry = listed.get(name, {})
            source_file, _ = SourceFile.objects.update_or_create(
                investigation=investigation,
                path=entry.get("remote_path") or f"/Home/psi-data/{psi_id}/Experimental table/{name}",
                defaults={
                    "name": name,
                    "category": "Experimental table",
                    "size": entry.get("file_size", table.get("bytes")),
                    "version": table.get("version"),
                    "checksum": sha256(content),
                    "retrieved_at": retrieved_at,
                    "status": SourceFile.Status.RETRIEVED,
                },
            )
            counts["source_files"] += 1
            SourceDocument.objects.update_or_create(
                investigation=investigation,
                kind=SourceDocument.Kind.EXPERIMENT_TABLE,
                title=name,
                defaults={
                    "text": content,
                    "source_file": source_file,
                    "url": investigation.psi_url,
                    "checksum": sha256(content),
                    "retrieved_at": retrieved_at,
                },
            )
            counts["documents"] += 1
            parser = PARSERS.get(name)
            if parser is None:
                continue
            try:
                parsed = list(parser(content))
            except Exception as exc:  # a broken table must not stop the load
                errors.append(f"{psi_id} {name}: {exc}")
                continue
            for item in parsed:
                errors += [f"validation, {psi_id} {name}, {issue}" for issue in validate(item)]
            TestRun.objects.bulk_create(
                [
                    TestRun(
                        investigation=investigation,
                        source_file=source_file,
                        source_row=item.source_row,
                        raw_row=item.raw_row,
                        test_label=item.test_label[:120],
                        date=item.date,
                        fuel=item.fuel[:120],
                        fuel_form=item.fuel_form,
                        geometry=item.geometry[:300],
                        oxygen_pct=item.oxygen_pct,
                        diluent=item.diluent,
                        pressure_kpa=item.pressure_kpa,
                        flow_speed_cm_s=item.flow_speed_cm_s,
                        flow_direction=item.flow_direction,
                        gravity_level=item.gravity_level,
                        ignited=item.ignited,
                        extinction_mode=item.extinction_mode,
                        outcomes=item.outcomes,
                    )
                    for item in parsed
                ]
            )
            counts["test_runs"] += len(parsed)

        recompute_ranges_from_test_runs(investigation)
        investigation.refresh_search_text()

    Publication.objects.update(search_text=SearchVector("title", "authors", config="english"))
    for kind, column in (
        (VocabularyTerm.Kind.FUEL, "fuel"),
        (VocabularyTerm.Kind.FUEL_FORM, "fuel_form"),
        (VocabularyTerm.Kind.DILUENT, "diluent"),
        (VocabularyTerm.Kind.EXTINCTION_MODE, "extinction_mode"),
    ):
        for value in TestRun.objects.exclude(**{column: ""}).values_list(column, flat=True).distinct():
            VocabularyTerm.objects.get_or_create(
                kind=kind, code=slugify(value)[:60] or "term", defaults={"label": value}
            )

    run.counts, run.errors, run.finished = counts, errors, timezone.now()
    run.save()
    return run
