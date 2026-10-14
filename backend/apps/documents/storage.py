"""S3-compatible object storage adapter (SeaweedFS locally). The only module that imports boto3."""

import logging
from functools import lru_cache
from typing import Protocol

import boto3
from botocore.client import Config
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings

logger = logging.getLogger(__name__)


class StorageError(Exception):
    """Transient or unexpected storage failure (safe to retry)."""


class ObjectNotFound(StorageError):
    """The object does not exist (not retryable)."""


class ObjectStorage(Protocol):
    def ensure_bucket(self) -> None: ...
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str, max_bytes: int | None = None) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def delete(self, key: str) -> None: ...


def _is_missing(exc: ClientError) -> bool:
    code = exc.response.get("Error", {}).get("Code", "")
    return code in {"404", "NoSuchKey", "NotFound", "NoSuchBucket"}


class S3ObjectStorage:
    def __init__(self, *, endpoint_url: str, bucket: str, access_key: str, secret_key: str, region: str):
        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            region_name=region,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
                retries={"max_attempts": 3, "mode": "standard"},
                connect_timeout=5,
                read_timeout=30,
            ),
        )

    def ensure_bucket(self) -> None:
        try:
            self._client.head_bucket(Bucket=self.bucket)
        except ClientError as exc:
            if not _is_missing(exc):
                raise StorageError("bucket check failed") from exc
            try:
                self._client.create_bucket(Bucket=self.bucket)
            except (ClientError, BotoCoreError) as exc2:
                raise StorageError("bucket creation failed") from exc2
        except BotoCoreError as exc:
            raise StorageError("storage unreachable") from exc

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
        except (ClientError, BotoCoreError) as exc:
            raise StorageError("upload failed") from exc

    def get(self, key: str, max_bytes: int | None = None) -> bytes:
        try:
            body = self._client.get_object(Bucket=self.bucket, Key=key)["Body"]
            data = body.read(max_bytes + 1 if max_bytes else None)
        except ClientError as exc:
            if _is_missing(exc):
                raise ObjectNotFound(key) from exc
            raise StorageError("download failed") from exc
        except BotoCoreError as exc:
            raise StorageError("download failed") from exc
        if max_bytes and len(data) > max_bytes:
            raise StorageError("object larger than allowed size")
        return data

    def exists(self, key: str) -> bool:
        try:
            self._client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if _is_missing(exc):
                return False
            raise StorageError("existence check failed") from exc
        except BotoCoreError as exc:
            raise StorageError("existence check failed") from exc

    def delete(self, key: str) -> None:
        """Idempotent: deleting a missing key succeeds (S3 semantics)."""
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except (ClientError, BotoCoreError) as exc:
            raise StorageError("delete failed") from exc


@lru_cache(maxsize=1)
def get_storage() -> ObjectStorage:
    return S3ObjectStorage(
        endpoint_url=settings.S3_ENDPOINT_URL,
        bucket=settings.S3_BUCKET,
        access_key=settings.S3_ACCESS_KEY,
        secret_key=settings.S3_SECRET_KEY,
        region=settings.S3_REGION,
    )
