import uuid

from django.db import models


class Conversation(models.Model):
    """Assistant history under an anonymous session ID. No IP address is stored (section 11)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_key = models.CharField(max_length=64, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]


class Message(models.Model):
    class Role(models.TextChoices):
        USER = "user", "User"
        ASSISTANT = "assistant", "Assistant"

    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    citations = models.JSONField(default=list, blank=True)
    tool_calls = models.JSONField(default=list, blank=True)
    token_usage = models.JSONField(default=dict, blank=True)
    verification = models.JSONField(default=dict, blank=True)
    model = models.CharField(max_length=80, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]
