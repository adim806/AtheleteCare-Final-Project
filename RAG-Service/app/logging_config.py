"""
Shared logging setup for the RAG pipeline (ingest + query).

Prerequisite (Step 0): called before any other imports in ingest.py and main.py.
Keeps application logs readable by silencing noisy third-party libraries.
"""

import logging
import os
import warnings

# Third-party loggers that flood the terminal at INFO during ingest/query.
NOISY_LIBRARIES = (
    "httpx",                    # HTTP client — logs every HuggingFace request
    "httpcore",                 # Low-level HTTP layer used by httpx
    "sentence_transformers",    # Embedding model load messages
    "huggingface_hub",          # Model download / auth warnings
    "huggingface_hub.utils._http",
    "transformers",             # HuggingFace transformers verbosity
    "urllib3",                  # HTTP warnings
    "chromadb",                 # Vector DB internal logs
    "llama_cpp",                # Local LLM inference logs
)


def configure_rag_logging(namespace: str) -> logging.Logger:
    """
    Step 0 — Initialize logging (runs before ingest Steps 1–5 or query Steps 1–6).

    Args:
        namespace: Logger name, e.g. "rag.ingest" or "rag.query"

    Returns:
        Configured logger for that namespace.
    """
    # Step 0.1 — Disable HF progress bars and reduce transformers console noise.
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    # Step 0.2 — Suppress known harmless warnings (LangChain deprecation, HF token notice).
    warnings.filterwarnings("ignore", category=DeprecationWarning, module=r"langchain_community.*")
    warnings.filterwarnings(
        "ignore",
        message=r".*langchain-community.*",
        category=DeprecationWarning,
    )
    warnings.filterwarnings(
        "ignore",
        message=r".*unauthenticated requests to the HF Hub.*",
    )

    # Step 0.3 — Log level: INFO by default; set RAG_LOG_LEVEL=DEBUG for chunk/query previews.
    level_name = os.getenv("RAG_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    # Step 0.4 — Configure root handler once (shared by all loggers).
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%H:%M:%S",
        )

    # Step 0.5 — Silence third-party libraries — only ERROR and above.
    for library in NOISY_LIBRARIES:
        logging.getLogger(library).setLevel(logging.ERROR)

    # Step 0.6 — Application logger stays at INFO or DEBUG per RAG_LOG_LEVEL.
    logger = logging.getLogger(namespace)
    logger.setLevel(level)
    return logger
