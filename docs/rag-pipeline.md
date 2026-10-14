# RAG pipeline

## Indexing (`apps/documents`)

1. **Validate** (`validation.py`): extension allow-list (`.pdf .txt .md .markdown`), size cap, libmagic content sniffing
   (PDFs must start with `%PDF-` and be detected as `application/pdf`; text must be UTF-8 without NUL bytes). The
   client-supplied MIME type is ignored.
2. **Store**: key is `orgs/{org_id}/documents/{document_uuid}{ext}`; the filename is display-only and sanitized.
3. **Parse** (`parsing.py`): PDFs via `pypdf`, per page, so page numbers survive; Markdown is split by heading so each
   segment carries a `section`; text is normalized (NFC, newline unification, NUL removal, blank-line collapsing) without
   touching indentation, lists or code fences. Encrypted PDFs, page-limit violations and image-only PDFs fail permanently with a clear message (no OCR).
4. **Chunk** (`chunking.py`): character windows of `CHUNK_SIZE` with `CHUNK_OVERLAP`, preferring paragraph, line,
   sentence, then word boundaries. Chunks never cross page/section segments.
5. **Embed** (`rag/embeddings.py`): `EmbeddingProvider` protocol. Default is a local `sentence-transformers` model
   (`all-MiniLM-L6-v2`, 384 dimensions, normalized, cosine). Query and documents use the same provider.
6. **Upsert** (`rag/vector_store.py`): one Qdrant collection for all tenants; payload per chunk:
   `organization_id, document_id, chunk_id, chunk_index, document_name, page, section, text, embedding_model`.
   Payload indexes exist on `organization_id`, `document_id`, `chunk_index`. The collection is created idempotently by
   `init_services`; a dimension mismatch aborts rather than corrupting data.

## Retrieval (`rag/retrieval.py`)

1. Embed the question.
2. Search Qdrant with a **mandatory** `organization_id` filter. `QdrantVectorStore.search` has no unscoped form and raises on an empty org id.
   The org id comes from the server-resolved membership, never from the request body.
3. Apply `RAG_TOP_K` and `RAG_SCORE_THRESHOLD` (cosine similarity).
4. Re-validate every hit against PostgreSQL: the document must exist, belong to the same organization, and be `indexed`.
   Stale vectors (deleted/deleting/failed documents) are dropped and logged.
5. Assign stable ids `S1..Sn` and enforce `RAG_MAX_CONTEXT_CHARS`.

If nothing survives, the pipeline returns the insufficient-context answer **without calling Gemini**: no cost, no chance of an ungrounded answer.

Visibility model: every active member can see every document in their organization (documented in `security.md`), so no
extra per-document filter is needed beyond organization + document state. If per-document ACLs are added later, they belong in step 2 (Qdrant filter) *and* step 4 (DB check).

## Generation (`rag/prompts.py`, `rag/llm.py`)

* `SYSTEM_PROMPT` lives only in `prompts.py`. It instructs the model to answer only from `<sources>`, treat sources and history as untrusted data,
  admit insufficient context, and return JSON `{answer, sufficient_context, citations}`.
* Sources are rendered as `<source id="S1" document="…" page="…">…</source>`. Document text is escaped so it cannot close or forge delimiter tags.
* Gemini is called through the official `google-genai` SDK with the model from `GEMINI_MODEL`, a request timeout, and at most `GEMINI_MAX_ATTEMPTS`
  attempts. Only 429/5xx and network errors are retried (with short backoff); 4xx errors and malformed output are never retried.
* Failure surfaces as HTTP 502 `llm_unavailable` with a generic message; nothing is persisted.

## Citations

The model may only cite the ids it was given. `validate_citations` maps ids to the chunks retrieved **for that request**; unknown ids are discarded.
If a "sufficient" answer ends up with zero valid citations it is replaced by the insufficient-context answer.
Citations are persisted as snapshots (document id, title, chunk id, page, section, excerpt) in the same transaction as the messages.
Snapshots survive document deletion (`document` becomes null, the title and excerpt remain). Retrieval scores are stored but only returned when `DEBUG` is on.

## Quality evaluation

`backend/tests/fixtures/` holds synthetic documents and `eval_questions.json` (question → expected source file).
`tests/test_rag.py` asserts that the expected document is the top hit, irrelevant questions produce an insufficient answer, citations map to retrieved chunks,
and tenants never see each other's data. Automated tests use a deterministic *hashing* embedder (lexical only) so they run offline;
semantic quality with the real MiniLM model is not covered by CI and should be spot-checked manually.

## Extending

* Reranker/hybrid search: change `retrieve()`; everything downstream consumes `RetrievedChunk`.
* Another LLM: implement `LLMClient.generate` and return the same JSON contract.
* Another embedding model: implement `EmbeddingProvider`, set `EMBEDDING_*`, create a new collection if dimensions differ, run `make reindex`.
