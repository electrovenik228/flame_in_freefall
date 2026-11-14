import anthropic
from django.core.management.base import BaseCommand, CommandError

from ai.models import AICall
from ai.services import generate
from catalog.models import Investigation

JOBS = {"extraction": generate.generate_extraction, "summary": generate.generate_summary}


class Command(BaseCommand):
    help = "Generate and store AI output (extraction, summaries) for investigations. Unchanged input is skipped."

    def add_arguments(self, parser):
        parser.add_argument("--jobs", default="extraction,summary", help="Comma-separated: extraction, summary")
        parser.add_argument("--psi", action="append", help="PSI identifier; repeat for several. Default: all records")
        parser.add_argument("--seed-only", action="store_true", help="Only the twelve seed investigations")
        parser.add_argument("--force", action="store_true", help="Regenerate even when the input is unchanged")
        parser.add_argument("--report", action="store_true", help="Only print the step 6 check, generate nothing")
        parser.add_argument("--reproject", action="store_true", help="Re-apply stored extractions, no API call")

    def handle(self, *args, jobs, psi, seed_only, force, report, reproject, **options):
        if reproject:
            done = sum(generate.reproject_extraction(item) for item in Investigation.objects.all())
            self.stdout.write(f"Re-applied {done} stored extractions")
        elif not report:
            names = [name.strip() for name in jobs.split(",") if name.strip()]
            unknown = set(names) - set(JOBS)
            if unknown:
                raise CommandError(f"Unknown jobs: {', '.join(sorted(unknown))}")
            investigations = Investigation.objects.all()
            if psi:
                investigations = investigations.filter(psi_id__in=psi)
            if seed_only:
                investigations = investigations.filter(is_seed=True)
            before = AICall.objects.count()
            for investigation in investigations:
                for name in names:
                    try:
                        status = JOBS[name](investigation, force=force)
                    except anthropic.AuthenticationError as exc:
                        raise CommandError(
                            "The Claude API rejected the key in ANTHROPIC_API_KEY. Nothing was generated."
                        ) from exc
                    except anthropic.BadRequestError as exc:
                        if "credit balance" in str(exc):
                            raise CommandError(
                                "The Claude API account has no credit left. Stopped; finished records are stored."
                            ) from exc
                        status = f"failed: BadRequestError: {exc}"
                    except anthropic.APIError as exc:
                        status = f"failed: {type(exc).__name__}: {exc}"
                    self.stdout.write(f"{investigation.psi_id:8} {name:11} {status}")
            calls = AICall.objects.order_by("-id")[: AICall.objects.count() - before]
            tokens_in = sum(call.input_tokens + call.cache_read_tokens + call.cache_write_tokens for call in calls)
            tokens_out = sum(call.output_tokens for call in calls)
            self.stdout.write(f"Claude requests: {len(calls)}, input tokens: {tokens_in}, output tokens: {tokens_out}")
        result = generate.step6_report()
        verdict = (
            "PASSED"
            if result["passed"]
            else ("PASSED for the seed set, not for all records" if result["passed_for_seed_set"] else "NOT PASSED")
        )
        self.stdout.write(f"Step 6 check: {verdict} {result}")
