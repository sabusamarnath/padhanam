"""Unit tests for the plain-text parser adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.ingestion.adapters.outbound.parsers.plain_text_parser import (
    PlainTextParser,
)
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState
from contexts.ingestion.ports.parser_port import ParserError


def _source(content: bytes) -> Source:
    now = datetime.now(timezone.utc)
    return Source(
        id=uuid4(),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        file_name="x.txt",
        file_type="text",
        file_size_bytes=len(content),
        raw_content=content,
        state=SourceState.RECEIVED,
        parsing_error_text=None,
        created_by_user_id="user-1",
        created_at=now,
        updated_at=now,
    )


def test_empty_text_produces_no_chunks() -> None:
    parser = PlainTextParser()
    assert parser.parse(_source(b"")).chunks == ()


def test_whitespace_only_text_produces_no_chunks() -> None:
    parser = PlainTextParser()
    assert parser.parse(_source(b"  \n\n  \n\t\n")).chunks == ()


def test_single_paragraph_produces_one_chunk() -> None:
    parser = PlainTextParser()
    parsed = parser.parse(_source(b"first line\nsecond line"))
    assert len(parsed.chunks) == 1
    assert parsed.chunks[0].content == "first line\nsecond line"
    assert parsed.chunks[0].structural_metadata == {"paragraph_index": 0}


def test_paragraph_separator_runs_collapse() -> None:
    parser = PlainTextParser()
    text = "para one\n\n\n\npara two\n\n\npara three"
    parsed = parser.parse(_source(text.encode("utf-8")))
    assert [c.content for c in parsed.chunks] == [
        "para one",
        "para two",
        "para three",
    ]
    assert [c.structural_metadata["paragraph_index"] for c in parsed.chunks] == [
        0,
        1,
        2,
    ]


def test_whitespace_only_paragraphs_are_filtered() -> None:
    parser = PlainTextParser()
    text = "para one\n\n   \n\npara two"
    parsed = parser.parse(_source(text.encode("utf-8")))
    assert [c.content for c in parsed.chunks] == ["para one", "para two"]


def test_non_utf8_content_raises_parser_error() -> None:
    parser = PlainTextParser()
    with pytest.raises(ParserError):
        parser.parse(_source(b"\xff\xfe\x00invalid"))


def test_unicode_content_parses_cleanly() -> None:
    parser = PlainTextParser()
    text = "Übergroße Frage\n\n答え: 一二三"
    parsed = parser.parse(_source(text.encode("utf-8")))
    assert [c.content for c in parsed.chunks] == [
        "Übergroße Frage",
        "答え: 一二三",
    ]
