"""Read access to stored AI output. Hidden and not-generated rows are never shown."""

from ai.models import Insight, ReviewStatus

VISIBLE = [ReviewStatus.UNREVIEWED, ReviewStatus.APPROVED]


def current_insight(investigation, insight_type: str) -> Insight | None:
    return (
        Insight.objects.filter(
            investigation=investigation, type=insight_type, is_current=True, review_status__in=VISIBLE
        )
        .order_by("-generated_at")
        .first()
    )


def insight_payload(insight: Insight | None) -> dict | None:
    """Every AI-bearing response carries citations, model, generated_at and review_status (section 9)."""
    if insight is None:
        return None
    return {
        "content": insight.content,
        "citations": insight.citations,
        "model": insight.model,
        "generated_at": insight.generated_at,
        "review_status": insight.review_status,
        "prompt_version": insight.prompt_version,
        "checks": insight.checks,
    }
