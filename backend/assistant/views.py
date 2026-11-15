"""Assistant endpoints. Plain async Django views, because the reply is a server-sent event stream."""

import json
import uuid

from asgiref.sync import sync_to_async
from django.http import HttpResponseNotAllowed, JsonResponse, StreamingHttpResponse
from django.views.decorators.csrf import csrf_exempt

from assistant import service
from assistant.models import Conversation, Message
from catalog.api.errors import error_body

JSON = "application/json"


def error(status: int, code: str, message: str) -> JsonResponse:
    return JsonResponse(error_body(code, message), status=status)


def session_key(request) -> str:
    """Anonymous session ID. The cookie expires when the browser closes (section 8.1)."""
    if not request.session.session_key:
        request.session.create()
    request.session["assistant"] = True
    return request.session.session_key


def json_post(request) -> dict | JsonResponse:
    """Only JSON bodies are accepted. A cross-site form cannot send this content type, which
    stands in for the CSRF token on these two endpoints."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    if not (request.content_type or "").startswith(JSON):
        return error(415, "unsupported_media_type", "Send the request as application/json.")
    try:
        body = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return error(400, "invalid", "The request body is not valid JSON.")
    return body if isinstance(body, dict) else error(400, "invalid", "The request body must be a JSON object.")


def message_payload(message: Message) -> dict:
    verification = dict(message.verification or {})
    segments = verification.pop("segments", None)
    return {
        "id": message.id,
        "role": message.role,
        "content": message.content,
        "segments": segments or [{"text": message.content, "citations": []}],
        "citations": message.citations,
        "model": message.model,
        "generated_at": message.created_at.isoformat(),
        "review_status": "unreviewed" if message.role == Message.Role.ASSISTANT else None,
        "verification": verification or None,
    }


@csrf_exempt
async def conversations(request):
    """POST: start a conversation for this browser session."""
    body = json_post(request)
    if not isinstance(body, dict):
        return body
    key = await sync_to_async(session_key)(request)
    conversation = await Conversation.objects.acreate(session_key=key)
    return JsonResponse({"id": str(conversation.id)}, status=201)


async def find_conversation(request, conversation_id: uuid.UUID) -> Conversation | None:
    key = await sync_to_async(lambda: request.session.session_key)()
    if not key:
        return None
    return await Conversation.objects.filter(id=conversation_id, session_key=key).afirst()


async def conversation_detail(request, conversation_id: uuid.UUID):
    """GET: history of one conversation, for the browser session that owns it only."""
    conversation = await find_conversation(request, conversation_id)
    if conversation is None:
        return error(404, "not_found", "No such conversation in this browser session.")
    messages = [message_payload(message) async for message in conversation.messages.all()]
    return JsonResponse({"id": str(conversation.id), "messages": messages})


def sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@csrf_exempt
async def messages(request, conversation_id: uuid.UUID):
    """POST: send a message. The reply is a server-sent event stream."""
    body = json_post(request)
    if not isinstance(body, dict):
        return body
    question = str(body.get("content", "")).strip()
    if not question:
        return error(400, "invalid", "The message is empty.")
    if len(question) > service.MAX_QUESTION_CHARS:
        return error(400, "invalid", f"The message is longer than {service.MAX_QUESTION_CHARS} characters.")
    conversation = await find_conversation(request, conversation_id)
    if conversation is None:
        return error(404, "not_found", "No such conversation in this browser session.")
    ip = request.META.get("HTTP_X_REAL_IP") or request.META.get("REMOTE_ADDR", "")

    async def stream():
        async for event, data in service.run_turn(conversation, question, ip):
            yield sse(event, data)

    response = StreamingHttpResponse(stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
