"""Source aggregate — the upload primitive (D60 / D61).

The user-facing primitive for ingestion: a file submitted by a
tenant for parsing into chunks, embedding into pgvector, and
extraction into Neo4j. S19 lands the upload + parse stages; S20
adds embedding, S21 adds extraction.

Frozen dataclass per the codebase's domain-purity discipline (D16).
The Postgres adapter is responsible for the impedance mismatch
between Python frozen dataclasses and SQLAlchemy Core; the domain
stays free of vendor concerns.

raw_content is bytes at S19 — the dev shape stores raw bytes on
the row directly. Production object-store URI defers to production
deployment context per D60. The migration's ``raw_content`` column
is bytea so the wire shape carries the bytes verbatim.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.ingestion.domain.state import SourceState


@dataclass(frozen=True)
class Source:
    id: UUID
    tenant_id: str
    jurisdiction: str
    file_name: str
    file_type: str
    file_size_bytes: int
    raw_content: bytes
    state: SourceState
    parsing_error_text: str | None
    created_by_user_id: str
    created_at: datetime
    updated_at: datetime
    # S20 / D62: embedding-stage error surface, mirroring
    # parsing_error_text. Defaulted to None so existing call sites
    # (S19 register_source) continue to construct without churn.
    embedding_error_text: str | None = None
