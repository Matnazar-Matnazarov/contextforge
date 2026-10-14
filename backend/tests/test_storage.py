import pytest

from apps.documents.storage import ObjectNotFound, StorageError, get_storage


def test_put_get_exists_delete_roundtrip():
    s = get_storage()
    s.put("orgs/x/a.txt", b"hello", "text/plain")
    assert s.exists("orgs/x/a.txt")
    assert s.get("orgs/x/a.txt") == b"hello"
    s.delete("orgs/x/a.txt")
    assert not s.exists("orgs/x/a.txt")
    s.delete("orgs/x/a.txt")  # idempotent


def test_get_missing_raises_not_found():
    with pytest.raises(ObjectNotFound):
        get_storage().get("nope")


def test_get_enforces_max_bytes():
    s = get_storage()
    s.put("big", b"x" * 100, "text/plain")
    with pytest.raises(StorageError):
        s.get("big", max_bytes=10)


def test_ensure_bucket_is_idempotent():
    get_storage().ensure_bucket()
    get_storage().ensure_bucket()
