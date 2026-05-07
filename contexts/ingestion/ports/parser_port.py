"""ParserPort — the parser-as-port shape (D61).

Each format adapter implements ``parse(source) -> ParsedContent``.
The parser receives the full ``Source`` (raw_content + file_type
+ tenant context) and returns ordered chunks plus structural
metadata. Format dispatch happens at
``contexts/ingestion/application/parser_dispatch.py`` and routes
by ``source.file_type``.

Two adapters land at S19: MarkdownParser, PlainTextParser. PDF,
DOCX, HTML defer to sessions with real consumers per D61. The
port shape is the architectural commitment that gates the format
extension surface — additional formats land as adapter additions
plus a dispatch entry, not as a refactor of the worker or the
register-source use case.

Errors: parsers signal unparseable content by raising
``ParserError`` (defined alongside the port). The worker catches
it, transitions the source to FAILED with the error text in
parsing_error_text. Implementation errors (programming bugs) bubble
up so they surface as worker crashes the operator notices rather
than silently-failed sources.
"""

from __future__ import annotations

from typing import Protocol

from contexts.ingestion.domain.parsed_content import ParsedContent
from contexts.ingestion.domain.source import Source


class ParserError(Exception):
    """Raised by parsers when content is structurally invalid for
    the format. The worker catches this, marks the source FAILED,
    populates parsing_error_text. Distinguished from generic
    Exception so unrelated bugs surface as crashes rather than
    silently-failed sources.
    """


class ParserPort(Protocol):
    def parse(self, source: Source) -> ParsedContent:
        """Return parsed chunks for the source.

        Raises ``ParserError`` for content that is structurally
        invalid for this parser's format.
        """
        ...
