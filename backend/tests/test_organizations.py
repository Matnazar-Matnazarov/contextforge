"""Permission matrix + cross-tenant checks for organizations and memberships."""

import pytest

from apps.organizations.models import Membership

pytestmark = pytest.mark.django_db


def test_create_org_makes_creator_owner(make_user, make_client):
    u = make_user()
    r = make_client(u).post("/api/orgs/", {"name": "Acme"}, format="json")
    assert r.status_code == 201 and r.json()["role"] == "owner"
    assert make_client(u).get("/api/orgs/").json()[0]["name"] == "Acme"


def test_non_member_gets_404_not_403(make_org, make_user, make_client):
    org, _ = make_org()
    stranger = make_client(make_user())
    for path in ("", "members/", "documents/", "conversations/"):
        assert stranger.get(f"/api/orgs/{org.id}/{path}").status_code == 404


def test_org_list_only_shows_own(make_org, make_user, make_client):
    make_org(name="A")
    other, owner = make_org(name="B")
    names = [o["name"] for o in make_client(owner).get("/api/orgs/").json()]
    assert names == ["B"]


def test_only_owner_can_rename_and_delete(make_org, make_user, make_client, add_member):
    org, owner = make_org()
    admin, member = make_user(), make_user()
    add_member(org, admin, "admin")
    add_member(org, member, "member")
    for u in (admin, member):
        assert make_client(u).patch(f"/api/orgs/{org.id}/", {"name": "x"}, format="json").status_code == 403
        assert make_client(u).delete(f"/api/orgs/{org.id}/").status_code == 403
    assert make_client(owner).patch(f"/api/orgs/{org.id}/", {"name": "New"}, format="json").status_code == 200


def test_add_member_rules(make_org, make_user, make_client, add_member):
    org, owner = make_org()
    admin, member, newbie = make_user(), make_user(), make_user("new@example.com")
    add_member(org, admin, "admin")
    add_member(org, member, "member")
    url = f"/api/orgs/{org.id}/members/"
    assert make_client(member).post(url, {"email": newbie.email}, format="json").status_code == 403
    # admin may add plain members but not elevated roles
    assert make_client(admin).post(url, {"email": newbie.email, "role": "admin"}, format="json").status_code == 403
    assert make_client(admin).post(url, {"email": newbie.email}, format="json").status_code == 201
    assert make_client(admin).post(url, {"email": newbie.email}, format="json").status_code == 409
    assert make_client(owner).post(url, {"email": "ghost@example.com"}, format="json").status_code == 404


def test_role_changes_owner_only_and_last_owner_protected(make_org, make_user, make_client, add_member):
    org, owner = make_org()
    admin, member = make_user(), make_user()
    ma, mm = add_member(org, admin, "admin"), add_member(org, member, "member")
    mo = Membership.objects.get(organization=org, user=owner)
    # admin cannot self-promote or promote others
    assert (
        make_client(admin).patch(f"/api/orgs/{org.id}/members/{ma.id}/", {"role": "owner"}, format="json").status_code
        == 403
    )
    assert (
        make_client(admin).patch(f"/api/orgs/{org.id}/members/{mm.id}/", {"role": "admin"}, format="json").status_code
        == 403
    )
    assert (
        make_client(owner).patch(f"/api/orgs/{org.id}/members/{mm.id}/", {"role": "admin"}, format="json").status_code
        == 200
    )
    # last owner cannot be demoted or removed
    assert (
        make_client(owner).patch(f"/api/orgs/{org.id}/members/{mo.id}/", {"role": "member"}, format="json").status_code
        == 409
    )
    assert make_client(owner).delete(f"/api/orgs/{org.id}/members/{mo.id}/").status_code == 409


def test_admin_removal_boundaries(make_org, make_user, make_client, add_member):
    org, owner = make_org()
    admin, admin2, member = make_user(), make_user(), make_user()
    add_member(org, admin, "admin")
    ma2 = add_member(org, admin2, "admin")
    mm = add_member(org, member, "member")
    mo = Membership.objects.get(organization=org, user=owner)
    c = make_client(admin)
    assert c.delete(f"/api/orgs/{org.id}/members/{ma2.id}/").status_code == 403
    assert c.delete(f"/api/orgs/{org.id}/members/{mo.id}/").status_code == 403
    assert c.delete(f"/api/orgs/{org.id}/members/{mm.id}/").status_code == 204
    assert (
        make_client(member).delete(f"/api/orgs/{org.id}/members/{ma2.id}/").status_code == 404
    )  # removed -> not a member


def test_cannot_touch_membership_of_another_org(make_org, make_user, make_client):
    org_a, owner_a = make_org(name="A")
    org_b, owner_b = make_org(name="B")
    target = Membership.objects.get(organization=org_b, user=owner_b)
    # owner of A uses A's id in the URL with B's membership id
    r = make_client(owner_a).delete(f"/api/orgs/{org_a.id}/members/{target.id}/")
    assert r.status_code == 404
    assert Membership.objects.filter(pk=target.pk).exists()


def test_duplicate_membership_blocked_by_db(make_org, make_user):
    from django.db import IntegrityError, transaction

    org, owner = make_org()
    with pytest.raises(IntegrityError), transaction.atomic():
        Membership.objects.create(organization=org, user=owner, role="member")


def test_suspended_member_loses_access(make_org, make_user, make_client, add_member):
    org, _ = make_org()
    u = make_user()
    m = add_member(org, u)
    m.status = "suspended"
    m.save()
    assert make_client(u).get(f"/api/orgs/{org.id}/").status_code == 404
