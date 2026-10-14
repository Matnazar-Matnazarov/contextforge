import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


def test_register_login_logout_me():
    c = APIClient()
    r = c.post("/api/auth/register/", {"email": "A@Example.com", "password": "a-long-enough-pass"}, format="json")
    assert r.status_code == 201 and r.json()["email"] == "a@example.com"
    assert c.get("/api/auth/me/").status_code == 200
    assert c.post("/api/auth/logout/").status_code == 204
    assert c.get("/api/auth/me/").status_code in (401, 403)
    r = c.post("/api/auth/login/", {"email": "a@example.com", "password": "a-long-enough-pass"}, format="json")
    assert r.status_code == 200


def test_register_rejects_weak_and_duplicate():
    c = APIClient()
    assert (
        c.post("/api/auth/register/", {"email": "a@example.com", "password": "short"}, format="json").status_code == 400
    )
    c.post("/api/auth/register/", {"email": "a@example.com", "password": "a-long-enough-pass"}, format="json")
    r = APIClient().post(
        "/api/auth/register/", {"email": "A@example.com", "password": "a-long-enough-pass"}, format="json"
    )
    assert r.status_code == 400 and r.json()["error"]["code"] == "validation_error"


def test_login_wrong_password_is_generic():
    c = APIClient()
    c.post("/api/auth/register/", {"email": "a@example.com", "password": "a-long-enough-pass"}, format="json")
    r = APIClient().post("/api/auth/login/", {"email": "a@example.com", "password": "nope-nope-nope"}, format="json")
    assert r.status_code == 400


def test_csrf_enforced_for_session_clients():
    c = APIClient(enforce_csrf_checks=True)
    c.post("/api/auth/register/", {"email": "a@example.com", "password": "a-long-enough-pass"}, format="json")
    # Registration itself is unauthenticated; but an authenticated session POST without token must fail.
    c.post("/api/auth/login/", {"email": "a@example.com", "password": "a-long-enough-pass"}, format="json")
    r = c.post("/api/orgs/", {"name": "X"}, format="json")
    assert r.status_code == 403


def test_unauthenticated_api_denied():
    assert APIClient().get("/api/orgs/").status_code in (401, 403)
