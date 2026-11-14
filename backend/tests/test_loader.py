import pytest

from catalog.models import ConditionsSource, DataDepth, Investigation, SourceDocument, TestRun
from ingestion.loader import load_fixture
from tests.conftest import FIXTURE

pytestmark = pytest.mark.django_db


def test_record_count_matches_fixture_and_every_record_has_a_psi_link(seeded, psi_fixture):
    """The check of build step 3."""
    assert Investigation.objects.count() == len(psi_fixture["investigations"]) == seeded.counts["investigations"]
    for investigation in Investigation.objects.all():
        assert investigation.psi_url == f"https://psi.nasa.gov/physci/repo/data/investigations/{investigation.psi_id}"
    assert set(Investigation.objects.filter(is_seed=True).values_list("psi_id", flat=True)) == set(
        psi_fixture["seed_set"]
    )
    assert Investigation.objects.filter(is_seed=True).count() == 12


def test_only_combustion_records_are_loaded(seeded):
    assert set(Investigation.objects.values_list("research_area", flat=True)) == {"Combustion Science"}
    assert not Investigation.objects.filter(psi_id__in=["PSI-108", "PSI-181"]).exists()


def test_ranges_come_from_test_runs_and_missing_stays_missing(seeded):
    flex = Investigation.objects.get(psi_id="PSI-69")
    assert flex.conditions_source == ConditionsSource.TEST_RUNS and flex.data_depth == DataDepth.PER_TEST
    assert flex.test_runs.count() == 274
    assert flex.oxygen_pct_min < 21 < flex.oxygen_pct_max
    assert flex.flow_speed_cm_s_min is None  # FLEX table has no flow column
    saffire = Investigation.objects.get(psi_id="PSI-99")
    assert saffire.flow_speed_cm_s_min is not None and saffire.pressure_kpa_min is None
    bass = Investigation.objects.get(psi_id="PSI-26")
    assert bass.test_runs.count() == 0 and bass.conditions_source == "" and bass.oxygen_pct_min is None


def test_every_test_run_traces_to_file_and_row(seeded):
    run = TestRun.objects.filter(investigation__psi_id="PSI-69").order_by("source_row").first()
    assert run.source_file.name == "PSI-69_Experimental table_FLEX.csv" and run.source_row == 2
    assert run.source_file.checksum and run.raw_row["Fuel"] == run.fuel


def test_record_document_holds_text_word_for_word(seeded, psi_fixture):
    document = SourceDocument.objects.get(investigation__psi_id="PSI-25", kind=SourceDocument.Kind.RECORD)
    assert psi_fixture["investigations"]["PSI-25"]["objective"].strip() in document.text


def test_no_contact_details_are_stored(seeded):
    for contacts in Investigation.objects.values_list("contacts", flat=True):
        for contact in contacts:
            assert set(contact) == {"name", "affiliation", "roles"}


def test_loading_twice_does_not_duplicate(seeded):
    before = (Investigation.objects.count(), TestRun.objects.count(), SourceDocument.objects.count())
    load_fixture(FIXTURE)
    assert (Investigation.objects.count(), TestRun.objects.count(), SourceDocument.objects.count()) == before


def test_implausible_value_is_left_empty_and_reported(seeded):
    """FLEX row 115 lists an ambient pressure of 0 mmHg in the PSI table."""
    run = TestRun.objects.get(investigation__psi_id="PSI-69", source_row=115)
    assert run.pressure_kpa is None and run.raw_row["Ambient pressure; mmHg"] == "0"
    assert any("PSI-69" in error and "row 115" in error for error in seeded.errors)
    assert Investigation.objects.get(psi_id="PSI-69").pressure_kpa_min > 60
