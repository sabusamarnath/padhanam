"""Markdown parser adapter (D61).

Splits markdown content on heading boundaries, preserving the
heading hierarchy as structural metadata. Uses ``markdown-it-py``
per D61 — its token-based AST exposes the source-line range of
each token via the ``map`` attribute, which is the cleanest seam
for boundary-aware slicing of the original text. Re-emitting the
markdown from tokens would lose round-trip fidelity for atx vs
setext headings, fenced vs indented code, and other variations
the operator may have authored intentionally; slicing the source
text by heading position preserves the original verbatim.

Behaviour:

  - Each heading begins a new chunk. The chunk's
    ``structural_metadata`` carries
    ``{"heading_text": str, "heading_level": int}``.
  - Content before the first heading (if any) becomes a chunk with
    empty ``structural_metadata`` so the front-matter or intro is
    not silently dropped.
  - Empty content (whitespace-only) collapses to no chunks. An
    empty markdown file produces ``ParsedContent(chunks=())``.
  - Each chunk is trimmed of leading and trailing whitespace; the
    chunk content includes the heading line itself so the chunk is
    self-describing when displayed.
"""

from __future__ import annotations

from markdown_it import MarkdownIt

from contexts.ingestion.domain.parsed_content import ParsedChunk, ParsedContent
from contexts.ingestion.domain.source import Source
from contexts.ingestion.ports.parser_port import ParserError


class MarkdownParser:
    """Adapter for ParserPort against markdown sources."""

    def __init__(self) -> None:
        self._md = MarkdownIt()

    def parse(self, source: Source) -> ParsedContent:
        try:
            text = source.raw_content.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ParserError(
                f"markdown source is not valid UTF-8: {exc}"
            ) from exc

        if not text.strip():
            return ParsedContent(chunks=())

        lines = text.splitlines(keepends=True)
        tokens = self._md.parse(text)

        # Collect (start_line, heading_text, heading_level) tuples
        # for every heading. heading_text comes from the inline token
        # immediately following the heading_open.
        boundaries: list[tuple[int, str, int]] = []
        i = 0
        while i < len(tokens):
            tok = tokens[i]
            if tok.type == "heading_open" and tok.map is not None:
                level = int(tok.tag[1:])  # 'h1' → 1
                heading_text = ""
                if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                    heading_text = tokens[i + 1].content.strip()
                boundaries.append((tok.map[0], heading_text, level))
            i += 1

        chunks: list[ParsedChunk] = []

        # Pre-first-heading content (front matter, intro paragraphs).
        if not boundaries or boundaries[0][0] > 0:
            end = boundaries[0][0] if boundaries else len(lines)
            preamble = "".join(lines[0:end]).strip()
            if preamble:
                chunks.append(ParsedChunk(content=preamble))

        # Heading-anchored chunks.
        for idx, (start_line, heading_text, heading_level) in enumerate(
            boundaries
        ):
            end_line = (
                boundaries[idx + 1][0]
                if idx + 1 < len(boundaries)
                else len(lines)
            )
            chunk_text = "".join(lines[start_line:end_line]).strip()
            if not chunk_text:
                continue
            chunks.append(
                ParsedChunk(
                    content=chunk_text,
                    structural_metadata={
                        "heading_text": heading_text,
                        "heading_level": heading_level,
                    },
                )
            )

        return ParsedContent(chunks=tuple(chunks))
