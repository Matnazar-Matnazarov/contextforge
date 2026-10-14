"""Overlapping character-window chunker that prefers natural boundaries."""

from dataclasses import dataclass

from .parsing import Segment


@dataclass(frozen=True)
class Chunk:
    index: int
    text: str
    page: int | None
    section: str | None


_BREAKS = ("\n\n", "\n", ". ", "? ", "! ", "; ", ", ", " ")


def split_text(text: str, size: int, overlap: int) -> list[str]:
    if size <= 0:
        raise ValueError("chunk size must be positive")
    if not 0 <= overlap < size:
        raise ValueError("overlap must be >= 0 and < chunk size")
    pieces: list[str] = []
    start, n = 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            window_floor = start + size // 2
            for sep in _BREAKS:
                pos = text.rfind(sep, window_floor, end)
                if pos != -1:
                    end = pos + len(sep)
                    break
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= n:
            break
        nxt = end - overlap
        start = nxt if nxt > start else end
    return pieces


def chunk_segments(segments: list[Segment], size: int, overlap: int) -> list[Chunk]:
    """Chunks never span segments, so page/section provenance stays exact."""
    chunks: list[Chunk] = []
    for seg in segments:
        for piece in split_text(seg.text, size, overlap):
            chunks.append(Chunk(index=len(chunks), text=piece, page=seg.page, section=seg.section))
    return chunks
