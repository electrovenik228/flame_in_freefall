"""One parser per experiment-table layout (section 4.5).

Each parser turns CSV rows into normalized test-run fields. Rules:
- A missing or unreadable value stays None. Nothing is guessed.
- The untouched original row is kept by the loader in `raw_row`.
- When a cell holds a range or an approximate value ("21.5 - 21.7", "~ 22.1"), the
  normalized value is the first number in the cell and the original text is kept in
  `outcomes` under `<field>_as_written`.
"""

import csv
import datetime as dt
import io
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

MMHG_TO_KPA = 0.1333224
BAR_TO_KPA = 100.0
NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)")


@dataclass
class ParsedRun:
    source_row: int
    raw_row: dict[str, str]
    test_label: str = ""
    date: dt.date | None = None
    fuel: str = ""
    fuel_form: str = ""
    geometry: str = ""
    oxygen_pct: float | None = None
    diluent: str = ""
    pressure_kpa: float | None = None
    flow_speed_cm_s: float | None = None
    flow_direction: str = ""
    gravity_level: str = "microgravity"
    ignited: bool | None = None
    extinction_mode: str = ""
    outcomes: dict = field(default_factory=dict)


def validate(run: ParsedRun) -> list[str]:
    """Schema checks (section 4.5). An implausible value is removed from the normalized
    column and reported; the original stays in `raw_row`."""
    issues = []
    if run.pressure_kpa is not None and run.pressure_kpa <= 0:
        issues.append(f"row {run.source_row}: pressure {run.pressure_kpa} kPa is not positive, left empty")
        run.pressure_kpa = None
    if run.oxygen_pct is not None and not 0 < run.oxygen_pct <= 100:
        issues.append(f"row {run.source_row}: oxygen {run.oxygen_pct}% is outside 0-100, left empty")
        run.oxygen_pct = None
    if run.flow_speed_cm_s is not None and run.flow_speed_cm_s < 0:
        issues.append(f"row {run.source_row}: flow {run.flow_speed_cm_s} cm/s is negative, left empty")
        run.flow_speed_cm_s = None
    return issues


def first_number(text: str | None) -> float | None:
    match = NUMBER.search(text or "")
    return float(match.group()) if match else None


def is_plain_number(text: str) -> bool:
    return bool(NUMBER.fullmatch((text or "").strip()))


def parse_date(text: str) -> dt.date | None:
    for fmt in ("%m/%d/%Y", "%m/%d/%y"):
        try:
            return dt.datetime.strptime(text.strip(), fmt).date()
        except ValueError:
            continue
    return None


def yes_no(text: str) -> bool | None:
    value = (text or "").strip().lower()
    return {"yes": True, "no": False}.get(value)


def read_rows(content: str) -> Iterator[tuple[int, dict[str, str]]]:
    """Yield (1-based file row number, row as dict). The header is row 1; header names are stripped."""
    reader = csv.reader(io.StringIO(content))
    header = [name.strip() for name in next(reader)]
    for index, cells in enumerate(reader, start=2):
        if not any(cell.strip() for cell in cells):
            continue
        yield index, {name: cell.strip() for name, cell in zip(header, cells, strict=False)}


def put_number(outcomes: dict, key: str, text: str) -> None:
    value = first_number(text)
    if value is not None:
        outcomes[key] = value


def note_if_not_plain(outcomes: dict, key: str, text: str) -> None:
    if text and not is_plain_number(text):
        outcomes[f"{key}_as_written"] = text


def parse_flex(content: str) -> Iterator[ParsedRun]:
    """FLEX droplet tests (PSI-69). Pressure in mmHg, ambient composition in mole fractions.

    The source headers read "O", "N", "CO" and "He initial ambient composition". They are read
    as O2, N2, CO2 and He; see docs/decisions.md.
    """
    for row_number, row in read_rows(content):
        oxygen = first_number(row.get("O initial ambient composition; mole fraction"))
        pressure = first_number(row.get("Ambient pressure; mmHg"))
        diluents = ["N2"] if (first_number(row.get("N initial ambient composition; mole fraction")) or 0) > 0 else []
        if (first_number(row.get("CO initial ambient composition; mole fraction")) or 0) > 0:
            diluents.append("CO2")
        if (first_number(row.get("He initial ambient composition; mole fraction")) or 0) > 0:
            diluents.append("He")
        diameter = row.get("Droplet initial diameter; mm", "")
        outcomes: dict = {}
        put_number(outcomes, "burn_time_s", row.get("Burn time; s", ""))
        put_number(outcomes, "burning_rate_as_tabulated", row.get("Burning rate; mm", ""))
        put_number(
            outcomes, "visible_flame_extinction_diameter_mm", row.get("Visible flame extinction diameter; mm", "")
        )
        yield ParsedRun(
            source_row=row_number,
            raw_row=row,
            test_label=row.get("FLEX Identifier") or row.get("FLEX Test #", ""),
            date=parse_date(row.get("Test Date", "")),
            fuel=row.get("Fuel", ""),
            fuel_form="droplet",
            geometry=f"droplet, initial diameter {diameter} mm" if diameter else "droplet",
            oxygen_pct=round(oxygen * 100, 4) if oxygen is not None else None,
            diluent=" + ".join(diluents),
            pressure_kpa=round(pressure * MMHG_TO_KPA, 3) if pressure is not None else None,
            extinction_mode=row.get("Test end", ""),
            outcomes=outcomes,
        )


CFI_G_END = {"se": "Self-extinction", "ft": "Flow termination"}


def parse_cfi_g_normal(content: str) -> Iterator[ParsedRun]:
    """ACME CFI-G normal flames (PSI-159). Ambient oxygen as mole fraction, pressure in bar."""
    for row_number, row in read_rows(content):
        oxygen = first_number(row.get("XO2 before test"))
        pressure = first_number(row.get("approx p (bar)"))
        outcomes: dict = {}
        put_number(outcomes, "oxygen_mole_fraction_after_test", row.get("XO2  after test", ""))
        put_number(outcomes, "fuel_mole_fraction_in_burner_gas", row.get("Xf", ""))
        put_number(outcomes, "burn_time_s", row.get("burn time (sec)", ""))
        put_number(outcomes, "adiabatic_flame_temperature_k", row.get("Tad (K)", ""))
        put_number(outcomes, "peak_burner_temperature_c", row.get("Peak burner T (C )", ""))
        if row.get("Cool flame?"):
            outcomes["cool_flame"] = row["Cool flame?"]
        if row.get("Comments"):
            outcomes["comments"] = row["Comments"]
        yield ParsedRun(
            source_row=row_number,
            raw_row=row,
            test_label=row.get("Test", ""),
            fuel=row.get("Fuel", ""),
            fuel_form="gas",
            geometry="normal flame (fuel issues from the burner)",
            oxygen_pct=round(oxygen * 100, 4) if oxygen is not None else None,
            pressure_kpa=round(pressure * BAR_TO_KPA, 3) if pressure is not None else None,
            ignited=yes_no(row.get("Hot ignition", "")),
            extinction_mode=CFI_G_END.get(row.get("Self-ext or flow term", "").lower(), ""),
            outcomes=outcomes,
        )


def parse_cfi_g_inverse(content: str) -> Iterator[ParsedRun]:
    """ACME CFI-G inverse flames (PSI-159). The oxidizer issues from the burner into a fuel ambient.

    XO2 is therefore the oxygen fraction of the burner gas, not of an atmosphere, so
    `oxygen_pct` stays empty and the value is kept in `outcomes`.
    """
    for row_number, row in read_rows(content):
        pressure = first_number(row.get("approx p (bar)"))
        outcomes: dict = {}
        put_number(outcomes, "burner_gas_oxygen_mole_fraction", row.get("XO2", ""))
        put_number(outcomes, "ambient_fuel_mole_fraction_before_test", row.get("Xf  before test", ""))
        put_number(outcomes, "burn_time_s", row.get("burn time (sec)", ""))
        put_number(outcomes, "adiabatic_flame_temperature_k", row.get("Tad (K)", ""))
        if row.get("Comments"):
            outcomes["comments"] = row["Comments"]
        yield ParsedRun(
            source_row=row_number,
            raw_row=row,
            test_label=row.get("Test", ""),
            fuel=row.get("Fuel", ""),
            fuel_form="gas",
            geometry="inverse flame (oxidizer issues from the burner)",
            pressure_kpa=round(pressure * BAR_TO_KPA, 3) if pressure is not None else None,
            ignited=yes_no(row.get("Hot ignition", "")),
            extinction_mode=CFI_G_END.get(row.get("Self -ext or flow term", "").lower(), ""),
            outcomes=outcomes,
        )


def parse_bass2(content: str) -> Iterator[ParsedRun]:
    """BASS-II solid samples (PSI-25). Oxygen in percent by volume.

    Flow is recorded as fan and air display settings, not as a speed, so `flow_speed_cm_s`
    stays empty. The table has no pressure column.
    """
    for row_number, row in read_rows(content):
        oxygen_text = row.get("Calibrated  initial O2 % by vol", "")
        outcomes: dict = {"principal_investigator": row.get("PI", "")}
        note_if_not_plain(outcomes, "oxygen_pct", oxygen_text)
        put_number(outcomes, "final_oxygen_pct", row.get("Calibrated final O2 % by vol", ""))
        put_number(outcomes, "initial_co2_pct", row.get("Initial CO2 % by vol", ""))
        put_number(outcomes, "final_co2_pct", row.get("Final CO2 % by vol", ""))
        for key, column in (("fan_display", "Fan display"), ("air_display", "Air display")):
            if row.get(column):
                outcomes[key] = row[column]
        material = row.get("Fuel Sample Material", "")
        yield ParsedRun(
            source_row=row_number,
            raw_row=row,
            test_label=row.get("Test #", ""),
            date=parse_date(row.get("Date", "")),
            fuel=material,
            fuel_form="solid",
            geometry=material,
            oxygen_pct=first_number(oxygen_text),
            outcomes=outcomes,
        )


def parse_saffire(content: str) -> Iterator[ParsedRun]:
    """Saffire-I, -II and -III sample tables (PSI-98, 99, 100). Flow in cm/s, oxygen in percent.

    Rows without an air-flow value are notes or flow-visualization entries, not samples.
    """
    for row_number, row in read_rows(content):
        flow_text = row.get("Air Flow (cm/s)") or row.get("Air Flow", "")
        if first_number(flow_text) is None:
            continue
        oxygen_text = row.get("Percent O2") or row.get("Percent O2 (Note 1)", "")
        dimensions = [
            f"{label} {value}"
            for label, value in (
                (
                    "thickness",
                    row.get("Sample Thickness (cm)") or row.get("Sample Thickness") or row.get("Samle Thickness", ""),
                ),
                ("length", row.get("Sample Length (cm)") or row.get("Sample Length", "")),
                ("width", row.get("Sample Width (cm)") or row.get("Sample Width", "")),
            )
            if value
        ]
        outcomes: dict = {}
        note_if_not_plain(outcomes, "oxygen_pct", oxygen_text)
        for key, column in (
            ("burn_time", "Burn Time (s)"),
            ("ignition_power", "Ignition Power (W)"),
            ("ignition_time", "Ignition Time (s)"),
        ):
            if row.get(column):
                outcomes[f"{key}_as_written"] = row[column]
        yield ParsedRun(
            source_row=row_number,
            raw_row=row,
            test_label=row.get("Sample Number", ""),
            fuel=row.get("Material", ""),
            fuel_form="solid",
            geometry=", ".join(dimensions),
            oxygen_pct=first_number(oxygen_text),
            flow_speed_cm_s=first_number(flow_text),
            flow_direction=(row.get("Flow Direction") or row.get("Direction", "")).strip(),
            outcomes=outcomes,
        )


# File name of the PSI experiment table -> parser. Tables not listed here are stored as
# source documents but are not turned into test runs in the weekend build.
PARSERS: dict[str, Callable[[str], Iterator[ParsedRun]]] = {
    "PSI-69_Experimental table_FLEX.csv": parse_flex,
    "PSI-159_Experimental table_CFI-G_Normal Flames.csv": parse_cfi_g_normal,
    "PSI-159_Experimental table_CFI-G_Inverse Flames.csv": parse_cfi_g_inverse,
    "PSI-25_Experimental table_BASS-II.csv": parse_bass2,
    "PSI-98_Experimental table_SAFFIRE-1.csv": parse_saffire,
    "PSI-99_Experimental table_SAFFIRE-2.csv": parse_saffire,
    "PSI-100_Experimental table_SAFFIRE-3.csv": parse_saffire,
}
