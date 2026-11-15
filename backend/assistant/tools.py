"""Assistant tools (section 7.3). Read-only, typed parameters, no free-form SQL, no network access.

Every tool returns `search_result` blocks, so Claude can cite them, plus the plain texts used
for the number check after the stream.
"""

from catalog.api.filters import search_investigations
from catalog.api.views import investigations_queryset
from catalog.models import Environment, Investigation, SourceDocument
from catalog.services import ranking

MAX_RECORD_CHARS = 14000
PILLARS = ["prevention", "detection", "suppression"]

TOOLS = [
    {
        "name": "search_investigations",
        "description": "Search the catalogue of NASA PSI Combustion Science investigations. Returns a short "
        "fact sheet per match: fuel state, safety function, data depth, tested oxygen, pressure and flow "
        "ranges, and the objective. Use it to find records by topic, acronym, fuel or condition.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Words to search for, such as an acronym, fuel or topic"},
                "fuel_state": {"type": "string", "enum": ["gas", "liquid", "solid"]},
                "safety_function": {"type": "string", "enum": PILLARS},
                "oxygen_pct_min": {
                    "type": "number",
                    "description": "Keep records whose tested oxygen reaches this percent",
                },
                "has_test_runs": {"type": "boolean", "description": "Keep only records with test-by-test data"},
                "limit": {"type": "integer", "description": "Maximum number of records, 1 to 10, default 6"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_investigation",
        "description": "Get one investigation by its PSI identifier: the full PSI record text (objective, "
        "approach, hypothesis, research impacts), its catalogue attributes and, when the record has "
        "test-by-test data, statistics of its test runs.",
        "input_schema": {
            "type": "object",
            "properties": {"psi_id": {"type": "string", "description": "PSI identifier, for example PSI-69"}},
            "required": ["psi_id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_ranking",
        "description": "Get the relevance ranking of investigations for a crew environment, with the score "
        "breakdown and the explanation of each criterion. Environments: earth-sea-level, space-station, "
        "spacesuit, lunar-habitat, mars-habitat.",
        "input_schema": {
            "type": "object",
            "properties": {
                "environment": {
                    "type": "string",
                    "enum": ["earth-sea-level", "space-station", "spacesuit", "lunar-habitat", "mars-habitat"],
                },
                "limit": {"type": "integer", "description": "How many top records to return, 1 to 10, default 5"},
            },
            "required": ["environment"],
            "additionalProperties": False,
        },
    },
]


class ToolError(Exception):
    """A problem the model can act on, returned to it as an error result."""


def block(title: str, source: str, text: str) -> dict:
    return {
        "type": "search_result",
        "source": source,
        "title": title,
        "content": [{"type": "text", "text": text}],
        "citations": {"enabled": True},
    }


def bounded(value, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def fact_sheet(item: Investigation, runs: int) -> str:
    def span(low, high, unit):
        return ranking.fmt_range(low, high, unit)

    source = {
        "test_runs": "computed from the record's test runs",
        "record_text": "read from the record text by AI with quoted evidence",
        "not_available": "the record states no test conditions",
    }.get(item.conditions_source, "not determined")
    lines = [
        f"{item.psi_id} {item.display_name}." + (f" Full title: {item.title}." if item.acronym else ""),
        f"Fuel state: {item.fuel_state or 'not determined'}.",
        f"Safety function: {', '.join(item.safety_pillars) or 'not determined'}.",
        f"Data depth: {item.get_data_depth_display() if item.data_depth else 'not determined'}. "
        f"Test runs in the catalogue: {runs}.",
        f"Tested oxygen: {span(item.oxygen_pct_min, item.oxygen_pct_max, '%')}. "
        f"Tested pressure: {span(item.pressure_kpa_min, item.pressure_kpa_max, 'kPa')}. "
        f"Tested flow speed: {span(item.flow_speed_cm_s_min, item.flow_speed_cm_s_max, 'cm/s')}. "
        f"Source of these ranges: {source}.",
    ]
    if item.objectives:
        lines.append(f"Objective, from the PSI record: {item.objectives[:700]}")
    lines.append(f"Page in the site: /investigations/{item.psi_id}")
    return "\n".join(lines)


def tool_search(params: dict) -> list[dict]:
    queryset = investigations_queryset()
    if params.get("query"):
        queryset = search_investigations(queryset, str(params["query"])[:200])
    if params.get("fuel_state") in ("gas", "liquid", "solid"):
        queryset = queryset.filter(fuel_state=params["fuel_state"])
    if params.get("safety_function") in PILLARS:
        queryset = queryset.filter(safety_pillars__contains=[params["safety_function"]])
    if isinstance(params.get("oxygen_pct_min"), int | float):
        queryset = queryset.filter(oxygen_pct_max__gte=params["oxygen_pct_min"])
    if params.get("has_test_runs") is True:
        queryset = queryset.filter(test_run_count__gt=0)
    items = list(queryset[: bounded(params.get("limit"), 6, 1, 10)])
    if not items:
        raise ToolError("No investigation in the catalogue matches. Try fewer or different words.")
    return [
        block(
            f"{item.psi_id} {item.display_name}: catalogue entry", item.psi_url, fact_sheet(item, item.test_run_count)
        )
        for item in items
    ]


def tool_get(params: dict) -> list[dict]:
    psi_id = str(params.get("psi_id", "")).strip().upper()
    item = Investigation.objects.filter(psi_id=psi_id).first()
    if item is None:
        raise ToolError(f"{psi_id or 'That identifier'} is not in the catalogue. Use search_investigations to find it.")
    blocks = [
        block(
            f"{item.psi_id} {item.display_name}: catalogue entry",
            item.psi_url,
            fact_sheet(item, item.test_runs.count()),
        )
    ]
    kinds = [SourceDocument.Kind.RECORD, SourceDocument.Kind.TEST_RUN_STATS]
    for document in sorted(item.documents.filter(kind__in=kinds), key=lambda d: kinds.index(d.kind)):
        blocks.append(block(document.title, item.psi_url, document.text[:MAX_RECORD_CHARS]))
    return blocks


def tool_ranking(params: dict) -> list[dict]:
    environment = Environment.objects.filter(slug=params.get("environment")).first()
    if environment is None:
        raise ToolError(
            "Unknown environment. Use one of: " + ", ".join(Environment.objects.values_list("slug", flat=True))
        )
    rows = ranking.rank(ranking.Target.from_environment(environment))
    target = ranking.Target.from_environment(environment)
    windows = [
        f"oxygen {ranking.describe_window(target.oxygen, '%')}",
        f"pressure {ranking.describe_window(target.pressure, 'kPa')}",
    ]
    method = (
        f"Ranking for {environment.name}: {', '.join(windows)}, gravity {environment.gravity}. "
        f"Source of the atmosphere: {environment.source}.\n"
        "Method: a weighted rubric. Atmosphere match 30, fuel and material relevance 25, safety function 20, "
        "flow match 15, gravity relevance 10. A criterion without data is left out and the total is rescaled "
        "over the others; such rows are tagged partial data. The ranking is a research aid, not a safety rating.\n"
        "PSI holds no partial-gravity data. Rankings for the Moon and Mars differ only through the atmosphere "
        "criterion.\n"
        f"Page in the site: /ranking?env={environment.slug}"
    )
    blocks = [block(f"Ranking method and environment: {environment.name}", f"/ranking?env={environment.slug}", method)]
    for row in rows[: bounded(params.get("limit"), 5, 1, 10)]:
        lines = [
            f"Rank {row['rank']} of {len(rows)} for {environment.name}: {row['psi_id']} {row['display_name']}.",
            f"Total score: {row['total']} of 100." + (" Partial data." if row["partial_data"] else ""),
        ]
        for sub in row["sub_scores"].values():
            if sub["status"] == "scored":
                lines.append(
                    f"{sub['label']}: {round(sub['score'] * 100)}% of its weight, {sub['points']} points. "
                    f"{sub['explanation']}"
                )
            else:
                state = (
                    "no data for this record" if sub["status"] == "not_available" else "not scored for this environment"
                )
                lines.append(f"{sub['label']}: {state}. {sub['explanation']}")
        lines.append(f"Page in the site: /investigations/{row['psi_id']}")
        blocks.append(
            block(
                f"Rank {row['rank']} for {environment.name}: {row['psi_id']} {row['display_name']}",
                row["psi_url"],
                "\n".join(lines),
            )
        )
    return blocks


HANDLERS = {"search_investigations": tool_search, "get_investigation": tool_get, "get_ranking": tool_ranking}


def execute(name: str, params) -> tuple[list[dict] | str, bool, list[str]]:
    """Run one tool. Returns (tool_result content, is_error, texts for the number check)."""
    handler = HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool {name}.", True, []
    try:
        blocks = handler(params if isinstance(params, dict) else {})
    except ToolError as exc:
        return str(exc), True, []
    return blocks, False, [item["content"][0]["text"] for item in blocks]
