from django.urls import path

from . import views

urlpatterns = [
    path("orgs/<uuid:org_id>/conversations/", views.ConversationListCreateView.as_view()),
    path("orgs/<uuid:org_id>/conversations/<uuid:conversation_id>/", views.ConversationDetailView.as_view()),
    path("orgs/<uuid:org_id>/conversations/<uuid:conversation_id>/messages/", views.MessageListCreateView.as_view()),
]
