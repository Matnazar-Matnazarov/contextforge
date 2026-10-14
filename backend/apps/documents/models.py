import uuid

from django.conf import settings
from django.db import models


class DocumentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    INDEXED = "indexed", "Indexed"
    FAILED = "failed", "Failed"
    DELETING = "deleting", "Deleting"


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    organization = models.ForeignKey("organizations.Organization", on_delete=models.CASCADE, related_name="documents")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="uploaded_documents"
    )
    original_filename = models.CharField(max_length=255)
    object_key = models.CharField(max_length=512, unique=True)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    checksum_sha256 = models.CharField(max_length=64)
    status = models.CharField(max_length=16, choices=DocumentStatus.choices, default=DocumentStatus.PENDING)
    error_message = models.CharField(max_length=500, blank=True)
    page_count = models.PositiveIntegerField(null=True, blank=True)
    chunk_count = models.PositiveIntegerField(default=0)
    # Embedding model + chunking config the current vectors were built with (drives re-index decisions).
    indexed_with = models.CharField(max_length=255, blank=True)
    attempts = models.PositiveIntegerField(default=0)
    processing_started_at = models.DateTimeField(null=True, blank=True)
    indexed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["organization", "checksum_sha256"], name="uniq_document_org_checksum"),
            models.CheckConstraint(condition=models.Q(status__in=DocumentStatus.values), name="document_status_valid"),
        ]
        indexes = [
            models.Index(fields=["organization", "status"]),
            models.Index(fields=["organization", "-created_at"]),
        ]

    def __str__(self) -> str:
        return self.original_filename
