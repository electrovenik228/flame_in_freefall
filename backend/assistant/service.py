"""One assistant turn: a streamed, cited answer built from read-only tool results (sections 7.3 to 7.6)."""

import datetime
import hashlib
import re

import anthropic
from asgiref.sync import sync_to_async
from django.conf import settings
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from ai import prompts
from ai.models import AICall
from ai.services import llm, verify
from assistant import tools
from assistant.models import Conversation, Message

MAX_STEPS = 6
MAX_QUESTION_CHARS = 2000
HISTORY_MESSAGES = 10

REFUSED_TEXT = (
    "I can't help with that request. I can answer questions about microgravity combustion investigations "
    "and fire safety."
)
UNAVAILABLE_TEXT = (
    "The assistant cannot answer right now. Stored summaries, rankings and charts on the site keep working. "
    "Please try again later."
)
DAILY_LIMIT_TEXT = (
    "The assistant has reached its daily limit and will be back tomorrow. Stored summaries, rankings and "
    "charts keep working."
)
SESSION_LIMIT_TEXT = "This session has reached its message limit. Stored summaries, rankings and charts keep working."
TOOL_STATUS = {
    "search_investigations": "Searching the catalogue…",
    "get_investigation": "Reading the PSI record…",
    "get_ranking": "Computing the ranking…",
}


def tokens_used_today() -> int:
    """Tokens of the public AI endpoints since midnight UTC (section 7.6)."""
    start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    totals = AICall.objects.filter(public=True, created_at__gte=start).aggregate(
        a=Sum("input_tokens"), b=Sum("output_tokens"), c=Sum("cache_read_tokens"), d=Sum("cache_write_tokens")
    )
    return sum(value or 0 for value in totals.values())


def limit_reason(conversation: Conversation, ip: str) -> str | None:
    """Global daily token limit, then the caps per session and per IP address per day."""
    if tokens_used_today() >= settings.AI_DAILY_TOKEN_LIMIT:
        return DAILY_LIMIT_TEXT
    asked = Message.objects.filter(conversation__session_key=conversation.session_key, role=Message.Role.USER).count()
    if asked >= settings.ASSISTANT_SESSION_MESSAGE_LIMIT:
        return SESSION_LIMIT_TEXT
    # The address is never stored: only a salted hash is used as a counter key for one day.
    digest = hashlib.sha256(f"{settings.SECRET_KEY}:{ip}".encode()).hexdigest()[:32]
    key = f"assistant-ip:{digest}:{datetime.date.today().isoformat()}"
    cache.add(key, 0, timeout=86400)
    if cache.incr(key) > settings.ASSISTANT_IP_DAILY_MESSAGE_LIMIT:
        return SESSION_LIMIT_TEXT
    return None


def history_messages(conversation: Conversation) -> list[dict]:
    recent = list(conversation.messages.order_by("-created_at", "-id")[:HISTORY_MESSAGES])[::-1]
    while recent and recent[0].role != Message.Role.USER:
        recent.pop(0)
    return [{"role": message.role, "content": message.content} for message in recent if message.content]


def to_citation(raw, number: int) -> dict:
    """Citation of a search result. `source` is the PSI link or a page of the site."""
    source = getattr(raw, "source", "") or ""
    title = getattr(raw, "title", "") or ""
    match = re.search(r"PSI-\d+", f"{source} {title}")
    return {
        "n": number,
        "psi_id": match.group() if match else "",
        "document_title": title,
        "document_kind": "search_result",
        "psi_url": source,
        "cited_text": getattr(raw, "cited_text", "") or "",
    }


def verify_answer(text: str, citations: list[dict], allowed_texts: list[str]) -> dict:
    """Checked when the stream ends (section 7.5): citations present, numbers found in the tool results."""
    unmatched = sorted(set(verify.unmatched_numbers(text, allowed_texts)))
    return {
        "has_citation": bool(citations),
        "unmatched_numbers": unmatched,
        "verified": bool(citations) and not unmatched,
    }


async def run_turn(conversation: Conversation, question: str, ip: str):
    """Async generator of (event name, data) pairs for one user message."""
    # The status line goes out before any slow work, so it appears within a second.
    yield "status", {"text": "Reading your question…"}
    reason = await sync_to_async(limit_reason)(conversation, ip)
    if reason:
        yield "notice", {"text": reason, "kind": "limit"}
        return
    history = await sync_to_async(history_messages)(conversation)
    await Message.objects.acreate(conversation=conversation, role=Message.Role.USER, content=question)
    messages: list[dict] = [*history, {"role": "user", "content": question}]
    allowed_texts = [m["content"] for m in messages if m["role"] == "user"]
    client = llm.get_async_client()
    segments: list[dict] = []
    citations: list[dict] = []
    tool_calls: list[dict] = []
    usage = {"input_tokens": 0, "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0}
    model = settings.CLAUDE_MODEL_FAST

    try:
        for _ in range(MAX_STEPS):
            segments, citations = [], []  # text before a tool call is a progress note, not the answer
            async with client.messages.stream(
                model=settings.CLAUDE_MODEL_FAST,
                max_tokens=settings.ASSISTANT_MAX_OUTPUT_TOKENS,
                system=[{"type": "text", "text": prompts.ASSISTANT_SYSTEM, "cache_control": {"type": "ephemeral"}}],
                tools=tools.TOOLS,
                messages=messages,
                # Sonnet 5.5 does not accept thinking fully disabled; this is its thinking-off setting.
                thinking={"type": "between_tools"},
                output_config={"effort": "low"},
            ) as stream:
                async for event in stream:
                    if event.type == "content_block_start":
                        if event.content_block.type == "text":
                            segments.append({"text": "", "citations": []})
                            yield "block", {"index": len(segments) - 1}
                        elif event.content_block.type == "tool_use":
                            yield "status", {"text": TOOL_STATUS.get(event.content_block.name, "Looking it up…")}
                    elif event.type == "content_block_delta" and segments:
                        if event.delta.type == "text_delta":
                            segments[-1]["text"] += event.delta.text
                            yield "delta", {"index": len(segments) - 1, "text": event.delta.text}
                        elif event.delta.type == "citations_delta":
                            citation = to_citation(event.delta.citation, len(citations) + 1)
                            same = next(
                                (
                                    c
                                    for c in citations
                                    if (c["psi_url"], c["cited_text"]) == (citation["psi_url"], citation["cited_text"])
                                ),
                                None,
                            )
                            if same is None:
                                citations.append(citation)
                            number = (same or citation)["n"]
                            if number not in segments[-1]["citations"]:
                                segments[-1]["citations"].append(number)
                                yield "citation", {"index": len(segments) - 1, "citation": same or citation}
                message = await stream.get_final_message()
            await sync_to_async(llm.log_call)("assistant", message, True)
            model = message.model
            for key, value in llm.usage_fields(message).items():
                usage[key] += value

            if message.stop_reason == "refusal":
                # Never stored or shown; the visitor sees a neutral message.
                yield "reset", {}
                yield "notice", {"text": REFUSED_TEXT, "kind": "refusal"}
                return
            if message.stop_reason != "tool_use":
                break
            results = []
            for item in message.content:
                if item.type != "tool_use":
                    continue
                content, is_error, texts = await sync_to_async(tools.execute)(item.name, item.input)
                allowed_texts += texts
                tool_calls.append({"name": item.name, "input": item.input, "error": is_error})
                results.append(
                    {"type": "tool_result", "tool_use_id": item.id, "content": content, "is_error": is_error}
                )
            messages += [{"role": "assistant", "content": message.content}, {"role": "user", "content": results}]
            yield "reset", {}
        else:
            yield "reset", {}
            yield "notice", {"text": UNAVAILABLE_TEXT, "kind": "unavailable"}
            return
    except anthropic.APIError:
        yield "reset", {}
        yield "notice", {"text": UNAVAILABLE_TEXT, "kind": "unavailable"}
        return

    text = "".join(segment["text"] for segment in segments)
    verification = verify_answer(text, citations, allowed_texts)
    if not tool_calls:
        verification["verified"] = None  # a redirect or a clarifying reply states no catalogue facts
    saved = await Message.objects.acreate(
        conversation=conversation,
        role=Message.Role.ASSISTANT,
        content=text,
        citations=citations,
        tool_calls=tool_calls,
        token_usage=usage,
        verification={**verification, "segments": segments},
        model=model,
    )
    yield (
        "done",
        {
            "message_id": saved.id,
            "model": model,
            "generated_at": saved.created_at.isoformat(),
            "verification": verification,
            "tools": [call["name"] for call in tool_calls],
        },
    )
