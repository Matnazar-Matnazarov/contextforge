"""Upload validation: extension, size, and *content* (never trust the client MIME type)."""

import re
from dataclasses import dataclass

import magic
from django.conf import settings

from apps.core.exceptions import ServiceError

ALLOWED = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".markdown": "text/markdown",
}


@dataclass(frozen=True)
class ValidatedUpload:
    extension: str
    mime_type: str
    display_name: str


_UNSAFE = re.compile(r"[\x00-\x1f\x7f/\\]")


def sanitize_display_name(name: str) -> str:
    """For display only. The storage key never contains the filename."""
    base = _UNSAFE.sub("_", name.replace("\\", "/").split("/")[-1]).strip().strip(".")
    return (base or "document")[:255]


def _reject(message: str, code: str, status_code: int = 400) -> ServiceError:
    return ServiceError(message, code=code, status_code=status_code)


def validate_upload(filename: str, data: bytes) -> ValidatedUpload:
    display = sanitize_display_name(filename or "")
    ext = ("." + display.rsplit(".", 1)[-1].lower()) if "." in display else ""
    if ext not in ALLOWED:
        raise _reject("Unsupported file type. Allowed: PDF, TXT, Markdown.", "unsupported_type", 415)
    if not data:
        raise _reject("File is empty.", "empty_file")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        raise _reject(f"File exceeds the {mb} MB limit.", "file_too_large", 413)

    detected = magic.from_buffer(data[:4096], mime=True)
    if ext == ".pdf":
        if detected != "application/pdf" or not data.startswith(b"%PDF-"):
            raise _reject("File content is not a valid PDF.", "content_mismatch", 415)
    else:
        if not detected.startswith("text/") and detected not in {"application/json", "application/x-empty"}:
            raise _reject("File content is not plain text.", "content_mismatch", 415)
        if b"\x00" in data[:8192]:
            raise _reject("File content is not plain text.", "content_mismatch", 415)
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise _reject("Text files must be UTF-8 encoded.", "bad_encoding", 415) from exc
    return ValidatedUpload(extension=ext, mime_type=ALLOWED[ext], display_name=display)
