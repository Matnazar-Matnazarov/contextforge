from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import status

from apps.core.exceptions import ServiceError

from .models import Membership, MembershipStatus, Organization, Role
from .permissions import Action, can, can_manage_target_member

User = get_user_model()


@transaction.atomic
def create_organization(*, user, name: str) -> Organization:
    org = Organization.objects.create(name=name.strip(), created_by=user)
    Membership.objects.create(organization=org, user=user, role=Role.OWNER)
    return org


def _active_owner_count(org_id) -> int:
    return Membership.objects.filter(organization_id=org_id, role=Role.OWNER, status=MembershipStatus.ACTIVE).count()


@transaction.atomic
def add_member(*, actor: Membership, email: str, role: str) -> Membership:
    if not can(actor, Action.ADD_MEMBER):
        raise ServiceError("Not allowed.", code="forbidden", status_code=status.HTTP_403_FORBIDDEN)
    if role != Role.MEMBER and not can(actor, Action.CHANGE_ROLE):
        raise ServiceError("Only owners can assign elevated roles.", code="forbidden", status_code=403)
    user = User.objects.filter(email__iexact=email).first()
    if user is None:
        raise ServiceError("No registered user with that email.", code="user_not_found", status_code=404)
    if Membership.objects.filter(organization=actor.organization, user=user).exists():
        raise ServiceError("User is already a member.", code="already_member", status_code=409)
    return Membership.objects.create(organization=actor.organization, user=user, role=role)


@transaction.atomic
def change_role(*, actor: Membership, target: Membership, role: str) -> Membership:
    if not can(actor, Action.CHANGE_ROLE):
        raise ServiceError("Only owners can change roles.", code="forbidden", status_code=403)
    target = Membership.objects.select_for_update().get(pk=target.pk)
    if target.role == Role.OWNER and role != Role.OWNER and _active_owner_count(target.organization_id) <= 1:
        raise ServiceError("Organization needs at least one owner.", code="last_owner", status_code=409)
    target.role = role
    target.save(update_fields=["role", "updated_at"])
    return target


@transaction.atomic
def remove_member(*, actor: Membership, target: Membership) -> None:
    if not can_manage_target_member(actor, target):
        raise ServiceError("Not allowed.", code="forbidden", status_code=403)
    if target.role == Role.OWNER and _active_owner_count(target.organization_id) <= 1:
        raise ServiceError("Organization needs at least one owner.", code="last_owner", status_code=409)
    target.delete()
