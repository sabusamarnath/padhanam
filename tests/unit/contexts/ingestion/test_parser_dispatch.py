"""Unit tests for parser_dispatch and the adapter registry.

The split between application-layer routing (SUPPORTED_FILE_TYPES,
extension mapping, is_supported_file_type) and adapter-layer
construction (get_parser) preserves the hexagonal-layers contract:
application code never imports adapters, but the routing surface
they share lives at one source of truth (D61).
"""

from __future__ import annotations

import pytest

from contexts.ingestion.adapters.outbound.parsers import (
    MarkdownParser,
    PlainTextParser,
    get_parser,
)
from contexts.ingestion.application.parser_dispatch import (
    SUPPORTED_FILE_TYPES,
    file_type_for_extension,
    is_supported_file_type,
)


def test_supported_file_types_match_d61_scope() -> None:
    """The application-layer routing surface mirrors D61's parsing
    scope. If a future commit adds a parser without extending this
    set the dispatch breaks loudly; if it adds an entry without an
    adapter get_parser raises the ValueError below.
    """
    assert SUPPORTED_FILE_TYPES == frozenset({"markdown", "text"})


def test_is_supported_file_type_matches_supported_set() -> None:
    assert is_supported_file_type("markdown") is True
    assert is_supported_file_type("text") is True
    assert is_supported_file_type("pdf") is False
    assert is_supported_file_type("") is False


def test_get_parser_returns_markdown_parser_for_markdown() -> None:
    assert isinstance(get_parser("markdown"), MarkdownParser)


def test_get_parser_returns_plain_text_parser_for_text() -> None:
    assert isinstance(get_parser("text"), PlainTextParser)


def test_get_parser_raises_for_unknown_file_type() -> None:
    with pytest.raises(ValueError, match="no parser adapter"):
        get_parser("pdf")


def test_get_parser_membership_matches_supported_file_types() -> None:
    """Every entry in SUPPORTED_FILE_TYPES has a working adapter
    in the registry, and the registry rejects everything outside
    the set. A divergence here is a programming bug per the
    registry's own docstring.
    """
    for file_type in SUPPORTED_FILE_TYPES:
        assert get_parser(file_type) is not None
    # Spot-check a few outside-the-set rejections.
    for absent in ("pdf", "docx", "html", "json"):
        with pytest.raises(ValueError):
            get_parser(absent)


def test_extension_mapping_handles_canonical_extensions() -> None:
    assert file_type_for_extension(".md") == "markdown"
    assert file_type_for_extension(".markdown") == "markdown"
    assert file_type_for_extension(".txt") == "text"
    assert file_type_for_extension(".text") == "text"


def test_extension_mapping_is_case_insensitive() -> None:
    assert file_type_for_extension(".MD") == "markdown"
    assert file_type_for_extension(".Txt") == "text"


def test_extension_mapping_returns_none_for_unsupported() -> None:
    assert file_type_for_extension(".pdf") is None
    assert file_type_for_extension(".docx") is None
    assert file_type_for_extension("") is None
