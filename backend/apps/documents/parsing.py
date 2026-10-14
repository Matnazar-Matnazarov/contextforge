"""Text extraction. Returns segments that carry page/section provenance."""

import io
import re
import unicodedata
from dataclasses import dataclass

from django.conf import settings
from pypdf import PdfReader
from pypdf.errors import PyPdfError


class ParseError(Exception):
    """Permanent parse failure; retrying will not help."""


@dataclass(frozen=True)
class Segment:
    text: str
    page: int | None = None
    section: str | None = None


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def normalize_text(text: str) -> str:
    """Unicode NFC, unified newlines, no NULs/trailing spaces, at most one blank line in a row.

    Indentation, list markers and code fences are left untouched.
    """
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = "\n".join(line.rstrip() for line in text.split("\n"))
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _parse_pdf(data: bytes) -> tuple[list[Segment], int]:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ParseError("PDF is encrypted.")
        total = len(reader.pages)
        if total > settings.MAX_PDF_PAGES:
            raise ParseError(f"PDF has more than {settings.MAX_PDF_PAGES} pages.")
        segments = []
        for number, page in enumerate(reader.pages, start=1):
            text = normalize_text(page.extract_text() or "")
            if text:
                segments.append(Segment(text=text, page=number))
        return segments, total
    except ParseError:
        raise
    except (PyPdfError, ValueError, KeyError, OSError, RecursionError) as exc:
        raise ParseError("PDF could not be parsed.") from exc


def _parse_markdown(text: str) -> list[Segment]:
    segments: list[Segment] = []
    heading: str | None = None
    buf: list[str] = []
    in_fence = False

    def flush() -> None:
        body = normalize_text("\n".join(buf))
        if body:
            segments.append(Segment(text=body, section=heading))
        buf.clear()

    for line in text.split("\n"):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        m = None if in_fence else _HEADING.match(line)
        if m:
            flush()
            heading = m.group(2)
        buf.append(line)
    flush()
    return segments


def extract_segments(data: bytes, extension: str) -> tuple[list[Segment], int | None]:
    """Return (segments, page_count). Raises ParseError if no text could be extracted."""
    page_count = None
    if extension == ".pdf":
        segments, page_count = _parse_pdf(data)
    else:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ParseError("File is not valid UTF-8.") from exc
        if extension in (".md", ".markdown"):
            segments = _parse_markdown(text)
        else:
            body = normalize_text(text)
            segments = [Segment(text=body)] if body else []
    if not segments:
        raise ParseError("No extractable text found (scanned PDFs are not supported).")
    return segments, page_count
