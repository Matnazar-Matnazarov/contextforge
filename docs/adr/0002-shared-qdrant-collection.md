# ADR 0002: One Qdrant collection with mandatory organization filter

**Status:** accepted

**Context:** Multi-tenant vector search needs isolation. Options: collection per tenant, or shared collection with payload filtering.

**Decision:** A single collection with an indexed `organization_id` payload. The vector-store adapter exposes no unscoped search or delete; organization ids come from verified membership.

**Consequences:** Few collections and cheap tenant creation. Isolation depends on code discipline (covered by tests) rather than physical separation. Per-tenant collections remain an option for stricter isolation.
