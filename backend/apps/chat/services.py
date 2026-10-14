import logging

from django.conf import settings
from django.db import transaction

from apps.core.exceptions import ServiceError
from apps.organizations.models import Membership
from apps.organizations.permissions import Action, can
from apps.rag.llm import LLMClient, LLMError
from apps.rag.pipeline import answer_question

from .models import Citation, Conversation, Message, MessageRole

logger = logging.getLogger(__name__)

HISTORY_TURNS = 3
HISTORY_CHARS = 600
EXCERPT_CHARS = 600


def create_conversation(*, membership: Membership, title: str = "") -> Conversation:
    if not can(membership, Action.CHAT):
        raise ServiceError("Not allowed.", code="forbidden", status_code=403)
    return Conversation.objects.create(organization=membership.organization, owner=membership.user, title=title[:200])


def _history(conversation: Conversation) -> list[tuple[str, str]]:
    recent = list(conversation.messages.order_by("-created_at")[: HISTORY_TURNS * 2])[::-1]
    return [("user" if m.role == MessageRole.USER else "assistant", m.content[:HISTORY_CHARS]) for m in recent]


def ask(*, membership: Membership, conversation: Conversation, question: str, llm: LLMClient | None = None):
    """Authorize -> run RAG scoped to the *membership's* org -> persist both messages + citations atomically."""
    if not can(membership, Action.CHAT):
        raise ServiceError("Not allowed.", code="forbidden", status_code=403)
    # Defense in depth: the conversation must belong to the validated org and the caller.
    if conversation.organization_id != membership.organization_id or conversation.owner_id != membership.user_id:
        raise ServiceError("Conversation not found.", code="not_found", status_code=404)
    question = question.strip()
    if not question or len(question) > settings.RAG_MAX_QUESTION_CHARS:
        raise ServiceError("Question is empty or too long.", code="invalid_question", status_code=400)

    try:
        result = answer_question(
            organization_id=membership.organization_id, question=question, history=_history(conversation), llm=llm
        )
    except LLMError as exc:
        logger.error("llm_failure org=%s reason=%s", membership.organization_id, exc)
        raise ServiceError(
            "The answer service is temporarily unavailable. Please try again.", code="llm_unavailable", status_code=502
        ) from exc
    except Exception as exc:
        logger.exception("retrieval_failure org=%s", membership.organization_id)
        raise ServiceError(
            "Search is temporarily unavailable. Please try again.", code="retrieval_unavailable", status_code=503
        ) from exc

    with transaction.atomic():
        user_msg = Message.objects.create(conversation=conversation, role=MessageRole.USER, content=question)
        assistant = Message.objects.create(
            conversation=conversation,
            role=MessageRole.ASSISTANT,
            content=result.answer,
            insufficient_context=result.insufficient_context,
            model_name=result.model,
        )
        Citation.objects.bulk_create(
            Citation(
                message=assistant,
                document_id=c.document_id,
                document_title=c.document_name,
                chunk_id=c.chunk_id,
                source_label=c.source_id,
                page_number=c.page,
                section=c.section or "",
                excerpt=c.text[:EXCERPT_CHARS],
                score=c.score,
                position=i,
            )
            for i, c in enumerate(result.citations)
        )
        if not conversation.title:
            conversation.title = question[:80]
        conversation.save(update_fields=["title", "updated_at"])
    return user_msg, assistant
