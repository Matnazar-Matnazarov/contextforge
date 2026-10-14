"""Explicit RAG pipeline: retrieve -> (guard) -> prompt -> generate -> validate citations."""

import logging
from dataclasses import dataclass
from uuid import UUID

from .llm import LLMClient, get_llm
from .prompts import INSUFFICIENT_ANSWER, SYSTEM_PROMPT, PromptSource, build_user_prompt
from .retrieval import RetrievedChunk, retrieve

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RagResult:
    answer: str
    insufficient_context: bool
    citations: list[RetrievedChunk]
    model: str


def validate_citations(cited_ids: list[str], retrieved: list[RetrievedChunk]) -> list[RetrievedChunk]:
    """Keep only citations that map to chunks retrieved for *this* request (order-preserving, de-duplicated)."""
    by_id = {c.source_id: c for c in retrieved}
    seen: set[str] = set()
    valid = []
    for raw in cited_ids:
        sid = str(raw).strip().upper()
        if sid in by_id and sid not in seen:
            seen.add(sid)
            valid.append(by_id[sid])
        elif sid not in by_id:
            logger.warning("llm_invented_citation id=%s", sid[:20])
    return valid


def answer_question(
    *,
    organization_id: UUID,
    question: str,
    history: list[tuple[str, str]] | None = None,
    llm: LLMClient | None = None,
) -> RagResult:
    retrieved = retrieve(organization_id=organization_id, question=question)
    if not retrieved:
        # No relevant evidence: do not call (and pay) the LLM, do not let it free-associate.
        return RagResult(INSUFFICIENT_ANSWER, True, [], model="none")

    sources = [PromptSource(c.source_id, c.document_name, c.page, c.section, c.text) for c in retrieved]
    result = (llm or get_llm()).generate(
        system_prompt=SYSTEM_PROMPT, user_prompt=build_user_prompt(question, sources, history or [])
    )
    if not result.sufficient_context:
        return RagResult(result.answer or INSUFFICIENT_ANSWER, True, [], model=result.model)

    citations = validate_citations(result.cited_source_ids, retrieved)
    if not citations:
        # A factual answer with no verifiable support is not acceptable.
        logger.warning("answer_without_valid_citations")
        return RagResult(INSUFFICIENT_ANSWER, True, [], model=result.model)
    return RagResult(result.answer, False, citations, model=result.model)
