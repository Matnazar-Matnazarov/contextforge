"""Replaceable embedding interface. Swap providers via EMBEDDING_PROVIDER without touching callers."""

import hashlib
import math
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Protocol

from django.conf import settings


class EmbeddingProvider(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class SentenceTransformerProvider:
    """Local model; no network calls at inference time (model download happens once)."""

    def __init__(self, model_name: str, dimensions: int, batch_size: int):
        self.model_name = model_name
        # E5-family models are trained with these task prefixes; omitting them noticeably hurts retrieval.
        e5 = "e5" in model_name.lower()
        self._query_prefix = "query: " if e5 else ""
        self._passage_prefix = "passage: " if e5 else ""
        self.dimensions = dimensions
        self._batch_size = batch_size
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            # Optional extra cache (compose mounts data/hf-cache, HF_HOME layout); else the image's baked-in one.
            extra = Path(os.environ.get("EMBEDDING_CACHE_DIR", "/nonexistent")) / "hub"
            repo = "models--" + self.model_name.replace("/", "--")
            complete = any((extra / repo / "snapshots").glob("*/model.safetensors"))
            cache = str(extra) if complete else None
            self._model = SentenceTransformer(self.model_name, cache_folder=cache)
            actual = self._model.get_embedding_dimension()
            if actual != self.dimensions:
                raise RuntimeError(f"EMBEDDING_DIMENSIONS={self.dimensions} but {self.model_name} produces {actual}")
        return self._model

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(
            texts, batch_size=self._batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return [v.tolist() for v in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([self._passage_prefix + t for t in texts])

    def embed_query(self, text: str) -> list[float]:
        return self._encode([self._query_prefix + text])[0]


class HashingProvider:
    """Deterministic bag-of-words hashing embedder. Offline; for tests/CI only (lexical, not semantic)."""

    _token = re.compile(r"[a-z0-9]+")

    def __init__(self, dimensions: int):
        self.model_name = f"hashing-bow-{dimensions}"
        self.dimensions = dimensions

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self.dimensions
        for tok in self._token.findall(text.lower()):
            if len(tok) < 3:
                continue
            h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")
            vec[h % self.dimensions] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)


@lru_cache(maxsize=1)
def get_embedder() -> EmbeddingProvider:
    provider = settings.EMBEDDING_PROVIDER
    if provider == "sentence_transformers":
        return SentenceTransformerProvider(
            settings.EMBEDDING_MODEL, settings.EMBEDDING_DIMENSIONS, settings.EMBEDDING_BATCH_SIZE
        )
    if provider == "hashing":
        return HashingProvider(settings.EMBEDDING_DIMENSIONS)
    raise RuntimeError(f"Unknown EMBEDDING_PROVIDER: {provider}")
