from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.core.exceptions import ServiceError

from . import services
from .models import Membership, MembershipStatus, Organization
from .permissions import Action, IsOrgActionAllowed, OrgContextMixin
from .serializers import (
    AddMemberSerializer,
    ChangeRoleSerializer,
    MembershipSerializer,
    OrganizationSerializer,
)


class OrganizationListCreateView(APIView):
    @extend_schema(responses=OrganizationSerializer(many=True))
    def get(self, request):
        memberships = (
            Membership.objects.filter(user=request.user, status=MembershipStatus.ACTIVE)
            .select_related("organization")
            .order_by("organization__name")
        )
        roles = {m.organization_id: m.role for m in memberships}
        data = OrganizationSerializer([m.organization for m in memberships], many=True, context={"roles": roles}).data
        return Response(data)

    @extend_schema(request=OrganizationSerializer, responses={201: OrganizationSerializer})
    def post(self, request):
        serializer = OrganizationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        org = services.create_organization(user=request.user, name=serializer.validated_data["name"])
        return Response(
            OrganizationSerializer(org, context={"roles": {org.id: "owner"}}).data,
            status=status.HTTP_201_CREATED,
        )


class OrganizationDetailView(OrgContextMixin, APIView):
    permission_classes = [*APIView.permission_classes, IsOrgActionAllowed]

    def get_permissions(self):
        self.required_action = Action.MANAGE_ORG if self.request.method in ("PATCH", "DELETE") else None
        return super().get_permissions()

    @extend_schema(responses=OrganizationSerializer)
    def get(self, request, org_id):
        ctx = {"roles": {self.organization.id: self.membership.role}}
        return Response(OrganizationSerializer(self.organization, context=ctx).data)

    @extend_schema(request=OrganizationSerializer, responses=OrganizationSerializer)
    def patch(self, request, org_id):
        serializer = OrganizationSerializer(self.organization, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @extend_schema(responses={204: None})
    def delete(self, request, org_id):
        from apps.documents.services import purge_organization_data

        purge_organization_data(self.organization)
        Organization.objects.filter(pk=self.organization.pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MemberListCreateView(OrgContextMixin, APIView):
    @extend_schema(responses=MembershipSerializer(many=True))
    def get(self, request, org_id):
        qs = Membership.objects.filter(organization=self.organization).select_related("user").order_by("created_at")
        return Response(MembershipSerializer(qs, many=True).data)

    @extend_schema(request=AddMemberSerializer, responses={201: MembershipSerializer})
    def post(self, request, org_id):
        serializer = AddMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = services.add_member(actor=self.membership, **serializer.validated_data)
        return Response(MembershipSerializer(member).data, status=status.HTTP_201_CREATED)


class MemberDetailView(OrgContextMixin, APIView):
    def _target(self, org_id, membership_id) -> Membership:
        # Scoped to the *validated* organization, never a bare pk lookup.
        try:
            return Membership.objects.select_related("user").get(pk=membership_id, organization=self.organization)
        except Membership.DoesNotExist as exc:
            raise ServiceError("Member not found.", code="not_found", status_code=404) from exc

    @extend_schema(request=ChangeRoleSerializer, responses=MembershipSerializer)
    def patch(self, request, org_id, membership_id):
        serializer = ChangeRoleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        target = self._target(org_id, membership_id)
        updated = services.change_role(actor=self.membership, target=target, role=serializer.validated_data["role"])
        return Response(MembershipSerializer(updated).data)

    @extend_schema(responses={204: None})
    def delete(self, request, org_id, membership_id):
        target = self._target(org_id, membership_id)
        services.remove_member(actor=self.membership, target=target)
        return Response(status=status.HTTP_204_NO_CONTENT)
