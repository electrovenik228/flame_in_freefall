"""Attribute extraction: structured output with evidence quotes (sections 7.1 and 7.3)."""

from typing import Literal

from django.conf import settings
from pydantic import BaseModel

from ai import prompts
from ai.services import llm, verify
from ai.services.sources import Source

PRESSURE_TO_KPA = {
    "kPa": 1.0,
    "atm": 101.325,
    "bar": 100.0,
    "psi": 6.894757,
    "mmHg": 0.1333224,
    "torr": 0.1333224,
    "MPa": 1000.0,
}
OXYGEN_TO_PCT = {"percent": 1.0, "mole_fraction": 100.0}
FLOW_TO_CM_S = {"cm/s": 1.0, "mm/s": 0.1, "m/s": 100.0}


class Evidence(BaseModel):
    source_id: str
    quote: str


class FuelStateField(BaseModel):
    value: Literal["gas", "liquid", "solid", "unknown"]
    evidence: list[Evidence]


class DataDepthField(BaseModel):
    value: Literal["per_test", "summary", "qualitative", "unknown"]
    evidence: list[Evidence]


class PillarItem(BaseModel):
    value: Literal["prevention", "detection", "suppression"]
    evidence: list[Evidence]


class OxygenRange(BaseModel):
    min_value: float | None
    max_value: float | None
    unit: Literal["percent", "mole_fraction", "not_stated"]
    evidence: list[Evidence]


class PressureRange(BaseModel):
    min_value: float | None
    max_value: float | None
    unit: Literal["kPa", "atm", "bar", "psi", "mmHg", "torr", "MPa", "not_stated"]
    evidence: list[Evidence]


class FlowRange(BaseModel):
    min_value: float | None
    max_value: float | None
    unit: Literal["cm/s", "mm/s", "m/s", "not_stated"]
    evidence: list[Evidence]


class NamedItem(BaseModel):
    name: str
    evidence: list[Evidence]


class InstrumentItem(BaseModel):
    name: str
    measurement_type: str
    evidence: list[Evidence]


class Extraction(BaseModel):
    fuel_state: FuelStateField
    fuels: list[NamedItem]
    safety_pillars: list[PillarItem]
    data_depth: DataDepthField
    oxygen: OxygenRange
    pressure: PressureRange
    flow_speed: FlowRange
    instruments: list[InstrumentItem]


def render_sources(sources: list[Source]) -> str:
    return "\n\n".join(
        f'<source id="{s.source_id}" kind="{s.document.kind}" title="{s.document.title}">\n{s.text}\n</source>'
        for s in sources
    )


def check_evidence(extraction: Extraction, sources: list[Source]) -> list[str]:
    """Problems that make the result invalid. An empty list means every quote and number checks out."""
    texts = {s.source_id: s.text for s in sources}
    problems: list[str] = []

    def check(label: str, evidence: list[Evidence], required: bool) -> list[str]:
        if required and not evidence:
            problems.append(f"{label}: a value was given without evidence")
        for item in evidence:
            if item.source_id not in texts:
                problems.append(f"{label}: unknown source_id {item.source_id!r}")
            elif not verify.quote_in_source(item.quote, texts[item.source_id]):
                problems.append(f"{label}: quote not found word for word in {item.source_id}: {item.quote!r}")
        return [item.quote for item in evidence]

    check("fuel_state", extraction.fuel_state.evidence, extraction.fuel_state.value != "unknown")
    check("data_depth", extraction.data_depth.evidence, extraction.data_depth.value != "unknown")
    for pillar in extraction.safety_pillars:
        check(f"safety_pillars.{pillar.value}", pillar.evidence, True)
    for fuel in extraction.fuels:
        check(f"fuels.{fuel.name}", fuel.evidence, True)
    for instrument in extraction.instruments:
        check(f"instruments.{instrument.name}", instrument.evidence, True)
    for label, field in (
        ("oxygen", extraction.oxygen),
        ("pressure", extraction.pressure),
        ("flow_speed", extraction.flow_speed),
    ):
        has_value = field.min_value is not None or field.max_value is not None
        quotes = check(label, field.evidence, has_value)
        if has_value and field.unit == "not_stated":
            problems.append(f"{label}: a value was given without its unit")
        for value in (field.min_value, field.max_value):
            if value is not None and not verify.number_in_quotes(value, quotes):
                problems.append(f"{label}: the number {value:g} does not appear in its evidence quotes")
    return problems


def normalized_ranges(extraction: Extraction) -> dict[str, float | None]:
    """Convert the as-written values to the fixed units of section 5.3. The conversion is done in code."""

    def convert(field, factors: dict[str, float]) -> tuple[float | None, float | None]:
        # A one-sided statement such as "up to 20 atm" keeps its missing bound empty.
        factor = factors.get(field.unit)
        if factor is None:
            return None, None
        low = None if field.min_value is None else round(field.min_value * factor, 4)
        high = None if field.max_value is None else round(field.max_value * factor, 4)
        if low is not None and high is not None and low > high:
            low, high = high, low
        return low, high

    oxygen = convert(extraction.oxygen, OXYGEN_TO_PCT)
    pressure = convert(extraction.pressure, PRESSURE_TO_KPA)
    flow = convert(extraction.flow_speed, FLOW_TO_CM_S)
    return {
        "oxygen_pct_min": oxygen[0], "oxygen_pct_max": oxygen[1],
        "pressure_kpa_min": pressure[0], "pressure_kpa_max": pressure[1],
        "flow_speed_cm_s_min": flow[0], "flow_speed_cm_s_max": flow[1],
    }  # fmt: skip


def run_extraction(sources: list[Source], attempts: int = 2) -> tuple[Extraction | None, dict, str]:
    """Returns (extraction or None when rejected, checks, model). Raises llm.Refused on a refusal."""
    client = llm.get_client()
    messages: list[dict] = [
        {
            "role": "user",
            "content": f"Sources for one investigation:\n\n{render_sources(sources)}\n\n"
            "Fill the fields for this investigation.",
        }
    ]
    checks: dict = {"attempts": 0, "problems": []}
    model = settings.CLAUDE_MODEL_DEEP
    for attempt in range(1, attempts + 1):
        response = client.messages.parse(
            model=settings.CLAUDE_MODEL_DEEP,
            max_tokens=llm.BACKGROUND_MAX_TOKENS,
            system=prompts.EXTRACTION_SYSTEM,
            messages=messages,
            output_format=Extraction,
            output_config=llm.background_effort(),
        )
        llm.log_call("extraction", response)
        llm.check_stop(response)
        model, checks["attempts"] = response.model, attempt
        extraction = response.parsed_output
        problems = check_evidence(extraction, sources)
        checks["problems"] = problems
        if not problems:
            checks["evidence_quotes_verified"] = True
            return extraction, checks, model
        messages += [
            {"role": "assistant", "content": response.content},  # passed back unchanged
            {
                "role": "user",
                "content": "A program checked your evidence and found these problems:\n- "
                + "\n- ".join(problems)
                + "\nGive the full result again. Copy quotes character for character from the sources, "
                "or leave a field unknown if the sources do not support it.",
            },
        ]
    checks["evidence_quotes_verified"] = False
    return None, checks, model
