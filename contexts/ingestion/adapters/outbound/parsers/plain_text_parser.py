"""Plain-text parser adapter (D61).

Splits plain-text content on paragraph boundaries (one or more
blank lines). Each chunk's structural_metadata carries
``{"paragraph_index": int}`` so downstream consumers (retrieval,
recommendation surface) can preserve order.

Behaviour:

  - Paragraphs are separated by one or more blank lines (whitespace-
    only lines collapse to a separator). Standard ``str.split`` on
    ``"\n\n"`` is too brittle (handles ``\r\n`` ambiguously and
    misses runs of blank lines); the implementation walks lines and
    accumulates non-blank groups instead.
  - Whitespace-only paragraphs are filtered out.
  - Empty content (no non-whitespace) produces
    ``ParsedContent(chunks=())``.
  - Each chunk is trimmed of leading/trailing whitespace.
"""

from __future__ import annotations

from contexts.ingestion.domain.parsed_content import ParsedChunk, ParsedContent
from contexts.ingestion.domain.source import Source
from contexts.ingestion.ports.parser_port import ParserError


class PlainTextParser:
    """Adapter for ParserPort against plain-text sources."""

    def parse(self, source: Source) -> ParsedContent:
        try:
            text = source.raw_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParserError(
                f"plain-text source is not valid UTF-8: {exc}"
            ) from exc

        if not text.strip():
            return ParsedContent(chunks=())

        paragraphs: list[str] = []
        buffer: list[str] = []
        for line in text.splitlines():
            if line.strip() == "":
                if buffer:
                    paragraphs.append("\n".join(buffer).strip())
                    buffer = []
                continue
            buffer.append(line)
        if buffer:
            paragraphs.append("\n".join(buffer).strip())

        chunks = tuple(
            ParsedChunk(
                content=para,
                structural_metadata={"paragraph_index": idx},
            )
            for idx, para in enumerate(paragraphs)
            if para
        )
        return ParsedContent(chunks=chunks)
