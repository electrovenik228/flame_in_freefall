from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from ai.models import Insight
from ai.services.current import current_insight, insight_payload
from catalog import models
from catalog.services.conditions import variable_summary

RANGE_FIELDS = [
    "oxygen_pct_min",
    "oxygen_pct_max",
    "pressure_kpa_min",
    "pressure_kpa_max",
    "flow_speed_cm_s_min",
    "flow_speed_cm_s_max",
]


class ProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Project
        fields = ["id", "name", "description"]


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Facility
        fields = ["id", "name", "type", "description", "url"]


class InstrumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Instrument
        fields = ["id", "name", "measurement_type"]


class PublicationSerializer(serializers.ModelSerializer):
    psi_id = serializers.CharField(source="investigation.psi_id", read_only=True)

    class Meta:
        model = models.Publication
        fields = ["id", "psi_id", "title", "authors", "year", "doi", "url"]


class SourceFileSerializer(serializers.ModelSerializer):
    psi_url = serializers.CharField(source="investigation.psi_url", read_only=True)

    class Meta:
        model = models.SourceFile
        fields = [
            "id",
            "name",
            "path",
            "category",
            "gravity_class",
            "size",
            "version",
            "status",
            "retrieved_at",
            "psi_url",
        ]


class TestRunSerializer(serializers.ModelSerializer):
    psi_id = serializers.CharField(source="investigation.psi_id", read_only=True)
    investigation_name = serializers.CharField(source="investigation.display_name", read_only=True)
    source_file = serializers.CharField(source="source_file.name", read_only=True)
    psi_url = serializers.CharField(source="investigation.psi_url", read_only=True)

    class Meta:
        model = models.TestRun
        fields = [
            "id", "psi_id", "investigation_name", "test_label", "date", "fuel", "fuel_form", "geometry",
            "oxygen_pct", "diluent", "pressure_kpa", "flow_speed_cm_s", "flow_direction", "gravity_level",
            "ignited", "extinction_mode", "outcomes", "raw_row", "source_file", "source_row", "psi_url",
        ]  # fmt: skip


class InvestigationListSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)
    project = serializers.CharField(source="project.name", read_only=True, default=None, allow_null=True)
    facilities = serializers.SlugRelatedField(slug_field="name", many=True, read_only=True)
    test_run_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = models.Investigation
        fields = [
            "psi_id", "acronym", "title", "display_name", "doi", "project", "research_area", "sub_research_area",
            "project_type", "start_date", "end_date", "objectives", "fuel_state", "safety_pillars", "data_depth",
            *RANGE_FIELDS, "conditions_source", "test_run_count", "facilities", "is_seed", "psi_url",
        ]  # fmt: skip


class RelatedInvestigationSerializer(serializers.ModelSerializer):
    display_name = serializers.CharField(read_only=True)

    class Meta:
        model = models.Investigation
        fields = ["psi_id", "display_name", "title"]


class InvestigationDetailSerializer(InvestigationListSerializer):
    facilities = FacilitySerializer(many=True, read_only=True)
    instruments = InstrumentSerializer(many=True, read_only=True)
    publications = PublicationSerializer(many=True, read_only=True)
    variables = serializers.SerializerMethodField()
    summary = serializers.SerializerMethodField()
    extraction = serializers.SerializerMethodField()
    related = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()

    class Meta(InvestigationListSerializer.Meta):
        fields = [
            *InvestigationListSerializer.Meta.fields, "approach", "hypothesis", "benefits", "flight_program",
            "hardware_text", "hardware_links", "contacts", "license_name", "license_url", "psi_version",
            "total_file_size", "retrieved_at", "judgment_scores", "instruments", "publications", "variables",
            "summary", "extraction", "related", "file_count",
        ]  # fmt: skip

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_variables(self, obj) -> dict:
        return variable_summary(obj)

    @extend_schema_field({"type": "object", "nullable": True})
    def get_summary(self, obj):
        return insight_payload(current_insight(obj, Insight.Type.SUMMARY))

    @extend_schema_field({"type": "object", "nullable": True})
    def get_extraction(self, obj):
        return insight_payload(current_insight(obj, Insight.Type.EXTRACTION))

    @extend_schema_field(RelatedInvestigationSerializer(many=True))
    def get_related(self, obj):
        if obj.project_id is None:
            return []
        siblings = models.Investigation.objects.filter(project_id=obj.project_id).exclude(pk=obj.pk)
        return RelatedInvestigationSerializer(siblings, many=True).data

    def get_file_count(self, obj) -> int:
        return obj.files.count()


class EnvironmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Environment
        fields = [
            "id", "slug", "name", "oxygen_pct_min", "oxygen_pct_max", "pressure_kpa_min", "pressure_kpa_max",
            "gravity", "gravity_g", "flow_cm_s_min", "flow_cm_s_max", "ventilation_notes", "source", "source_url",
        ]  # fmt: skip
