"""Condition ranges of an investigation, computed from its test runs (section 5.1)."""

from django.db.models import Max, Min

from catalog.models import ConditionsSource, DataDepth, Investigation

RANGE_FIELDS = {
    "oxygen_pct": "oxygen_pct",
    "pressure_kpa": "pressure_kpa",
    "flow_speed_cm_s": "flow_speed_cm_s",
}


def recompute_ranges_from_test_runs(investigation: Investigation) -> bool:
    """Set min/max columns from test runs. Returns False when the record has no test runs."""
    runs = investigation.test_runs.all()
    if not runs.exists():
        return False
    aggregates = runs.aggregate(
        **{f"{name}_min": Min(column) for name, column in RANGE_FIELDS.items()},
        **{f"{name}_max": Max(column) for name, column in RANGE_FIELDS.items()},
    )
    for key, value in aggregates.items():
        setattr(investigation, key, value)
    investigation.conditions_source = ConditionsSource.TEST_RUNS
    investigation.data_depth = DataDepth.PER_TEST
    investigation.save()
    return True


VARIABLES = [
    ("fuel", "Fuel", None),
    ("fuel_form", "Fuel form", None),
    ("geometry", "Sample or burner geometry", None),
    ("oxygen_pct", "Oxygen", "%"),
    ("diluent", "Diluent", None),
    ("pressure_kpa", "Pressure", "kPa"),
    ("flow_speed_cm_s", "Flow speed", "cm/s"),
    ("flow_direction", "Flow direction", None),
    ("gravity_level", "Gravity", None),
]


def variable_summary(investigation: Investigation) -> dict:
    """Which test variables varied between tests and which were held constant.

    A variable with no recorded value in any run is listed as not recorded, never as constant.
    """
    runs = investigation.test_runs.all()
    total = runs.count()
    result = {"test_run_count": total, "varied": [], "constant": [], "not_recorded": []}
    if not total:
        return result
    for column, label, unit in VARIABLES:
        numeric = unit is not None
        known = runs.filter(**{f"{column}__isnull": False}) if numeric else runs.exclude(**{column: ""})
        recorded = known.count()
        if not recorded:
            result["not_recorded"].append({"field": column, "label": label})
            continue
        distinct = known.values(column).distinct().count()
        entry = {"field": column, "label": label, "unit": unit, "recorded_runs": recorded, "distinct_values": distinct}
        if numeric:
            bounds = known.aggregate(low=Min(column), high=Max(column))
            entry["min"], entry["max"] = bounds["low"], bounds["high"]
        elif distinct <= 12:
            entry["values"] = sorted(known.values_list(column, flat=True).distinct())
        result["varied" if distinct > 1 else "constant"].append(entry)
    return result
