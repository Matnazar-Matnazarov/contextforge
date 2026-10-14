import pytest

from apps.documents.chunking import chunk_segments, split_text
from apps.documents.parsing import ParseError, Segment, extract_segments, normalize_text


def test_split_respects_size_and_overlap():
    text = ("Sentence number one is here. " * 80).strip()
    pieces = split_text(text, 200, 40)
    assert len(pieces) > 5
    assert all(len(p) <= 200 for p in pieces)
    # consecutive chunks overlap
    assert any(pieces[i][-15:] in pieces[i + 1] for i in range(len(pieces) - 1))
    # nothing is lost: every word of the source appears somewhere
    assert set(text.split()) <= set(" ".join(pieces).split())


def test_split_short_text_single_chunk():
    assert split_text("hello world", 1000, 100) == ["hello world"]


def test_split_always_terminates_without_spaces():
    pieces = split_text("x" * 1000, 100, 20)
    assert "".join(pieces).count("x") >= 1000
    assert len(pieces) < 20


@pytest.mark.parametrize("size,overlap", [(0, 0), (100, 100), (100, -1)])
def test_split_rejects_bad_config(size, overlap):
    with pytest.raises(ValueError):
        split_text("abc", size, overlap)


def test_chunks_keep_page_and_section_metadata():
    segs = [Segment("alpha " * 100, page=1), Segment("beta " * 100, page=2), Segment("gamma", section="Intro")]
    chunks = chunk_segments(segs, 200, 20)
    assert [c.index for c in chunks] == list(range(len(chunks)))
    assert {c.page for c in chunks if "alpha" in c.text} == {1}
    assert {c.page for c in chunks if "beta" in c.text} == {2}
    assert chunks[-1].section == "Intro" and chunks[-1].page is None


def test_normalize_preserves_structure():
    out = normalize_text("Title\r\n\r\n\r\n\r\n  - item  \r\n    code\x00 line")
    assert out == "Title\n\n  - item\n    code line"


def test_markdown_sections_and_code_fences():
    md = b"# Top\ntext a\n```\n# not a heading\n```\n## Sub\ntext b\n"
    segs, pages = extract_segments(md, ".md")
    assert pages is None
    assert [s.section for s in segs] == ["Top", "Sub"]
    assert "# not a heading" in segs[0].text


def test_empty_text_raises():
    with pytest.raises(ParseError):
        extract_segments(b"   \n  ", ".txt")


def test_corrupt_pdf_raises_parse_error():
    with pytest.raises(ParseError):
        extract_segments(b"%PDF-1.4 garbage", ".pdf")
