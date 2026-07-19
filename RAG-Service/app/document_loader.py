"""Shared document loading with YAML frontmatter parsing for Markdown files."""

from __future__ import annotations

import re
from pathlib import Path

from typing import Any

import yaml
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document

_FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.DOTALL)


def _normalize_metadata(value: Any) -> Any:
    """Convert YAML-parsed values to Chroma-safe primitives."""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Parse a leading YAML frontmatter block from Markdown text.

    Returns:
        (metadata_dict, body_without_frontmatter)
    """
    match = _FRONTMATTER_PATTERN.match(text)
    if not match:
        return {}, text

    raw_yaml = match.group(1)
    body = text[match.end() :]
    try:
        metadata = yaml.safe_load(raw_yaml) or {}
    except yaml.YAMLError:
        metadata = {}

    if not isinstance(metadata, dict):
        metadata = {}

    metadata = {k: _normalize_metadata(v) for k, v in metadata.items()}
    return metadata, body.lstrip("\n")


def _load_markdown_documents(data_dir: Path) -> list[Document]:
    """Load .md files with YAML frontmatter parsed into metadata."""
    documents: list[Document] = []

    for path in sorted(data_dir.rglob("*.md")):
        text = path.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(text)
        metadata = {**frontmatter, "source": str(path.resolve())}
        documents.append(Document(page_content=body, metadata=metadata))

    return documents


def _load_other_documents(data_dir: Path) -> list[Document]:
    """Load .txt and .pdf files using LangChain DirectoryLoader."""
    text_loader_kwargs = {"autodetect_encoding": True}
    documents: list[Document] = []

    for glob_pattern, loader_cls in [
        ("**/*.txt", TextLoader),
        ("**/*.pdf", PyPDFLoader),
    ]:
        loader = DirectoryLoader(
            str(data_dir),
            glob=glob_pattern,
            loader_cls=loader_cls,
            loader_kwargs=text_loader_kwargs if loader_cls is TextLoader else {},
            use_multithreading=True,
        )
        documents.extend(loader.load())

    return documents


def load_all_documents(data_dir: Path) -> list[Document]:
    """
    Load all supported documents from data_dir.

    Markdown files get YAML frontmatter parsed into metadata.
    """
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    documents = _load_markdown_documents(data_dir)
    documents.extend(_load_other_documents(data_dir))

    if not documents:
        raise ValueError(
            f"No documents found in {data_dir}. Add .md, .txt, or .pdf files."
        )

    return documents
