import logging

from celery import shared_task
from celery.exceptions import SoftTimeLimitExceeded
from django.conf import settings

from . import services

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=settings.INDEX_MAX_RETRIES, acks_late=True)
def index_document_task(self, document_id: str) -> None:
    """Idempotent: re-running for an indexed/claimed/deleted document is a no-op."""
    try:
        services.index_document(document_id)
    except services.PermanentIndexError as exc:
        logger.warning("index_permanent_failure doc=%s reason=%s", document_id, exc)
        services.mark_failed(document_id, str(exc))
    except (services.TransientIndexError, SoftTimeLimitExceeded) as exc:
        if self.request.retries >= self.max_retries:
            logger.error("index_gave_up doc=%s", document_id)
            services.mark_failed(document_id, "Indexing failed after several attempts. Please retry.")
            return
        services.release_to_pending(document_id)
        raise self.retry(exc=exc, countdown=min(30 * 2**self.request.retries, 300)) from exc


@shared_task(bind=True, max_retries=5, acks_late=True)
def delete_document_task(self, document_id: str) -> None:
    try:
        services.finalize_deletion(document_id)
    except Exception as exc:
        logger.exception("delete_failed doc=%s", document_id)
        raise self.retry(exc=exc, countdown=min(30 * 2**self.request.retries, 300)) from exc
