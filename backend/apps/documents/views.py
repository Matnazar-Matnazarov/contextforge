from django.http import HttpResponse
from drf_spectacular.utils import OpenApiTypes, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ServiceError
from apps.organizations.permissions import OrgContextMixin

from . import services
from .models import Document, DocumentStatus
from .serializers import DocumentSerializer, UploadSerializer


class _DocScoped(OrgContextMixin):
    def get_document(self, document_id) -> Document:
        # Always scoped by the validated organization: a foreign id behaves exactly like a missing one.
        doc = (
            Document.objects.select_related("uploaded_by")
            .filter(pk=document_id, organization=self.organization)
            .first()
        )
        if doc is None or doc.status == DocumentStatus.DELETING:
            raise ServiceError("Document not found.", code="not_found", status_code=404)
        return doc

    def ser_ctx(self):
        return {"membership": self.membership, "request": self.request}


class DocumentListCreateView(_DocScoped, ListAPIView):
    serializer_class = DocumentSerializer
    parser_classes = [MultiPartParser]

    def get_throttles(self):
        if self.request.method == "POST":
            self.throttle_scope = "upload"
        return super().get_throttles()

    def get_queryset(self):
        qs = Document.objects.filter(organization=self.organization).exclude(status=DocumentStatus.DELETING)
        status_filter = self.request.query_params.get("status")
        if status_filter in DocumentStatus.values:
            qs = qs.filter(status=status_filter)
        return qs.select_related("uploaded_by")

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "membership": self.membership}

    @extend_schema(request={"multipart/form-data": UploadSerializer}, responses={201: DocumentSerializer})
    def post(self, request, org_id):
        serializer = UploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        upload = serializer.validated_data["file"]
        from django.conf import settings

        if upload.size > settings.MAX_UPLOAD_BYTES:  # reject before reading into memory
            raise ServiceError("File exceeds the size limit.", code="file_too_large", status_code=413)
        doc = services.upload_document(membership=self.membership, filename=upload.name, data=upload.read())
        return Response(DocumentSerializer(doc, context=self.ser_ctx()).data, status=status.HTTP_201_CREATED)


class DocumentDetailView(_DocScoped, APIView):
    @extend_schema(responses=DocumentSerializer)
    def get(self, request, org_id, document_id):
        doc = self.get_document(document_id)
        return Response(DocumentSerializer(doc, context=self.ser_ctx()).data)

    @extend_schema(responses={202: None})
    def delete(self, request, org_id, document_id):
        services.request_deletion(membership=self.membership, document=self.get_document(document_id))
        return Response(status=status.HTTP_202_ACCEPTED)


class DocumentReindexView(_DocScoped, APIView):
    @extend_schema(request=None, responses={202: DocumentSerializer})
    def post(self, request, org_id, document_id):
        doc = services.request_reindex(membership=self.membership, document=self.get_document(document_id))
        return Response(DocumentSerializer(doc, context=self.ser_ctx()).data, status=status.HTTP_202_ACCEPTED)


class DocumentDownloadView(_DocScoped, APIView):
    """Backend-mediated download: auth + org check, then stream bytes. No storage URL ever reaches the browser."""

    @extend_schema(responses={200: OpenApiTypes.BINARY})
    def get(self, request, org_id, document_id):
        doc = self.get_document(document_id)
        data = services.read_original(doc)
        response = HttpResponse(data, content_type=doc.mime_type)
        safe_name = doc.original_filename.encode("ascii", "replace").decode().replace('"', "")
        response["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "private, no-store"
        return response
