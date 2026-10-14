"""Tenant-scoped retrieval with DB re-validation of every hit."""

import logging
from dataclasses import dataclass
from uuid import UUID

from django.conf import settings

from apps.documents.models import Document, DocumentStatus

from .embeddings import get_embedder
from .vector_store import get_vector_store

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetrievedChunk:
    source_id: str  # "S1".. stable within one request; the only handle the LLM may cite
    document_id: UUID
    document_name: str
    chunk_id: str
    chunk_index: int
    page: int | None
    section: str | None
    text: str
    score: float


def retrieve(
    *, organization_id: UUID, question: str, limit: int | None = None, max_chars: int | None = None
) -> list[RetrievedChunk]:
    """Search Qdrant filtered to `organization_id` (trusted, from membership), then drop stale hits.

    A hit survives only if its document still exists in PostgreSQL, belongs to the same organization,
    and is currently `indexed`. Context is capped at RAG_MAX_CONTEXT_CHARS.
    """
    vector = get_embedder().embed_query(question)
    hits = get_vector_store().search(
        organization_id=organization_id,
        vector=vector,
        limit=limit or settings.RAG_TOP_K,
        score_threshold=settings.RAG_SCORE_THRESHOLD,
    )
    if not hits:
        return []

    doc_ids = {h.payload.get("document_id") for h in hits}
    valid = {
        str(pk): name
        for pk, name in Document.objects.filter(
            pk__in=[d for d in doc_ids if d], organization_id=organization_id, status=DocumentStatus.INDEXED
        ).values_list("pk", "original_filename")
    }

    chunks: list[RetrievedChunk] = []
    budget = max_chars or settings.RAG_MAX_CONTEXT_CHARS
    for hit in hits:
        p = hit.payload
        if p.get("organization_id") != str(organization_id) or p.get("document_id") not in valid:
            logger.warning("retrieval_dropped_stale_hit org=%s", organization_id)
            continue
        text = str(p.get("text", ""))
        if len(text) > budget:
            if chunks:
                break
            text = text[:budget]
        budget -= len(text)
        chunks.append(
            RetrievedChunk(
                source_id=f"S{len(chunks) + 1}",
                document_id=UUID(p["document_id"]),
                document_name=valid[p["document_id"]],
                chunk_id=str(p["chunk_id"]),
                chunk_index=int(p["chunk_index"]),
                page=p.get("page"),
                section=p.get("section"),
                text=text,
                score=float(hit.score),
            )
        )
    return chunks
