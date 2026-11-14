"""Store the rubric scores of every investigation and reference environment pair (section 5.1)."""

from ai.models import RelevanceScore
from catalog.models import Environment, Investigation
from catalog.services.ranking import Target, load_context, rank


def refresh_scores() -> int:
    by_psi = {investigation.psi_id: investigation for investigation in Investigation.objects.all()}
    stored = 0
    context = load_context()
    for environment in Environment.objects.all():
        for row in rank(Target.from_environment(environment), context=context):
            RelevanceScore.objects.update_or_create(
                investigation=by_psi[row["psi_id"]],
                environment=environment,
                defaults={
                    "total": row["total"],
                    "sub_scores": row["sub_scores"],
                    "rationale": row["sub_scores"]["atmosphere"]["explanation"],
                    "citations": [s["source"] for s in row["sub_scores"].values() if s["source"]],
                    "partial_data": row["partial_data"],
                },
            )
            stored += 1
    return stored
