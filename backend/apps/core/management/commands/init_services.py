from django.core.management.base import BaseCommand

from apps.documents.storage import get_storage
from apps.rag.vector_store import get_vector_store


class Command(BaseCommand):
    help = "Idempotently create the S3 bucket and Qdrant collection/payload indexes."

    def handle(self, *args, **options):
        get_storage().ensure_bucket()
        self.stdout.write("bucket ok")
        get_vector_store().ensure_collection()
        self.stdout.write("qdrant collection ok")
