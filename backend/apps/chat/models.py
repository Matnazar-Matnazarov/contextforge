import uuid

from django.conf import settings
from django.db import models


class Conversation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.CASCADE, related_name="conversations"
    )
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="conversations")
    title = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        indexes = [models.Index(fields=["organization", "owner", "-updated_at"])]

    def __str__(self) -> str:
        return self.title or str(self.id)


class MessageRole(models.TextChoices):
    USER = "user", "User"
    ASSISTANT = "assistant", "Assistant"


class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    role = models.CharField(max_length=16, choices=MessageRole.choices)
    content = models.TextField()
    insufficient_context = models.BooleanField(default=False)
    model_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [models.Index(fields=["conversation", "created_at"])]

    def __str__(self) -> str:
        return f"{self.role}:{self.id}"


class Citation(models.Model):
    """Snapshot of a validated source. Title/excerpt are copied so history survives document deletion."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name="citations")
    document = models.ForeignKey("documents.Document", on_delete=models.SET_NULL, null=True, related_name="+")
    document_title = models.CharField(max_length=255)
    chunk_id = models.CharField(max_length=100)
    source_label = models.CharField(max_length=8)
    page_number = models.PositiveIntegerField(null=True, blank=True)
    section = models.CharField(max_length=255, blank=True)
    excerpt = models.TextField()
    score = models.FloatField(null=True, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position"]

    def __str__(self) -> str:
        return f"{self.source_label} {self.document_title}"
