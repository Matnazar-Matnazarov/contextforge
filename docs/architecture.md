# Architecture

## Components and responsibilities

| Component | Responsibility | Why it owns this |
|---|---|---|
| **Caddy** | Single browser-facing origin (`http://localhost:8080`). Routes `/api/*` to Django and everything else to Next.js. Caps request bodies. | Same origin means first-party session cookies and no CORS surface. |
| **Next.js** | UI only. Holds no secrets and talks to the API with relative URLs. | Keeps presentation separate from business rules; authorization is never decided here. |
| **Django + DRF** | Auth, tenancy, authorization, upload validation, orchestration of RAG. Views are thin; logic lives in `services.py` / `pipeline.py`. | One place that enforces who can do what. |
| **PostgreSQL** | System of record: users, organizations, memberships, document metadata and state, conversations, messages, citation snapshots. | Relational integrity, constraints, transactions. |
| **SeaweedFS (S3)** | Original uploaded bytes, in a private bucket. | Binary blobs do not belong in the database; S3 API keeps the adapter portable. |
| **Qdrant** | Chunk vectors plus a retrieval payload (org, document, chunk, page, text). | Purpose-built ANN search with payload filtering. |
| **RabbitMQ** | Transports indexing/deletion tasks to Celery. | Durable queue so slow work (parsing, embedding) never blocks a request. |
| **Celery worker** | Runs `index_document_task` / `delete_document_task` using the same Django domain services. | Shares code with the API; no separate microservice. |
| **Gemini API** | Generates the answer from retrieved passages. | External; only bounded excerpts are sent. |

```mermaid
flowchart LR
  B[Browser] --> C[Caddy :8080]
  C -->|/| N[Next.js]
  C -->|/api| D[Django API]
  D --> P[(PostgreSQL)]
  D --> S[(SeaweedFS S3)]
  D --> Q[(Qdrant)]
  D -->|enqueue| R[[RabbitMQ]]
  R --> W[Celery worker]
  W --> S
  W --> Q
  W --> P
  D -->|question + excerpts| G[Gemini API]
```

## Django apps

`accounts` (custom email user, session auth) · `organizations` (tenant, membership, permission matrix) ·
`documents` (model, storage adapter, validation, parsing, chunking, lifecycle, tasks) ·
`rag` (embedding interface, Qdrant adapter, retrieval, prompts, LLM adapter, pipeline) ·
`chat` (conversations, messages, citations) · `core` (health, errors, pagination, ops commands).

`rag` is intentionally free of HTTP and chat persistence, so a reranker, hybrid search or another LLM can
be added by changing `retrieval.py` / `llm.py` only.

## Document ingestion

```mermaid
sequenceDiagram
  participant U as Browser
  participant A as Django API
  participant S as SeaweedFS
  participant DB as PostgreSQL
  participant MQ as RabbitMQ
  participant W as Celery worker
  participant E as Embedder (local)
  participant Q as Qdrant
  U->>A: POST /api/orgs/{org}/documents/ (file, session+CSRF)
  A->>A: resolve membership, validate ext/size/magic bytes
  A->>S: PUT orgs/{org}/documents/{uuid}.ext
  A->>DB: INSERT document (pending, sha256)
  A->>MQ: enqueue(document_id) after commit
  A-->>U: 201 pending
  MQ->>W: index_document_task(document_id)
  W->>DB: claim row (SELECT FOR UPDATE -> processing)
  W->>S: GET object (org prefix re-checked)
  W->>W: verify sha256, parse, normalize, chunk
  W->>E: embed chunks
  W->>Q: upsert deterministic point ids, then delete stale tail
  W->>DB: status = indexed (only now)
  U->>A: poll GET /documents/ (2.5 s while pending/processing)
```

## Question answering

```mermaid
sequenceDiagram
  participant U as Browser
  participant A as Django API
  participant E as Embedder
  participant Q as Qdrant
  participant DB as PostgreSQL
  participant G as Gemini
  U->>A: POST /api/orgs/{org}/conversations/{id}/messages/
  A->>DB: membership(user, org) active? conversation owner+org match?
  A->>E: embed question
  A->>Q: search WITH filter organization_id = trusted org, score >= threshold, top-k
  A->>DB: keep only hits whose document exists, same org, status=indexed
  alt no relevant evidence
    A-->>U: insufficient-context answer (Gemini NOT called)
  else evidence
    A->>G: system prompt + bounded <source> blocks + question
    G-->>A: JSON {answer, sufficient_context, citations[S#]}
    A->>A: drop citation ids not in this request's retrieved set
    A->>DB: save user msg, assistant msg, citation snapshots (one transaction)
    A-->>U: answer + structured citations
  end
```

## Coordinating PostgreSQL, Qdrant and object storage

These three systems cannot commit atomically. The design chooses an order for each operation so that a crash leaves
a state that is *detectable and recoverable*, and never a false success.

| Failure | Resulting state | Recovery |
|---|---|---|
| Object stored, DB insert fails | Orphan object, no row. Best-effort delete runs immediately. | Orphans are invisible and unreferenced; a periodic bucket sweep is future work. |
| Row committed, broker down at enqueue | Row marked `failed` with "queue unavailable". | User/admin presses Retry. |
| Worker crashes mid-index | Row stays `processing`. | After `PROCESSING_STALE_SECONDS` the claim is stale and a retry/`reindex_stale` re-claims it. `acks_late` also redelivers the message. |
| Vectors upserted, DB update fails | Vectors exist but row is not `indexed`; retrieval ignores it (DB re-validation). | Task retry overwrites the same deterministic point ids. |
| Re-index with fewer chunks | Old tail chunks would linger. | `delete_stale_chunks` removes `chunk_index >= n` after the new upsert (no empty window). |
| Delete: vectors removed, object delete fails | Row remains `deleting` (hidden from users and retrieval). | Task retries with backoff. Row is deleted last. |
| Delete during indexing | Worker sees `deleting` at finalisation, removes the vectors it wrote, does not mark indexed. | — |

Idempotency: Qdrant point id = `uuid5(document_id, chunk_index)`; tasks no-op for `indexed` / `deleting` documents
or fresh `processing` claims.

## Configuration changes and re-indexing

Each indexed document records `indexed_with` (embedding model + chunk size + overlap). Changing the embedding model,
dimensions, or chunking requires a new collection when dimensions change (startup refuses a mismatched collection) and
`make reindex` (`reindex_stale`) to re-queue documents whose signature differs.

## Observability

Structured one-line logs with a request id (`X-Request-ID`). Document text, prompts, credentials and API keys are not logged.
`/api/health/` (liveness) and `/api/ready/` (database + Qdrant) back the Docker health checks. No metrics stack is included.
