"""Relevance rubric of section 7.4. Everything here is computed in code, with no AI call.

A criterion yields a score between 0 and 1, or no score:
- "not_available": the record lacks the data. The total is rescaled over the remaining
  criteria and the row carries a "partial data" tag. A missing value never counts as zero.
- "not_applicable": the environment defines no target for the criterion (for example no
  ventilation speed). The total is rescaled, without a partial-data tag.

Rubric parameters are constants below and are shown on the About page.
"""

import re
from collections import defaultdict
from dataclasses import dataclass, field

from catalog.models import Environment, Investigation, SourceDocument, TestRun

DEFAULT_WEIGHTS = {"atmosphere": 30, "fuel": 25, "safety": 20, "flow": 15, "gravity": 10}
CRITERIA = {
    "atmosphere": "Atmosphere match",
    "fuel": "Fuel and material relevance",
    "safety": "Safety function",
    "flow": "Flow match",
    "gravity": "Gravity relevance",
}

# A tested condition within the tolerance of the environment window scores 1. Beyond it the
# score falls in a straight line and reaches 0 at tolerance + scale.
OXYGEN_TOLERANCE_PCT, OXYGEN_SCALE_PCT = 1.0, 10.0
PRESSURE_TOLERANCE_KPA, PRESSURE_SCALE_KPA = 5.0, 50.0
FLOW_TOLERANCE_CM_S, FLOW_SCALE_CM_S = 2.0, 20.0

# Gravity relevance: 6 points for microgravity data, 2 more for 1 g reference data, 2 more
# for a partial-gravity proxy such as an electric field.
GRAVITY_POINTS = {"microgravity": 6, "one_g_reference": 2, "partial_gravity_proxy": 2}
ONE_G_PATTERN = re.compile(
    r"\b1-?g\b[^.\n]{0,80}?(?:burn|spread|test|data|experiment|reference)"
    r"|normal[- ]gravity (?:tests?|testing|experiments?|data|flames?)"
    r"|ground[- ]based (?:tests?|testing|experiments?|data)|drop[- ]tower",
    re.IGNORECASE,
)
PROXY_PATTERN = re.compile(r"electric[- ]fields?", re.IGNORECASE)


def find_sentence(pattern: re.Pattern, text: str) -> str | None:
    """The sentence or table line around the first match, as the evidence quote."""
    match = pattern.search(text)
    if not match:
        return None
    start = max(text.rfind(".", 0, match.start()), text.rfind("\n", 0, match.start())) + 1
    ends = [pos for pos in (text.find(".", match.end()), text.find("\n", match.end())) if pos != -1]
    end = min(ends) + 1 if ends else len(text)
    return text[start:end].strip()[:300]


Window = tuple[float | None, float | None]


@dataclass
class Target:
    """What an investigation is scored against: a reference environment or a custom atmosphere."""

    name: str
    oxygen: Window
    pressure: Window
    flow: Window = (None, None)

    @classmethod
    def from_environment(cls, env: Environment) -> "Target":
        return cls(
            env.name,
            (env.oxygen_pct_min, env.oxygen_pct_max),
            (env.pressure_kpa_min, env.pressure_kpa_max),
            (env.flow_cm_s_min, env.flow_cm_s_max),
        )


@dataclass
class Criterion:
    status: str  # scored, not_available, not_applicable
    score: float | None = None
    explanation: str = ""
    source: dict = field(default_factory=dict)
    details: dict = field(default_factory=dict)


def has_window(window: Window) -> bool:
    return window[0] is not None or window[1] is not None


def describe_window(window: Window, unit: str) -> str:
    low, high = window
    if low is not None and high is not None:
        return f"{low:g} {unit}" if low == high else f"{low:g} to {high:g} {unit}"
    if low is not None:
        return f"{low:g} {unit} or more"
    return f"{high:g} {unit} or less"


def gap(low: float, high: float, window: Window) -> float:
    """Distance between the tested interval [low, high] and the window. 0 when they overlap."""
    w_low, w_high = window
    if w_low is not None and high < w_low:
        return w_low - high
    if w_high is not None and low > w_high:
        return low - w_high
    return 0.0


def closeness(distance: float, tolerance: float, scale: float) -> float:
    return 1.0 if distance <= tolerance else max(0.0, 1.0 - (distance - tolerance) / scale)


def interval(low: float | None, high: float | None) -> tuple[float, float] | None:
    """A one-sided statement such as "up to 20 atm" is treated as the one known value."""
    if low is None and high is None:
        return None
    return (low if low is not None else high, high if high is not None else low)


def fmt_range(low: float | None, high: float | None, unit: str) -> str:
    if low is None and high is None:
        return "not recorded"
    if low is None:
        return f"up to {high:g} {unit}"
    if high is None:
        return f"{low:g} {unit} or more"
    return f"{low:g} {unit}" if round(low, 1) == round(high, 1) else f"{low:.1f} to {high:.1f} {unit}"


AXES = {
    "oxygen": ("oxygen_pct", "%", OXYGEN_TOLERANCE_PCT, OXYGEN_SCALE_PCT),
    "pressure": ("pressure_kpa", "kPa", PRESSURE_TOLERANCE_KPA, PRESSURE_SCALE_KPA),
    "flow": ("flow_speed_cm_s", "cm/s", FLOW_TOLERANCE_CM_S, FLOW_SCALE_CM_S),
}


def conditions_source(investigation: Investigation, has_runs: bool) -> dict:
    if has_runs:
        label = "Test runs parsed from the PSI experiment table"
    else:
        label = "Ranges read from the PSI record text by AI, with quoted evidence"
    return {"label": label, "psi_id": investigation.psi_id, "psi_url": investigation.psi_url}


def match_axes(investigation: Investigation, runs: list[dict], windows: dict[str, Window]) -> Criterion:
    """Score how close the tested conditions come to the windows of the given axes.

    With test runs, the best single run decides the score, so the axes are matched jointly.
    Without test runs, the investigation-level ranges are used.
    """
    wanted = {axis: window for axis, window in windows.items() if has_window(window)}
    if not wanted:
        return Criterion("not_applicable", explanation="The environment defines no target for this criterion.")
    target_text = " and ".join(f"{axis} {describe_window(w, AXES[axis][1])}" for axis, w in wanted.items())

    def axis_score(axis: str, low: float, high: float) -> float:
        _, _, tolerance, scale = AXES[axis]
        return closeness(gap(low, high, wanted[axis]), tolerance, scale)

    recorded_in_runs = {axis for axis in wanted if any(run[AXES[axis][0]] is not None for run in runs)}
    if recorded_in_runs:
        best, inside = 0.0, 0
        for run in runs:
            scores = [
                axis_score(axis, run[AXES[axis][0]], run[AXES[axis][0]])
                for axis in recorded_in_runs
                if run[AXES[axis][0]] is not None
            ]
            if len(scores) < len(recorded_in_runs):
                continue  # a run missing one of the recorded axes cannot be matched jointly
            best = max(best, sum(scores) / len(scores))
            inside += all(score == 1.0 for score in scores)
        missing = [axis for axis in wanted if axis not in recorded_in_runs]
        tested = "; ".join(
            f"{axis} "
            + fmt_range(
                min(r[AXES[axis][0]] for r in runs if r[AXES[axis][0]] is not None),
                max(r[AXES[axis][0]] for r in runs if r[AXES[axis][0]] is not None),
                AXES[axis][1],
            )
            for axis in sorted(recorded_in_runs)
        )
        text = f"Tested {tested}. {inside} of {len(runs)} test runs fall inside the target ({target_text})."
        if missing:
            text += f" Not recorded in the test runs: {', '.join(missing)}."
        return Criterion(
            "scored",
            round(best, 4),
            text,
            conditions_source(investigation, True),
            {"runs_inside": inside, "runs": len(runs), "missing_axes": missing, "basis": "test_runs"},
        )

    ranges = {
        axis: interval(getattr(investigation, f"{AXES[axis][0]}_min"), getattr(investigation, f"{AXES[axis][0]}_max"))
        for axis in wanted
    }
    available = {axis: value for axis, value in ranges.items() if value is not None}
    if not available:
        return Criterion(
            "not_available",
            explanation=f"The record states no {' or '.join(wanted)} values to compare with the target "
            f"({target_text}).",
        )
    scores = [axis_score(axis, low, high) for axis, (low, high) in available.items()]
    missing = [axis for axis in wanted if axis not in available]
    tested = "; ".join(
        f"{axis} "
        + fmt_range(
            getattr(investigation, f"{AXES[axis][0]}_min"),
            getattr(investigation, f"{AXES[axis][0]}_max"),
            AXES[axis][1],
        )
        for axis in sorted(available)
    )
    text = f"The record states {tested}, compared with the target ({target_text})."
    if missing:
        text += f" Not stated in the record: {', '.join(missing)}."
    return Criterion(
        "scored",
        round(sum(scores) / len(scores), 4),
        text,
        conditions_source(investigation, False),
        {"missing_axes": missing, "basis": "record_ranges"},
    )


def gravity_criterion(investigation: Investigation, record_text: str, table_text: str) -> Criterion:
    """6 points for microgravity data, 2 for 1 g reference data, 2 for a partial-gravity proxy."""
    points, parts, quotes = 0, [], []
    microgravity = investigation.project_type == "Microgravity Investigation"
    if microgravity:
        points += GRAVITY_POINTS["microgravity"]
        parts.append("PSI lists it as a microgravity investigation")
    else:
        parts.append(f'PSI lists it as "{investigation.project_type or "no project type"}", not a microgravity one')
    one_g = find_sentence(ONE_G_PATTERN, table_text) or find_sentence(ONE_G_PATTERN, record_text)
    if one_g:
        points += GRAVITY_POINTS["one_g_reference"]
        parts.append("the record refers to 1 g or ground reference tests")
        quotes.append(one_g)
    proxy = find_sentence(PROXY_PATTERN, record_text)
    if proxy:
        points += GRAVITY_POINTS["partial_gravity_proxy"]
        parts.append("it uses an electric field, a possible proxy for a body force")
        quotes.append(proxy)
    return Criterion(
        "scored",
        points / sum(GRAVITY_POINTS.values()),
        f"{points} of 10 points: " + "; ".join(parts) + ". PSI holds no partial-gravity data.",
        {"label": "PSI record", "psi_id": investigation.psi_id, "psi_url": investigation.psi_url, "quotes": quotes},
        {"microgravity": microgravity, "one_g_reference": bool(one_g), "partial_gravity_proxy": bool(proxy)},
    )


def judged_criterion(investigation: Investigation, key: str, what: str) -> Criterion:
    """Fuel relevance and safety function are judged by Claude once per investigation and stored."""
    judged = investigation.judgment_scores.get(key)
    if not judged:
        return Criterion("not_available", explanation=f"No stored AI judgment of {what} for this record yet.")
    return Criterion(
        "scored",
        judged["score"],
        judged["rationale"],
        {
            "label": "AI judgment with quoted evidence",
            "psi_id": investigation.psi_id,
            "psi_url": investigation.psi_url,
            "quotes": [item["quote"] for item in judged.get("evidence", [])],
            "ai": {"model": judged.get("model"), "generated_at": judged.get("generated_at")},
        },
    )


def total_of(criteria: dict[str, Criterion], weights: dict[str, float]) -> tuple[float | None, dict[str, float | None]]:
    """Rescale over the criteria that have a score. The rescaled points add up to the total."""
    usable = {key: c for key, c in criteria.items() if c.status == "scored" and weights.get(key, 0) > 0}
    weight_sum = sum(weights[key] for key in usable)
    points: dict[str, float | None] = dict.fromkeys(criteria)
    if not weight_sum:
        return None, points
    for key, criterion in usable.items():
        points[key] = round(100 * weights[key] * criterion.score / weight_sum, 2)
    return round(sum(value for value in points.values() if value is not None), 2), points


@dataclass
class Context:
    """Everything the rubric reads, loaded once and reusable across several targets."""

    investigations: list[Investigation]
    runs: dict[int, list[dict]]
    gravity: dict[int, Criterion]


def load_context() -> Context:
    """Three queries in total. Gravity does not depend on the target, so it is scored here once."""
    runs: dict[int, list[dict]] = defaultdict(list)
    for run in TestRun.objects.values("investigation_id", "oxygen_pct", "pressure_kpa", "flow_speed_cm_s"):
        runs[run["investigation_id"]].append(run)
    texts: dict[int, dict[str, str]] = defaultdict(lambda: {"record": "", "table": ""})
    for document in SourceDocument.objects.exclude(kind=SourceDocument.Kind.TEST_RUN_STATS).values(
        "investigation_id", "kind", "text"
    ):
        key = "record" if document["kind"] == SourceDocument.Kind.RECORD else "table"
        texts[document["investigation_id"]][key] += document["text"][:20000] + "\n"
    investigations = list(Investigation.objects.all())
    gravity = {
        item.id: gravity_criterion(item, texts[item.id]["record"], texts[item.id]["table"]) for item in investigations
    }
    return Context(investigations, runs, gravity)


def rank(target: Target, weights: dict[str, float] | None = None, context: Context | None = None) -> list[dict]:
    """Ranked investigations with sub-scores for one target. No AI call."""
    weights = {**DEFAULT_WEIGHTS, **(weights or {})}
    context = context or load_context()
    rows = []
    for investigation in context.investigations:
        own_runs = context.runs.get(investigation.id, [])
        criteria = {
            "atmosphere": match_axes(investigation, own_runs, {"oxygen": target.oxygen, "pressure": target.pressure}),
            "fuel": judged_criterion(investigation, "fuel_relevance", "fuel and material relevance"),
            "safety": judged_criterion(investigation, "safety_function", "safety function"),
            "flow": match_axes(investigation, own_runs, {"flow": target.flow}),
            "gravity": context.gravity[investigation.id],
        }
        total, points = total_of(criteria, weights)
        rows.append(
            {
                "psi_id": investigation.psi_id,
                "display_name": investigation.display_name,
                "title": investigation.title,
                "data_depth": investigation.data_depth,
                "fuel_state": investigation.fuel_state,
                "safety_pillars": investigation.safety_pillars,
                "psi_url": investigation.psi_url,
                "total": total,
                "partial_data": any(c.status == "not_available" for c in criteria.values())
                or bool(criteria["atmosphere"].details.get("missing_axes")),
                "sub_scores": {
                    key: {
                        "label": CRITERIA[key],
                        "status": c.status,
                        "score": c.score,
                        "weight": weights[key],
                        "points": points[key],
                        "explanation": c.explanation,
                        "source": c.source,
                        "details": c.details,
                    }
                    for key, c in criteria.items()
                },
            }
        )
    rows.sort(key=lambda row: (row["total"] is None, -(row["total"] or 0), row["psi_id"]))
    for position, row in enumerate(rows, start=1):
        row["rank"] = position
    return rows
