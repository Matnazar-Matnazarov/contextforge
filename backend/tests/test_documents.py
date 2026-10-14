import pytest
from django.conf import settings
from rest_framework.test import APIClient

from apps.core.exceptions import ServiceError
from apps.documents import services
from apps.documents.models import Document, DocumentStatus
from apps.documents.storage import StorageError, get_storage
from apps.documents.validation import sanitize_display_name, validate_upload
from apps.rag.vector_store import get_vector_store

from .pdfutil import make_pdf

pytestmark = pytest.mark.django_db


# ------------------------------------------------------------ validation


def test_validate_accepts_supported_types():
    assert validate_upload("a.txt", b"hello").mime_type == "text/plain"
    assert validate_upload("a.md", b"# hi").mime_type == "text/markdown"
    assert validate_upload("a.pdf", make_pdf(["hi"])).mime_type == "application/pdf"


@pytest.mark.parametrize(
    "name,data,code",
    [
        ("a.exe", b"MZ", "unsupported_type"),
        ("a.txt", b"", "empty_file"),
        ("a.pdf", b"this is not a pdf", "content_mismatch"),
        ("a.txt", b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, "content_mismatch"),
        ("a.txt", b"caf\xe9 latin1", "bad_encoding"),
    ],
)
def test_validate_rejects(name, data, code):
    with pytest.raises(ServiceError) as e:
        validate_upload(name, data)
    assert e.value.code == code


def test_validate_rejects_oversize(settings):
    settings.MAX_UPLOAD_BYTES = 10
    with pytest.raises(ServiceError) as e:
        validate_upload("a.txt", b"x" * 11)
    assert e.value.status_code == 413


def test_filename_sanitized_and_never_in_key(make_org, membership_of):
    org, owner = make_org()
    assert sanitize_display_name("../../etc/passwd") == "passwd"
    assert sanitize_display_name("..\\..\\win.txt") == "win.txt"
    doc = services.upload_document(membership=membership_of(org, owner), filename="../../evil.txt", data=b"hello world")
    assert doc.original_filename == "evil.txt"
    assert doc.object_key == f"orgs/{org.id}/documents/{doc.id}.txt"
    assert get_storage().exists(doc.object_key)


# ------------------------------------------------------------ upload API + lifecycle


def test_upload_api_creates_pending_doc_and_enqueues(make_org, make_client, django_capture_on_commit_callbacks):
    org, owner = make_org()
    c = make_client(owner)
    with django_capture_on_commit_callbacks(execute=True):
        r = c.post(
            f"/api/orgs/{org.id}/documents/",
            {"file": _upload("notes.txt", b"alpha beta gamma delta")},
            format="multipart",
        )
    assert r.status_code == 201, r.content
    doc = Document.objects.get(pk=r.json()["id"])
    # CELERY_TASK_ALWAYS_EAGER runs the worker inline on commit
    assert doc.status == DocumentStatus.INDEXED and doc.chunk_count == 1


def _upload(name, data):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, data)


def test_duplicate_upload_rejected(make_org, membership_of):
    org, owner = make_org()
    m = membership_of(org, owner)
    services.upload_document(membership=m, filename="a.txt", data=b"same content here")
    with pytest.raises(ServiceError) as e:
        services.upload_document(membership=m, filename="b.txt", data=b"same content here")
    assert e.value.code == "duplicate_document"


def test_storage_failure_creates_no_record(make_org, membership_of, monkeypatch):
    org, owner = make_org()

    def boom(*a, **k):
        raise StorageError("down")

    monkeypatch.setattr(get_storage(), "put", boom)
    with pytest.raises(ServiceError) as e:
        services.upload_document(membership=membership_of(org, owner), filename="a.txt", data=b"hello there")
    assert e.value.status_code == 503 and Document.objects.count() == 0


def test_db_failure_after_put_cleans_object(make_org, membership_of, monkeypatch):
    org, owner = make_org()

    def boom(*a, **k):
        raise RuntimeError("db down")

    monkeypatch.setattr(Document.objects, "create", boom)
    with pytest.raises(RuntimeError):
        services.upload_document(membership=membership_of(org, owner), filename="a.txt", data=b"hello there")
    keys = [o["Key"] for o in get_storage()._client.list_objects_v2(Bucket="test-bucket").get("Contents", [])]
    assert keys == []


def test_index_creates_vectors_with_full_metadata(make_org, membership_of, index_file):
    org, owner = make_org()
    doc = index_file(membership_of(org, owner), "vacation_policy.md")
    assert doc.status == DocumentStatus.INDEXED and doc.chunk_count >= 1 and doc.indexed_with
    store = get_vector_store()
    assert store.count_document_chunks(organization_id=org.id, document_id=doc.id) == doc.chunk_count
    points, _ = store.client.scroll(store.collection, limit=50, with_payload=True)
    p = points[0].payload
    for key in ("organization_id", "document_id", "chunk_id", "document_name", "page", "text", "embedding_model"):
        assert key in p
    assert p["organization_id"] == str(org.id)


def test_pdf_page_numbers_preserved(make_org, membership_of, index_file):
    org, owner = make_org()
    pdf = make_pdf(["Alpha content on first page about rockets", "Beta content on second page about gardens"])
    doc = index_file(membership_of(org, owner), "r.pdf", pdf)
    assert doc.page_count == 2
    store = get_vector_store()
    pts, _ = store.client.scroll(store.collection, limit=10, with_payload=True)
    pages = {p.payload["page"] for p in pts}
    assert pages == {1, 2}


def test_reindex_is_idempotent_no_duplicate_vectors(make_org, membership_of, index_file):
    org, owner = make_org()
    m = membership_of(org, owner)
    doc = index_file(m, "vacation_policy.md")
    before = get_vector_store().count_document_chunks(organization_id=org.id, document_id=doc.id)
    for _ in range(2):
        Document.objects.filter(pk=doc.pk).update(status=DocumentStatus.PENDING)
        assert services.index_document(doc.id) is True
    assert get_vector_store().count_document_chunks(organization_id=org.id, document_id=doc.id) == before


def test_reindex_removes_stale_tail_chunks(make_org, membership_of, index_file, settings):
    settings.CHUNK_SIZE, settings.CHUNK_OVERLAP = 120, 10
    org, owner = make_org()
    doc = index_file(membership_of(org, owner), "vacation_policy.md")
    many = doc.chunk_count
    settings.CHUNK_SIZE = 5000
    Document.objects.filter(pk=doc.pk).update(status=DocumentStatus.PENDING)
    services.index_document(doc.id)
    doc.refresh_from_db()
    assert doc.chunk_count < many
    assert get_vector_store().count_document_chunks(organization_id=org.id, document_id=doc.id) == doc.chunk_count


def test_indexing_is_skipped_when_already_indexed_or_claimed(make_org, membership_of, index_file):
    org, owner = make_org()
    doc = index_file(membership_of(org, owner), "vacation_policy.md")
    assert services.index_document(doc.id) is False  # indexed
    Document.objects.filter(pk=doc.pk).update(status=DocumentStatus.PROCESSING, processing_started_at=_now())
    assert services.index_document(doc.id) is False  # fresh claim by another worker


def _now():
    from django.utils import timezone

    return timezone.now()


def test_stale_processing_claim_can_be_recovered(make_org, membership_of):
    org, owner = make_org()
    doc = services.upload_document(membership=membership_of(org, owner), filename="a.txt", data=b"hello crash recovery")
    from datetime import timedelta

    Document.objects.filter(pk=doc.pk).update(
        status=DocumentStatus.PROCESSING,
        processing_started_at=_now() - timedelta(seconds=settings.PROCESSING_STALE_SECONDS + 5),
    )
    assert services.index_document(doc.id) is True


def test_permanent_failure_marks_failed_with_message(make_org, membership_of):
    from apps.documents.tasks import index_document_task

    org, owner = make_org()
    doc = services.upload_document(membership=membership_of(org, owner), filename="a.txt", data=b"hello there friend")
    get_storage().delete(doc.object_key)
    index_document_task.apply(args=[str(doc.id)])
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.FAILED and "missing" in doc.error_message


def test_transient_failure_retries_then_succeeds(make_org, membership_of, monkeypatch):
    from apps.documents import tasks

    org, owner = make_org()
    doc = services.upload_document(membership=membership_of(org, owner), filename="a.txt", data=b"hello retry world")
    real = services.get_vector_store().upsert_chunks
    calls = {"n": 0}

    def flaky(**kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise ConnectionError("qdrant down")
        return real(**kw)

    monkeypatch.setattr(services.get_vector_store(), "upsert_chunks", flaky)
    tasks.index_document_task.apply(args=[str(doc.id)])
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.INDEXED and calls["n"] == 2


def test_gives_up_after_max_retries_and_marks_failed(make_org, membership_of, monkeypatch):
    from apps.documents import tasks

    org, owner = make_org()
    doc = services.upload_document(membership=membership_of(org, owner), filename="a.txt", data=b"hello giveup world")

    def always(**kw):
        raise ConnectionError("down")

    monkeypatch.setattr(services.get_vector_store(), "upsert_chunks", always)
    tasks.index_document_task.apply(args=[str(doc.id)])
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.FAILED and "several attempts" in doc.error_message


def test_enqueue_failure_marks_failed_not_indexed(make_org, membership_of, monkeypatch):
    from apps.documents import tasks

    org, owner = make_org()
    doc = services.upload_document(membership=membership_of(org, owner), filename="a.txt", data=b"hello broker down")
    monkeypatch.setattr(tasks.index_document_task, "delay", lambda *a, **k: (_ for _ in ()).throw(OSError("amqp")))
    services.enqueue_indexing(doc.id)
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.FAILED


def test_task_rejects_foreign_object_key(make_org, membership_of):
    org, owner = make_org()
    doc = services.upload_document(membership=membership_of(org, owner), filename="a.txt", data=b"hello tampered")
    Document.objects.filter(pk=doc.pk).update(object_key="orgs/someone-else/documents/x.txt")
    with pytest.raises(services.PermanentIndexError):
        services.index_document(doc.id)
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.FAILED


# ------------------------------------------------------------ retry / delete / download via API


def test_delete_removes_vectors_object_and_row(
    make_org, make_client, membership_of, index_file, django_capture_on_commit_callbacks
):
    org, owner = make_org()
    doc = index_file(membership_of(org, owner), "vacation_policy.md")
    with django_capture_on_commit_callbacks(execute=True):
        r = make_client(owner).delete(f"/api/orgs/{org.id}/documents/{doc.id}/")
    assert r.status_code == 202
    assert not Document.objects.filter(pk=doc.pk).exists()
    assert not get_storage().exists(doc.object_key)
    assert get_vector_store().count_document_chunks(organization_id=org.id, document_id=doc.id) == 0


def test_member_can_only_manage_own_documents(make_org, make_user, make_client, add_member, membership_of, index_file):
    org, owner = make_org()
    member = make_user()
    add_member(org, member)
    doc = index_file(membership_of(org, owner), "vacation_policy.md")
    c = make_client(member)
    assert c.delete(f"/api/orgs/{org.id}/documents/{doc.id}/").status_code == 403
    assert c.post(f"/api/orgs/{org.id}/documents/{doc.id}/reindex/").status_code == 403
    admin = make_user()
    add_member(org, admin, "admin")
    assert make_client(admin).post(f"/api/orgs/{org.id}/documents/{doc.id}/reindex/").status_code == 202


def test_retry_failed_document(make_org, make_client, membership_of, django_capture_on_commit_callbacks):
    org, owner = make_org()
    doc = services.upload_document(membership=membership_of(org, owner), filename="a.txt", data=b"hello retry me")
    Document.objects.filter(pk=doc.pk).update(status=DocumentStatus.FAILED, error_message="boom")
    with django_capture_on_commit_callbacks(execute=True):
        r = make_client(owner).post(f"/api/orgs/{org.id}/documents/{doc.id}/reindex/")
    assert r.status_code == 202
    doc.refresh_from_db()
    assert doc.status == DocumentStatus.INDEXED and doc.error_message == ""


def test_download_streams_with_safe_headers(make_org, make_client, membership_of, index_file):
    org, owner = make_org()
    doc = index_file(membership_of(org, owner), "vacation_policy.md")
    r = make_client(owner).get(f"/api/orgs/{org.id}/documents/{doc.id}/download/")
    assert r.status_code == 200 and b"Vacation" in r.content
    assert r["X-Content-Type-Options"] == "nosniff" and r["Content-Disposition"].startswith("attachment")


# ------------------------------------------------------------ cross-tenant


def test_cross_tenant_document_access_denied(make_org, make_client, membership_of, index_file):
    org_a, owner_a = make_org(name="A")
    org_b, owner_b = make_org(name="B")
    doc = index_file(membership_of(org_a, owner_a), "vacation_policy.md")
    b = make_client(owner_b)
    # 1) B's own org url with A's doc id: not found
    base = f"/api/orgs/{org_b.id}/documents/{doc.id}/"
    assert b.get(base).status_code == 404
    assert b.get(base + "download/").status_code == 404
    assert b.delete(base).status_code == 404
    assert b.post(base + "reindex/").status_code == 404
    # 2) A's org url: B is not a member
    assert b.get(f"/api/orgs/{org_a.id}/documents/{doc.id}/").status_code == 404
    assert b.get(f"/api/orgs/{org_a.id}/documents/{doc.id}/download/").status_code == 404
    assert b.get(f"/api/orgs/{org_b.id}/documents/").json()["count"] == 0
    assert Document.objects.filter(pk=doc.pk).exists()


def test_org_delete_purges_vectors_and_objects(make_org, make_client, membership_of, index_file):
    org, owner = make_org()
    doc = index_file(membership_of(org, owner), "vacation_policy.md")
    key = doc.object_key
    r = make_client(owner).delete(f"/api/orgs/{org.id}/")
    assert r.status_code == 204
    assert not get_storage().exists(key)
    store = get_vector_store()
    pts, _ = store.client.scroll(store.collection, limit=10)
    assert pts == []


def test_list_pagination_shape(make_org, make_client, membership_of, index_file):
    org, owner = make_org()
    index_file(membership_of(org, owner), "vacation_policy.md")
    body = make_client(owner).get(f"/api/orgs/{org.id}/documents/").json()
    assert {"count", "results"} <= body.keys() and body["results"][0]["can_manage"] is True


def test_upload_requires_csrf_when_session_authenticated(make_org, make_user):
    org, owner = make_org()
    c = APIClient(enforce_csrf_checks=True)
    c.force_login(owner)
    r = c.post(f"/api/orgs/{org.id}/documents/", {"file": _upload("a.txt", b"hello csrf")}, format="multipart")
    assert r.status_code == 403
