"""Unit tests for the Source / Chunk / SourceState domain types.

The domain is framework-free per D16 — these tests exercise only
stdlib behaviour (frozen dataclass immutability, StrEnum value
parity). The Postgres adapter's behaviour is exercised by the
worker integration test at commit 6 against the live tenant_a
data plane.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.ingestion.domain.chunk import Chunk
from contexts.ingestion.domain.source import Source
from contexts.ingestion.domain.state import SourceState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def test_source_state_values_match_schema_check_constraint() -> None:
    """SourceState values mirror the CHECK constraint on sources.state
    landed in revision 0005. If the values diverge the worker will
    write strings the schema rejects; the test pins the contract.
    """
    assert {s.value for s in SourceState} == {
        "received",
        "parsing",
        "parsed",
        "failed",
    }


def test_source_state_str_compatible() -> None:
    """SourceState is a StrEnum so the adapter's ``state.value``
    write path also works for direct string equality (e.g.
    ``state == 'received'`` in joins or filters)."""
    assert SourceState.RECEIVED == "received"
    assert SourceState.PARSED == "parsed"


def test_source_dataclass_is_frozen() -> None:
    source = Source(
        id=uuid4(),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        file_name="x.md",
        file_type="markdown",
        file_size_bytes=10,
        raw_content=b"# hello\n",
        state=SourceState.RECEIVED,
        parsing_error_text=None,
        created_by_user_id="user-1",
        created_at=_utcnow(),
        updated_at=_utcnow(),
    )
    with pytest.raises(FrozenInstanceError):
        source.state = SourceState.PARSED  # type: ignore[misc]


def test_chunk_dataclass_default_metadata_empty() -> None:
    chunk = Chunk(
        id=uuid4(),
        source_id=uuid4(),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        chunk_index=0,
        content="paragraph one",
    )
    assert chunk.structural_metadata == {}
    assert chunk.created_at is None


def test_chunk_carries_structural_metadata() -> None:
    metadata = {"heading_text": "Introduction", "heading_level": 1}
    chunk = Chunk(
        id=uuid4(),
        source_id=uuid4(),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        chunk_index=0,
        content="under intro",
        structural_metadata=metadata,
    )
    assert chunk.structural_metadata == metadata


def test_chunk_dataclass_is_frozen() -> None:
    chunk = Chunk(
        id=uuid4(),
        source_id=uuid4(),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        chunk_index=0,
        content="x",
    )
    with pytest.raises(FrozenInstanceError):
        chunk.content = "y"  # type: ignore[misc]
