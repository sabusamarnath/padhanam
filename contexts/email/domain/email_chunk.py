"""EmailChunk — a body chunk of a stored Email (D151).

Email bodies are long (the largest divergence from calendar's short
meeting summaries), so a body is chunked and each chunk embedded into the
email-local ``email_chunks`` store. The chunk text is sensitive content,
so it is P3 envelope-encrypted at rest (D21) like the parent Email's
body; the per-chunk ``vector(768)`` is written through a dedicated adapter
path. Framework-free per D16.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class EmailChunk:
    id: UUID
    email_id: UUID
    message_id: str
    chunk_index: int
    content: str

    def __post_init__(self) -> None:
        if self.chunk_index < 0:
            raise ValueError("EmailChunk.chunk_index must be >= 0")
        if not self.content or not self.content.strip():
            raise ValueError("EmailChunk.content must be non-empty")


__all__ = ["EmailChunk"]
