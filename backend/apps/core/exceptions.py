"""Consistent error envelope: {"error": {"code": str, "message": str, "details": ...}}."""

import logging

from django.core.exceptions import PermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


class ServiceError(Exception):
    """Domain error that maps cleanly onto an HTTP response."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code


def api_exception_handler(exc, context):
    if isinstance(exc, ServiceError):
        return Response({"error": {"code": exc.code, "message": exc.message}}, status=exc.status_code)
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, PermissionDenied):
        exc = exceptions.PermissionDenied()

    response = exception_handler(exc, context)
    if response is None:
        logger.exception("unhandled_exception")
        return Response(
            {"error": {"code": "server_error", "message": "Internal server error."}},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
    if isinstance(exc, exceptions.ValidationError):
        response.data = {"error": {"code": "validation_error", "message": "Invalid input.", "details": response.data}}
    else:
        detail = (
            response.data.get("detail", "Request failed.") if isinstance(response.data, dict) else "Request failed."
        )
        code = getattr(exc, "default_code", "error")
        response.data = {"error": {"code": str(code), "message": str(detail)}}
    return response
