"""Unit tests for YAML frontmatter document loading."""

from pathlib import Path

from app.document_loader import load_all_documents, parse_frontmatter


SAMPLE_WITH_FRONTMATTER = """---
title: "Calf Tear Case – Player #7 (2024)"
type: case
body_region: calf
date: 2024-03-12
---

# Case Report

Player reported sudden sharp pain.
"""

SAMPLE_WITHOUT_FRONTMATTER = """# Plain Document

No YAML header here.
"""


def test_parse_frontmatter_extracts_metadata_and_body():
    metadata, body = parse_frontmatter(SAMPLE_WITH_FRONTMATTER)

    assert metadata["title"] == "Calf Tear Case – Player #7 (2024)"
    assert metadata["type"] == "case"
    assert metadata["body_region"] == "calf"
    assert metadata["date"] == "2024-03-12"
    assert body.startswith("# Case Report")
    assert "---" not in body.split("\n")[0]


def test_parse_frontmatter_without_yaml_returns_empty_metadata():
    metadata, body = parse_frontmatter(SAMPLE_WITHOUT_FRONTMATTER)

    assert metadata == {}
    assert body == SAMPLE_WITHOUT_FRONTMATTER


def test_load_all_documents_parses_markdown_frontmatter(tmp_path: Path):
    md_file = tmp_path / "case_test.md"
    md_file.write_text(SAMPLE_WITH_FRONTMATTER, encoding="utf-8")

    docs = load_all_documents(tmp_path)

    assert len(docs) == 1
    assert docs[0].metadata["title"] == "Calf Tear Case – Player #7 (2024)"
    assert docs[0].metadata["body_region"] == "calf"
    assert "source" in docs[0].metadata
    assert docs[0].page_content.startswith("# Case Report")
