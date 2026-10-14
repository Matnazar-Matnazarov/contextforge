from django.core.management.base import BaseCommand

from apps.documents.models import Document, DocumentStatus
from apps.documents.services import current_index_signature, enqueue_indexing


class Command(BaseCommand):
    help = "Re-queue documents indexed with a different embedding model or chunking config (or still pending)."

    def handle(self, *args, **options):
        signature = current_index_signature()
        qs = Document.objects.filter(status=DocumentStatus.INDEXED).exclude(indexed_with=signature)
        ids = list(qs.values_list("id", flat=True))
        qs.update(status=DocumentStatus.PENDING)
        pending = list(Document.objects.filter(status=DocumentStatus.PENDING).values_list("id", flat=True))
        for doc_id in set(ids) | set(pending):
            enqueue_indexing(doc_id)
        self.stdout.write(f"queued {len(set(ids) | set(pending))} documents")
