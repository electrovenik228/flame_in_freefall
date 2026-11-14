from django.contrib import admin

from .models import AICall, Insight, RelevanceScore, ReviewStatus


@admin.action(description="Hide selected items from the site")
def hide(modeladmin, request, queryset):
    queryset.update(review_status=ReviewStatus.HIDDEN)


@admin.action(description="Mark selected items as approved")
def approve(modeladmin, request, queryset):
    queryset.update(review_status=ReviewStatus.APPROVED)


@admin.register(Insight)
class InsightAdmin(admin.ModelAdmin):
    """Review queue: AI rows are read-only apart from their review status."""

    list_display = ["type", "investigation", "model", "prompt_version", "review_status", "is_current", "generated_at"]
    list_filter = ["type", "review_status", "is_current", "prompt_version"]
    readonly_fields = [
        "type",
        "investigation",
        "target",
        "content",
        "citations",
        "model",
        "prompt_version",
        "input_hash",
        "checks",
        "is_current",
        "generated_at",
    ]
    actions = [hide, approve]


@admin.register(RelevanceScore)
class RelevanceScoreAdmin(admin.ModelAdmin):
    list_display = ["investigation", "environment", "total", "partial_data"]
    list_filter = ["environment", "partial_data"]


@admin.register(AICall)
class AICallAdmin(admin.ModelAdmin):
    list_display = ["created_at", "job", "model", "public", "input_tokens", "output_tokens", "stop_reason"]
    list_filter = ["job", "model", "public"]
