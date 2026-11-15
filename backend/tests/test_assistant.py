"""Step 8 logic against a stand-in for the Claude API. No network call is made."""

import json
from types import SimpleNamespace

import anthropic
import pytest
from asgiref.sync import async_to_sync

from ai.models import AICall
from ai.services import llm
from assistant import tools
from assistant.models import Conversation, Message
from catalog.reference import load_environments
from ingestion.loader import load_fixture
from tests.conftest import FIXTURE

BASE = "/api/v1/assistant"


def text_start():
    return SimpleNamespace(type="content_block_start", content_block=SimpleNamespace(type="text"))


def tool_start(name):
    return SimpleNamespace(type="content_block_start", content_block=SimpleNamespace(type="tool_use", name=name))


def delta(text):
    return SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="text_delta", text=text))


def cite(source, title, cited_text):
    citation = SimpleNamespace(type="search_result_location", source=source, title=title, cited_text=cited_text)
    return SimpleNamespace(type="content_block_delta", delta=SimpleNamespace(type="citations_delta", citation=citation))


def final(stop_reason="end_turn", content=None):
    return SimpleNamespace(
        model="fake-fast",
        stop_reason=stop_reason,
        stop_details=None,
        usage=SimpleNamespace(input_tokens=50, output_tokens=10),
        content=content or [],
    )


def tool_use(name, params, call_id="t1"):
    return SimpleNamespace(type="tool_use", id=call_id, name=name, input=params)


class FakeStream:
    def __init__(self, events, message):
        self.events, self.message = events, message

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def __aiter__(self):
        for event in self.events:
            yield event

    async def get_final_message(self):
        return self.message


class FakeAsyncClient:
    def __init__(self, turns):
        self.turns, self.calls = list(turns), []
        self.messages = SimpleNamespace(stream=self._stream)

    def _stream(self, **kwargs):
        self.calls.append(kwargs)
        turn = self.turns.pop(0)
        if isinstance(turn, Exception):
            raise turn
        return turn


@pytest.fixture
def site(transactional_db, monkeypatch, client):
    """Seeded catalogue, a stand-in Claude client, and a browser session with one conversation."""
    load_fixture(FIXTURE)
    load_environments()

    def install(*turns):
        fake = FakeAsyncClient(turns)
        monkeypatch.setattr(llm, "get_async_client", lambda: fake)
        return fake

    conversation_id = client.post(f"{BASE}/conversations/", {}, content_type="application/json").json()["id"]

    def ask(text):
        response = client.post(
            f"{BASE}/conversations/{conversation_id}/messages/", {"content": text}, content_type="application/json"
        )
        assert response["Content-Type"] == "text/event-stream"

        async def collect():
            return b"".join([chunk async for chunk in response.streaming_content])

        raw = async_to_sync(collect)().decode()
        events = []
        for chunk in raw.strip().split("\n\n"):
            name, data = chunk.split("\n", 1)
            events.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
        return events

    return SimpleNamespace(install=install, ask=ask, conversation_id=conversation_id, client=client)


PSI_69 = "https://psi.nasa.gov/physci/repo/data/investigations/PSI-69"


def answered_turns(answer="FLEX burned droplets of heptane and methanol.", cited="Varied between tests"):
    return [
        FakeStream(
            [tool_start("get_investigation")], final("tool_use", [tool_use("get_investigation", {"psi_id": "PSI-69"})])
        ),
        FakeStream(
            [
                text_start(),
                delta(answer),
                cite(PSI_69, "PSI-69 FLEX: catalogue entry", cited),
                text_start(),
                delta(" It is not a safety rating."),
            ],
            final(),
        ),
    ]


@pytest.mark.django_db
def test_tools_return_citable_blocks(seeded):
    load_environments()
    blocks, is_error, texts = tools.execute("search_investigations", {"query": "smoke aerosol", "limit": 3})
    assert not is_error and 1 <= len(blocks) <= 3
    assert all(b["type"] == "search_result" and b["citations"] == {"enabled": True} for b in blocks)
    assert blocks[0]["source"].startswith("https://psi.nasa.gov/") and texts[0] == blocks[0]["content"][0]["text"]
    blocks, _, texts = tools.execute("get_investigation", {"psi_id": "psi-69"})
    assert [b["title"] for b in blocks][:2] == ["PSI-69 FLEX: catalogue entry", "PSI-69 investigation record"]
    assert "Test runs in the catalogue: 274" in texts[0]
    assert blocks[2]["title"].endswith("test-run statistics computed from the database") and "274" in texts[2]
    blocks, _, texts = tools.execute("get_ranking", {"environment": "lunar-habitat", "limit": 3})
    assert len(blocks) == 4 and "not a safety rating" in texts[0] and texts[1].startswith("Rank 1 of 23")
    message, is_error, _ = tools.execute("get_investigation", {"psi_id": "PSI-9999"})
    assert is_error and "not in the catalogue" in message
    assert tools.execute("drop_tables", {})[1] is True  # there is no such tool
    assert tools.execute("search_investigations", {"query": "zzzzqqq"})[1] is True


def test_a_turn_streams_a_cited_answer_and_checks_its_numbers(site):
    fake = site.install(*answered_turns())
    events = site.ask("What did FLEX burn?")
    names = [name for name, _ in events]
    assert names[0] == "status"  # the status line goes out before any Claude request
    assert names == ["status", "status", "reset", "block", "delta", "citation", "block", "delta", "done"]
    assert events[1][1]["text"] == "Reading the PSI record…"
    citation = events[5][1]["citation"]
    assert citation["n"] == 1 and citation["psi_id"] == "PSI-69" and citation["psi_url"] == PSI_69
    done = events[-1][1]
    assert done["verification"] == {"has_citation": True, "unmatched_numbers": [], "verified": True}
    assert done["model"] == "fake-fast" and done["tools"] == ["get_investigation"]

    first, second = fake.calls
    assert first["model"] == "claude-sonnet-5-5" and first["thinking"] == {"type": "between_tools"}
    assert first["output_config"] == {"effort": "low"} and first["max_tokens"] == 2000
    assert [tool["name"] for tool in first["tools"]] == ["search_investigations", "get_investigation", "get_ranking"]
    result = second["messages"][-1]["content"][0]
    assert (
        result["type"] == "tool_result" and result["content"][0]["type"] == "search_result" and not result["is_error"]
    )

    saved = Message.objects.get(role="assistant")
    assert saved.content.startswith("FLEX burned") and saved.citations[0]["psi_id"] == "PSI-69"
    assert saved.verification["segments"][0]["citations"] == [1]
    assert AICall.objects.filter(job="assistant", public=True).count() == 2  # counted toward the daily limit

    history = site.client.get(f"{BASE}/conversations/{site.conversation_id}/").json()["messages"]
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert history[1]["segments"][0]["citations"] == [1] and history[1]["verification"]["verified"] is True
    assert history[1]["review_status"] == "unreviewed" and history[1]["model"] == "fake-fast"


def test_a_number_that_is_not_in_the_tool_results_is_flagged(site):
    site.install(*answered_turns(answer="FLEX ran 9999 tests at 12 to 34 % oxygen."))
    done = site.ask("How many tests did FLEX run?")[-1][1]
    assert done["verification"]["verified"] is False
    assert done["verification"]["unmatched_numbers"] == ["9999"]  # 12 and 34 are in the tool result; 9999 is not


def test_an_answer_without_citations_is_not_marked_verified(site):
    turns = answered_turns()
    turns[1] = FakeStream([text_start(), delta("FLEX burned droplets.")], final())
    site.install(*turns)
    assert site.ask("What did FLEX burn?")[-1][1]["verification"]["verified"] is False


def test_an_off_topic_reply_uses_no_tool_and_makes_no_claim_to_verify(site):
    site.install(
        FakeStream(
            [text_start(), delta("I can only help with microgravity combustion and fire-safety research.")], final()
        )
    )
    done = site.ask("Write me a poem about cats")[-1][1]
    assert done["tools"] == [] and done["verification"]["verified"] is None


def test_refusal_is_never_stored_or_shown(site):
    site.install(FakeStream([text_start(), delta("Partial text that must not be kept")], final("refusal")))
    events = site.ask("Something the model declines")
    assert events[-2][0] == "reset" and events[-1] == ("notice", {"text": events[-1][1]["text"], "kind": "refusal"})
    assert "Partial text" not in events[-1][1]["text"]
    assert not Message.objects.filter(role="assistant").exists()


def test_claude_being_unreachable_gives_a_clear_notice(site):
    class Unreachable(anthropic.APIError):
        def __init__(self):
            Exception.__init__(self, "unreachable")

    site.install(Unreachable())
    events = site.ask("What did FLEX burn?")
    assert events[-1][0] == "notice" and events[-1][1]["kind"] == "unavailable"
    assert "Stored summaries, rankings and charts" in events[-1][1]["text"]


def test_daily_token_limit_and_session_cap(site, settings):
    fake = site.install()
    settings.AI_DAILY_TOKEN_LIMIT = 0
    events = site.ask("What did FLEX burn?")
    assert events[-1][1]["kind"] == "limit" and "daily limit" in events[-1][1]["text"] and fake.calls == []
    settings.AI_DAILY_TOKEN_LIMIT = 10**9
    settings.ASSISTANT_SESSION_MESSAGE_LIMIT = 0
    assert "message limit" in site.ask("What did FLEX burn?")[-1][1]["text"]
    assert not Message.objects.exists()


def test_history_belongs_to_the_browser_session_and_bodies_must_be_json(site, django_user_model):
    from django.test import Client

    other = Client()
    assert other.get(f"{BASE}/conversations/{site.conversation_id}/").status_code == 404
    url = f"{BASE}/conversations/{site.conversation_id}/messages/"
    assert other.post(url, {"content": "hi"}, content_type="application/json").status_code == 404
    assert site.client.post(url, {"content": "hi"}).status_code == 415  # a form post is refused
    assert site.client.post(url, {"content": "  "}, content_type="application/json").status_code == 400
    assert site.client.post(url, {"content": "x" * 2001}, content_type="application/json").status_code == 400
    assert site.client.get(url).status_code == 405
    assert Conversation.objects.count() == 1 and set(Conversation.objects.get().session_key) != set()
    assert not hasattr(Conversation, "ip") and not hasattr(Message, "ip")  # no address is stored
