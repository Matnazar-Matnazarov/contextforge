# ADR 0003: Celery + RabbitMQ with idempotent, DB-claimed indexing

**Status:** accepted

**Context:** Parsing and embedding are slow and span three stores with no shared transaction.

**Decision:** RabbitMQ is the only broker. Tasks carry just a document id, claim the row with `SELECT … FOR UPDATE`, use deterministic Qdrant point ids, `acks_late`, bounded retries with backoff, and only set `indexed` after Qdrant confirms. Redis is not used because there is no concrete need.

**Consequences:** Redelivery and retries are safe. A crashed worker leaves a `processing` row that becomes re-claimable after a timeout rather than being silently reported as indexed.
