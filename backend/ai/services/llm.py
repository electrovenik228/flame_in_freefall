"""Thin layer over the Anthropic SDK: one client, usage logging, stop-reason handling."""

import anthropic
from django.conf import settings

from ai.models import AICall

BACKGROUND_MAX_TOKENS = 16000


class Refused(Exception):
    """The model declined. The result is never stored or shown (section 7.3)."""


class Truncated(Exception):
    """The response hit max_tokens and cannot be trusted as complete."""


_client: anthropic.Anthropic | None = None
_async_client: anthropic.AsyncAnthropic | None = None


def get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY or None, max_retries=4)
    return _client


def get_async_client() -> anthropic.AsyncAnthropic:
    global _async_client
    if _async_client is None:
        _async_client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY or None, max_retries=2)
    return _async_client


def usage_fields(response) -> dict:
    usage = response.usage
    return {
        "input_tokens": usage.input_tokens or 0,
        "output_tokens": usage.output_tokens or 0,
        "cache_read_tokens": getattr(usage, "cache_read_input_tokens", 0) or 0,
        "cache_write_tokens": getattr(usage, "cache_creation_input_tokens", 0) or 0,
    }


def log_call(job: str, response, public: bool = False) -> None:
    AICall.objects.create(
        job=job, model=response.model, public=public, stop_reason=response.stop_reason or "", **usage_fields(response)
    )


def check_stop(response) -> None:
    if response.stop_reason == "refusal":
        details = getattr(response, "stop_details", None)
        raise Refused(getattr(details, "category", None) or "refusal")
    if response.stop_reason == "max_tokens":
        raise Truncated("response reached max_tokens")


def background_effort() -> dict:
    """Effort for stored jobs. Opus 5.5 defaults to medium; reading records accurately is worth high."""
    return {"effort": settings.CLAUDE_BACKGROUND_EFFORT}
