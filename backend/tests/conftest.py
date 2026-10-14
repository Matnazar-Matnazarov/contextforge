import json
from pathlib import Path

import pytest
from moto import mock_aws
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.documents import storage as storage_mod
from apps.organizations import services as org_services
from apps.rag import embeddings, vector_store
from apps.rag.llm import LLMAnswer

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _isolated_backends():
    """Fresh in-memory Qdrant and moto S3 for every test."""
    embeddings.get_embedder.cache_clear()
    vector_store._client.cache_clear()
    vector_store.get_vector_store.cache_clear()
    with mock_aws():
        storage_mod.get_storage.cache_clear()
        storage_mod.get_storage().ensure_bucket()
        yield
    storage_mod.get_storage.cache_clear()


@pytest.fixture
def make_user(db):
    counter = iter(range(10_000))

    def _make(email: str | None = None) -> User:
        return User.objects.create_user(
            email=email or f"user{next(counter)}@example.com", password="correct-horse-battery"
        )

    return _make


@pytest.fixture
def make_client():
    def _make(user: User) -> APIClient:
        client = APIClient()
        client.force_authenticate(user)
        return client

    return _make


@pytest.fixture
def make_org(make_user):
    def _make(owner: User | None = None, name: str = "Acme"):
        owner = owner or make_user()
        return org_services.create_organization(user=owner, name=name), owner

    return _make


@pytest.fixture
def add_member(db):
    def _add(org, user, role="member"):
        from apps.organizations.models import Membership

        return Membership.objects.create(organization=org, user=user, role=role)

    return _add


class FakeLLM:
    """Records prompts and returns a scripted answer. Never touches the network."""

    def __init__(self, answer: str = "Answer.", cites: list[str] | None = None, sufficient: bool = True):
        self.answer, self.cites, self.sufficient = answer, cites if cites is not None else ["S1"], sufficient
        self.calls: list[dict] = []

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMAnswer:
        self.calls.append({"system": system_prompt, "user": user_prompt})
        return LLMAnswer(self.answer, self.sufficient, list(self.cites), "fake-model")


@pytest.fixture
def fake_llm():
    return FakeLLM


@pytest.fixture
def index_file(make_org):
    """Upload + index a fixture file synchronously for a membership."""

    from apps.documents import services

    def _index(membership, filename: str, data: bytes | None = None):
        payload = data if data is not None else (FIXTURES / filename).read_bytes()
        doc = services.upload_document(membership=membership, filename=filename, data=payload)
        assert services.index_document(doc.id) is True
        doc.refresh_from_db()
        return doc

    return _index


@pytest.fixture
def eval_questions():
    return json.loads((FIXTURES / "eval_questions.json").read_text())


@pytest.fixture
def membership_of():
    from apps.organizations.models import Membership

    return lambda org, user: Membership.objects.select_related("organization").get(organization=org, user=user)
