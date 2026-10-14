from django.urls import path

from . import views

urlpatterns = [
    path("orgs/<uuid:org_id>/documents/", views.DocumentListCreateView.as_view()),
    path("orgs/<uuid:org_id>/documents/<uuid:document_id>/", views.DocumentDetailView.as_view()),
    path("orgs/<uuid:org_id>/documents/<uuid:document_id>/reindex/", views.DocumentReindexView.as_view()),
    path("orgs/<uuid:org_id>/documents/<uuid:document_id>/download/", views.DocumentDownloadView.as_view()),
]
