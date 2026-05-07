"""Embedding value object — the per-chunk vector (D62).

The ChunkEmbedder port returns one Embedding per Chunk it
processes. The vector is a list of floats (768-dim for the S20
default ``nomic-embed-text:v1.5``); the dimension is not enforced
on the Python side because the database column type ``vector(768)``
is the architectural authority. Mismatches surface as Postgres
errors at write time rather than as silently-truncated vectors.

Frozen dataclass per D16 — the domain is framework-free.

The chunk_id field carries the identity link back to ``chunks.id``
so the worker can write embeddings via UPSERT on the primary key
per D62's idempotent-re-embed commitment.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence
from uuid import UUID


@dataclass(frozen=True)
class Embedding:
    chunk_id: UUID
    vector: Sequence[float]
    model: str
