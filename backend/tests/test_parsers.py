"""Parsers are tested against the real PSI tables held in the fixture (section 11)."""

import pytest

from ingestion import parsers


def table(psi_fixture, psi_id: str, index: int = 0) -> str:
    return psi_fixture["experiment_tables"][psi_id][index]["content"]


def test_first_number_and_plain_number():
    assert parsers.first_number("~ 21.5") == 21.5
    assert parsers.first_number("21.5 - 21.7") == 21.5
    assert parsers.first_number("20 cm/s") == 20
    assert parsers.first_number("n/a") is None
    assert parsers.first_number("") is None
    assert parsers.is_plain_number("22.2") and not parsers.is_plain_number("~ 22.1")


def test_flex_units_and_provenance(psi_fixture):
    runs = list(parsers.parse_flex(table(psi_fixture, "PSI-69")))
    assert len(runs) == 274
    first = runs[0]
    assert first.source_row == 2 and first.test_label == "20CAL08"
    assert first.fuel == "Methanol" and first.fuel_form == "droplet"
    assert first.oxygen_pct == pytest.approx(21.0)
    assert first.pressure_kpa == pytest.approx(757.7 * 0.1333224, abs=0.01)  # mmHg to kPa
    assert first.diluent == "N2" and first.extinction_mode == "Disruption"
    assert first.flow_speed_cm_s is None  # the table has no flow column
    assert first.raw_row["Ambient pressure; mmHg"] == "757.7"
    assert runs[-1].diluent == "N2 + He"
    assert runs[59].outcomes.get("visible_flame_extinction_diameter_mm") is None  # blank cell stays missing


def test_cfi_g_normal_and_inverse(psi_fixture):
    normal = list(parsers.parse_cfi_g_normal(table(psi_fixture, "PSI-159", 0)))
    inverse = list(parsers.parse_cfi_g_inverse(table(psi_fixture, "PSI-159", 1)))
    files = [t["file_name"] for t in psi_fixture["experiment_tables"]["PSI-159"]]
    assert "Normal" in files[0] and "Inverse" in files[1]
    assert len(normal) == 179 and len(inverse) == 154
    assert normal[0].oxygen_pct == pytest.approx(39.39)
    assert normal[0].pressure_kpa == pytest.approx(94.44, abs=0.01)  # bar to kPa
    assert normal[0].ignited is True and normal[0].extinction_mode == "Self-extinction"
    assert all(run.oxygen_pct is None for run in inverse)  # burner-gas oxygen is not an atmosphere
    assert inverse[0].outcomes["burner_gas_oxygen_mole_fraction"] == 0.21
    assert inverse[0].ignited is False


def test_bass2_keeps_flow_unconverted(psi_fixture):
    runs = list(parsers.parse_bass2(table(psi_fixture, "PSI-25")))
    assert len(runs) == 129
    assert runs[0].oxygen_pct == 22.2 and runs[0].fuel_form == "solid"
    assert all(run.flow_speed_cm_s is None and run.pressure_kpa is None for run in runs)
    assert runs[0].outcomes["fan_display"] == "62"


def test_saffire_skips_note_rows(psi_fixture):
    one = list(parsers.parse_saffire(table(psi_fixture, "PSI-98")))
    two = list(parsers.parse_saffire(table(psi_fixture, "PSI-99")))
    three = list(parsers.parse_saffire(table(psi_fixture, "PSI-100")))
    assert [run.test_label for run in one] == ["S1", "S2"]
    assert one[0].oxygen_pct == 21.5 and one[0].outcomes["oxygen_pct_as_written"] == "21.5 - 21.7"
    assert one[0].flow_speed_cm_s == 20 and one[1].flow_direction == "Opposed"
    assert len(two) == 9 and all(run.flow_speed_cm_s == 20 for run in two)
    # Samples 2-6 and 2-9 have an empty Material cell in the PSI table; it stays empty.
    assert [run.test_label for run in two if not run.fuel] == ["2-6", "2-9"]
    assert two[7].oxygen_pct == 22.1 and two[7].outcomes["oxygen_pct_as_written"] == "22.1 to 22.0"
    assert len(three) == 2 and three[0].flow_speed_cm_s == 30 and three[0].oxygen_pct is None
