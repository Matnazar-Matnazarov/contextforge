from django.urls import path

from . import views

urlpatterns = [
    path("orgs/", views.OrganizationListCreateView.as_view()),
    path("orgs/<uuid:org_id>/", views.OrganizationDetailView.as_view()),
    path("orgs/<uuid:org_id>/members/", views.MemberListCreateView.as_view()),
    path("orgs/<uuid:org_id>/members/<uuid:membership_id>/", views.MemberDetailView.as_view()),
]
