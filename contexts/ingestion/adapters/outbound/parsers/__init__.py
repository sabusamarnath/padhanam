"""Parser adapter registry (D61).

The composition layer (the worker entry-point at apps/cli/_ingest)
calls ``get_parser(file_type)`` to fetch the right adapter
instance. Keeping construction here rather than in the application
layer preserves the hexagonal-layers contract: application code
never reaches into adapters.

Stateless adapters are constructed per call at S19 — markdown-it-py
and the plain-text walker have no measurable startup cost at the
expected per-source-pipeline cadence. Future stateful adapters
(e.g., a PDF parser holding a long-lived OCR pipeline) cache here
when their cost profile justifies it.
"""

from __future__ import annotations

from contexts.ingestion.adapters.outbound.parsers.markdown_parser import (
    MarkdownParser,
)
from contexts.ingestion.adapters.outbound.parsers.plain_text_parser import (
    PlainTextParser,
)
from contexts.ingestion.ports.parser_port import ParserPort


def get_parser(file_type: str) -> ParserPort:
    """Return the parser adapter for the given file_type.

    Mirrors ``contexts/ingestion/application/parser_dispatch``'s
    SUPPORTED_FILE_TYPES set. A divergence between the application-
    layer routing surface and this registry is a programming bug —
    the SUPPORTED_FILE_TYPES set is the source of truth and this
    function asserts the same membership.
    """
    if file_type == "markdown":
        return MarkdownParser()
    if file_type == "text":
        return PlainTextParser()
    raise ValueError(
        f"no parser adapter registered for file_type {file_type!r}"
    )


__all__ = [
    "MarkdownParser",
    "PlainTextParser",
    "get_parser",
]
