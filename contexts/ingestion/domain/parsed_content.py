"""ParsedContent — the parser's return shape (D61).

A ``ParsedContent`` is what a parser hands back to the worker:
ordered chunk strings plus per-chunk structural metadata. The
worker turns each into a ``Chunk`` row (assigning chunk_index
positionally) and writes them atomically with the source state
transition.

structural_metadata at S19 is parser-specific:
  - markdown: ``{"heading_text": str, "heading_level": int}``
    when the chunk is anchored by a heading; ``{}`` for the
    pre-first-heading content if any.
  - plain text: ``{"paragraph_index": int}``.

The shape stays open per Mapping[str, object] so future parsers
(PDF page numbers, DOCX section names) extend without schema
churn.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ParsedChunk:
    content: str
    structural_metadata: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedContent:
    chunks: Sequence[ParsedChunk]
