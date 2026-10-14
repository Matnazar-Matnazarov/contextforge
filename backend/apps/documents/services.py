"""Document lifecycle: upload, indexing, retry, deletion.

PostgreSQL, SeaweedFS and Qdrant cannot share a transaction, so each step is ordered so that a crash
leaves a *detectable* state (never a false "indexed"):

upload   : validate -> put object -> insert row(pending) -> commit -> enqueue.
           Crash after put / before insert leaves an orphan object (no row, harmless, documented).
index    : claim(processing) -> read object -> parse -> embed -> upsert vectors (deterministic ids)
           -> mark indexed only after Qdrant confirms. Crash leaves "processing"; stale claims are
           re-claimable after PROCESSING_STALE_SECONDS.
delete   : mark deleting (immediately invisible to retrieval) -> delete vectors -> delete object -> delete row.
"""

import hashlib
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.exceptions import ServiceError
from apps.organizations.models import Membership, Organization
from apps.organizations.permissions import Action, can
from apps.rag.embeddings import get_embedder
from apps.rag.vector_store import ChunkPoint, get_vector_store

from .chunking import chunk_segments
from .models import Document, DocumentStatus
from .parsing import ParseError, extract_segments
from .storage import ObjectNotFound, StorageError, get_storage
from .validation import validate_upload

logger = logging.getLogger(__name__)


class TransientIndexError(Exception):
    """Retryable (network, storage, vector store, embedding runtime)."""


class PermanentIndexError(Exception):
    """Retrying cannot help (corrupt/unsupported file, missing object)."""


def current_index_signature() -> str:
    return f"{get_embedder().model_name}|size={settings.CHUNK_SIZE}|overlap={settings.CHUNK_OVERLAP}"


def object_key_for(organization_id, document_id, extension: str) -> str:
    return f"orgs/{organization_id}/documents/{document_id}{extension}"


def can_manage_document(membership: Membership, document: Document) -> bool:
    if document.organization_id != membership.organization_id:
        return False
    return can(membership, Action.MANAGE_ANY_DOCUMENT) or document.uploaded_by_id == membership.user_id


# ---------------------------------------------------------------- upload


def upload_document(*, membership: Membership, filename: str, data: bytes) -> Document:
    if not can(membership, Action.UPLOAD_DOCUMENT):
        raise ServiceError("Not allowed.", code="forbidden", status_code=403)
    validated = validate_upload(filename, data)
    checksum = hashlib.sha256(data).hexdigest()
    org = membership.organization

    existing = Document.objects.filter(organization=org, checksum_sha256=checksum).first()
    if existing:
        raise ServiceError(
            f"This file was already uploaded as '{existing.original_filename}'.",
            code="duplicate_document",
            status_code=409,
        )

    doc_id = uuid.uuid4()
    key = object_key_for(org.id, doc_id, validated.extension)
    storage = get_storage()
    try:
        storage.put(key, data, validated.mime_type)
    except StorageError as exc:
        logger.error("upload_storage_failed org=%s", org.id)
        raise ServiceError(
            "Storage is unavailable. Try again later.", code="storage_unavailable", status_code=503
        ) from exc

    try:
        document = Document.objects.create(
            id=doc_id,
            organization=org,
            uploaded_by=membership.user,
            original_filename=validated.display_name,
            object_key=key,
            mime_type=validated.mime_type,
            size_bytes=len(data),
            checksum_sha256=checksum,
        )
    except IntegrityError as exc:
        _best_effort_delete_object(key)
        raise ServiceError("This file was already uploaded.", code="duplicate_document", status_code=409) from exc
    except Exception:
        _best_effort_delete_object(key)
        raise

    transaction.on_commit(lambda: enqueue_indexing(document.id))
    logger.info("document_uploaded org=%s doc=%s size=%s", org.id, document.id, document.size_bytes)
    return document


def _best_effort_delete_object(key: str) -> None:
    try:
        get_storage().delete(key)
    except StorageError:
        logger.warning("orphan_object_left key=%s", key)


def enqueue_indexing(document_id) -> None:
    from .tasks import index_document_task

    try:
        index_document_task.delay(str(document_id))
    except Exception:
        logger.exception("enqueue_failed doc=%s", document_id)
        mark_failed(document_id, "Indexing queue unavailable. Use retry once the service is back.", force=True)


# ---------------------------------------------------------------- indexing


def _is_stale(document: Document) -> bool:
    started = document.processing_started_at
    return started is None or timezone.now() - started > timedelta(seconds=settings.PROCESSING_STALE_SECONDS)


def claim_for_processing(document_id) -> Document | None:
    with transaction.atomic():
        doc = Document.objects.select_for_update().filter(pk=document_id).first()
        if doc is None or doc.status in (DocumentStatus.INDEXED, DocumentStatus.DELETING):
            return None
        if doc.status == DocumentStatus.PROCESSING and not _is_stale(doc):
            return None
        doc.status = DocumentStatus.PROCESSING
        doc.processing_started_at = timezone.now()
        doc.attempts += 1
        doc.error_message = ""
        doc.save(update_fields=["status", "processing_started_at", "attempts", "error_message", "updated_at"])
        return doc


def mark_failed(document_id, message: str, *, force: bool = False) -> None:
    allowed = [DocumentStatus.PROCESSING] if not force else [DocumentStatus.PROCESSING, DocumentStatus.PENDING]
    Document.objects.filter(pk=document_id, status__in=allowed).update(
        status=DocumentStatus.FAILED, error_message=message[:500], updated_at=timezone.now()
    )


def release_to_pending(document_id) -> None:
    Document.objects.filter(pk=document_id, status=DocumentStatus.PROCESSING).update(
        status=DocumentStatus.PENDING, updated_at=timezone.now()
    )


def index_document(document_id) -> bool:
    """Index one document. Returns True if work was done, False if skipped (already done/claimed/deleted).

    The task carries only the id. Organization, object key and filename all come from the DB row.
    """
    doc = claim_for_processing(document_id)
    if doc is None:
        logger.info("index_skipped doc=%s", document_id)
        return False

    org_id = doc.organization_id
    if not doc.object_key.startswith(f"orgs/{org_id}/"):
        mark_failed(doc.id, "Storage key does not belong to the document's organization.")
        raise PermanentIndexError("object key / organization mismatch")

    try:
        data = get_storage().get(doc.object_key, max_bytes=settings.MAX_UPLOAD_BYTES)
    except ObjectNotFound as exc:
        raise PermanentIndexError("Original file is missing from storage.") from exc
    except StorageError as exc:
        raise TransientIndexError("storage read failed") from exc

    if hashlib.sha256(data).hexdigest() != doc.checksum_sha256:
        raise PermanentIndexError("Stored file does not match its recorded checksum.")

    extension = "." + doc.object_key.rsplit(".", 1)[-1]
    try:
        segments, page_count = extract_segments(data, extension)
    except ParseError as exc:
        raise PermanentIndexError(str(exc)) from exc

    chunks = chunk_segments(segments, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
    if not chunks:
        raise PermanentIndexError("No extractable text found.")

    embedder = get_embedder()
    store = get_vector_store()
    try:
        vectors = embedder.embed_documents([c.text for c in chunks])
        store.ensure_collection()
        store.upsert_chunks(
            organization_id=org_id,
            document_id=doc.id,
            document_name=doc.original_filename,
            embedding_model=embedder.model_name,
            chunks=[
                ChunkPoint(chunk_index=c.index, vector=v, text=c.text, page=c.page, section=c.section)
                for c, v in zip(chunks, vectors, strict=True)
            ],
        )
        store.delete_stale_chunks(organization_id=org_id, document_id=doc.id, keep_below=len(chunks))
    except Exception as exc:
        raise TransientIndexError("embedding or vector store failure") from exc

    with transaction.atomic():
        fresh = Document.objects.select_for_update().get(pk=doc.pk)
        if fresh.status != DocumentStatus.PROCESSING:
            # Deleted (or reset) while we worked: do not claim success; undo what we wrote if deleting.
            if fresh.status == DocumentStatus.DELETING:
                store.delete_document(organization_id=org_id, document_id=doc.id)
            return False
        fresh.status = DocumentStatus.INDEXED
        fresh.chunk_count = len(chunks)
        fresh.page_count = page_count
        fresh.indexed_with = current_index_signature()
        fresh.indexed_at = timezone.now()
        fresh.error_message = ""
        fresh.save()
    logger.info("document_indexed org=%s doc=%s chunks=%s", org_id, doc.id, len(chunks))
    return True


# ---------------------------------------------------------------- retry / delete


def request_reindex(*, membership: Membership, document: Document) -> Document:
    if not can_manage_document(membership, document):
        raise ServiceError("Not allowed.", code="forbidden", status_code=403)
    with transaction.atomic():
        doc = Document.objects.select_for_update().get(pk=document.pk)
        if doc.status == DocumentStatus.DELETING:
            raise ServiceError("Document is being deleted.", code="invalid_state", status_code=409)
        if doc.status == DocumentStatus.PROCESSING and not _is_stale(doc):
            raise ServiceError("Document is already being processed.", code="invalid_state", status_code=409)
        doc.status = DocumentStatus.PENDING
        doc.error_message = ""
        doc.save(update_fields=["status", "error_message", "updated_at"])
        transaction.on_commit(lambda: enqueue_indexing(doc.id))
    return doc


def request_deletion(*, membership: Membership, document: Document) -> None:
    if not can_manage_document(membership, document):
        raise ServiceError("Not allowed.", code="forbidden", status_code=403)
    with transaction.atomic():
        Document.objects.filter(pk=document.pk).update(status=DocumentStatus.DELETING, updated_at=timezone.now())
        transaction.on_commit(lambda: _enqueue_deletion(document.id))


def _enqueue_deletion(document_id) -> None:
    from .tasks import delete_document_task

    try:
        delete_document_task.delay(str(document_id))
    except Exception:
        logger.exception("enqueue_delete_failed doc=%s", document_id)


def finalize_deletion(document_id) -> bool:
    doc = Document.objects.filter(pk=document_id, status=DocumentStatus.DELETING).first()
    if doc is None:
        return False
    get_vector_store().delete_document(organization_id=doc.organization_id, document_id=doc.id)
    get_storage().delete(doc.object_key)
    doc.delete()
    logger.info("document_deleted org=%s doc=%s", doc.organization_id, document_id)
    return True


def purge_organization_data(organization: Organization) -> None:
    """Remove vectors and objects for a whole tenant before its rows are cascade-deleted."""
    try:
        get_vector_store().delete_organization(organization_id=organization.id)
        storage = get_storage()
        for key in organization.documents.values_list("object_key", flat=True):
            storage.delete(key)
    except Exception as exc:
        logger.exception("org_purge_failed org=%s", organization.id)
        raise ServiceError(
            "Could not clean up organization data. Nothing was deleted.", code="cleanup_failed", status_code=502
        ) from exc


def read_original(document: Document) -> bytes:
    try:
        return get_storage().get(document.object_key, max_bytes=settings.MAX_UPLOAD_BYTES)
    except ObjectNotFound as exc:
        raise ServiceError("Original file is missing.", code="file_missing", status_code=404) from exc
    except StorageError as exc:
        raise ServiceError("Storage is unavailable.", code="storage_unavailable", status_code=503) from exc
