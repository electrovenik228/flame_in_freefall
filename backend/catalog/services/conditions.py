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
