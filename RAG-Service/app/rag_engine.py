"""Core RAG engine: hybrid retrieval (ChromaDB + BM25) and Llama.cpp generation."""

from __future__ import annotations

import json
import logging
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_community.llms import LlamaCpp
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_huggingface import HuggingFaceEmbeddings
from sentence_transformers import CrossEncoder

try:
    from langchain.retrievers import EnsembleRetriever
except ImportError:  # LangChain 1.0+
    from langchain_classic.retrievers import EnsembleRetriever

from app.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    DATA_DIR,
    ENABLE_METADATA_FILTERING,
    ENABLE_RERANKING,
    ENSEMBLE_WEIGHTS,
    EMBED_MODEL_NAME,
    FINAL_TOP_K,
    INSIGHT_MIN_LENGTH,
    LLAMA_CHAT_FORMAT,
    LLAMA_MAX_TOKENS,
    LLAMA_N_CTX,
    LLAMA_N_GPU_LAYERS,
    LLAMA_N_THREADS,
    LLAMA_TEMPERATURE,
    LLAMA_VERBOSE,
    LLM_GENERATION_MAX_RETRIES,
    MODEL_PATH,
    RERANK_MODEL_NAME,
    RETRIEVER_FETCH_K,
)
from app.document_loader import load_all_documents

logger = logging.getLogger(__name__)

INSIGHT_FALLBACK = (
    "Insufficient data in retrieved cases to generate a reliable clinical insight. "
    "Review the similar listings and consult a club medical officer."
)

_INVALID_INSIGHT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"<[^>]{1,120}>", re.IGNORECASE),
    re.compile(r"\byour .+ here\b", re.IGNORECASE),
    re.compile(r"\bplaceholder\b", re.IGNORECASE),
    re.compile(r"\bplease provide your response\b", re.IGNORECASE),
    re.compile(r"\bdo not add any extra\b", re.IGNORECASE),
    re.compile(r"\bthe ai will then\b", re.IGNORECASE),
    re.compile(r"\bexact format\b", re.IGNORECASE),
    re.compile(r"\bexample output\b", re.IGNORECASE),
)

CLINICAL_PROMPT = PromptTemplate.from_template(
    """You are a sports medicine AI assistant for a professional football club.

Write ONE short clinical insight using ONLY the Context below.
Rules:
- Cite documents explicitly (e.g. "Document 1", "Document 2").
- Use only facts present in Context. Do not invent details.
- Never use placeholders such as <your ... here>.
- If Context is insufficient, set insight to exactly:
  "Insufficient data in retrieved cases to generate a reliable clinical insight."

Example (follow this style):
Context: Document 1 describes a Grade II calf tear with return-to-play at 8 weeks.
Query: Player has posterior calf pain during sprinting.
Output:
{{"insight": "Based on Document 1 (calf tear case), sudden posterior calf pain during sprinting is consistent with gastrocnemius tear. Conservative management and return-to-play around 8 weeks align with the documented club case."}}

Context:
{context}

Injury / Query Description:
{query}

Respond with ONLY one JSON object and nothing else:
{{"insight": "<your clinical insight>"}}
"""
)

RETRY_PROMPT = PromptTemplate.from_template(
    """You failed to follow instructions. Try again.

Write ONE clinical insight as plain JSON. No placeholders. No extra text.
Cite Document numbers from Context. Use only facts from Context.

Context:
{context}

Query:
{query}

Return ONLY:
{{"insight": "<complete clinical insight with citations>"}}
"""
)


def _build_embeddings() -> HuggingFaceEmbeddings:
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL_NAME,
        encode_kwargs={"normalize_embeddings": True},
    )


def _format_context(docs: list[Document]) -> str:
    """Format retrieved documents for LLM context injection."""
    parts: list[str] = []
    for i, doc in enumerate(docs):
        meta = doc.metadata or {}
        title = meta.get("title", f"Document {i + 1}")
        doc_type = meta.get("type", "")
        region = meta.get("body_region", "")
        header = f"Document {i + 1}: {title}"
        if doc_type or region:
            header += f" [{doc_type}/{region}]".strip("/")
        parts.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def _format_document_listing(doc: Document, index: int) -> str:
    """Format a retrieved document as a readable listing string."""
    meta = doc.metadata or {}
    title = meta.get("title") or Path(meta.get("source", "")).stem or f"Document {index}"
    doc_type = meta.get("type", "")
    region = meta.get("body_region", "")
    date = meta.get("date", "")

    tags: list[str] = []
    if doc_type and region:
        tags.append(f"{doc_type}/{region}")
    elif doc_type:
        tags.append(doc_type)
    elif region:
        tags.append(region)
    if date:
        tags.append(str(date))

    tag_str = f" [{', '.join(tags)}]" if tags else ""
    snippet = doc.page_content.strip().replace("\n", " ")
    if len(snippet) > 300:
        snippet = snippet[:297] + "..."
    return f"[{index}] {title}{tag_str}: {snippet}"


def _extract_json(text: str) -> dict[str, Any]:
    """Attempt to parse JSON from LLM output, with graceful fallback."""
    text = text.strip()

    fence_match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    if fence_match:
        text = fence_match.group(1).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass

    return {"insight": text}


def validate_insight(insight: str) -> tuple[bool, str]:
    """Validate LLM insight text. Returns (is_valid, reason)."""
    if not isinstance(insight, str):
        return False, "insight is not a string"

    cleaned = insight.strip()
    if not cleaned:
        return False, "insight is empty"

    if len(cleaned) < INSIGHT_MIN_LENGTH:
        return False, f"insight shorter than {INSIGHT_MIN_LENGTH} characters"

    for pattern in _INVALID_INSIGHT_PATTERNS:
        if pattern.search(cleaned):
            return False, f"insight matches invalid pattern: {pattern.pattern}"

    return True, ""


def _parse_insight(raw_output: str) -> str:
    """Extract insight string from raw LLM output."""
    parsed = _extract_json(raw_output)
    insight = parsed.get("insight", raw_output)
    if not isinstance(insight, str):
        insight = str(insight)
    return insight.strip()


def _dedupe_by_source(docs: list[Document]) -> list[Document]:
    """Keep the first (highest-ranked) chunk per unique source file."""
    seen: set[str] = set()
    unique: list[Document] = []
    for doc in docs:
        source = doc.metadata.get("source", id(doc))
        if source in seen:
            continue
        seen.add(source)
        unique.append(doc)
    return unique


def _merge_document_lists(*lists: list[Document]) -> list[Document]:
    """Merge document lists preserving order and deduplicating by source."""
    merged: list[Document] = []
    seen: set[str] = set()
    for doc_list in lists:
        for doc in doc_list:
            source = doc.metadata.get("source", id(doc))
            if source in seen:
                continue
            seen.add(source)
            merged.append(doc)
    return merged


class RAGEngine:
    """Hybrid-search RAG engine backed by ChromaDB + BM25 and Llama.cpp."""

    def __init__(self) -> None:
        self._embeddings = _build_embeddings()
        self._source_docs = load_all_documents(DATA_DIR)
        self._known_regions = self._build_known_regions(self._source_docs)
        self._chroma_store = Chroma(
            collection_name=COLLECTION_NAME,
            embedding_function=self._embeddings,
            persist_directory=str(CHROMA_DIR),
        )
        self._ensemble_retriever = self._build_ensemble_retriever()
        self._bm25_retriever = BM25Retriever.from_documents(self._source_docs)
        self._bm25_retriever.k = RETRIEVER_FETCH_K * 2
        self._reranker = self._build_reranker()
        self._llm = self._build_llm()

    def _build_known_regions(self, docs: list[Document]) -> set[str]:
        regions: set[str] = set()
        for doc in docs:
            region = doc.metadata.get("body_region")
            if region:
                regions.add(str(region).lower())
        return regions

    def _build_ensemble_retriever(self) -> EnsembleRetriever:
        chroma_retriever = self._chroma_store.as_retriever(
            search_kwargs={"k": RETRIEVER_FETCH_K}
        )
        bm25_retriever = BM25Retriever.from_documents(self._source_docs)
        bm25_retriever.k = RETRIEVER_FETCH_K
        return EnsembleRetriever(
            retrievers=[chroma_retriever, bm25_retriever],
            weights=ENSEMBLE_WEIGHTS,
        )

    def _build_reranker(self) -> CrossEncoder | None:
        if not ENABLE_RERANKING:
            return None
        logger.info("Loading cross-encoder reranker: %s", RERANK_MODEL_NAME)
        return CrossEncoder(RERANK_MODEL_NAME)

    def _build_llm(self) -> LlamaCpp:
        if not MODEL_PATH.exists():
            raise FileNotFoundError(
                f"LLM model not found at '{MODEL_PATH}'. "
                "Place a .gguf file in models/ or set LLAMA_MODEL_PATH in .env. "
                "See models/README.md for instructions."
            )
        return LlamaCpp(
            model_path=str(MODEL_PATH),
            chat_format=LLAMA_CHAT_FORMAT,
            n_ctx=LLAMA_N_CTX,
            n_threads=LLAMA_N_THREADS,
            n_gpu_layers=LLAMA_N_GPU_LAYERS,
            temperature=LLAMA_TEMPERATURE,
            max_tokens=LLAMA_MAX_TOKENS,
            verbose=LLAMA_VERBOSE,
            stop=["<|eot_id|>", "<|end_of_text|>"],
        )

    def _extract_region_filter(self, query: str) -> str | None:
        """Return body_region if query mentions a known region (whole-word match)."""
        query_lower = query.lower()
        for region in sorted(self._known_regions, key=len, reverse=True):
            if re.search(rf"\b{re.escape(region)}\b", query_lower):
                return region
        return None

    def _retrieve_candidates(self, query: str) -> list[Document]:
        """Fetch raw candidate documents via hybrid search, optionally filtered."""
        if not ENABLE_METADATA_FILTERING:
            return self._ensemble_retriever.invoke(query)

        region = self._extract_region_filter(query)
        if region is None:
            return self._ensemble_retriever.invoke(query)

        logger.info("Applying metadata filter: body_region=%s", region)

        chroma_filtered = self._chroma_store.similarity_search(
            query,
            k=RETRIEVER_FETCH_K,
            filter={"body_region": region},
        )

        bm25_filtered = [
            doc
            for doc in self._bm25_retriever.invoke(query)
            if str(doc.metadata.get("body_region", "")).lower() == region
        ]

        filtered = _merge_document_lists(chroma_filtered, bm25_filtered)
        if len(filtered) >= FINAL_TOP_K:
            return filtered

        logger.info(
            "Filtered results (%d) below FINAL_TOP_K (%d); topping up unfiltered",
            len(filtered),
            FINAL_TOP_K,
        )
        unfiltered = self._ensemble_retriever.invoke(query)
        return _merge_document_lists(filtered, unfiltered)

    def _rerank(self, query: str, docs: list[Document]) -> list[Document]:
        """Re-score documents with a cross-encoder and return sorted list."""
        if not docs or self._reranker is None:
            return docs

        pairs = [(query, doc.page_content) for doc in docs]
        scores = self._reranker.predict(pairs)
        ranked = sorted(zip(scores, docs, strict=False), key=lambda x: x[0], reverse=True)
        return [doc for _, doc in ranked]

    def _select_top_documents(self, query: str) -> list[Document]:
        """Unified retrieval pipeline: fetch → dedupe → rerank → top-k."""
        candidates = self._retrieve_candidates(query)
        candidates = _dedupe_by_source(candidates)
        candidates = self._rerank(query, candidates)
        return candidates[:FINAL_TOP_K]

    def _generate_insight_with_validation(
        self,
        query: str,
        context: str,
    ) -> str:
        """Run LLM generation with validation and optional retry."""
        attempts = 1 + max(LLM_GENERATION_MAX_RETRIES, 0)
        last_reason = "unknown validation failure"

        for attempt in range(attempts):
            prompt = CLINICAL_PROMPT if attempt == 0 else RETRY_PROMPT
            raw_output = (prompt | self._llm | StrOutputParser()).invoke(
                {"context": context, "query": query}
            )
            insight = _parse_insight(raw_output)
            is_valid, reason = validate_insight(insight)

            if is_valid:
                if attempt > 0:
                    logger.info("Insight generation succeeded on retry %d", attempt)
                return insight

            last_reason = reason
            logger.warning(
                "Invalid insight on attempt %d/%d: %s",
                attempt + 1,
                attempts,
                reason,
            )

        logger.error("Insight validation failed after %d attempts: %s", attempts, last_reason)
        return INSIGHT_FALLBACK

    def generate_insight(self, query: str) -> dict[str, Any]:
        """
        Retrieve top-k documents via hybrid search and generate a clinical insight.

        Returns:
            {
                "similar_listings": ["doc1 summary", "doc2 summary", "doc3 summary"],
                "insight": "<generated clinical insight>"
            }
        """
        retrieved_docs = self._select_top_documents(query)
        context = _format_context(retrieved_docs)

        similar_listings = [
            _format_document_listing(doc, i + 1)
            for i, doc in enumerate(retrieved_docs)
        ]

        insight = self._generate_insight_with_validation(query, context)

        return {
            "similar_listings": similar_listings,
            "insight": insight,
        }


@lru_cache(maxsize=1)
def get_rag_engine() -> RAGEngine:
    """Return a cached RAGEngine instance (initialised once per process)."""
    return RAGEngine()


def generate_insight(query: str) -> dict[str, Any]:
    """Module-level convenience wrapper around RAGEngine.generate_insight."""
    return get_rag_engine().generate_insight(query)
