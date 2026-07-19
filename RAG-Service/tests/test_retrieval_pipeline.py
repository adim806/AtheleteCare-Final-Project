"""Unit tests for retrieval pipeline helpers (no LLM required)."""

from langchain_core.documents import Document

from app.rag_engine import _dedupe_by_source, _format_document_listing, _merge_document_lists


def _doc(source: str, content: str, **meta) -> Document:
    return Document(page_content=content, metadata={"source": source, **meta})


def test_dedupe_by_source_keeps_first_chunk_per_file():
    docs = [
        _doc("a.md", "chunk 1"),
        _doc("a.md", "chunk 2"),
        _doc("b.md", "chunk 3"),
    ]
    result = _dedupe_by_source(docs)

    assert len(result) == 2
    assert result[0].page_content == "chunk 1"
    assert result[1].metadata["source"] == "b.md"


def test_merge_document_lists_preserves_order_and_dedupes():
    list_a = [_doc("a.md", "a"), _doc("b.md", "b")]
    list_b = [_doc("b.md", "b-dup"), _doc("c.md", "c")]

    merged = _merge_document_lists(list_a, list_b)

    assert [d.metadata["source"] for d in merged] == ["a.md", "b.md", "c.md"]


def test_format_document_listing_uses_frontmatter_metadata():
    doc = _doc(
        "case_calf_tear_2024.md",
        "Player reported sudden sharp pain in the posterior lower leg.",
        title="Calf Tear Case – Player #7 (2024)",
        type="case",
        body_region="calf",
        date="2024-03-12",
    )

    listing = _format_document_listing(doc, 1)

    assert listing.startswith("[1] Calf Tear Case – Player #7 (2024)")
    assert "[case/calf, 2024-03-12]" in listing
    assert "Player reported sudden sharp pain" in listing
