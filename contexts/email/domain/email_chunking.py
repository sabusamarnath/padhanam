"""Email body chunker (D151) — the email-local chunker.

The largest divergence from calendar: email bodies are long, so they are
split into chunks for embedding. Ingestion's chunking is embedded in its
format-specific parsers (markdown/plain-text), each coupled to ingestion's
``Source`` domain object — not a standalone tool — so email builds its own
small chunker rather than constructing a synthetic Source (the
substrate-inheritance discipline: inherit the embedder *port*, build the
context-specific glue). Paragraph-aware greedy packing into ~``max_chars``
windows, hard-splitting an over-long paragraph; mirrors plain-text's
paragraph logic with a length cap.

Chunks the Email's synthesised text (subject + body) so the subject is
searchable. Framework-free per D16.
"""

from __future__ import annotations

from uuid import uuid4

from contexts.email.domain.email import Email
from contexts.email.domain.email_chunk import EmailChunk

_DEFAULT_MAX_CHARS = 1000


def _paragraphs(text: str) -> list[str]:
    paras: list[str] = []
    buffer: list[str] = []
    for line in text.splitlines():
        if line.strip() == "":
            if buffer:
                paras.append("\n".join(buffer).strip())
                buffer = []
            continue
        buffer.append(line)
    if buffer:
        paras.append("\n".join(buffer).strip())
    return [p for p in paras if p]


def _pack(paragraphs: list[str], max_chars: int) -> list[str]:
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        # Hard-split an over-long paragraph into max_chars windows.
        while len(para) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:max_chars])
            para = para[max_chars:]
        if not current:
            current = para
        elif len(current) + 2 + len(para) <= max_chars:
            current = f"{current}\n\n{para}"
        else:
            chunks.append(current)
            current = para
    if current:
        chunks.append(current)
    return chunks


def chunk_email(email: Email, *, max_chars: int = _DEFAULT_MAX_CHARS) -> list[EmailChunk]:
    """Split an Email's subject+body into ordered EmailChunks (empty if no text)."""
    text = email.to_search_text()
    if not text.strip():
        return []
    contents = _pack(_paragraphs(text), max_chars)
    return [
        EmailChunk(
            id=uuid4(),
            email_id=email.id,
            message_id=email.message_id,
            chunk_index=idx,
            content=content,
        )
        for idx, content in enumerate(contents)
        if content.strip()
    ]


__all__ = ["chunk_email"]
