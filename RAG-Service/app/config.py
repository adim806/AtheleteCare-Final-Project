"""Central configuration for the AthleteCare RAG Service."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATA_DIR: Path = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
CHROMA_DIR: Path = Path(os.getenv("CHROMA_DIR", BASE_DIR / "chroma_db"))
MODELS_DIR: Path = Path(os.getenv("MODELS_DIR", BASE_DIR / "models"))

DEFAULT_MODEL_FILENAME = "llama-3-8b-instruct.gguf"
MODEL_PATH: Path = Path(
    os.getenv("LLAMA_MODEL_PATH", MODELS_DIR / DEFAULT_MODEL_FILENAME)
)

# ---------------------------------------------------------------------------
# Embeddings & ChromaDB
# ---------------------------------------------------------------------------
EMBED_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
COLLECTION_NAME: str = "athletecare_medical"

# ---------------------------------------------------------------------------
# Text splitting
# ---------------------------------------------------------------------------
CHUNK_SIZE: int = 800
CHUNK_OVERLAP: int = 120

# ---------------------------------------------------------------------------
# Retrieval
# ---------------------------------------------------------------------------
RETRIEVER_K: int = 3
RETRIEVER_FETCH_K: int = int(os.getenv("RETRIEVER_FETCH_K", "8"))
FINAL_TOP_K: int = int(os.getenv("FINAL_TOP_K", "3"))
ENSEMBLE_WEIGHTS: list[float] = [0.5, 0.5]

ENABLE_METADATA_FILTERING: bool = (
    os.getenv("ENABLE_METADATA_FILTERING", "true").lower() == "true"
)
ENABLE_RERANKING: bool = os.getenv("ENABLE_RERANKING", "true").lower() == "true"
RERANK_MODEL_NAME: str = os.getenv(
    "RERANK_MODEL_NAME", "cross-encoder/ms-marco-MiniLM-L-6-v2"
)

# ---------------------------------------------------------------------------
# Insight validation & generation retries
# ---------------------------------------------------------------------------
INSIGHT_MIN_LENGTH: int = int(os.getenv("INSIGHT_MIN_LENGTH", "50"))
LLM_GENERATION_MAX_RETRIES: int = int(os.getenv("LLM_GENERATION_MAX_RETRIES", "1"))

# ---------------------------------------------------------------------------
# Llama.cpp inference
# ---------------------------------------------------------------------------
LLAMA_CHAT_FORMAT: str = os.getenv("LLAMA_CHAT_FORMAT", "llama-3")
LLAMA_N_CTX: int = int(os.getenv("LLAMA_N_CTX", "4096"))
LLAMA_N_THREADS: int = int(os.getenv("LLAMA_N_THREADS", "4"))
LLAMA_N_GPU_LAYERS: int = int(os.getenv("LLAMA_N_GPU_LAYERS", "0"))
LLAMA_TEMPERATURE: float = float(os.getenv("LLAMA_TEMPERATURE", "0.1"))
LLAMA_MAX_TOKENS: int = int(os.getenv("LLAMA_MAX_TOKENS", "512"))
LLAMA_VERBOSE: bool = os.getenv("LLAMA_VERBOSE", "false").lower() == "true"

# ---------------------------------------------------------------------------
# FastAPI
# ---------------------------------------------------------------------------
API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
API_PORT: int = int(os.getenv("API_PORT", "8000"))
