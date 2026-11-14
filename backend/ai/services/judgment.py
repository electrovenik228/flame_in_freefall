"""Relevance judgment: the two rubric criteria that need judgment (sections 7.1 and 7.4)."""

from django.conf import settings
from pydantic import BaseModel

from ai import prompts
from ai.services import llm, verify
from ai.services.extraction import Evidence, render_sources
from ai.services.sources import Source


class Judged(BaseModel):
    score: int
    rationale: str
    evidence: list[Evidence]


class Judgment(BaseModel):
    fuel_relevance: Judged
    safety_function: Judged


def check_judgment(judgment: Judgment, sources: list[Source]) -> list[str]:
    texts = {s.source_id: s.text for s in sources}
    problems = []
    for label, judged in (("fuel_relevance", judgment.fuel_relevance), ("safety_function", judgment.safety_function)):
        if not 0 <= judged.score <= 10:
            problems.append(f"{label}: score {judged.score} is outside 0 to 10")
        if not judged.evidence:
            problems.append(f"{label}: no evidence quote")
        for item in judged.evidence:
            if item.source_id not in texts:
                problems.append(f"{label}: unknown source_id {item.source_id!r}")
            elif not verify.quote_in_source(item.quote, texts[item.source_id]):
                problems.append(f"{label}: quote not found word for word in {item.source_id}: {item.quote!r}")
        unmatched = verify.unmatched_numbers(judged.rationale, list(texts.values()))
        if unmatched:
            problems.append(f"{label}: numbers in the rationale are not in the sources: {', '.join(unmatched)}")
    return problems


def run_judgment(sources: list[Source], attempts: int = 2) -> tuple[Judgment | None, dict, str]:
    """Returns (judgment or None when rejected, checks, model). Raises llm.Refused on a refusal."""
    client = llm.get_client()
    messages: list[dict] = [
        {
            "role": "user",
            "content": f"Sources for one investigation:\n\n{render_sources(sources)}\n\n"
            "Score this investigation on the two criteria.",
        }
    ]
    checks: dict = {"attempts": 0, "problems": []}
    model = settings.CLAUDE_MODEL_FRONTIER
    for attempt in range(1, attempts + 1):
        response = client.messages.parse(
            model=settings.CLAUDE_MODEL_FRONTIER,
            max_tokens=llm.BACKGROUND_MAX_TOKENS,
            system=prompts.JUDGMENT_SYSTEM,
            messages=messages,
            output_format=Judgment,
            output_config=llm.background_effort(),
        )
        llm.log_call("judgment", response)
        llm.check_stop(response)
        model, checks["attempts"] = response.model, attempt
        judgment = response.parsed_output
        checks["problems"] = check_judgment(judgment, sources)
        if not checks["problems"]:
            checks["evidence_quotes_verified"] = True
            return judgment, checks, model
        messages += [
            {"role": "assistant", "content": response.content},  # passed back unchanged
            {
                "role": "user",
                "content": "A program checked your result and found these problems:\n- "
                + "\n- ".join(checks["problems"])
                + "\nGive the full result again with quotes copied character for character from the sources.",
            },
        ]
    checks["evidence_quotes_verified"] = False
    return None, checks, model
