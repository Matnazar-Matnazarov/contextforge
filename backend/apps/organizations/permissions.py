"""Permission matrix (also documented in docs/security.md).

| Action                               | Owner | Admin | Member       |
|--------------------------------------|-------|-------|--------------|
| View org, members                    |  yes  |  yes  | yes          |
| Rename / delete org                  |  yes  |  no   | no           |
| Add member (role=member)             |  yes  |  yes  | no           |
| Add admin / change roles             |  yes  |  no   | no           |
| Remove member (role=member)          |  yes  |  yes  | no           |
| Remove admin / owner                 |  yes  |  no   | no           |
| Upload / view / download documents   |  yes  |  yes  | yes          |
| Delete / re-index document           |  yes  |  yes  | own uploads  |
| Chat, own conversations              |  yes  |  yes  | yes          |
"""

from enum import StrEnum

from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import NotFound
from rest_framework.permissions import BasePermission

from .models import Membership, MembershipStatus, Organization, Role


class Action(StrEnum):
    MANAGE_ORG = "manage_org"
    ADD_MEMBER = "add_member"
    CHANGE_ROLE = "change_role"
    REMOVE_MEMBER = "remove_member"
    UPLOAD_DOCUMENT = "upload_document"
    MANAGE_ANY_DOCUMENT = "manage_any_document"
    CHAT = "chat"


_ALLOWED: dict[Action, set[str]] = {
    Action.MANAGE_ORG: {Role.OWNER},
    Action.ADD_MEMBER: {Role.OWNER, Role.ADMIN},
    Action.CHANGE_ROLE: {Role.OWNER},
    Action.REMOVE_MEMBER: {Role.OWNER, Role.ADMIN},
    Action.UPLOAD_DOCUMENT: {Role.OWNER, Role.ADMIN, Role.MEMBER},
    Action.MANAGE_ANY_DOCUMENT: {Role.OWNER, Role.ADMIN},
    Action.CHAT: {Role.OWNER, Role.ADMIN, Role.MEMBER},
}


def can(membership: Membership, action: Action) -> bool:
    return membership.status == MembershipStatus.ACTIVE and membership.role in _ALLOWED[action]


def can_manage_target_member(actor: Membership, target: Membership) -> bool:
    """Owners manage anyone; admins only plain members."""
    if not can(actor, Action.REMOVE_MEMBER):
        return False
    if actor.role == Role.OWNER:
        return True
    return target.role == Role.MEMBER


def resolve_membership(user, org_id) -> Membership:
    """Trusted org context: active membership of the *authenticated* user, else 404.

    404 (not 403) so non-members cannot probe which organization ids exist.
    """
    try:
        return get_object_or_404(
            Membership.objects.select_related("organization"),
            organization_id=org_id,
            user=user,
            status=MembershipStatus.ACTIVE,
        )
    except Http404 as exc:
        raise NotFound() from exc


class OrgContextMixin:
    """Views mixin: self.membership / self.organization are derived server-side from URL + session."""

    org_url_kwarg = "org_id"
    membership: Membership
    organization: "Organization"

    def check_permissions(self, request):
        # Runs after authentication (request.user is resolved) and before view-level permissions.
        if request.user and request.user.is_authenticated:
            self.membership = resolve_membership(request.user, self.kwargs[self.org_url_kwarg])
            self.organization = self.membership.organization
        super().check_permissions(request)


class IsOrgActionAllowed(BasePermission):
    """Set `required_action` on the view; evaluated against the resolved membership."""

    def has_permission(self, request, view):
        action = getattr(view, "required_action", None)
        if action is None:
            return True
        membership = getattr(view, "membership", None)
        return membership is not None and can(membership, action)
