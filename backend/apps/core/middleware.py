import logging
import uuid

logger = logging.getLogger("apps.request")


class RequestIdMiddleware:
    """Attach a request id (for log correlation) and log method/path/status only."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid.uuid4().hex[:12]
        response = self.get_response(request)
        response["X-Request-ID"] = request.request_id
        if not request.path.startswith("/api/health"):
            logger.info(
                "request id=%s method=%s path=%s status=%s",
                request.request_id,
                request.method,
                request.path,
                response.status_code,
            )
        return response
