"""Source documents handed to Claude for one investigation."""

import hashlib
from dataclasses import dataclass

from django.db.models import Count

from catalog.models import Investigation, SourceDocument
from catalog.services.conditions import variable_summary

STATS_TITLE = "Test-run statistics computed from the database"


@dataclass
class Source:
    source_id: str
    document: SourceDocument

    @property
    def text(self) -> str:
        return self.document.text


def refresh_stats_document(investigation: Investigation) -> SourceDocument | None:
    """Plain-text statistics of the parsed test runs, so counts and ranges can be cited.

    Every number here is computed from the database, never written by AI.
    """
    summary = variable_summary(investigation)
    title = f"{investigation.psi_id} {STATS_TITLE.lower()}"
    if not summary["test_run_count"]:
        investigation.documents.filter(kind=SourceDocument.Kind.TEST_RUN_STATS).delete()
        return None
    files = ", ".join(sorted({run.source_file.name for run in investigation.test_runs.select_related("source_file")}))
    lines = [
        f"{STATS_TITLE} for {investigation.psi_id} ({investigation.display_name}).",
        f"Number of test runs parsed from the PSI experiment table: {summary['test_run_count']}.",
        f"Source file: {files}.",
    ]

    def describe(entry: dict) -> str:
        if "min" in entry:
            low, high = round(entry["min"], 2), round(entry["max"], 2)
            value = f"{low:g} {entry['unit']}" if low == high else f"{low:g} to {high:g} {entry['unit']}"
        elif "values" in entry:
            value = ", ".join(entry["values"])
        else:
            value = f"{entry['distinct_values']} different values"
        return f"{entry['label']}: {value} (recorded in {entry['recorded_runs']} runs)."

    lines.append("Varied between tests:")
    lines += [f"- {describe(entry)}" for entry in summary["varied"]] or ["- nothing"]
    lines.append("Held constant:")
    lines += [f"- {describe(entry)}" for entry in summary["constant"]] or ["- nothing"]
    if summary["not_recorded"]:
        names = ", ".join(entry["label"].lower() for entry in summary["not_recorded"])
        lines.append(f"Not recorded in the PSI table: {names}.")
    fuels = (
        investigation.test_runs.exclude(fuel="").order_by().values("fuel").annotate(n=Count("id")).order_by("-n")[:12]
    )
    if fuels:
        lines.append("Test runs per fuel: " + "; ".join(f"{row['fuel']} {row['n']}" for row in fuels) + ".")
    text = "\n".join(lines) + "\n"
    document, _ = SourceDocument.objects.update_or_create(
        investigation=investigation,
        kind=SourceDocument.Kind.TEST_RUN_STATS,
        title=title,
        defaults={
            "text": text,
            "url": investigation.psi_url,
            "checksum": hashlib.sha256(text.encode()).hexdigest(),
            "retrieved_at": investigation.retrieved_at,
        },
    )
    return document


def sources_for(investigation: Investigation, with_stats: bool = True) -> list[Source]:
    """Record first, then experiment tables, then computed statistics. IDs are S1, S2, ..."""
    if with_stats:
        refresh_stats_document(investigation)
    order = {
        SourceDocument.Kind.RECORD: 0,
        SourceDocument.Kind.EXPERIMENT_TABLE: 1,
        SourceDocument.Kind.TEST_RUN_STATS: 2,
    }
    documents = sorted(investigation.documents.all(), key=lambda d: (order[d.kind], d.title))
    if not with_stats:
        documents = [d for d in documents if d.kind != SourceDocument.Kind.TEST_RUN_STATS]
    return [Source(f"S{index}", document) for index, document in enumerate(documents, start=1)]


def input_hash(prompt_version: str, model: str, sources: list[Source], extra: str = "") -> str:
    """Unchanged input is never regenerated (section 7.6)."""
    parts = [prompt_version, model, extra, *[f"{s.document.title}:{s.document.checksum}" for s in sources]]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()
