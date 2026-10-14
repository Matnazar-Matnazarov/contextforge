import logging

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def health(request):
    """Liveness: process is up."""
    return JsonResponse({"status": "ok"})


@require_GET
def ready(request):
    """Readiness: database + vector store reachable."""
    checks: dict[str, str] = {}
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:
        logger.exception("readiness_db_failed")
        checks["database"] = "error"
    try:
        from apps.rag.vector_store import get_vector_store

        get_vector_store().ping()
        checks["qdrant"] = "ok"
    except Exception:
        logger.exception("readiness_qdrant_failed")
        checks["qdrant"] = "error"
    ok = all(v == "ok" for v in checks.values())
    return JsonResponse({"status": "ok" if ok else "degraded", "checks": checks}, status=200 if ok else 503)
