import pytest
from django.db import IntegrityError, transaction

from ai.models import Insight, RelevanceScore, ReviewStatus
from assistant.models import Conversation, Message
from catalog.models import Environment, Facility, Investigation, SourceFile, TestRun
from ingestion.models import IngestionRun

pytestmark = pytest.mark.django_db


@pytest.fixture
def investigation():
    return Investigation.objects.create(
        psi_id="PSI-999",
        acronym="DEMO",
        title="Demo flame experiment",
        objectives="Study ethylene flames.",
        psi_url="https://psi.nasa.gov/physci/repo/data/investigations/PSI-999",
    )


def test_missing_values_stay_missing(investigation):
    investigation.refresh_from_db()
    assert investigation.oxygen_pct_min is None
    assert investigation.fuel_state == ""
    assert investigation.safety_pillars == []
    assert investigation.judgment_scores == {}


def test_psi_id_is_unique(investigation):
    with pytest.raises(IntegrityError), transaction.atomic():
        Investigation.objects.create(psi_id="PSI-999", title="Duplicate", psi_url="https://psi.nasa.gov/x")


def test_test_run_keeps_raw_row_and_provenance(investigation):
    source = SourceFile.objects.create(investigation=investigation, path="/t.csv", name="t.csv")
    run = TestRun.objects.create(
        investigation=investigation,
        source_file=source,
        source_row=2,
        oxygen_pct=21.0,
        raw_row={"O2": "0.21"},
    )
    assert run.raw_row == {"O2": "0.21"}
    assert run.pressure_kpa is None
    with pytest.raises(IntegrityError), transaction.atomic():
        TestRun.objects.create(investigation=investigation, source_file=source, source_row=2, raw_row={})


def test_search_text_includes_fuel_and_facility(investigation):
    source = SourceFile.objects.create(investigation=investigation, path="/t.csv", name="t.csv")
    TestRun.objects.create(investigation=investigation, source_file=source, source_row=2, fuel="Heptane", raw_row={})
    investigation.facilities.add(Facility.objects.create(name="Combustion Integrated Rack"))
    investigation.refresh_search_text()
    assert Investigation.objects.filter(search_text="heptane").exists()
    assert Investigation.objects.filter(search_text="rack").exists()
    assert not Investigation.objects.filter(search_text="xenon").exists()


def test_relevance_pair_is_unique(investigation):
    env = Environment.objects.create(slug="e", name="E", gravity="1 g", source="test")
    RelevanceScore.objects.create(investigation=investigation, environment=env, total=50, sub_scores={})
    with pytest.raises(IntegrityError), transaction.atomic():
        RelevanceScore.objects.create(investigation=investigation, environment=env, total=60, sub_scores={})


def test_insight_defaults_to_unreviewed(investigation):
    insight = Insight.objects.create(
        type=Insight.Type.SUMMARY, investigation=investigation, model="m", prompt_version="v1", input_hash="h"
    )
    assert insight.review_status == ReviewStatus.UNREVIEWED
    assert insight.is_current


def test_conversation_and_run_log():
    conversation = Conversation.objects.create(session_key="abc")
    Message.objects.create(conversation=conversation, role=Message.Role.USER, content="Hello")
    assert conversation.messages.count() == 1
    assert IngestionRun.objects.create(route="owner_export").finished is None
