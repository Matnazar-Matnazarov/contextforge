from django.conf import settings
from rest_framework import serializers

from .models import Citation, Conversation, Message


class CitationSerializer(serializers.ModelSerializer):
    document_id = serializers.UUIDField(read_only=True, allow_null=True)
    score = serializers.SerializerMethodField()

    class Meta:
        model = Citation
        fields = [
            "id",
            "document_id",
            "document_title",
            "chunk_id",
            "source_label",
            "page_number",
            "section",
            "excerpt",
            "score",
        ]
        read_only_fields = fields

    def get_score(self, obj) -> float | None:
        # Retrieval score is an internal debugging aid; only exposed in DEBUG.
        return obj.score if settings.DEBUG else None


class MessageSerializer(serializers.ModelSerializer):
    citations = CitationSerializer(many=True, read_only=True)

    class Meta:
        model = Message
        fields = ["id", "role", "content", "insufficient_context", "citations", "created_at"]
        read_only_fields = fields


class ConversationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Conversation
        fields = ["id", "title", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]
        extra_kwargs = {"title": {"required": False}}


class AskSerializer(serializers.Serializer):
    question = serializers.CharField(max_length=settings.RAG_MAX_QUESTION_CHARS, trim_whitespace=True)
