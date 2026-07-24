"""
Offline ingest pipeline — load data, chunk, embed, persist to chroma_db/.

Run once (or after data changes): python -m app.ingest

Chronological steps:
  Step 0 — Configure logging (logging_config.py)
  Step 1 — Load Markdown files with YAML frontmatter (protocols/, cases/, policies/)
  Step 2 — Load optional TXT/PDF files
  Step 3 — Hybrid chunking (MD headers / char split for long TXT/PDF)
  Step 4 — Embed chunks and persist to chroma_db/

catalog.json is an admin index only — it is NOT ingested.
"""

import re
import shutil
from collections import Counter
from pathlib import Path

# Step 0 — Configure logging before LangChain imports.
from app.logging_config import configure_rag_logging

logger = configure_rag_logging("rag.ingest")

import yaml
from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, PyPDFLoader, TextLoader
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

# --- Paths ---
BASE_DIR = Path(__file__).resolve().parent.parent  # RAG-Service root
DATA_DIR = BASE_DIR / "data"                       # Source: protocols/, cases/, policies/*.md
CHROMA_DIR = BASE_DIR / "chroma_db"                # Output vector store (created by ingest)

# --- Chunking thresholds ---
SINGLE_DOC_MAX_CHARS = 800   # Short non-MD docs: keep as one chunk if below this
MAX_SECTION_CHARS = 1200     # MD section above this gets an extra character split
CHAR_CHUNK_SIZE = 600        # Fallback splitter: max chars per chunk
CHAR_CHUNK_OVERLAP = 60      # Overlap between character-split chunks

# Markdown header levels → metadata key names on each chunk
MD_HEADERS_TO_SPLIT = [
    ("##", "section"),       # e.g. "## Classification" → metadata["section"]
    ("###", "subsection"),   # e.g. "### Phase 1" → metadata["subsection"]
]

# Regex to detect YAML frontmatter block at the top of .md files (--- ... ---)
FRONTMATTER_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _preview(text: str, limit: int = 90) -> str:
    """Truncate text to a single line for DEBUG log output."""
    compact = " ".join(text.split())
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """
    Split YAML frontmatter from markdown body.

    Returns:
        (metadata dict from YAML, body text without frontmatter block)
    """
    match = FRONTMATTER_PATTERN.match(text)
    if not match:
        logger.debug("No YAML frontmatter detected; treating entire file as body.")
        return {}, text

    try:
        metadata = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        logger.warning("Failed to parse YAML frontmatter: %s", exc)
        metadata = {}

    if not isinstance(metadata, dict):
        metadata = {}

    body = text[match.end():].strip()
    logger.debug(
        "Parsed frontmatter keys: %s | body length: %d chars",
        list(metadata.keys()),
        len(body),
    )
    return metadata, body


def _normalize_doc_type(doc_type: str | None) -> str:
    """Map legacy 'past_case' to unified schema value 'case'."""
    if doc_type == "past_case":
        return "case"
    return doc_type or "general"


def _default_source(doc_type: str) -> str:
    """Default provenance label when source is not set in frontmatter."""
    if doc_type == "protocol":
        return "Club Medical Department"
    if doc_type == "case":
        return "Injury Database"
    if doc_type == "policy":
        return "Club Medical Department"
    return "Internal DB"


def _build_metadata(
    *,
    doc_id: str,
    doc_type: str,
    body_region: str,
    source: str,
    date: str | None = None,
    title: str | None = None,
    source_file: str | None = None,
    linked_protocol_id: str | None = None,
    player_id: str | None = None,
    category: str | None = None,
    days_to_return: int | str | None = None,
) -> dict:
    """
    Build unified metadata dict stored on every Chroma chunk.

    Required for retrieval filtering and API response fields (id, type, source).
    """
    metadata = {
        "id": doc_id or "N/A",
        "type": doc_type,
        "body_region": body_region or "unknown",
        "source": source,
    }

    if date:
        metadata["date"] = str(date)
    if title:
        metadata["title"] = title
    if source_file:
        metadata["source_file"] = source_file
    if linked_protocol_id:
        metadata["linked_protocol_id"] = linked_protocol_id
    if player_id:
        metadata["player_id"] = str(player_id)
    if category:
        metadata["category"] = str(category)
    if days_to_return is not None:
        metadata["days_to_return"] = str(days_to_return)

    return metadata


def _format_page_content(title: str, body: str) -> str:
    """Format text embedded and searched in Chroma (Title + body)."""
    if body:
        return f"Title: {title}\n\n{body}"
    return f"Title: {title}"


def _log_loaded_document(metadata: dict) -> None:
    """Log one INFO line per loaded Markdown source document."""
    logger.info(
        "Loaded id=%s | type=%s | body_region=%s | source=%s",
        metadata.get("id", "N/A"),
        metadata.get("type", "general"),
        metadata.get("body_region", "unknown"),
        metadata.get("source", "N/A"),
    )


def load_markdown_documents() -> list[Document]:
    """
    Ingest Step 1 — Load all *.md under data/ (protocols/, cases/, policies/).

    Parses YAML frontmatter into metadata; body (without --- blocks) goes to page_content.
    Sets source_file so Step 3 uses MarkdownHeaderTextSplitter for these files.
    """
    documents: list[Document] = []
    md_paths = sorted(DATA_DIR.glob("**/*.md"))

    logger.info("Step 1/4 — Loading markdown files (%d found)", len(md_paths))
    for md_path in md_paths:
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("Could not read %s: %s", md_path, e)
            continue

        frontmatter, body = parse_frontmatter(text)
        doc_type = _normalize_doc_type(frontmatter.get("type"))
        title = frontmatter.get("title", md_path.stem)
        metadata = _build_metadata(
            doc_id=frontmatter.get("id", "N/A"),
            doc_type=doc_type,
            body_region=frontmatter.get("body_region", "unknown"),
            source=frontmatter.get("source", _default_source(doc_type)),
            date=frontmatter.get("date"),
            title=title,
            source_file=str(md_path.relative_to(DATA_DIR)),
            player_id=frontmatter.get("player_id"),
            linked_protocol_id=frontmatter.get("linked_protocol_id"),
            category=frontmatter.get("category"),
            days_to_return=frontmatter.get("days_to_return"),
        )
        doc = Document(
            page_content=_format_page_content(title, body),
            metadata=metadata,
        )
        documents.append(doc)
        _log_loaded_document(metadata)
        logger.debug(
            "  MD file=%s | body length=%d | preview: %s",
            md_path.name,
            len(body),
            _preview(body),
        )

    logger.info("Markdown load complete: %d document(s)", len(documents))
    return documents


def load_all_documents() -> list[Document]:
    """
    Orchestrate ingest Steps 1–2: Markdown → optional TXT/PDF.

    Returns flat list of source documents (not yet chunked — Step 3 follows).
    """
    logger.info("Data directory: %s", DATA_DIR)
    documents: list[Document] = []
    documents.extend(load_markdown_documents())

    if not DATA_DIR.exists():
        logger.warning("Data directory does not exist: %s", DATA_DIR)
        return documents

    logger.info("Step 2/4 — Loading optional TXT/PDF files")
    try:
        txt_loader = DirectoryLoader(
            str(DATA_DIR),
            glob="**/*.txt",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
        )
        txt_docs = txt_loader.load()
        documents.extend(txt_docs)
        if txt_docs:
            logger.info("Loaded %d TXT file(s)", len(txt_docs))
        else:
            logger.debug("No TXT files found")
    except Exception as e:
        logger.warning("Error reading text files: %s", e)

    try:
        pdf_loader = DirectoryLoader(str(DATA_DIR), glob="**/*.pdf", loader_cls=PyPDFLoader)
        pdf_docs = pdf_loader.load()
        documents.extend(pdf_docs)
        if pdf_docs:
            logger.info("Loaded %d PDF file(s)", len(pdf_docs))
        else:
            logger.debug("No PDF files found")
    except Exception as e:
        logger.warning("Error reading PDF files: %s", e)

    logger.info("Total source documents loaded: %d", len(documents))
    return documents


def _is_markdown_document(doc: Document) -> bool:
    """True if document came from a .md file (has source_file ending in .md)."""
    source_file = str(doc.metadata.get("source_file", ""))
    return source_file.endswith(".md")


def _merge_chunk_metadata(parent: dict, child: dict) -> dict:
    """Merge parent doc metadata (id, body_region) with section/subsection from splitter."""
    merged = parent.copy()
    for key, value in child.items():
        if value is not None and value != "":
            merged[key] = value
    return merged


def _split_oversized_section(doc: Document, char_splitter: RecursiveCharacterTextSplitter) -> list[Document]:
    """If an MD section exceeds MAX_SECTION_CHARS, apply character splitting as fallback."""
    if len(doc.page_content) <= MAX_SECTION_CHARS:
        return [doc]
    logger.debug(
        "Section exceeds %d chars (id=%s); applying character split.",
        MAX_SECTION_CHARS,
        doc.metadata.get("id", "N/A"),
    )
    return char_splitter.split_documents([doc])


def _log_chunk(doc: Document, strategy: str) -> None:
    """DEBUG log for one produced chunk (strategy: markdown_header, single, or character)."""
    section = doc.metadata.get("section")
    subsection = doc.metadata.get("subsection")
    section_label = subsection or section or "-"
    logger.debug(
        "  chunk | id=%s | strategy=%s | section=%s | chars=%d | preview=%s",
        doc.metadata.get("id", "N/A"),
        strategy,
        section_label,
        len(doc.page_content),
        _preview(doc.page_content),
    )


def chunk_documents(raw_documents: list[Document]) -> list[Document]:
    """
    Ingest Step 3 — Hybrid chunking strategy:

    | Source type  | Strategy                           |
    |--------------|------------------------------------|
    | .md files    | MarkdownHeaderTextSplitter (##/###)|
    | Long TXT/PDF | RecursiveCharacterTextSplitter     |

    Each chunk inherits parent metadata (id, type, body_region) plus section labels.
    Output feeds into Step 4 (embed + persist).
    """
    logger.info(
        "Step 3/4 — Chunking %d source document(s) "
        "(MD headers=%s, char split=%d/%d for long TXT/PDF)",
        len(raw_documents),
        MD_HEADERS_TO_SPLIT,
        CHAR_CHUNK_SIZE,
        CHAR_CHUNK_OVERLAP,
    )

    md_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=MD_HEADERS_TO_SPLIT,
        strip_headers=False,  # Keep "## Phase 2" in text for LLM context
    )
    char_splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHAR_CHUNK_SIZE,
        chunk_overlap=CHAR_CHUNK_OVERLAP,
    )

    all_chunks: list[Document] = []

    for doc in raw_documents:
        parent_meta = doc.metadata.copy()
        doc_id = parent_meta.get("id", "N/A")

        if _is_markdown_document(doc):
            section_docs = md_splitter.split_text(doc.page_content)
            if not section_docs:
                logger.warning("Markdown split returned no sections for id=%s; keeping whole document.", doc_id)
                all_chunks.append(doc)
                continue

            doc_chunks: list[Document] = []
            for section in section_docs:
                merged = Document(
                    page_content=section.page_content,
                    metadata=_merge_chunk_metadata(parent_meta, section.metadata),
                )
                split_sections = _split_oversized_section(merged, char_splitter)
                doc_chunks.extend(split_sections)

            logger.info(
                "Chunked MD id=%s file=%s → %d chunk(s) via MarkdownHeaderTextSplitter",
                doc_id,
                parent_meta.get("source_file", "?"),
                len(doc_chunks),
            )
            for chunk in doc_chunks:
                _log_chunk(chunk, "markdown_header")
            all_chunks.extend(doc_chunks)
            continue

        if len(doc.page_content) <= SINGLE_DOC_MAX_CHARS:
            logger.info(
                "Kept single chunk for id=%s (%d chars, no split)",
                doc_id,
                len(doc.page_content),
            )
            _log_chunk(doc, "single")
            all_chunks.append(doc)
        else:
            split_docs = char_splitter.split_documents([doc])
            logger.info(
                "Character-split id=%s → %d chunk(s)",
                doc_id,
                len(split_docs),
            )
            for chunk in split_docs:
                _log_chunk(chunk, "character")
            all_chunks.extend(split_docs)

    counts_by_id = Counter(chunk.metadata.get("id", "N/A") for chunk in all_chunks)
    logger.info("Chunking summary — %d total chunk(s) from %d source document(s):", len(all_chunks), len(raw_documents))
    for doc_id, count in sorted(counts_by_id.items()):
        logger.info("  %s → %d chunk(s)", doc_id, count)

    return all_chunks


def build_vector_store() -> None:
    """
    Main ingest entry point — runs Steps 1–4 in order:

      Step 1–2  load_all_documents()  — MD from protocols/cases/policies + optional TXT/PDF
      Step 3    chunk_documents()     — header-based split
      Step 4    HuggingFaceEmbeddings + Chroma.from_documents → chroma_db/

    Clears chroma_db/ before each run to prevent duplicate chunks.
    """
    logger.info("=== RAG Ingestion Started ===")
    logger.info("Output vector store: %s", CHROMA_DIR)

    if CHROMA_DIR.exists():
        shutil.rmtree(CHROMA_DIR, ignore_errors=True)
        logger.info("Cleared existing vector store at '%s'", CHROMA_DIR)

    # Steps 1–2 — Load all source documents from data/
    raw_documents = load_all_documents()
    if not raw_documents:
        logger.error("No documents loaded. Verify content in '%s'.", DATA_DIR)
        return

    # Step 3 — Split documents into searchable chunks
    chunks = chunk_documents(raw_documents)

    # Step 4 — Embed chunks and persist to Chroma on disk
    logger.info("Step 4/4 — Generating embeddings with all-MiniLM-L6-v2 for %d chunk(s)...", len(chunks))
    try:
        embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
        Chroma.from_documents(
            documents=chunks,
            embedding=embeddings,
            persist_directory=str(CHROMA_DIR),
        )
        logger.info("=== Ingestion SUCCESS — %d chunks persisted to '%s' ===", len(chunks), CHROMA_DIR)
    except Exception as e:
        logger.exception("Ingestion FAILED while creating vector database: %s", e)


if __name__ == "__main__":
    build_vector_store()
