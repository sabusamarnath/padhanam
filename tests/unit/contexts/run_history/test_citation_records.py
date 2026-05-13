"""Unit tests for ChunkCitationRecord and EntityCitationRecord (D96, S32).

The run-history-context-owned record types mirror the agent-context
citation candidates one-for-one per the D54 mirror-types pattern.
Tests fence the invariants ``__post_init__`` enforces; the wiring
adapter at ``apps/cli/_cross_context.py`` translates candidates to
records, so the producer-side enforcement is defence-in-depth.
"""

from __future__ import annotations

import dataclasses
from uuid import UUID, uuid4

import pytest

from contexts.run_history.domain.citation_records import (
    ChunkCitationRecord,
    EntityCitationRecord,
)


_RUN_ID = UUID("11111111-1111-4111-8111-111111111111")
_CHUNK_ID = UUID("22222222-2222-4222-8222-222222222222")


def _valid_chunk(**overrides) -> ChunkCitationRecord:
    defaults: dict = dict(
        id=uuid4(),
        run_id=_RUN_ID,
        chunk_id=_CHUNK_ID,
        tenant_id="tenant-a",
        jurisdiction="eu-west",
        chunk_excerpt="content",
        source_snapshot={"file_name": "doc.pdf", "file_type": "application/pdf"},
    )
    defaults.update(overrides)
    return ChunkCitationRecord(**defaults)


def _valid_entity(**overrides) -> EntityCitationRecord:
    defaults: dict = dict(
        id=uuid4(),
        run_id=_RUN_ID,
        entity_tenant_id="tenant-a",
        entity_name="Acme",
        entity_type="Organization",
        tenant_id="tenant-a",
        source_chunk_ids=(_CHUNK_ID,),
    )
    defaults.update(overrides)
    return EntityCitationRecord(**defaults)


# ChunkCitationRecord


def test_chunk_record_constructs_with_valid_fields() -> None:
    record = _valid_chunk()
    assert record.tenant_id == "tenant-a"
    assert record.chunk_excerpt == "content"


def test_chunk_record_is_frozen() -> None:
    record = _valid_chunk()
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.chunk_excerpt = "other"  # type: ignore[misc]


def test_chunk_record_accepts_null_chunk_id() -> None:
    """ON DELETE SET NULL on chunk_id per D95 means existing rows can
    surface chunk_id=None after the source is removed; the domain
    type accepts this state."""
    record = _valid_chunk(chunk_id=None)
    assert record.chunk_id is None


def test_chunk_record_rejects_empty_tenant_id() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        _valid_chunk(tenant_id="")


def test_chunk_record_rejects_empty_jurisdiction() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        _valid_chunk(jurisdiction="")


def test_chunk_record_rejects_empty_excerpt() -> None:
    with pytest.raises(ValueError, match="chunk_excerpt"):
        _valid_chunk(chunk_excerpt="")


# EntityCitationRecord


def test_entity_record_constructs_with_valid_fields() -> None:
    record = _valid_entity()
    assert record.entity_name == "Acme"
    assert record.source_chunk_ids == (_CHUNK_ID,)


def test_entity_record_is_frozen() -> None:
    record = _valid_entity()
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.entity_name = "Other"  # type: ignore[misc]


def test_entity_record_accepts_empty_source_chunk_ids() -> None:
    """Forward-affordance for entities without recorded source chunks."""
    record = _valid_entity(source_chunk_ids=())
    assert record.source_chunk_ids == ()


def test_entity_record_rejects_empty_entity_tenant_id() -> None:
    with pytest.raises(ValueError, match="entity_tenant_id"):
        _valid_entity(entity_tenant_id="", tenant_id="tenant-a")


def test_entity_record_rejects_empty_entity_name() -> None:
    with pytest.raises(ValueError, match="entity_name"):
        _valid_entity(entity_name="")


def test_entity_record_rejects_empty_entity_type() -> None:
    with pytest.raises(ValueError, match="entity_type"):
        _valid_entity(entity_type="")


def test_entity_record_rejects_empty_tenant_id() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        _valid_entity(tenant_id="", entity_tenant_id="tenant-a")


def test_entity_record_rejects_tenant_id_mismatch() -> None:
    """entity_tenant_id must match tenant_id; mismatch indicates
    cross-tenant data leak the record type structurally rejects."""
    with pytest.raises(ValueError, match="entity_tenant_id"):
        _valid_entity(entity_tenant_id="tenant-a", tenant_id="tenant-b")
