# ADR 0004: Local embeddings, Gemini for generation

**Status:** accepted

**Context:** No paid embedding API or hosted vector database should be required.

**Decision:** `sentence-transformers` (CPU torch) embeds documents and queries behind an `EmbeddingProvider` interface; the model is baked into the Docker image. Gemini (`google-genai`) generates answers; the model id is an environment variable.

**Consequences:** Indexing needs no network and no per-token cost. Embedding quality is limited to a small English-centric model by default. Answer generation sends excerpts to Google (documented in `security.md`).
