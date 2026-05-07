"""Unit tests for the ChunkResult and EntityResult value objects (D65).

Frozen-dataclass invariants and the ``__post_init__`` validation per
D50's TenantContext discipline applied to the retrieval-result
shape. The adapters' query behaviour is exercised by the live
integration tests; this module fences the domain shape itself.
"""

from __future__ import annotations

from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.ingestion.domain.chunk_result import ChunkResult
from contexts.ingestion.domain.entity_result import EntityResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def test_chunk_result_frozen() -> None:
    result = ChunkResult(
        chunk_id=uuid4(),
        source_id=uuid4(),
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        content="hello",
        structural_metadata={"heading": "intro"},
        similarity_score=0.87,
        created_at=_utcnow(),
    )
    with pytest.raises(FrozenInstanceError):
        result.similarity_score = 0.5  # type: ignore[misc]


def test_chunk_result_rejects_empty_tenant_id() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        ChunkResult(
            chunk_id=uuid4(),
            source_id=uuid4(),
            tenant_id="",
            jurisdiction="eu-west",
            content="hello",
            structural_metadata={},
            similarity_score=0.5,
            created_at=_utcnow(),
        )


def test_chunk_result_rejects_empty_jurisdiction() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        ChunkResult(
            chunk_id=uuid4(),
            source_id=uuid4(),
            tenant_id="00000000-0000-4000-8000-00000000a001",
            jurisdiction="",
            content="hello",
            structural_metadata={},
            similarity_score=0.5,
            created_at=_utcnow(),
        )


def test_entity_result_frozen() -> None:
    result = EntityResult(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        name="ACME Corp",
        entity_type="Organisation",
        source_chunk_ids=(uuid4(),),
        relationship_path=("EMPLOYS",),
        created_at=_utcnow(),
    )
    with pytest.raises(FrozenInstanceError):
        result.name = "Other"  # type: ignore[misc]


def test_entity_result_rejects_empty_tenant_id() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        EntityResult(
            tenant_id="",
            jurisdiction="eu-west",
            name="ACME Corp",
            entity_type="Organisation",
            source_chunk_ids=(),
            relationship_path=(),
            created_at=_utcnow(),
        )


def test_entity_result_rejects_empty_jurisdiction() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        EntityResult(
            tenant_id="00000000-0000-4000-8000-00000000a001",
            jurisdiction="",
            name="ACME Corp",
            entity_type="Organisation",
            source_chunk_ids=(),
            relationship_path=(),
            created_at=_utcnow(),
        )


def test_entity_result_seed_has_empty_relationship_path() -> None:
    """The seed entity at depth=0 surfaces with an empty path tuple;
    no validation forbids the empty path. Read-side consumers
    distinguish seed from neighbours by ``len(relationship_path) == 0``.
    """
    seed = EntityResult(
        tenant_id="00000000-0000-4000-8000-00000000a001",
        jurisdiction="eu-west",
        name="ACME Corp",
        entity_type="Organisation",
        source_chunk_ids=(uuid4(),),
        relationship_path=(),
        created_at=_utcnow(),
    )
    assert seed.relationship_path == ()
