"""Offline script to populate the ChromaDB vector store from data/ documents."""

from __future__ import annotations

import sys
from pathlib import Path

from langchain_community.vectorstores import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.config import (
    CHROMA_DIR,
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    COLLECTION_NAME,
    DATA_DIR,
    EMBED_MODEL_NAME,
)
from app.document_loader import load_all_documents


def _build_embeddings() -> HuggingFaceEmbeddings:
    """Return normalised HuggingFace sentence-transformer embeddings."""
    return HuggingFaceEmbeddings(
        model_name=EMBED_MODEL_NAME,
        encode_kwargs={"normalize_embeddings": True},
    )


def load_documents(data_dir: Path) -> list:
    """Load Markdown, plain-text, and PDF files from the data directory."""
    documents = load_all_documents(data_dir)
    print(f"  Loaded {len(documents)} document(s) total")
    return documents


def split_documents(documents: list) -> list:
    """Split raw documents into overlapping chunks suitable for retrieval."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    print(f"  Split into {len(chunks)} chunk(s)")
    return chunks


def ingest(data_dir: Path | None = None, chroma_dir: Path | None = None) -> None:
    """Load, split, embed, and persist documents into ChromaDB."""
    data_dir = data_dir or DATA_DIR
    chroma_dir = chroma_dir or CHROMA_DIR

    print(f"[ingest] Loading documents from: {data_dir}")
    documents = load_documents(data_dir)
    print(f"[ingest] Total raw documents loaded: {len(documents)}")

    print("[ingest] Splitting documents …")
    chunks = split_documents(documents)

    print(f"[ingest] Initialising embeddings ({EMBED_MODEL_NAME}) …")
    embeddings = _build_embeddings()

    print(f"[ingest] Building ChromaDB vector store at: {chroma_dir}")
    chroma_dir.mkdir(parents=True, exist_ok=True)

    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=COLLECTION_NAME,
        persist_directory=str(chroma_dir),
    )

    print(f"[ingest] SUCCESS – {len(chunks)} chunks persisted to '{chroma_dir}'")


if __name__ == "__main__":
    try:
        ingest()
    except Exception as exc:
        print(f"[ingest] ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
