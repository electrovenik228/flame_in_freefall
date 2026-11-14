import django_filters as filters
from django.contrib.postgres.search import SearchQuery, SearchRank
from django.db.models import F, Q

from catalog import models


class CharInFilter(filters.BaseInFilter, filters.CharFilter):
    """Comma-separated list of values."""


def search_investigations(queryset, text: str):
    """Full-text search with a fallback on names, so short tokens such as "BASS" still match."""
    text = (text or "").strip()
    if not text:
        return queryset
    query = SearchQuery(text, config="english", search_type="websearch")
    return (
        queryset.annotate(rank=SearchRank(F("search_text"), query))
        .filter(Q(search_text=query) | Q(acronym__icontains=text) | Q(psi_id__iexact=text) | Q(title__icontains=text))
        .order_by("-rank", "psi_number")
    )


class InvestigationFilter(filters.FilterSet):
    q = filters.CharFilter(method="filter_q", label="Full-text search")
    fuel_state = CharInFilter(field_name="fuel_state", lookup_expr="in")
    data_depth = CharInFilter(field_name="data_depth", lookup_expr="in")
    project = filters.CharFilter(field_name="project__name", lookup_expr="iexact")
    facility = filters.CharFilter(method="filter_facility", label="Facility name contains")
    fuel = filters.CharFilter(method="filter_fuel", label="Fuel tested (from test runs) contains")
    safety_function = filters.CharFilter(method="filter_safety", label="prevention, detection or suppression")
    is_seed = filters.BooleanFilter()
    has_test_runs = filters.BooleanFilter(method="filter_has_runs")
    has_flow = filters.BooleanFilter(method="filter_has_flow", label="Flow speed recorded")
    oxygen_pct_min = filters.NumberFilter(method="filter_overlap_min", label="Tested oxygen reaches at least")
    oxygen_pct_max = filters.NumberFilter(method="filter_overlap_max", label="Tested oxygen goes down to at most")
    pressure_kpa_min = filters.NumberFilter(method="filter_overlap_min")
    pressure_kpa_max = filters.NumberFilter(method="filter_overlap_max")
    flow_speed_cm_s_min = filters.NumberFilter(method="filter_overlap_min")
    flow_speed_cm_s_max = filters.NumberFilter(method="filter_overlap_max")
    year_min = filters.NumberFilter(method="filter_year_min", label="Active in or after this year")
    year_max = filters.NumberFilter(method="filter_year_max", label="Active in or before this year")

    class Meta:
        model = models.Investigation
        fields: list[str] = []

    def filter_q(self, queryset, name, value):
        return search_investigations(queryset, value)

    def filter_facility(self, queryset, name, value):
        return queryset.filter(facilities__name__icontains=value).distinct()

    def filter_fuel(self, queryset, name, value):
        return queryset.filter(test_runs__fuel__icontains=value).distinct()

    def filter_safety(self, queryset, name, value):
        return queryset.filter(safety_pillars__contains=[value])

    def filter_has_runs(self, queryset, name, value):
        return queryset.filter(test_run_count__gt=0) if value else queryset.filter(test_run_count=0)

    def filter_has_flow(self, queryset, name, value):
        return queryset.filter(flow_speed_cm_s_max__isnull=not value)

    # A range filter keeps records whose tested range overlaps the requested one.
    def filter_overlap_min(self, queryset, name, value):
        return queryset.filter(**{f"{name.removesuffix('_min')}_max__gte": value})

    def filter_overlap_max(self, queryset, name, value):
        return queryset.filter(**{f"{name.removesuffix('_max')}_min__lte": value})

    def filter_year_min(self, queryset, name, value):
        return queryset.filter(Q(end_date__year__gte=value) | Q(end_date__isnull=True, start_date__year__gte=value))

    def filter_year_max(self, queryset, name, value):
        return queryset.filter(start_date__year__lte=value)


class TestRunFilter(filters.FilterSet):
    investigation = CharInFilter(field_name="investigation__psi_id", lookup_expr="in", label="PSI identifiers")
    fuel = filters.CharFilter(lookup_expr="icontains")
    fuel_form = CharInFilter(field_name="fuel_form", lookup_expr="in")
    diluent = filters.CharFilter(lookup_expr="icontains")
    gravity = filters.CharFilter(field_name="gravity_level", lookup_expr="iexact")
    outcome = filters.CharFilter(field_name="extinction_mode", lookup_expr="iexact")
    ignited = filters.BooleanFilter()
    flow_direction = filters.CharFilter(lookup_expr="iexact")
    oxygen_pct_min = filters.NumberFilter(field_name="oxygen_pct", lookup_expr="gte")
    oxygen_pct_max = filters.NumberFilter(field_name="oxygen_pct", lookup_expr="lte")
    pressure_kpa_min = filters.NumberFilter(field_name="pressure_kpa", lookup_expr="gte")
    pressure_kpa_max = filters.NumberFilter(field_name="pressure_kpa", lookup_expr="lte")
    flow_speed_cm_s_min = filters.NumberFilter(field_name="flow_speed_cm_s", lookup_expr="gte")
    flow_speed_cm_s_max = filters.NumberFilter(field_name="flow_speed_cm_s", lookup_expr="lte")
    has_flow = filters.BooleanFilter(field_name="flow_speed_cm_s", lookup_expr="isnull", exclude=True)

    class Meta:
        model = models.TestRun
        fields: list[str] = []
