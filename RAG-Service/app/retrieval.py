"""Retrieval helpers: metadata filter, dedupe by document id, protocol diversity."""

from __future__ import annotations

from langchain_core.documents import Document

MAX_RESULTS = 3


def dedupe_by_document_id(
    docs_with_relevance: list[tuple[Document, float]],
) -> list[tuple[Document, float]]:
    """Keep the highest-scoring chunk per parent document id."""
    best: dict[str, tuple[Document, float]] = {}
    for doc, relevance in docs_with_relevance:
        doc_id = str(doc.metadata.get("id") or "")
        if not doc_id:
            doc_id = doc.page_content[:80]
        prev = best.get(doc_id)
        if prev is None or relevance > prev[1]:
            best[doc_id] = (doc, relevance)
    return sorted(best.values(), key=lambda pair: pair[1], reverse=True)


def select_diverse_top_k(
    docs_with_relevance: list[tuple[Document, float]],
    k: int = MAX_RESULTS,
) -> list[tuple[Document, float]]:
    """
    Prefer one protocol (if present) plus highest-relevance cases/policies.

    Avoids returning three case chunks when a protocol exists for the injury type.
    """
    unique = dedupe_by_document_id(docs_with_relevance)
    if len(unique) <= k:
        return unique

    protocols = [pair for pair in unique if pair[0].metadata.get("type") == "protocol"]
    non_protocols = [pair for pair in unique if pair[0].metadata.get("type") != "protocol"]

    selected: list[tuple[Document, float]] = []
    if protocols:
        selected.append(protocols[0])
    for pair in non_protocols:
        if len(selected) >= k:
            break
        selected.append(pair)
    for pair in unique:
        if len(selected) >= k:
            break
        if pair not in selected:
            selected.append(pair)
    return selected[:k]
