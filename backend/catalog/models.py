"""Source facts from PSI and the reference scenarios we define (section 5).

AI output lives in the `ai` app and is never edited in place. The AI-derived
columns on Investigation (fuel_state, safety_pillars, text-derived condition
ranges, judgment_scores) are a projection of the newest accepted Insight rows,
written only by `ai.services.projection`.
"""

from django.contrib.postgres.fields import ArrayField
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVector, SearchVectorField
from django.db import models
from django.db.models import Value


class FuelState(models.TextChoices):
    GAS = "gas", "Gas"
    LIQUID = "liquid", "Liquid"
    SOLID = "solid", "Solid"


class SafetyPillar(models.TextChoices):
    PREVENTION = "prevention", "Prevention"
    DETECTION = "detection", "Detection"
    SUPPRESSION = "suppression", "Suppression"


class DataDepth(models.TextChoices):
    PER_TEST = "per_test", "Per-test data"
    TELEMETRY = "telemetry", "Telemetry"
    SUMMARY = "summary", "Summary table"
    QUALITATIVE = "qualitative", "Qualitative"


class ConditionsSource(models.TextChoices):
    TEST_RUNS = "test_runs", "Computed from test runs"
    RECORD_TEXT = "record_text", "Extracted from the record text"
    NOT_AVAILABLE = "not_available", "Not available"


class Project(models.Model):
    """Groups related records: ACME, FLEX family, BASS family, Saffire, SAME."""

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Facility(models.Model):
    name = models.CharField(max_length=200, unique=True)
    type = models.CharField(max_length=80, blank=True)
    description = models.TextField(blank=True)
    url = models.URLField(max_length=500, blank=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "facilities"

    def __str__(self) -> str:
        return self.name


class Instrument(models.Model):
    name = models.CharField(max_length=200, unique=True)
    measurement_type = models.CharField(max_length=120, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class VocabularyTerm(models.Model):
    """Controlled vocabularies (fuel, fuel form, diluent, extinction mode), editable in the admin."""

    class Kind(models.TextChoices):
        FUEL = "fuel", "Fuel"
        FUEL_FORM = "fuel_form", "Fuel form"
        DILUENT = "diluent", "Diluent"
        EXTINCTION_MODE = "extinction_mode", "Extinction mode"

    kind = models.CharField(max_length=20, choices=Kind.choices)
    code = models.SlugField(max_length=60)
    label = models.CharField(max_length=120)

    class Meta:
        ordering = ["kind", "label"]
        constraints = [models.UniqueConstraint(fields=["kind", "code"], name="uniq_vocabulary_kind_code")]

    def __str__(self) -> str:
        return f"{self.kind}: {self.label}"


class Investigation(models.Model):
    """One per PSI record."""

    psi_id = models.CharField(max_length=20, unique=True)
    acronym = models.CharField(max_length=120, blank=True)
    title = models.CharField(max_length=500)
    doi = models.CharField(max_length=120, blank=True)
    project = models.ForeignKey(
        Project, null=True, blank=True, on_delete=models.SET_NULL, related_name="investigations"
    )
    research_area = models.CharField(max_length=120, blank=True)
    sub_research_area = models.CharField(max_length=200, blank=True)
    project_type = models.CharField(max_length=120, blank=True)
    flight_program = models.CharField(max_length=200, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    objectives = models.TextField(blank=True)
    approach = models.TextField(blank=True)
    hypothesis = models.TextField(blank=True)
    benefits = models.TextField(blank=True)
    hardware_text = models.TextField(blank=True, help_text="Hardware as written in the PSI record")
    hardware_links = models.JSONField(default=list, blank=True)
    contacts = models.JSONField(default=list, blank=True, help_text="Name, affiliation and role only")
    license_name = models.CharField(max_length=200, blank=True)
    license_url = models.URLField(max_length=500, blank=True)

    # Normalized attributes. Empty means unknown; a missing value is never guessed.
    fuel_state = models.CharField(max_length=10, choices=FuelState.choices, blank=True)
    safety_pillars = ArrayField(models.CharField(max_length=12, choices=SafetyPillar.choices), default=list, blank=True)
    data_depth = models.CharField(max_length=12, choices=DataDepth.choices, blank=True)

    # Condition ranges, one fixed unit per quantity (section 5.3).
    oxygen_pct_min = models.FloatField(null=True, blank=True)
    oxygen_pct_max = models.FloatField(null=True, blank=True)
    pressure_kpa_min = models.FloatField(null=True, blank=True)
    pressure_kpa_max = models.FloatField(null=True, blank=True)
    flow_speed_cm_s_min = models.FloatField(null=True, blank=True)
    flow_speed_cm_s_max = models.FloatField(null=True, blank=True)
    conditions_source = models.CharField(max_length=14, choices=ConditionsSource.choices, blank=True)

    judgment_scores = models.JSONField(default=dict, blank=True)
    search_text = SearchVectorField(null=True, editable=False)

    psi_url = models.URLField(max_length=500)
    psi_version = models.PositiveIntegerField(null=True, blank=True)
    total_file_size = models.BigIntegerField(null=True, blank=True)
    is_seed = models.BooleanField(default=False, help_text="One of the twelve demo investigations (section 4.6)")
    retrieved_at = models.DateTimeField(null=True, blank=True)

    facilities = models.ManyToManyField(Facility, blank=True, related_name="investigations")
    instruments = models.ManyToManyField(Instrument, blank=True, related_name="investigations")

    class Meta:
        ordering = ["psi_id"]
        indexes = [GinIndex(fields=["search_text"], name="investigation_search_gin")]

    def __str__(self) -> str:
        return f"{self.psi_id} {self.acronym or self.title[:40]}"

    @property
    def display_name(self) -> str:
        return self.acronym or self.title

    def refresh_search_text(self) -> None:
        """Rebuild the full-text column, including fuel, facility and instrument names (section 5.3)."""
        head = " ".join(filter(None, [self.psi_id, self.acronym, self.title]))
        fuels = self.test_runs.exclude(fuel="").order_by().values_list("fuel", flat=True).distinct()
        body = " ".join(
            filter(
                None,
                [
                    self.objectives,
                    self.approach,
                    self.hypothesis,
                    self.benefits,
                    self.hardware_text,
                    self.sub_research_area,
                    " ".join(self.facilities.values_list("name", flat=True)),
                    " ".join(self.instruments.values_list("name", flat=True)),
                    " ".join(fuels),
                ],
            )
        )
        vector = SearchVector(Value(head), weight="A", config="english") + SearchVector(
            Value(body), weight="B", config="english"
        )
        Investigation.objects.filter(pk=self.pk).update(search_text=vector)


class SourceFile(models.Model):
    """Inventory of PSI files. `status` records files that are listed but missing."""

    class Status(models.TextChoices):
        LISTED = "listed", "Listed, not downloaded"
        RETRIEVED = "retrieved", "Retrieved"
        MISSING = "missing", "Listed but missing"

    investigation = models.ForeignKey(Investigation, on_delete=models.CASCADE, related_name="files")
    path = models.CharField(max_length=600)
    name = models.CharField(max_length=300)
    category = models.CharField(max_length=80, blank=True)
    gravity_class = models.CharField(max_length=40, blank=True)
    size = models.BigIntegerField(null=True, blank=True)
    version = models.PositiveIntegerField(null=True, blank=True)
    checksum = models.CharField(max_length=64, blank=True, help_text="SHA-256 of the stored copy")
    retrieved_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.LISTED)

    class Meta:
        ordering = ["investigation", "category", "name"]
        constraints = [models.UniqueConstraint(fields=["investigation", "path"], name="uniq_sourcefile_path")]

    def __str__(self) -> str:
        return self.name


class SourceDocument(models.Model):
    """Stored source text. AI evidence quotes and citations are checked against this text."""

    class Kind(models.TextChoices):
        RECORD = "record", "PSI investigation record"
        EXPERIMENT_TABLE = "experiment_table", "Experiment table"
        TEST_RUN_STATS = "test_run_stats", "Test-run statistics computed from the database"

    investigation = models.ForeignKey(Investigation, on_delete=models.CASCADE, related_name="documents")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=300)
    text = models.TextField()
    source_file = models.ForeignKey(SourceFile, null=True, blank=True, on_delete=models.SET_NULL)
    url = models.URLField(max_length=500, blank=True)
    checksum = models.CharField(max_length=64)
    retrieved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["investigation", "kind", "title"]
        constraints = [
            models.UniqueConstraint(fields=["investigation", "kind", "title"], name="uniq_sourcedocument_title")
        ]

    def __str__(self) -> str:
        return f"{self.investigation.psi_id}: {self.title}"


class TestRun(models.Model):
    """One row of an experiment table. Normalized columns sit beside the untouched original row."""

    __test__ = False  # not a pytest class

    investigation = models.ForeignKey(Investigation, on_delete=models.CASCADE, related_name="test_runs")
    test_label = models.CharField(max_length=120, blank=True)
    date = models.DateField(null=True, blank=True)
    fuel = models.CharField(max_length=120, blank=True)
    fuel_form = models.CharField(max_length=60, blank=True)
    geometry = models.CharField(max_length=300, blank=True)
    oxygen_pct = models.FloatField(null=True, blank=True)
    diluent = models.CharField(max_length=60, blank=True)
    pressure_kpa = models.FloatField(null=True, blank=True)
    flow_speed_cm_s = models.FloatField(null=True, blank=True)
    flow_direction = models.CharField(max_length=40, blank=True)
    gravity_level = models.CharField(max_length=40, blank=True)
    ignited = models.BooleanField(null=True, blank=True)
    extinction_mode = models.CharField(max_length=60, blank=True)
    outcomes = models.JSONField(default=dict, blank=True)
    raw_row = models.JSONField(default=dict)
    source_file = models.ForeignKey(SourceFile, on_delete=models.CASCADE, related_name="test_runs")
    source_row = models.PositiveIntegerField(help_text="1-based row number in the source file, header is row 1")

    class Meta:
        ordering = ["investigation", "source_file", "source_row"]
        constraints = [models.UniqueConstraint(fields=["source_file", "source_row"], name="uniq_testrun_source_row")]
        indexes = [models.Index(fields=["oxygen_pct"]), models.Index(fields=["pressure_kpa"])]

    def __str__(self) -> str:
        return f"{self.investigation.psi_id} {self.test_label}"


class Publication(models.Model):
    investigation = models.ForeignKey(Investigation, on_delete=models.CASCADE, related_name="publications")
    title = models.CharField(max_length=800)
    authors = models.TextField(blank=True)
    year = models.PositiveIntegerField(null=True, blank=True)
    doi = models.CharField(max_length=200, blank=True)
    url = models.URLField(max_length=600, blank=True)
    search_text = SearchVectorField(null=True, editable=False)

    class Meta:
        ordering = ["investigation", "title"]
        indexes = [GinIndex(fields=["search_text"], name="publication_search_gin")]

    def __str__(self) -> str:
        return self.title[:80]


class Environment(models.Model):
    """Reference crew environments used for ranking (section 5.2). Open-ended bounds are null."""

    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=120)
    oxygen_pct_min = models.FloatField(null=True, blank=True)
    oxygen_pct_max = models.FloatField(null=True, blank=True)
    pressure_kpa_min = models.FloatField(null=True, blank=True)
    pressure_kpa_max = models.FloatField(null=True, blank=True)
    gravity = models.CharField(max_length=40)
    gravity_g = models.FloatField(null=True, blank=True)
    flow_cm_s_min = models.FloatField(null=True, blank=True)
    flow_cm_s_max = models.FloatField(null=True, blank=True)
    ventilation_notes = models.TextField(blank=True)
    source = models.CharField(max_length=300)
    source_url = models.URLField(max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["order", "name"]

    def __str__(self) -> str:
        return self.name
