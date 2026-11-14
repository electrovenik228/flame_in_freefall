"""Run the stored AI jobs for one investigation and keep the results as versioned rows."""

from django.conf import settings
from django.db import transaction

from ai import prompts
from ai.models import Insight, ReviewStatus
from ai.services import extraction as extraction_job
from ai.services import llm
from ai.services import summary as summary_job
from ai.services.sources import input_hash, sources_for
from catalog.models import ConditionsSource, DataDepth, Instrument, Investigation

VISIBLE = [ReviewStatus.UNREVIEWED, ReviewStatus.APPROVED]


def already_generated(investigation: Investigation, insight_type: str, digest: str) -> bool:
    return Insight.objects.filter(
        investigation=investigation, type=insight_type, is_current=True, input_hash=digest, review_status__in=VISIBLE
    ).exists()


@transaction.atomic
def store(investigation, insight_type, *, content, citations, model, prompt_version, digest, checks, status) -> Insight:
    """A new row replaces the current one; the old row is kept for comparison (section 5.3)."""
    Insight.objects.filter(investigation=investigation, type=insight_type, is_current=True).update(is_current=False)
    return Insight.objects.create(
        investigation=investigation,
        type=insight_type,
        content=content,
        citations=citations,
        model=model,
        prompt_version=prompt_version,
        input_hash=digest,
        checks=checks,
        review_status=status,
    )


def apply_extraction(investigation: Investigation, extraction: extraction_job.Extraction, ranges: dict) -> None:
    """Project a verified extraction onto the Investigation columns. Test-run ranges always win."""
    investigation.fuel_state = "" if extraction.fuel_state.value == "unknown" else extraction.fuel_state.value
    investigation.safety_pillars = sorted({item.value for item in extraction.safety_pillars})
    if not investigation.test_runs.exists():
        depth = extraction.data_depth.value
        investigation.data_depth = "" if depth == "unknown" else depth
        for column, value in ranges.items():
            setattr(investigation, column, value)
        has_any = any(value is not None for value in ranges.values())
        investigation.conditions_source = ConditionsSource.RECORD_TEXT if has_any else ConditionsSource.NOT_AVAILABLE
    else:
        investigation.data_depth = DataDepth.PER_TEST
    investigation.save()
    instruments = []
    for item in extraction.instruments:
        name = item.name.strip()[:200]
        if not name:
            continue
        instrument = Instrument.objects.filter(name__iexact=name).first() or Instrument.objects.create(
            name=name[0].upper() + name[1:], measurement_type=item.measurement_type.strip()[:120]
        )
        instruments.append(instrument)
    investigation.instruments.set(instruments)
    investigation.refresh_search_text()


def generate_extraction(investigation: Investigation, force: bool = False) -> str:
    sources = sources_for(investigation, with_stats=False)
    digest = input_hash(prompts.EXTRACTION_VERSION, settings.CLAUDE_MODEL_DEEP, sources)
    if not force and already_generated(investigation, Insight.Type.EXTRACTION, digest):
        return "unchanged"
    common = {"prompt_version": prompts.EXTRACTION_VERSION, "digest": digest, "citations": []}
    try:
        extraction, checks, model = extraction_job.run_extraction(sources)
    except (llm.Refused, llm.Truncated) as exc:
        store(
            investigation,
            Insight.Type.EXTRACTION,
            content={},
            model=settings.CLAUDE_MODEL_DEEP,
            checks={"not_generated": f"{type(exc).__name__}: {exc}"},
            status=ReviewStatus.NOT_GENERATED,
            **common,
        )
        return "not generated"
    if extraction is None:
        store(
            investigation,
            Insight.Type.EXTRACTION,
            content={},
            model=model,
            checks=checks,
            status=ReviewStatus.NOT_GENERATED,
            **common,
        )
        return "rejected"
    ranges = extraction_job.normalized_ranges(extraction)
    content = {
        **extraction.model_dump(),
        "normalized": ranges,
        "sources": {s.source_id: s.document.title for s in sources},
    }
    store(
        investigation,
        Insight.Type.EXTRACTION,
        content=content,
        model=model,
        checks=checks,
        status=ReviewStatus.UNREVIEWED,
        **common,
    )
    apply_extraction(investigation, extraction, ranges)
    return "generated"


def generate_summary(investigation: Investigation, force: bool = False) -> str:
    sources = sources_for(investigation, with_stats=True)
    digest = input_hash(prompts.SUMMARY_VERSION, settings.CLAUDE_MODEL_DEEP, sources)
    if not force and already_generated(investigation, Insight.Type.SUMMARY, digest):
        return "unchanged"
    common = {"prompt_version": prompts.SUMMARY_VERSION, "digest": digest}
    try:
        content, citations, checks, model = summary_job.run_summary(sources)
    except (llm.Refused, llm.Truncated) as exc:
        store(
            investigation,
            Insight.Type.SUMMARY,
            content={},
            citations=[],
            model=settings.CLAUDE_MODEL_DEEP,
            checks={"not_generated": f"{type(exc).__name__}: {exc}"},
            status=ReviewStatus.NOT_GENERATED,
            **common,
        )
        return "not generated"
    if content is None:
        store(
            investigation,
            Insight.Type.SUMMARY,
            content={},
            citations=[],
            model=model,
            checks=checks,
            status=ReviewStatus.NOT_GENERATED,
            **common,
        )
        return "rejected"
    store(
        investigation,
        Insight.Type.SUMMARY,
        content=content,
        citations=citations,
        model=model,
        checks=checks,
        status=ReviewStatus.UNREVIEWED,
        **common,
    )
    return "generated"


def step6_report() -> dict:
    """The check of build step 6, computed from the database."""
    from ai.services.current import current_insight

    report: dict = {
        "records": 0,
        "without_ranges_or_mark": [],
        "without_cited_summary": [],
        "unverified_extraction": [],
    }
    for investigation in Investigation.objects.all():
        report["records"] += 1
        if investigation.conditions_source == "":
            report["without_ranges_or_mark"].append(investigation.psi_id)
        summary = current_insight(investigation, Insight.Type.SUMMARY)
        if summary is None or not summary.citations:
            report["without_cited_summary"].append(investigation.psi_id)
        extraction = current_insight(investigation, Insight.Type.EXTRACTION)
        if extraction is None or not extraction.checks.get("evidence_quotes_verified"):
            report["unverified_extraction"].append(investigation.psi_id)
    report["passed"] = not (
        report["without_ranges_or_mark"] or report["without_cited_summary"] or report["unverified_extraction"]
    )
    return report
