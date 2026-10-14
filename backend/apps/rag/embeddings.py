"""Replaceable embedding interface. Swap providers via EMBEDDING_PROVIDER without touching callers."""

import hashlib
import math
import re
from functools import lru_cache
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
        self.dimensions = dimensions
        self._batch_size = batch_size
        self._model = None

    def _load(self):
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(self.model_name)
            actual = self._model.get_sentence_embedding_dimension()
            if actual != self.dimensions:
                raise RuntimeError(f"EMBEDDING_DIMENSIONS={self.dimensions} but {self.model_name} produces {actual}")
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vectors = self._load().encode(
            texts, batch_size=self._batch_size, normalize_embeddings=True, show_progress_bar=False
        )
        return [v.tolist() for v in vectors]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


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
