"""Investigation summaries: prose with citations at two reading levels (sections 7.1 and 7.3)."""

from django.conf import settings

from ai import prompts
from ai.services import llm, verify
from ai.services.sources import Source


def document_blocks(sources: list[Source]) -> list[dict]:
    """Records are passed as document blocks with citations on. The last block carries the cache marker."""
    blocks = [
        {
            "type": "document",
            "source": {"type": "text", "media_type": "text/plain", "data": s.text},
            "title": s.document.title,
            "context": f"{s.document.get_kind_display()} of {s.document.investigation.psi_id}",
            "citations": {"enabled": True},
        }
        for s in sources
    ]
    blocks[-1]["cache_control"] = {"type": "ephemeral"}
    return blocks


def cited_segments(content_blocks, sources: list[Source], citations: list[dict]) -> list[dict]:
    """Turn response text blocks into segments, appending new citations to the shared numbered list."""
    index_of = {(c["document_index"], c["start"], c["end"]): c["n"] for c in citations}
    segments = []
    for block in content_blocks:
        if block.type != "text":
            continue
        numbers = []
        for citation in getattr(block, "citations", None) or []:
            document_index = citation.document_index
            start = getattr(citation, "start_char_index", None)
            end = getattr(citation, "end_char_index", None)
            key = (document_index, start, end)
            if key not in index_of:
                document = sources[document_index].document
                index_of[key] = len(citations) + 1
                citations.append(
                    {
                        "n": index_of[key],
                        "psi_id": document.investigation.psi_id,
                        "document_title": document.title,
                        "document_kind": document.kind,
                        "psi_url": document.investigation.psi_url,
                        "cited_text": citation.cited_text,
                        "document_index": document_index,
                        "start": start,
                        "end": end,
                    }
                )
            if index_of[key] not in numbers:
                numbers.append(index_of[key])
        segments.append({"text": block.text, "citations": numbers})
    return segments


def check_summary(segments: list[dict], citations: list[dict], sources: list[Source]) -> list[str]:
    problems = []
    text = "".join(segment["text"] for segment in segments)
    if not any(segment["citations"] for segment in segments):
        problems.append("the text carries no citation")
    for citation in citations:
        if not verify.quote_in_source(citation["cited_text"], sources[citation["document_index"]].text):
            problems.append(f"cited passage {citation['n']} is not in its source")
    unmatched = verify.unmatched_numbers(text, [s.text for s in sources])
    if unmatched:
        problems.append("numbers not found in the cited record: " + ", ".join(sorted(set(unmatched))))
    return problems


def run_level(level: str, sources: list[Source], citations: list[dict], attempts: int = 2):
    """One reading level. Returns (segments or None when rejected, problems, model)."""
    client = llm.get_client()
    messages: list[dict] = [
        {
            "role": "user",
            "content": [
                *document_blocks(sources),
                {"type": "text", "text": f"Summarize this investigation. {prompts.SUMMARY_LEVELS[level]}"},
            ],
        }
    ]
    problems: list[str] = []
    model = settings.CLAUDE_MODEL_DEEP
    for _ in range(attempts):
        response = client.messages.create(
            model=settings.CLAUDE_MODEL_DEEP,
            max_tokens=llm.BACKGROUND_MAX_TOKENS,
            system=prompts.SUMMARY_SYSTEM,
            messages=messages,
            output_config=llm.background_effort(),
        )
        llm.log_call(f"summary_{level}", response)
        llm.check_stop(response)
        model = response.model
        trial_citations = list(citations)
        segments = cited_segments(response.content, sources, trial_citations)
        problems = check_summary(segments, trial_citations, sources)
        if not problems:
            citations[:] = trial_citations
            return segments, [], model
        messages += [
            {"role": "assistant", "content": response.content},  # passed back unchanged
            {
                "role": "user",
                "content": "A program checked the summary and found these problems:\n- "
                + "\n- ".join(problems)
                + "\nWrite the summary again. Cite the documents for every fact and use only numbers "
                "that appear in the documents, written exactly as they appear there.",
            },
        ]
    return None, problems, model


def run_summary(sources: list[Source]) -> tuple[dict | None, list[dict], dict, str]:
    """Returns (content or None when rejected, citations, checks, model). Raises llm.Refused on a refusal."""
    citations: list[dict] = []
    content, checks, model = {}, {"problems": {}}, settings.CLAUDE_MODEL_DEEP
    for level in prompts.SUMMARY_LEVELS:
        segments, problems, model = run_level(level, sources, citations)
        if segments is None:
            checks["problems"][level] = problems
            return None, [], checks, model
        content[level] = segments
    checks.update({"has_citation": True, "numbers_match_cited_record": True, "cited_passages_verified": True})
    public = [{k: v for k, v in c.items() if k not in ("document_index", "start", "end")} for c in citations]
    return content, public, checks, model
