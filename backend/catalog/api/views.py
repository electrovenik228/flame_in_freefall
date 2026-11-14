import csv
import io

from django.contrib.postgres.search import SearchQuery
from django.db import connection
from django.db.models import Count, IntegerField
from django.db.models.functions import Cast, Substr
from django.http import HttpResponse, JsonResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, inline_serializer
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog import models
from ingestion.models import IngestionRun

from . import serializers as s
from .filters import InvestigationFilter, TestRunFilter, search_investigations

EXPORT_LIMIT = 20000
EXPORT_VALUE_FIELDS = [
    "test_label", "date", "fuel", "fuel_form", "geometry", "oxygen_pct", "diluent", "pressure_kpa",
    "flow_speed_cm_s", "flow_direction", "gravity_level", "ignited", "extinction_mode",
]  # fmt: skip


def investigations_queryset():
    return (
        models.Investigation.objects.annotate(
            psi_number=Cast(Substr("psi_id", 5), IntegerField()),
            test_run_count=Count("test_runs", distinct=True),
        )
        .select_related("project")
        .prefetch_related("facilities")
        .order_by("psi_number")
    )


class InvestigationViewSet(viewsets.ReadOnlyModelViewSet):
    """Combustion Science investigations from NASA PSI."""

    lookup_field = "psi_id"
    lookup_value_regex = r"PSI-\d+"
    filterset_class = InvestigationFilter
    ordering_fields = ["psi_number", "acronym", "start_date", "end_date", "oxygen_pct_max", "test_run_count"]

    def get_queryset(self):
        queryset = investigations_queryset()
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("instruments", "publications")
        return queryset

    def get_serializer_class(self):
        return s.InvestigationDetailSerializer if self.action == "retrieve" else s.InvestigationListSerializer

    @extend_schema(responses=s.TestRunSerializer(many=True))
    @action(detail=True, url_path="test-runs", filterset_class=None, ordering_fields=[])
    def test_runs(self, request, psi_id=None):
        """Test runs of one investigation."""
        runs = self.get_object().test_runs.select_related("investigation", "source_file")
        page = self.paginate_queryset(runs)
        return self.get_paginated_response(s.TestRunSerializer(page, many=True).data)

    @extend_schema(responses=s.SourceFileSerializer(many=True))
    @action(detail=True, filterset_class=None, ordering_fields=[])
    def files(self, request, psi_id=None):
        """PSI file inventory of one investigation, with links."""
        files = self.get_object().files.select_related("investigation")
        page = self.paginate_queryset(files)
        return self.get_paginated_response(s.SourceFileSerializer(page, many=True).data)


class TestRunViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Test runs across investigations."""

    __test__ = False
    queryset = models.TestRun.objects.select_related("investigation", "source_file")
    serializer_class = s.TestRunSerializer
    filterset_class = TestRunFilter
    ordering_fields = ["oxygen_pct", "pressure_kpa", "flow_speed_cm_s", "date", "source_row"]


class TestRunExportView(APIView):
    """Same filters as the test-run list. Returns CSV or JSON with provenance columns."""

    __test__ = False
    filter_backends: list = []
    pagination_class = None

    @extend_schema(
        parameters=[OpenApiParameter("output", str, enum=["csv", "json"], description="File type, default csv")],
        responses={(200, "text/csv"): OpenApiTypes.STR, (200, "application/json"): OpenApiTypes.OBJECT},
    )
    def get(self, request):
        runs = TestRunFilter(request.GET, queryset=models.TestRun.objects.all()).qs.select_related(
            "investigation", "source_file"
        )[:EXPORT_LIMIT]
        rows = []
        for run in runs:
            values = {field: getattr(run, field) for field in EXPORT_VALUE_FIELDS}
            missing = [field for field, value in values.items() if value is None or value == ""]
            rows.append(
                {
                    "psi_id": run.investigation.psi_id,
                    "investigation": run.investigation.display_name,
                    **{field: ("" if value is None else value) for field, value in values.items()},
                    "missing_fields": ";".join(missing),
                    "source_file": run.source_file.name,
                    "source_row": run.source_row,
                    "retrieved_at": run.source_file.retrieved_at.isoformat() if run.source_file.retrieved_at else "",
                    "psi_url": run.investigation.psi_url,
                }
            )
        if request.GET.get("output") == "json":
            response = JsonResponse({"count": len(rows), "results": rows})
            response["Content-Disposition"] = 'attachment; filename="test-runs.json"'
            return response
        buffer = io.StringIO()
        columns = (
            list(rows[0]) if rows else ["psi_id", *EXPORT_VALUE_FIELDS, "missing_fields", "source_file", "source_row"]
        )
        writer = csv.DictWriter(buffer, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
        response = HttpResponse(buffer.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="test-runs.csv"'
        return response


class ProjectViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = models.Project.objects.all()
    serializer_class = s.ProjectSerializer
    filter_backends: list = []


class FacilityViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = models.Facility.objects.all()
    serializer_class = s.FacilitySerializer
    filter_backends: list = []


class InstrumentViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = models.Instrument.objects.all()
    serializer_class = s.InstrumentSerializer
    filter_backends: list = []


class PublicationViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    queryset = models.Publication.objects.select_related("investigation")
    serializer_class = s.PublicationSerializer
    filterset_fields = {"investigation__psi_id": ["exact"]}


class EnvironmentViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Reference crew environments used for ranking."""

    queryset = models.Environment.objects.all()
    serializer_class = s.EnvironmentSerializer
    filter_backends: list = []
    pagination_class = None


@extend_schema(
    parameters=[OpenApiParameter("q", str, required=True, description="Search text")],
    responses=inline_serializer(
        "SearchResults",
        {
            "investigations": s.RelatedInvestigationSerializer(many=True),
            "publications": s.PublicationSerializer(many=True),
            "facilities": s.FacilitySerializer(many=True),
            "fuels": serializers.ListField(child=serializers.DictField()),
        },
    ),
)
@api_view(["GET"])
def global_search(request):
    """Global search over investigations, fuels, hardware and publications."""
    text = request.GET.get("q", "").strip()
    if not text:
        return Response({"investigations": [], "publications": [], "facilities": [], "fuels": []})
    query = SearchQuery(text, config="english", search_type="websearch")
    investigations = search_investigations(investigations_queryset(), text)[:8]
    publications = models.Publication.objects.filter(search_text=query).select_related("investigation")[:8]
    facilities = models.Facility.objects.filter(name__icontains=text)[:5]
    fuels = (
        models.TestRun.objects.filter(fuel__icontains=text)
        .values("fuel")
        .annotate(test_runs=Count("id"), investigations=Count("investigation", distinct=True))
        .order_by("-test_runs")[:8]
    )
    return Response(
        {
            "investigations": s.RelatedInvestigationSerializer(investigations, many=True).data,
            "publications": s.PublicationSerializer(publications, many=True).data,
            "facilities": s.FacilitySerializer(facilities, many=True).data,
            "fuels": list(fuels),
        }
    )


@extend_schema(
    responses=inline_serializer("Health", {"status": serializers.CharField(), "database": serializers.CharField()})
)
@api_view(["GET"])
def health(request):
    """Health endpoint for the API and its database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return Response({"status": "ok", "database": "ok"})


@extend_schema(
    responses=inline_serializer(
        "Stats",
        {
            "investigations": serializers.IntegerField(),
            "seed_investigations": serializers.IntegerField(),
            "test_runs": serializers.IntegerField(),
            "investigations_with_test_runs": serializers.IntegerField(),
            "publications": serializers.IntegerField(),
            "facilities": serializers.IntegerField(),
            "safety_pillars": serializers.DictField(child=serializers.IntegerField()),
            "fuel_states": serializers.DictField(child=serializers.IntegerField()),
            "last_refresh": serializers.DateTimeField(allow_null=True),
            "source_retrieved_at": serializers.DateTimeField(allow_null=True),
        },
    )
)
@api_view(["GET"])
def meta_stats(request):
    """Counts and last refresh date for the Overview page."""
    investigations = models.Investigation.objects.all()
    last_run = IngestionRun.objects.filter(finished__isnull=False).first()
    newest = investigations.exclude(retrieved_at=None).order_by("-retrieved_at").first()
    return Response(
        {
            "investigations": investigations.count(),
            "seed_investigations": investigations.filter(is_seed=True).count(),
            "test_runs": models.TestRun.objects.count(),
            "investigations_with_test_runs": investigations.filter(test_runs__isnull=False).distinct().count(),
            "publications": models.Publication.objects.count(),
            "facilities": models.Facility.objects.filter(investigations__isnull=False).distinct().count(),
            "safety_pillars": {
                pillar: investigations.filter(safety_pillars__contains=[pillar]).count()
                for pillar in models.SafetyPillar.values
            },
            "fuel_states": {
                state: investigations.filter(fuel_state=state).count() for state in models.FuelState.values
            },
            "last_refresh": last_run.finished if last_run else None,
            "source_retrieved_at": newest.retrieved_at if newest else None,
        }
    )
