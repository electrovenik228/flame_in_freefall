"""Step 7: rubric scoring in code, ranking and coverage endpoints."""

import pytest

from ai.models import Insight, RelevanceScore
from ai.services import generate
from ai.services.judgment import Judged, Judgment
from catalog.models import ConditionsSource, Environment, Investigation
from catalog.reference import load_environments
from catalog.services import ranking
from tests.test_ai import ev, reply

pytestmark = pytest.mark.django_db
BASE = "/api/v1"


@pytest.fixture
def ranked(seeded):
    load_environments()
    return {env.slug: env for env in Environment.objects.all()}


def by_id(rows):
    return {row["psi_id"]: row for row in rows}


def test_gap_and_closeness():
    assert ranking.gap(12, 34, (30, None)) == 0  # overlaps an open-ended window
    assert ranking.gap(21, 21, (30, None)) == 9
    assert ranking.gap(101.3, 101.3, (None, 70.3)) == pytest.approx(31.0)
    assert ranking.closeness(0.5, 1, 10) == 1.0
    assert ranking.closeness(6, 1, 10) == 0.5
    assert ranking.closeness(50, 1, 10) == 0.0


def test_reference_environments_match_section_5_2(ranked):
    lunar = ranked["lunar-habitat"]
    assert (lunar.oxygen_pct_min, lunar.oxygen_pct_max, lunar.pressure_kpa_min, lunar.pressure_kpa_max) == (
        30,
        None,
        None,
        70.3,
    )
    mars = ranked["mars-habitat"]
    assert (mars.oxygen_pct_min, mars.pressure_kpa_min, mars.gravity) == (34, 56.5, "3/8 g")
    assert ranked["spacesuit"].oxygen_pct_min == 100 and ranked["earth-sea-level"].pressure_kpa_min == 101.3
    assert all(env.flow_cm_s_min is None for env in ranked.values())  # the brief gives no ventilation speed


def test_sub_scores_add_up_to_the_total(ranked):
    """First part of the step 7 check."""
    for environment in ranked.values():
        for row in ranking.rank(ranking.Target.from_environment(environment)):
            points = [s["points"] for s in row["sub_scores"].values() if s["points"] is not None]
            assert row["total"] == pytest.approx(sum(points), abs=0.01)
            assert 0 <= row["total"] <= 100
            for sub in row["sub_scores"].values():
                assert (sub["points"] is None) == (sub["status"] != "scored")


def test_missing_data_is_rescaled_and_tagged_never_zero(ranked):
    rows = by_id(ranking.rank(ranking.Target.from_environment(ranked["lunar-habitat"])))
    flex = rows["PSI-69"]
    assert flex["sub_scores"]["fuel"]["status"] == "not_available" and flex["sub_scores"]["fuel"]["points"] is None
    assert flex["sub_scores"]["flow"]["status"] == "not_applicable"  # no ventilation speed defined
    assert flex["partial_data"] is True
    # Only atmosphere (30) and gravity (10) are scored: the total is rescaled over 40 points.
    atmosphere, gravity = flex["sub_scores"]["atmosphere"], flex["sub_scores"]["gravity"]
    expected = 100 * (30 * atmosphere["score"] + 10 * gravity["score"]) / 40
    assert flex["total"] == pytest.approx(expected, abs=0.01)


def test_atmosphere_uses_test_runs_and_counts_runs_inside(ranked):
    rows = by_id(ranking.rank(ranking.Target.from_environment(ranked["lunar-habitat"])))
    cfi_g = rows["PSI-159"]["sub_scores"]["atmosphere"]
    assert cfi_g["details"]["basis"] == "test_runs" and cfi_g["details"]["runs_inside"] > 0 and cfi_g["score"] == 1.0
    assert "test runs fall inside the target" in cfi_g["explanation"]
    saffire = rows["PSI-98"]["sub_scores"]["atmosphere"]
    assert saffire["details"]["missing_axes"] == ["pressure"] and 0 < saffire["score"] < 0.3  # 21.5% vs 30% or more
    assert rows["PSI-98"]["partial_data"] is True
    station = by_id(ranking.rank(ranking.Target.from_environment(ranked["space-station"])))
    assert station["PSI-98"]["sub_scores"]["atmosphere"]["score"] == 1.0  # 21.5% is within tolerance of 21%


def test_a_record_without_test_runs_is_ranked_from_its_ranges(ranked):
    """Second part of the step 7 check."""
    flex2 = Investigation.objects.get(psi_id="PSI-68")
    assert not flex2.test_runs.exists()
    Investigation.objects.filter(pk=flex2.pk).update(
        oxygen_pct_min=10, oxygen_pct_max=40, pressure_kpa_min=50.66, pressure_kpa_max=303.98,
        conditions_source=ConditionsSource.RECORD_TEXT,
    )  # fmt: skip
    rows = by_id(ranking.rank(ranking.Target.from_environment(ranked["lunar-habitat"])))
    atmosphere = rows["PSI-68"]["sub_scores"]["atmosphere"]
    assert atmosphere["status"] == "scored" and atmosphere["score"] == 1.0
    assert atmosphere["details"]["basis"] == "record_ranges" and "The record states" in atmosphere["explanation"]
    assert rows["PSI-26"]["sub_scores"]["atmosphere"]["status"] == "not_available"  # BASS: nothing stated yet


def test_gravity_points(ranked):
    rows = by_id(ranking.rank(ranking.Target.from_environment(ranked["lunar-habitat"])))
    e_field = rows["PSI-22"]["sub_scores"]["gravity"]
    assert (
        e_field["details"] == {"microgravity": True, "one_g_reference": False, "partial_gravity_proxy": True}
        or e_field["details"]["partial_gravity_proxy"]
    )
    assert e_field["score"] >= 0.8 and e_field["source"]["quotes"]
    saffire2 = rows["PSI-99"]["sub_scores"]["gravity"]  # the table has "1-g Burn Length" columns
    assert saffire2["details"]["one_g_reference"] and saffire2["score"] == 0.8
    ground = rows["PSI-60"]["sub_scores"]["gravity"]
    assert ground["details"]["microgravity"] is False
    # Gravity does not depend on the environment, so Moon and Mars differ only through the atmosphere.
    mars = by_id(ranking.rank(ranking.Target.from_environment(ranked["mars-habitat"])))
    assert all(mars[k]["sub_scores"]["gravity"]["score"] == rows[k]["sub_scores"]["gravity"]["score"] for k in rows)


def test_judgment_is_verified_stored_and_used(ranked, monkeypatch):
    from ai.services import llm
    from tests.test_ai import FakeClient

    bass2 = Investigation.objects.get(psi_id="PSI-25")
    record = bass2.documents.get(kind="record").text
    quote = record[record.index("Objective:") + 11 :][:80]
    good = Judgment(
        fuel_relevance=Judged(score=9, rationale="Solid cabin-type materials were burned.", evidence=ev(quote, "S1")),
        safety_function=Judged(score=8, rationale="The work feeds fire-safety models.", evidence=ev(quote, "S1")),
    )
    bad = Judgment(
        fuel_relevance=Judged(score=14, rationale="Tested 5000 samples.", evidence=ev("not in the source", "S1")),
        safety_function=Judged(score=8, rationale="Fine.", evidence=[]),
    )
    client = FakeClient([reply(parsed=bad), reply(parsed=good)])
    monkeypatch.setattr(llm, "get_client", lambda: client)
    assert generate.generate_judgment(bass2) == "generated" and len(client.calls) == 2
    feedback = client.calls[1]["messages"][-1]["content"]
    assert (
        "outside 0 to 10" in feedback
        and "quote not found" in feedback
        and "5000" in feedback
        and "no evidence" in feedback
    )
    bass2.refresh_from_db()
    assert bass2.judgment_scores["fuel_relevance"]["score"] == 0.9
    assert Insight.objects.get(investigation=bass2, type="judgment").checks["evidence_quotes_verified"]
    row = by_id(ranking.rank(ranking.Target.from_environment(ranked["lunar-habitat"])))["PSI-25"]
    assert row["sub_scores"]["fuel"]["status"] == "scored" and row["sub_scores"]["fuel"]["score"] == 0.9
    assert row["sub_scores"]["fuel"]["source"]["quotes"] == [quote]
    assert generate.generate_judgment(bass2) == "unchanged"


def test_ranking_endpoints(client, ranked):
    lunar = ranked["lunar-habitat"]
    body = client.get(f"{BASE}/environments/{lunar.id}/ranking/").json()
    assert body["environment"]["slug"] == "lunar-habitat" and body["weights"]["atmosphere"] == 30
    assert "not a safety rating" in body["disclaimer"] and "no partial-gravity data" in body["gravity_note"]
    assert len(body["results"]) == 23 and [r["rank"] for r in body["results"]][:3] == [1, 2, 3]
    totals = [r["total"] for r in body["results"] if r["total"] is not None]
    assert totals == sorted(totals, reverse=True)
    assert body["results"][0]["psi_id"] in {"PSI-159", "PSI-69"}  # the records with runs at 30% oxygen or more
    assert client.get(f"{BASE}/environments/9999/ranking/").status_code == 404
    assert len(client.get(f"{BASE}/environments/").json()) == 5


def test_custom_ranking_is_computed_in_code_with_flow(client, ranked):
    payload = {
        "oxygen_pct_min": 20,
        "oxygen_pct_max": 23,
        "flow_cm_s_min": 15,
        "flow_cm_s_max": 25,
        "weights": {"flow": 50, "fuel": 0, "safety": 0},
    }
    body = client.post(f"{BASE}/rankings/custom/", payload, content_type="application/json").json()
    assert body["weights"]["flow"] == 50 and body["environment"] is None
    top = body["results"][0]
    assert top["psi_id"] in {"PSI-98", "PSI-99"} and top["sub_scores"]["flow"]["score"] == 1.0
    assert top["sub_scores"]["fuel"]["points"] is None  # weight 0 leaves it out of the total
    bad = client.post(
        f"{BASE}/rankings/custom/", {"oxygen_pct_min": 40, "oxygen_pct_max": 30}, content_type="application/json"
    )
    assert bad.status_code == 400 and bad.json()["error"]["code"] == "invalid"
    assert client.post(f"{BASE}/rankings/custom/", {}, content_type="application/json").status_code == 400


def test_coverage_endpoint(client, ranked):
    body = client.get(f"{BASE}/coverage/").json()
    assert body["x"] == {"field": "oxygen_pct", "unit": "%", "bin": 2.0}
    assert sum(cell["count"] for cell in body["bins"]) == body["test_runs_plotted"]
    assert body["test_runs_plotted"] + body["test_runs_missing_an_axis"] == body["test_runs_total"] == 749
    assert body["test_runs_plotted"] == 273 + 179  # FLEX and CFI-G normal flames have both oxygen and pressure
    lunar = next(env for env in body["environments"] if env["slug"] == "lunar-habitat")
    assert lunar["tested"] and lunar["test_runs_inside"] > 0 and lunar["nearest"][0]["psi_id"] in {"PSI-159", "PSI-69"}
    suit = next(env for env in body["environments"] if env["slug"] == "spacesuit")
    assert suit["tested"] is False and suit["test_runs_inside"] == 0
    assert "No partial-gravity combustion data exists in PSI" in body["partial_gravity"]["statement"]
    assert any(item["psi_id"] == "PSI-22" for item in body["partial_gravity"]["bounding_records"])
    flow = client.get(f"{BASE}/coverage/?y=flow_speed_cm_s").json()
    assert flow["test_runs_plotted"] == 11  # Saffire-I and -II samples with both oxygen and flow
    assert client.get(f"{BASE}/coverage/?x=oxygen_pct&y=oxygen_pct").status_code == 400


def test_scores_are_stored_per_pair(ranked):
    from ai.services.scores import refresh_scores

    assert refresh_scores() == 23 * 5
    assert RelevanceScore.objects.count() == 115
    score = RelevanceScore.objects.get(investigation__psi_id="PSI-159", environment__slug="lunar-habitat")
    assert score.total is not None and set(score.sub_scores) == set(ranking.DEFAULT_WEIGHTS)
