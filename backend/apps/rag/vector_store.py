"""Qdrant adapter. Every read/write is tenant-scoped by construction:

* `search()` and `delete_document()` take a mandatory `organization_id`; there is no unscoped variant.
* Point ids are deterministic (uuid5 of document_id + chunk_index) so retries overwrite, never duplicate.
"""

import logging
import uuid
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from django.conf import settings
from qdrant_client import QdrantClient, models

logger = logging.getLogger(__name__)

_POINT_NS = uuid.UUID("6f1d2c1e-8f0a-4c43-9d57-0b5a3a2c9e11")


def point_id(document_id: uuid.UUID | str, chunk_index: int) -> str:
    return str(uuid.uuid5(_POINT_NS, f"{document_id}:{chunk_index}"))


def chunk_id(document_id: uuid.UUID | str, chunk_index: int) -> str:
    return f"{document_id}:{chunk_index}"


@dataclass(frozen=True)
class ChunkPoint:
    chunk_index: int
    vector: list[float]
    text: str
    page: int | None
    section: str | None


@dataclass(frozen=True)
class SearchHit:
    score: float
    payload: dict[str, Any]


class VectorStoreConfigError(Exception):
    pass


class QdrantVectorStore:
    def __init__(self, client: QdrantClient, collection: str, dimensions: int):
        self.client = client
        self.collection = collection
        self.dimensions = dimensions

    def ping(self) -> None:
        self.client.get_collections()

    def ensure_collection(self) -> None:
        """Idempotent. Fails loudly if an existing collection has incompatible dimensions."""
        if not self.client.collection_exists(self.collection):
            self.client.create_collection(
                self.collection,
                vectors_config=models.VectorParams(size=self.dimensions, distance=models.Distance.COSINE),
            )
        else:
            info = self.client.get_collection(self.collection)
            vectors = info.config.params.vectors
            size = getattr(vectors, "size", None)
            if size is not None and size != self.dimensions:
                raise VectorStoreConfigError(
                    f"Collection {self.collection} has dimension {size}, expected {self.dimensions}. "
                    "Use a new QDRANT_COLLECTION or re-create it, then re-index."
                )
        for field, schema in (
            ("organization_id", models.PayloadSchemaType.KEYWORD),
            ("document_id", models.PayloadSchemaType.KEYWORD),
            ("chunk_index", models.PayloadSchemaType.INTEGER),
        ):
            self.client.create_payload_index(self.collection, field_name=field, field_schema=schema)
        # Full-text index powers the lexical half of hybrid retrieval (names, terms, rare words in any language).
        self.client.create_payload_index(
            self.collection,
            field_name="text",
            field_schema=models.TextIndexParams(
                type=models.TextIndexType.TEXT,
                tokenizer=models.TokenizerType.WORD,
                min_token_len=2,
                max_token_len=40,
                lowercase=True,
            ),
        )

    def upsert_chunks(
        self, *, organization_id, document_id, document_name: str, embedding_model: str, chunks: list[ChunkPoint]
    ) -> None:
        points = [
            models.PointStruct(
                id=point_id(document_id, c.chunk_index),
                vector=c.vector,
                payload={
                    "organization_id": str(organization_id),
                    "document_id": str(document_id),
                    "chunk_id": chunk_id(document_id, c.chunk_index),
                    "chunk_index": c.chunk_index,
                    "document_name": document_name,
                    "page": c.page,
                    "section": c.section,
                    "text": c.text,
                    "embedding_model": embedding_model,
                },
            )
            for c in chunks
        ]
        for i in range(0, len(points), 128):
            self.client.upsert(self.collection, points=points[i : i + 128], wait=True)

    def delete_stale_chunks(self, *, organization_id, document_id, keep_below: int) -> None:
        """After a re-index, drop chunks of a previous (longer) version of the document."""
        self.client.delete(
            self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        *_scope(organization_id, document_id),
                        models.FieldCondition(key="chunk_index", range=models.Range(gte=keep_below)),
                    ]
                )
            ),
            wait=True,
        )

    def delete_document(self, *, organization_id, document_id) -> None:
        self.client.delete(
            self.collection,
            points_selector=models.FilterSelector(filter=models.Filter(must=_scope(organization_id, document_id))),
            wait=True,
        )

    def delete_organization(self, *, organization_id) -> None:
        self.client.delete(
            self.collection,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="organization_id", match=models.MatchValue(value=str(organization_id))
                        )
                    ]
                )
            ),
            wait=True,
        )

    def count_document_chunks(self, *, organization_id, document_id) -> int:
        return self.client.count(
            self.collection, count_filter=models.Filter(must=_scope(organization_id, document_id)), exact=True
        ).count

    def search(
        self, *, organization_id, vector: list[float], limit: int, score_threshold: float | None = None
    ) -> list[SearchHit]:
        if not organization_id:
            raise ValueError("organization_id is required for vector search")
        result = self.client.query_points(
            self.collection,
            query=vector,
            query_filter=models.Filter(
                must=[models.FieldCondition(key="organization_id", match=models.MatchValue(value=str(organization_id)))]
            ),
            limit=limit,
            score_threshold=score_threshold,
            with_payload=True,
        )
        return [SearchHit(score=p.score, payload=dict(p.payload or {})) for p in result.points]

    def _text_filter(self, organization_id, token: str) -> models.Filter:
        return models.Filter(
            must=[
                models.FieldCondition(key="organization_id", match=models.MatchValue(value=str(organization_id))),
                models.FieldCondition(key="text", match=models.MatchText(text=token)),
            ]
        )

    def count_org_chunks(self, *, organization_id) -> int:
        if not organization_id:
            raise ValueError("organization_id is required")
        return self.client.count(
            self.collection,
            count_filter=models.Filter(
                must=[models.FieldCondition(key="organization_id", match=models.MatchValue(value=str(organization_id)))]
            ),
            exact=True,
        ).count

    def token_document_frequency(self, *, organization_id, token: str) -> int:
        if not organization_id:
            raise ValueError("organization_id is required")
        return self.client.count(
            self.collection, count_filter=self._text_filter(organization_id, token), exact=True
        ).count

    def search_text(self, *, organization_id, token: str, limit: int) -> list[dict[str, Any]]:
        """Chunks of this organization whose text contains `token` (full-text match, no ranking)."""
        if not organization_id:
            raise ValueError("organization_id is required for text search")
        points, _ = self.client.scroll(
            self.collection,
            scroll_filter=self._text_filter(organization_id, token),
            limit=limit,
            with_payload=True,
            with_vectors=False,
        )
        return [dict(p.payload or {}) for p in points]


def _scope(organization_id, document_id) -> list[models.Condition]:
    return [
        models.FieldCondition(key="organization_id", match=models.MatchValue(value=str(organization_id))),
        models.FieldCondition(key="document_id", match=models.MatchValue(value=str(document_id))),
    ]


@lru_cache(maxsize=1)
def _client() -> QdrantClient:
    if settings.QDRANT_URL == ":memory:":
        return QdrantClient(":memory:")
    return QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=30, check_compatibility=False)


@lru_cache(maxsize=1)
def get_vector_store() -> QdrantVectorStore:
    return QdrantVectorStore(_client(), settings.QDRANT_COLLECTION, settings.EMBEDDING_DIMENSIONS)
