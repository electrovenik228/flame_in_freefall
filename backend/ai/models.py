"""AI output. Rows are never edited in place: a new prompt version writes a new row (section 5.3)."""

from django.db import models

from catalog.models import Environment, Investigation


class ReviewStatus(models.TextChoices):
    UNREVIEWED = "unreviewed", "Unreviewed"
    APPROVED = "approved", "Approved"
    HIDDEN = "hidden", "Hidden"
    NOT_GENERATED = "not_generated", "Not generated"


class Insight(models.Model):
    class Type(models.TextChoices):
        EXTRACTION = "extraction", "Attribute extraction"
        SUMMARY = "summary", "Investigation summary"
        JUDGMENT = "judgment", "Relevance judgment"
        COMPARISON = "comparison", "Comparison"
        GAP = "gap", "Insight or gap"
        EARTH_APPLICATION = "earth_application", "Earth application"

    type = models.CharField(max_length=20, choices=Type.choices)
    investigation = models.ForeignKey(
        Investigation, null=True, blank=True, on_delete=models.CASCADE, related_name="insights"
    )
    target = models.CharField(max_length=200, blank=True, help_text="Target key when it is not one investigation")
    content = models.JSONField(default=dict)
    citations = models.JSONField(default=list, blank=True)
    model = models.CharField(max_length=80)
    prompt_version = models.CharField(max_length=40)
    input_hash = models.CharField(max_length=64)
    review_status = models.CharField(max_length=14, choices=ReviewStatus.choices, default=ReviewStatus.UNREVIEWED)
    checks = models.JSONField(default=dict, blank=True, help_text="Results of the automated checks")
    is_current = models.BooleanField(default=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]
        indexes = [models.Index(fields=["type", "investigation", "is_current"])]

    def __str__(self) -> str:
        return f"{self.type} {self.investigation or self.target} ({self.prompt_version})"


class RelevanceScore(models.Model):
    """One per investigation and environment pair, computed in code from the rubric (section 7.4)."""

    investigation = models.ForeignKey(Investigation, on_delete=models.CASCADE, related_name="relevance_scores")
    environment = models.ForeignKey(Environment, on_delete=models.CASCADE, related_name="relevance_scores")
    total = models.FloatField(null=True)
    sub_scores = models.JSONField(default=dict)
    rationale = models.TextField(blank=True)
    citations = models.JSONField(default=list, blank=True)
    partial_data = models.BooleanField(default=False)
    computed_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["environment", "-total"]
        constraints = [models.UniqueConstraint(fields=["investigation", "environment"], name="uniq_relevance_pair")]


class AICall(models.Model):
    """Token usage per Claude request, so cost can be reported and the daily limit enforced (section 7.6)."""

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    job = models.CharField(max_length=40)
    model = models.CharField(max_length=80)
    public = models.BooleanField(default=False, help_text="Counts toward AI_DAILY_TOKEN_LIMIT")
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    cache_read_tokens = models.PositiveIntegerField(default=0)
    cache_write_tokens = models.PositiveIntegerField(default=0)
    stop_reason = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-created_at"]
