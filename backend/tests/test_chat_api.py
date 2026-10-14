import pytest

from apps.chat import services as chat_services
from apps.chat.models import Citation, Conversation, Message
from apps.rag.llm import LLMError

pytestmark = pytest.mark.django_db
Q = "How many days of annual leave do full-time employees get?"


@pytest.fixture
def setup(make_org, membership_of, index_file, make_client):
    org, owner = make_org()
    doc = index_file(membership_of(org, owner), "vacation_policy.md")
    return org, owner, doc, make_client(owner)


def _patch_llm(monkeypatch, llm):
    from apps.rag import pipeline

    monkeypatch.setattr(pipeline, "get_llm", lambda: llm)


def test_ask_persists_messages_and_citations(setup, monkeypatch, fake_llm):
    org, owner, doc, c = setup
    _patch_llm(monkeypatch, fake_llm("25 days.", cites=["S1"]))
    conv = c.post(f"/api/orgs/{org.id}/conversations/", {}, format="json").json()
    r = c.post(f"/api/orgs/{org.id}/conversations/{conv['id']}/messages/", {"question": Q}, format="json")
    assert r.status_code == 201, r.content
    body = r.json()["assistant_message"]
    assert body["content"] == "25 days." and not body["insufficient_context"]
    cit = body["citations"][0]
    assert cit["document_id"] == str(doc.id) and cit["document_title"] == "vacation_policy.md"
    assert "25 days" in cit["excerpt"] and "score" in cit and cit["score"] is None  # score hidden outside DEBUG
    msgs = c.get(f"/api/orgs/{org.id}/conversations/{conv['id']}/messages/").json()
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert c.get(f"/api/orgs/{org.id}/conversations/").json()["results"][0]["title"].startswith("How many days")


def test_no_evidence_returns_insufficient_without_llm(setup, monkeypatch, fake_llm):
    org, _, _, c = setup
    llm = fake_llm()
    _patch_llm(monkeypatch, llm)
    conv = c.post(f"/api/orgs/{org.id}/conversations/", {}, format="json").json()
    r = c.post(
        f"/api/orgs/{org.id}/conversations/{conv['id']}/messages/",
        {"question": "Quantum gauge lattice?"},
        format="json",
    )
    m = r.json()["assistant_message"]
    assert m["insufficient_context"] and m["citations"] == [] and llm.calls == []


def test_llm_failure_is_502_and_nothing_persisted(setup, monkeypatch):
    org, owner, _, c = setup

    class Boom:
        def generate(self, **kw):
            raise LLMError("secret internals")

    _patch_llm(monkeypatch, Boom())
    conv = c.post(f"/api/orgs/{org.id}/conversations/", {}, format="json").json()
    r = c.post(f"/api/orgs/{org.id}/conversations/{conv['id']}/messages/", {"question": Q}, format="json")
    assert r.status_code == 502 and "secret" not in r.content.decode()
    assert Message.objects.count() == 0


def test_missing_api_key_is_handled(setup):
    org, _, _, c = setup
    conv = c.post(f"/api/orgs/{org.id}/conversations/", {}, format="json").json()
    r = c.post(f"/api/orgs/{org.id}/conversations/{conv['id']}/messages/", {"question": Q}, format="json")
    assert r.status_code == 502 and r.json()["error"]["code"] == "llm_unavailable"


def test_question_validation(setup):
    org, _, _, c = setup
    conv = c.post(f"/api/orgs/{org.id}/conversations/", {}, format="json").json()
    url = f"/api/orgs/{org.id}/conversations/{conv['id']}/messages/"
    assert c.post(url, {"question": "   "}, format="json").status_code == 400
    assert c.post(url, {"question": "x" * 5000}, format="json").status_code == 400


def test_conversations_are_private_to_owner_even_within_org(
    setup, make_user, make_client, add_member, monkeypatch, fake_llm
):
    org, owner, _, c = setup
    other = make_user()
    add_member(org, other)
    oc = make_client(other)
    conv = c.post(f"/api/orgs/{org.id}/conversations/", {}, format="json").json()
    base = f"/api/orgs/{org.id}/conversations/{conv['id']}/"
    assert oc.get(base).status_code == 404
    assert oc.get(base + "messages/").status_code == 404
    assert oc.post(base + "messages/", {"question": Q}, format="json").status_code == 404
    assert oc.delete(base).status_code == 404
    assert oc.get(f"/api/orgs/{org.id}/conversations/").json()["count"] == 0


def test_cross_tenant_conversation_and_citation_isolation(setup, make_org, make_client, monkeypatch, fake_llm):
    org_a, owner_a, doc_a, ca = setup
    _patch_llm(monkeypatch, fake_llm("25 days.", cites=["S1"]))
    conv = ca.post(f"/api/orgs/{org_a.id}/conversations/", {}, format="json").json()
    ca.post(f"/api/orgs/{org_a.id}/conversations/{conv['id']}/messages/", {"question": Q}, format="json")

    org_b, owner_b = make_org(name="B")
    cb = make_client(owner_b)
    # B cannot read A's conversation via either org id
    for oid in (org_a.id, org_b.id):
        assert cb.get(f"/api/orgs/{oid}/conversations/{conv['id']}/messages/").status_code == 404
    # B's own conversation + same question never surfaces A's document
    conv_b = cb.post(f"/api/orgs/{org_b.id}/conversations/", {}, format="json").json()
    r = cb.post(f"/api/orgs/{org_b.id}/conversations/{conv_b['id']}/messages/", {"question": Q}, format="json")
    m = r.json()["assistant_message"]
    assert m["insufficient_context"] and m["citations"] == []
    assert "25 days" not in m["content"]


def test_service_level_guard_rejects_foreign_conversation(setup, make_org, membership_of):
    org_a, owner_a, _, _ = setup
    org_b, owner_b = make_org(name="B")
    conv = Conversation.objects.create(organization=org_a, owner=owner_a)
    from apps.core.exceptions import ServiceError

    with pytest.raises(ServiceError) as e:
        chat_services.ask(membership=membership_of(org_b, owner_b), conversation=conv, question=Q)
    assert e.value.status_code == 404


def test_citations_survive_document_deletion(setup, monkeypatch, fake_llm):
    org, owner, doc, c = setup
    _patch_llm(monkeypatch, fake_llm("25 days.", cites=["S1"]))
    conv = c.post(f"/api/orgs/{org.id}/conversations/", {}, format="json").json()
    c.post(f"/api/orgs/{org.id}/conversations/{conv['id']}/messages/", {"question": Q}, format="json")
    doc.delete()
    cit = Citation.objects.get()
    assert cit.document is None and cit.document_title == "vacation_policy.md" and cit.excerpt
