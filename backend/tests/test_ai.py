"""Step 6 logic, tested against a stand-in for the Claude API. No network call is made."""

from types import SimpleNamespace

import pytest

from ai.models import AICall, Insight, ReviewStatus
from ai.services import extraction as ex
from ai.services import generate, llm, verify
from ai.services.current import current_insight
from ai.services.sources import refresh_stats_document, sources_for
from catalog.models import ConditionsSource, Investigation, SourceDocument

pytestmark = pytest.mark.django_db


def reply(*, content=None, parsed=None, stop_reason="end_turn"):
    return SimpleNamespace(
        model="fake-model",
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="bio") if stop_reason == "refusal" else None,
        usage=SimpleNamespace(input_tokens=100, output_tokens=20),
        content=content or [],
        parsed_output=parsed,
    )


class FakeClient:
    def __init__(self, replies):
        self.replies, self.calls = list(replies), []
        self.messages = SimpleNamespace(parse=self._call, create=self._call)

    def _call(self, **kwargs):
        self.calls.append(kwargs)
        return self.replies.pop(0)


@pytest.fixture
def fake(monkeypatch):
    def install(*replies):
        client = FakeClient(replies)
        monkeypatch.setattr(llm, "get_client", lambda: client)
        return client

    return install


def ev(quote, source_id="S2"):
    return [ex.Evidence(source_id=source_id, quote=quote)]


def flex2_extraction(**overrides):
    """A correct extraction for FLEX-2 (PSI-68), with quotes copied from the real PSI text."""
    fields = {
        "fuel_state": ex.FuelStateField(value="liquid", evidence=ev("bi-component droplet combustion", "S1")),
        "fuels": [ex.NamedItem(name="Heptane", evidence=ev("Heptane (pure)"))],
        "safety_pillars": [],
        "data_depth": ex.DataDepthField(
            value="summary", evidence=ev("Sample (Fuel Type),Initial Droplet Diameter (mm)")
        ),
        "oxygen": ex.OxygenRange(
            min_value=0.17, max_value=0.3, unit="mole_fraction", evidence=ev("0.17; 0.21;0.25; 0.3")
        ),
        "pressure": ex.PressureRange(
            min_value=0.5, max_value=3.0, unit="atm", evidence=ev("0.5; 1.0; 1.5; 2.0; or 3.0")
        ),
        "flow_speed": ex.FlowRange(min_value=0.1, max_value=5, unit="cm/s", evidence=ev("0.1 - 5")),
        "instruments": [],
    }
    return ex.Extraction(**{**fields, **overrides})


def test_quote_check_is_word_for_word_apart_from_whitespace():
    source = "Flames were ignited\n  in 21% oxygen."
    assert verify.quote_in_source("ignited in 21% oxygen", source)
    assert not verify.quote_in_source("ignited in 21 % oxygen", source)
    assert not verify.quote_in_source("", source)


def test_number_check_rules():
    assert [token for token, _ in verify.numbers_in("PSI-69 burned C2H4 and CO2 at 21.5% in 1,000 s, sizes 2,3 mm")] == [
        "21.5", "1000", "2", "3",
    ]  # fmt: skip
    assert verify.unmatched_numbers("274 tests at 12 to 34 %", ["Runs: 274. Oxygen 12 to 34 %"]) == []
    assert verify.unmatched_numbers("about 300 tests", ["Runs: 274."]) == ["300"]


def test_extraction_is_verified_stored_and_projected(seeded, fake):
    client = fake(reply(parsed=flex2_extraction()))
    flex2 = Investigation.objects.get(psi_id="PSI-68")
    assert generate.generate_extraction(flex2) == "generated"
    flex2.refresh_from_db()
    assert flex2.conditions_source == ConditionsSource.RECORD_TEXT and flex2.fuel_state == "liquid"
    assert (flex2.oxygen_pct_min, flex2.oxygen_pct_max) == (17.0, 30.0)  # mole fraction to percent, in code
    assert flex2.pressure_kpa_min == pytest.approx(50.6625) and flex2.pressure_kpa_max == pytest.approx(303.975)
    assert (flex2.flow_speed_cm_s_min, flex2.flow_speed_cm_s_max) == (0.1, 5.0)
    assert flex2.data_depth == "summary"
    insight = current_insight(flex2, Insight.Type.EXTRACTION)
    assert insight.checks["evidence_quotes_verified"] and insight.review_status == ReviewStatus.UNREVIEWED
    assert insight.content["oxygen"]["evidence"][0]["quote"] == "0.17; 0.21;0.25; 0.3"
    assert AICall.objects.filter(job="extraction", public=False).count() == 1
    assert "<source id=" in client.calls[0]["messages"][0]["content"]
    # Unchanged input is never regenerated.
    assert generate.generate_extraction(flex2) == "unchanged" and len(client.calls) == 1


def test_a_quote_that_is_not_in_the_source_rejects_the_result(seeded, fake):
    bad = flex2_extraction(
        fuel_state=ex.FuelStateField(value="liquid", evidence=ev("liquid fuel droplets in space", "S1"))
    )
    client = fake(reply(parsed=bad), reply(parsed=bad))
    flex2 = Investigation.objects.get(psi_id="PSI-68")
    assert generate.generate_extraction(flex2) == "rejected"
    flex2.refresh_from_db()
    assert flex2.conditions_source == "" and flex2.oxygen_pct_min is None and flex2.fuel_state == ""
    assert current_insight(flex2, Insight.Type.EXTRACTION) is None
    row = Insight.objects.get(investigation=flex2, type=Insight.Type.EXTRACTION)
    assert row.review_status == ReviewStatus.NOT_GENERATED and "quote not found" in row.checks["problems"][0]
    assert len(client.calls) == 2 and "quote not found" in client.calls[1]["messages"][-1]["content"]


def test_a_number_missing_from_its_quote_or_a_value_without_evidence_is_a_problem(seeded):
    sources = sources_for(Investigation.objects.get(psi_id="PSI-68"), with_stats=False)
    wrong_number = flex2_extraction(
        oxygen=ex.OxygenRange(min_value=0.17, max_value=0.4, unit="mole_fraction", evidence=ev("0.17; 0.21;0.25; 0.3"))
    )
    assert any("0.4 does not appear" in p for p in ex.check_evidence(wrong_number, sources))
    no_evidence = flex2_extraction(fuel_state=ex.FuelStateField(value="gas", evidence=[]))
    assert any("without evidence" in p for p in ex.check_evidence(no_evidence, sources))
    assert ex.check_evidence(flex2_extraction(), sources) == []


def test_refusal_is_never_stored_as_content_or_shown(seeded, fake):
    client = fake(reply(stop_reason="refusal"))
    flex2 = Investigation.objects.get(psi_id="PSI-68")
    assert generate.generate_extraction(flex2) == "not generated"
    row = Insight.objects.get(investigation=flex2)
    assert row.review_status == ReviewStatus.NOT_GENERATED and row.content == {}
    assert current_insight(flex2, Insight.Type.EXTRACTION) is None and len(client.calls) == 1  # no retry loop


def test_test_run_ranges_win_over_extracted_ones(seeded, fake):
    flex = Investigation.objects.get(psi_id="PSI-69")
    before = (flex.oxygen_pct_min, flex.oxygen_pct_max)
    unknown = ex.OxygenRange(min_value=None, max_value=None, unit="not_stated", evidence=[])
    fake(reply(parsed=flex2_extraction(
        fuel_state=ex.FuelStateField(value="liquid", evidence=ev("liquid fuels in microgravity environments", "S1")),
        fuels=[], data_depth=ex.DataDepthField(value="unknown", evidence=[]), oxygen=unknown,
        pressure=ex.PressureRange(min_value=None, max_value=None, unit="not_stated", evidence=[]),
        flow_speed=ex.FlowRange(min_value=None, max_value=None, unit="not_stated", evidence=[]),
    )))  # fmt: skip
    assert generate.generate_extraction(flex) == "generated"
    flex.refresh_from_db()
    assert (flex.oxygen_pct_min, flex.oxygen_pct_max) == before
    assert flex.conditions_source == ConditionsSource.TEST_RUNS and flex.data_depth == "per_test"
    assert flex.fuel_state == "liquid"


def test_no_stated_conditions_gets_the_not_available_mark(seeded, fake):
    nothing = {"min_value": None, "max_value": None, "unit": "not_stated", "evidence": []}
    fake(reply(parsed=flex2_extraction(
        fuel_state=ex.FuelStateField(value="unknown", evidence=[]), fuels=[],
        data_depth=ex.DataDepthField(value="unknown", evidence=[]),
        oxygen=ex.OxygenRange(**nothing), pressure=ex.PressureRange(**nothing), flow_speed=ex.FlowRange(**nothing),
    )))  # fmt: skip
    record = Investigation.objects.get(psi_id="PSI-60")
    assert generate.generate_extraction(record) == "generated"
    record.refresh_from_db()
    assert record.conditions_source == ConditionsSource.NOT_AVAILABLE and record.oxygen_pct_min is None


def text_block(text, cited=None, document_index=0):
    citations = None
    if cited:
        citations = [
            SimpleNamespace(
                type="char_location",
                cited_text=cited,
                document_index=document_index,
                start_char_index=1,
                end_char_index=1 + len(cited),
            )
        ]
    return SimpleNamespace(type="text", text=text, citations=citations)


def test_stats_document_holds_database_numbers(seeded):
    document = refresh_stats_document(Investigation.objects.get(psi_id="PSI-69"))
    assert "Number of test runs parsed from the PSI experiment table: 274." in document.text
    assert "Oxygen: 12 to 34 %" in document.text and "Heptane 117" in document.text
    assert refresh_stats_document(Investigation.objects.get(psi_id="PSI-26")) is None


def test_summary_is_cited_checked_and_served_by_the_api(seeded, fake, client):
    flex = Investigation.objects.get(psi_id="PSI-69")
    record = flex.documents.get(kind=SourceDocument.Kind.RECORD).text
    passage = record[record.index("Objective:") + 11 :][:120]
    blocks = [
        text_block("FLEX studied how droplets of liquid fuel burn and go out in microgravity.", passage),
        text_block(" "),
        text_block(
            "The catalogue holds 274 test runs.",
            "Number of test runs parsed from the PSI experiment table: 274.",
            document_index=2,
        ),
    ]
    api = fake(reply(content=blocks), reply(content=blocks))
    assert generate.generate_summary(flex) == "generated"
    assert len(api.calls) == 2  # plain and expert
    first_document = api.calls[0]["messages"][0]["content"][0]
    assert first_document["type"] == "document" and first_document["citations"] == {"enabled": True}
    body = client.get("/api/v1/investigations/PSI-69/").json()["summary"]
    assert {"citations", "model", "generated_at", "review_status"} <= set(body)  # section 9 convention
    assert body["model"] == "fake-model" and body["review_status"] == "unreviewed"
    assert [c["n"] for c in body["citations"]] == [1, 2] and body["citations"][0]["psi_id"] == "PSI-69"
    assert body["citations"][0]["psi_url"].endswith("/PSI-69") and "document_index" not in body["citations"][0]
    assert body["content"]["plain"][0]["citations"] == [1] and body["content"]["expert"][2]["citations"] == [2]
    assert body["checks"]["numbers_match_cited_record"] is True


def test_summary_with_an_unsupported_number_or_no_citation_is_rejected(seeded, fake, client):
    flex = Investigation.objects.get(psi_id="PSI-69")
    record = flex.documents.get(kind=SourceDocument.Kind.RECORD).text
    wrong = [text_block("FLEX ran 9999 droplet tests.", record[20:80])]
    api = fake(reply(content=wrong), reply(content=wrong))
    assert generate.generate_summary(flex) == "rejected" and len(api.calls) == 2
    assert "9999" in Insight.objects.get(investigation=flex).checks["problems"]["plain"][0]
    assert client.get("/api/v1/investigations/PSI-69/").json()["summary"] is None
    uncited = [text_block("FLEX burned droplets.")]
    fake(reply(content=uncited), reply(content=uncited))
    assert generate.generate_summary(flex, force=True) == "rejected"
    assert Insight.objects.filter(investigation=flex, is_current=True).count() == 1  # older rows are kept, not current


def test_step6_report(seeded, fake):
    assert generate.step6_report()["passed"] is False
    assert "PSI-68" in generate.step6_report()["without_ranges_or_mark"]
    assert "PSI-69" not in generate.step6_report()["without_ranges_or_mark"]  # has ranges from test runs


def test_one_sided_statement_keeps_its_missing_bound(seeded):
    """ "Up to 20 atm" is an upper bound, not a single tested value."""
    up_to = flex2_extraction(pressure=ex.PressureRange(min_value=None, max_value=20, unit="atm", evidence=ev("x")))
    ranges = ex.normalized_ranges(up_to)
    assert ranges["pressure_kpa_min"] is None and ranges["pressure_kpa_max"] == pytest.approx(2026.5)


def test_ai_output_round_trips_through_the_fixture(seeded, fake, tmp_path):
    from django.core.management import call_command

    flex2 = Investigation.objects.get(psi_id="PSI-68")
    fake(reply(parsed=flex2_extraction()))
    generate.generate_extraction(flex2)
    path = tmp_path / "ai.json"
    call_command("export_ai_output", "--out", str(path))
    Insight.objects.all().delete()
    Investigation.objects.filter(pk=flex2.pk).update(fuel_state="", conditions_source="", oxygen_pct_min=None)
    call_command("import_ai_output", "--fixture", str(path))
    call_command("import_ai_output", "--fixture", str(path))  # second import adds nothing
    flex2.refresh_from_db()
    assert Insight.objects.count() == 1 and flex2.fuel_state == "liquid" and flex2.oxygen_pct_min == 17.0
    assert generate.generate_extraction(flex2) == "unchanged"  # no new Claude request after an import
