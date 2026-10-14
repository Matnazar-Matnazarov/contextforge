from rest_framework import serializers

from .models import Document
from .services import can_manage_document


class DocumentSerializer(serializers.ModelSerializer):
    uploaded_by_email = serializers.EmailField(source="uploaded_by.email", read_only=True, default=None)
    can_manage = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = [
            "id",
            "original_filename",
            "mime_type",
            "size_bytes",
            "status",
            "error_message",
            "page_count",
            "chunk_count",
            "uploaded_by_email",
            "can_manage",
            "created_at",
            "indexed_at",
        ]
        read_only_fields = fields

    def get_can_manage(self, obj) -> bool:
        membership = self.context.get("membership")
        return bool(membership and can_manage_document(membership, obj))


class UploadSerializer(serializers.Serializer):
    file = serializers.FileField()
