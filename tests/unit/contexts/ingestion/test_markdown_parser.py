"""Unit tests for the markdown parser adapter.

Cover the heading-boundary chunking shape D61 commits to plus
representative edge cases the parser-as-port abstraction will
inherit when later parsers (PDF, DOCX) extend it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.ingestion.adapters.outbound.parsers.markdown_parser import (
    MarkdownParser,
)
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.parser_port import ParserError


def _source(content: bytes, file_name: str = "x.md") -> Source:
    now = datetime.now(timezone.utc)
    return Source(
        id=uuid4(),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        file_name=file_name,
        file_type="markdown",
        file_size_bytes=len(content),
        raw_content=content,
        state=SourceState.RECEIVED,
        parsing_error_text=None,
        created_by_user_id="user-1",
        created_at=now,
        updated_at=now,
    )


def test_empty_markdown_produces_no_chunks() -> None:
    parser = MarkdownParser()
    parsed = parser.parse(_source(b""))
    assert parsed.chunks == ()


def test_whitespace_only_markdown_produces_no_chunks() -> None:
    parser = MarkdownParser()
    parsed = parser.parse(_source(b"   \n\n\t\n  "))
    assert parsed.chunks == ()


def test_single_heading_with_body_produces_one_chunk() -> None:
    parser = MarkdownParser()
    parsed = parser.parse(_source(b"# Hello\n\nworld\n"))
    assert len(parsed.chunks) == 1
    chunk = parsed.chunks[0]
    assert "Hello" in chunk.content
    assert "world" in chunk.content
    assert chunk.structural_metadata == {
        "heading_text": "Hello",
        "heading_level": 1,
    }


def test_multiple_headings_produce_chunks_at_boundaries() -> None:
    parser = MarkdownParser()
    text = (
        "# Intro\n"
        "\n"
        "intro body\n"
        "\n"
        "## Section\n"
        "\n"
        "section body\n"
        "\n"
        "### Subsection\n"
        "\n"
        "sub body\n"
    )
    parsed = parser.parse(_source(text.encode("utf-8")))
    assert len(parsed.chunks) == 3
    assert parsed.chunks[0].structural_metadata == {
        "heading_text": "Intro",
        "heading_level": 1,
    }
    assert "intro body" in parsed.chunks[0].content
    assert parsed.chunks[1].structural_metadata == {
        "heading_text": "Section",
        "heading_level": 2,
    }
    assert "section body" in parsed.chunks[1].content
    assert "sub body" not in parsed.chunks[1].content
    assert parsed.chunks[2].structural_metadata == {
        "heading_text": "Subsection",
        "heading_level": 3,
    }
    assert "sub body" in parsed.chunks[2].content


def test_pre_first_heading_content_becomes_unanchored_chunk() -> None:
    """A markdown file whose first paragraphs precede any heading
    must not silently lose the front matter; it lands as a chunk
    with empty structural metadata so it is preserved verbatim.
    """
    parser = MarkdownParser()
    text = "front matter line\n\nmore intro\n\n# First Heading\n\nbody\n"
    parsed = parser.parse(_source(text.encode("utf-8")))
    assert len(parsed.chunks) == 2
    assert parsed.chunks[0].structural_metadata == {}
    assert "front matter line" in parsed.chunks[0].content
    assert "more intro" in parsed.chunks[0].content
    assert parsed.chunks[1].structural_metadata["heading_text"] == "First Heading"


def test_deeply_nested_headings_preserve_levels() -> None:
    parser = MarkdownParser()
    text = "# H1\n\n## H2\n\n### H3\n\n#### H4\n\n##### H5\n\n###### H6\n"
    parsed = parser.parse(_source(text.encode("utf-8")))
    levels = [c.structural_metadata.get("heading_level") for c in parsed.chunks]
    assert levels == [1, 2, 3, 4, 5, 6]


def test_non_utf8_content_raises_parser_error() -> None:
    parser = MarkdownParser()
    with pytest.raises(ParserError):
        parser.parse(_source(b"\xff\xfe\x00\x00invalid"))


def test_unicode_content_parses_cleanly() -> None:
    parser = MarkdownParser()
    text = "# Überschrift\n\nINNHOLD: 一二三\n"
    parsed = parser.parse(_source(text.encode("utf-8")))
    assert len(parsed.chunks) == 1
    assert "Überschrift" in parsed.chunks[0].content
    assert "一二三" in parsed.chunks[0].content
    assert parsed.chunks[0].structural_metadata["heading_text"] == "Überschrift"
