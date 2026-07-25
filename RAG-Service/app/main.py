"""
Online RAG API — retrieval + local LLM insight generation.

Startup (once, at import): Steps S1–S4 load FastAPI, Chroma, LLM, prompt.
Per request (POST /query): Steps 1–6 validate → retrieve → filter → build → LLM → respond.

Requires chroma_db/ from ingest.py (Steps 1–5).
"""

import os
from pathlib import Path

# Step 0 — Configure logging before LangChain imports so warnings/filters apply in time.
from app.logging_config import configure_rag_logging

logger = configure_rag_logging("rag.query")

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.llms import LlamaCpp
from langchain_core.prompts import PromptTemplate

# Step S1 — FastAPI app + paths/constants (runs once at server startup).
app = FastAPI(
    title="The Club's Memory - Clinical RAG Service",
    description="Service 1: RAG Service for Football Club Medical Department"
)

# Step S1 (continued) — Paths resolved relative to RAG-Service root.
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / "models" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"
CHROMA_DIR = BASE_DIR / "chroma_db"

# Retrieval tuning (used in query Step 2 and Step 3).
RETRIEVAL_K = 8              # Fetch 8 candidates from Chroma (more than we return)
MAX_RESULTS = 3              # Max items in similar_listings JSON
MIN_RELEVANCE_SCORE = 0.35   # Drop chunks below 35% normalized relevance (0–1 scale)

# Step S2 — Load embedding model and connect to persisted Chroma DB (from ingest Step 5).
embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

vector_store = None
if CHROMA_DIR.exists():
    vector_store = Chroma(
        collection_name="athletecare_medical",
        persist_directory=str(CHROMA_DIR),
        embedding_function=embeddings
    )
else:
    print(f"⚠️ Warning: '{CHROMA_DIR}' does not exist. Run 'python -m app.ingest' first!")

# Step S3 — Load local LLM from GGUF file (runs once at server startup).
llm = None
if MODEL_PATH.exists():
    try:
        llm = LlamaCpp(
            model_path=str(MODEL_PATH),
            n_ctx=2048,
            temperature=0.1,       # Low randomness — safer for clinical text
            max_tokens=200,        # Cap response length
            repeat_penalty=1.2,    # Reduce repetitive sentences
            stop=["\n\n\n", "Retrieved Clinical", "Clinical Request:"],
            verbose=False
        )
    except Exception as e:
        print(f"⚠️ Error loading LlamaCpp model: {e}")
else:
    print(f"⚠️ Warning: Model file not found at '{MODEL_PATH}'. Place GGUF file in models/ directory.")

# Step S4 — Prompt template used in query Step 5 ({context} = retrieved chunks, {description} = user query).
prompt_template = """You are the Head Clinical Knowledge AI for a professional football club ("The Club's Memory").
Write a SHORT, direct clinical insight (max 3 sentences) based ONLY on the context below.

Retrieved Clinical Knowledge:
{context}

Clinical Request / Injury Description:
"{description}"

Strict Guidelines:
1. You MUST start your answer by citing the exact ID (e.g., "[Based on ID: CASE-2024]").
2. Do NOT hallucinate medical advice. If the context doesn't match the injury, say "Insufficient data".
3. Keep the output concise and directly actionable for the medical team.

Clinical Insight:"""

prompt = PromptTemplate(template=prompt_template, input_variables=["context", "description"])


class QueryRequest(BaseModel):
    """POST /query request body — natural-language injury or clinical question."""
    description: str = Field(..., min_length=3, description="Description of injury or medical query")


def _format_relevance_score(relevance: float) -> str:
    """Convert normalized relevance (0–1) to a percentage string for the API response."""
    return f"{relevance * 100:.1f}%"


def _preview(text: str, limit: int = 120) -> str:
    """Truncate text to a single line for log output."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def _resolve_source(metadata: dict) -> str:
    """
    Resolve a human-readable source label for the API response.

    Prefers metadata['source']; falls back to type-based defaults
    (protocol → Club Medical Department, case → Injury Database).
    """
    raw = metadata.get("source")
    if raw:
        raw_str = str(raw)
        path = Path(raw_str)
        if path.suffix in {".md", ".txt", ".pdf"}:
            return path.stem.replace("_", " ")
        return raw_str

    doc_type = metadata.get("type", "general")
    if doc_type == "protocol":
        return "Club Medical Department"
    if doc_type in {"past_case", "case"}:
        return "Injury Database"
    if doc_type == "policy":
        return "Club Medical Department"
    return "Internal DB"


@app.get("/")
async def root():
    """Service status: checks vector DB and GGUF model availability."""
    return {
        "service": "Clinical RAG Service - The Club's Memory",
        "status": "ready" if (vector_store and llm) else "degraded",
        "vector_db_exists": CHROMA_DIR.exists(),
        "model_exists": MODEL_PATH.exists()
    }


@app.post("/query")
async def query_rag(request: QueryRequest):
    """
    Main RAG pipeline — runs on every POST /query (Steps 1–6):

      Step 1 — Validate input and dependencies (Chroma DB + LLM)
      Step 2 — Vector search with relevance scores (k=RETRIEVAL_K)
      Step 3 — Filter by MIN_RELEVANCE_SCORE, cap at MAX_RESULTS
      Step 4 — Build similar_listings + LLM context blocks
      Step 5 — Generate insight via local LLM
      Step 6 — Return { similar_listings, insight }
    """
    # Step 1 — Input validation
    clean_description = request.description.strip()
    if not clean_description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Description query cannot be empty or whitespace only."
        )

    if vector_store is None or not CHROMA_DIR.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Vector Database not found at '{CHROMA_DIR}'. Please run 'python -m app.ingest' first."
        )

    if llm is None or not MODEL_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"GGUF Model file missing at '{MODEL_PATH}'. Ensure file exists in models/ folder."
        )

    try:
        logger.info("Query received (%d chars): %s", len(clean_description), _preview(clean_description, 200))

        # Step 2 — Semantic search in Chroma; returns (Document, score) pairs, score 0–1
        docs_with_relevance = vector_store.similarity_search_with_relevance_scores(
            clean_description,
            k=RETRIEVAL_K,
        )

        logger.info("Retrieval returned %d candidate(s) (k=%d):", len(docs_with_relevance), RETRIEVAL_K)
        for index, (doc, relevance) in enumerate(docs_with_relevance, start=1):
            logger.info(
                "  [%d] relevance=%.3f id=%s type=%s body_region=%s source=%s",
                index,
                relevance,
                doc.metadata.get("id", "N/A"),
                doc.metadata.get("type", "general"),
                doc.metadata.get("body_region", "unknown"),
                _resolve_source(doc.metadata),
            )
            logger.debug("      preview: %s", _preview(doc.page_content))

        # Step 3 — Drop low-relevance chunks; keep top MAX_RESULTS
        filtered_docs = [
            (doc, relevance)
            for doc, relevance in docs_with_relevance
            if relevance >= MIN_RELEVANCE_SCORE
        ][:MAX_RESULTS]

        logger.info(
            "After relevance filter (>=%.0f%%): %d document(s) kept (max=%d)",
            MIN_RELEVANCE_SCORE * 100,
            len(filtered_docs),
            MAX_RESULTS,
        )

        if not filtered_docs:
            logger.warning("No documents passed relevance threshold; returning insufficient data.")
            return {
                "similar_listings": [],
                "insight": "Insufficient data to match the requested injury."
            }

        # Step 4 — Build API response list and LLM context from the same filtered docs
        retrieved_items = []
        context_blocks = []

        for doc, relevance in filtered_docs:
            doc_id = doc.metadata.get("id", "N/A")
            doc_type = doc.metadata.get("type", "general")
            relevance_score = _format_relevance_score(relevance)
            doc_source = _resolve_source(doc.metadata)

            retrieved_items.append({
                "id": doc_id,
                "type": doc_type,
                "relevance_score": relevance_score,
                "source": doc_source,
                "content": doc.page_content
            })

            context_blocks.append(
                f"[ID: {doc_id} | Relevance: {relevance_score} | Source: {doc_source}]\n{doc.page_content}"
            )

        context_str = "\n\n".join(context_blocks)

        logger.info("LLM context prepared: %d block(s), %d chars total", len(context_blocks), len(context_str))
        logger.debug("Context preview:\n%s", _preview(context_str, 500))

        # Step 5 — LLM generates clinical insight from retrieved context only
        formatted_prompt = prompt.format(context=context_str, description=clean_description)
        logger.info("Invoking LLM (prompt length: %d chars)...", len(formatted_prompt))
        insight_result = llm.invoke(formatted_prompt)
        logger.info("LLM response (%d chars): %s", len(insight_result), _preview(insight_result.strip(), 300))

        # Step 6 — Return structured JSON response
        return {
            "similar_listings": retrieved_items,
            "insight": insight_result.strip()
        }

    except Exception as e:
        logger.exception("RAG pipeline error: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the RAG pipeline: {str(e)}"
        )
