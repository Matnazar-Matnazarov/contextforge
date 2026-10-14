"""Tenant-scoped retrieval with DB re-validation of every hit."""

import logging
import math
import re
from dataclasses import dataclass
from uuid import UUID

from django.conf import settings

from apps.documents.models import Document, DocumentStatus

from .embeddings import get_embedder
from .vector_store import SearchHit, get_vector_store

logger = logging.getLogger(__name__)

_WORD = re.compile(r"[^\W_]+", re.UNICODE)  # same splitting as Qdrant's word tokenizer
_MAX_QUERY_TOKENS = 8
_RARE_FRACTION = 0.15  # a token present in more than this share of the org's chunks carries no signal
_RRF_K = 60


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


def _tokens(text: str) -> list[str]:
    seen: dict[str, None] = {}
    for t in _WORD.findall(text.lower()):
        if len(t) >= 3:
            seen.setdefault(t)
    return list(seen)[:_MAX_QUERY_TOKENS]


def _lexical_hits(organization_id: UUID, query: str, limit: int) -> list[dict]:
    """Keyword half of hybrid retrieval: rank chunks by the summed IDF of the rare query words they contain.

    Embedding models are weak on rare words, names and low-resource languages; exact word matches are not.
    """
    store = get_vector_store()
    total = store.count_org_chunks(organization_id=organization_id)
    if total == 0:
        return []
    idf: dict[str, float] = {}
    for tok in _tokens(query):
        df = store.token_document_frequency(organization_id=organization_id, token=tok)
        if 0 < df <= max(3, total * _RARE_FRACTION):
            idf[tok] = math.log(1 + total / df)
    if not idf:
        return []
    candidates: dict[str, dict] = {}
    for tok in idf:
        for payload in store.search_text(organization_id=organization_id, token=tok, limit=30):
            candidates.setdefault(str(payload.get("chunk_id")), payload)
    scored = []
    for payload in candidates.values():
        words = set(_WORD.findall(str(payload.get("text", "")).lower()))
        score = sum(w for tok, w in idf.items() if tok in words)
        if score > 0:
            scored.append((score, payload))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:limit]]


def retrieve(
    *, organization_id: UUID, question: str, limit: int | None = None, max_chars: int | None = None
) -> list[RetrievedChunk]:
    """Search Qdrant filtered to `organization_id` (trusted, from membership), then drop stale hits.

    A hit survives only if its document still exists in PostgreSQL, belongs to the same organization,
    and is currently `indexed`. Context is capped at RAG_MAX_CONTEXT_CHARS.
    """
    top_k = limit or settings.RAG_TOP_K
    vector = get_embedder().embed_query(question)
    dense = get_vector_store().search(
        organization_id=organization_id,
        vector=vector,
        limit=top_k,
        score_threshold=settings.RAG_SCORE_THRESHOLD,
    )
    lexical = _lexical_hits(organization_id, question, top_k)

    # Reciprocal-rank fusion of the semantic and keyword rankings.
    fused: dict[str, float] = {}
    by_id: dict[str, SearchHit] = {}
    for rank, h in enumerate(dense):
        cid = str(h.payload.get("chunk_id"))
        by_id[cid] = h
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (_RRF_K + rank)
    for rank, payload in enumerate(lexical):
        cid = str(payload.get("chunk_id"))
        by_id.setdefault(cid, SearchHit(score=0.0, payload=payload))
        fused[cid] = fused.get(cid, 0.0) + 1.0 / (_RRF_K + rank)
    hits = [by_id[c] for c in sorted(fused, key=lambda c: -fused[c])[:top_k]]
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
