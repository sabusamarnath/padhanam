"""Unit tests for citation candidate domain value objects (D96, S32).

The candidate types are frozen dataclasses at the agent context's
domain layer. Tests fence every invariant the ``__post_init__``
methods enforce so the constructors refuse inconsistent inputs at
construction time. Discriminated-union dispatch via ``isinstance`` is
exercised separately so consumers (the run-history wiring adapter,
Phase 2 UX render dispatch) have a structural contract to rely on.
"""

from __future__ import annotations

import dataclasses
from uuid import UUID, uuid4

import pytest

from contexts.agent.domain.citation_candidates import (
    ChunkCitationCandidate,
    CitationCandidate,
    EntityCitationCandidate,
)


_CHUNK_ID = UUID("11111111-1111-4111-8111-111111111111")
_SOURCE_ID = UUID("22222222-2222-4222-8222-222222222222")


def _valid_chunk(**overrides) -> ChunkCitationCandidate:
    defaults: dict = dict(
        chunk_id=_CHUNK_ID,
        source_id=_SOURCE_ID,
        chunk_index=0,
        content_snapshot="chunk content",
        source_snapshot={"file_name": "doc.pdf", "file_type": "application/pdf"},
        tenant_id="tenant-a",
        jurisdiction="eu-west",
    )
    defaults.update(overrides)
    return ChunkCitationCandidate(**defaults)


def _valid_entity(**overrides) -> EntityCitationCandidate:
    defaults: dict = dict(
        entity_tenant_id="tenant-a",
        entity_name="Acme Corp",
        entity_type="Organization",
        source_chunk_ids=(_CHUNK_ID,),
        tenant_id="tenant-a",
        jurisdiction="eu-west",
    )
    defaults.update(overrides)
    return EntityCitationCandidate(**defaults)


# ---------------------------------------------------------------------------
# ChunkCitationCandidate: construction + invariants
# ---------------------------------------------------------------------------


def test_chunk_candidate_constructs_with_valid_fields() -> None:
    candidate = _valid_chunk()
    assert candidate.chunk_id == _CHUNK_ID
    assert candidate.source_id == _SOURCE_ID
    assert candidate.chunk_index == 0
    assert candidate.content_snapshot == "chunk content"
    assert candidate.source_snapshot == {
        "file_name": "doc.pdf",
        "file_type": "application/pdf",
    }
    assert candidate.tenant_id == "tenant-a"
    assert candidate.jurisdiction == "eu-west"


def test_chunk_candidate_is_frozen() -> None:
    """Frozen dataclass forbids post-construction mutation."""
    candidate = _valid_chunk()
    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.chunk_index = 99  # type: ignore[misc]


def test_chunk_candidate_accepts_empty_source_snapshot() -> None:
    """Empty source_snapshot is the forward-affordance for tools that
    surface chunks without source-level metadata."""
    candidate = _valid_chunk(source_snapshot={})
    assert candidate.source_snapshot == {}


def test_chunk_candidate_accepts_chunk_index_zero() -> None:
    candidate = _valid_chunk(chunk_index=0)
    assert candidate.chunk_index == 0


def test_chunk_candidate_accepts_large_chunk_index() -> None:
    candidate = _valid_chunk(chunk_index=999)
    assert candidate.chunk_index == 999


def test_chunk_candidate_rejects_empty_tenant_id() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        _valid_chunk(tenant_id="")


def test_chunk_candidate_rejects_empty_jurisdiction() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        _valid_chunk(jurisdiction="")


def test_chunk_candidate_rejects_negative_chunk_index() -> None:
    with pytest.raises(ValueError, match="chunk_index"):
        _valid_chunk(chunk_index=-1)


def test_chunk_candidate_rejects_empty_content_snapshot() -> None:
    with pytest.raises(ValueError, match="content_snapshot"):
        _valid_chunk(content_snapshot="")


# ---------------------------------------------------------------------------
# EntityCitationCandidate: construction + invariants
# ---------------------------------------------------------------------------


def test_entity_candidate_constructs_with_valid_fields() -> None:
    candidate = _valid_entity()
    assert candidate.entity_tenant_id == "tenant-a"
    assert candidate.entity_name == "Acme Corp"
    assert candidate.entity_type == "Organization"
    assert candidate.source_chunk_ids == (_CHUNK_ID,)
    assert candidate.tenant_id == "tenant-a"
    assert candidate.jurisdiction == "eu-west"


def test_entity_candidate_is_frozen() -> None:
    candidate = _valid_entity()
    with pytest.raises(dataclasses.FrozenInstanceError):
        candidate.entity_name = "Other"  # type: ignore[misc]


def test_entity_candidate_accepts_empty_source_chunk_ids() -> None:
    """Forward-affordance for entities with no recorded source chunks."""
    candidate = _valid_entity(source_chunk_ids=())
    assert candidate.source_chunk_ids == ()


def test_entity_candidate_accepts_multiple_source_chunk_ids() -> None:
    other_chunk = UUID("33333333-3333-4333-8333-333333333333")
    candidate = _valid_entity(source_chunk_ids=(_CHUNK_ID, other_chunk))
    assert candidate.source_chunk_ids == (_CHUNK_ID, other_chunk)


def test_entity_candidate_rejects_empty_entity_tenant_id() -> None:
    with pytest.raises(ValueError, match="entity_tenant_id"):
        _valid_entity(entity_tenant_id="", tenant_id="tenant-a")


def test_entity_candidate_rejects_empty_entity_name() -> None:
    with pytest.raises(ValueError, match="entity_name"):
        _valid_entity(entity_name="")


def test_entity_candidate_rejects_empty_entity_type() -> None:
    with pytest.raises(ValueError, match="entity_type"):
        _valid_entity(entity_type="")


def test_entity_candidate_rejects_empty_tenant_id() -> None:
    with pytest.raises(ValueError, match="tenant_id"):
        _valid_entity(tenant_id="", entity_tenant_id="tenant-a")


def test_entity_candidate_rejects_empty_jurisdiction() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        _valid_entity(jurisdiction="")


def test_entity_candidate_rejects_tenant_id_mismatch() -> None:
    """The Neo4j entity's tenant property must match the runtime's
    bound tenant per D63. Mismatch indicates cross-tenant data leak
    that the candidate structurally rejects."""
    with pytest.raises(ValueError, match="entity_tenant_id"):
        _valid_entity(entity_tenant_id="tenant-a", tenant_id="tenant-b")


# ---------------------------------------------------------------------------
# CitationCandidate union: discriminated dispatch
# ---------------------------------------------------------------------------


def test_chunk_candidate_is_citation_candidate() -> None:
    candidate: CitationCandidate = _valid_chunk()
    assert isinstance(candidate, ChunkCitationCandidate)
    assert not isinstance(candidate, EntityCitationCandidate)


def test_entity_candidate_is_citation_candidate() -> None:
    candidate: CitationCandidate = _valid_entity()
    assert isinstance(candidate, EntityCitationCandidate)
    assert not isinstance(candidate, ChunkCitationCandidate)


def test_union_supports_isinstance_dispatch() -> None:
    """Consumers branch on isinstance to route candidates to the
    appropriate citation table or render path."""
    candidates: tuple[CitationCandidate, ...] = (
        _valid_chunk(),
        _valid_entity(),
        _valid_chunk(chunk_index=1, content_snapshot="other"),
    )
    chunks = [c for c in candidates if isinstance(c, ChunkCitationCandidate)]
    entities = [c for c in candidates if isinstance(c, EntityCitationCandidate)]
    assert len(chunks) == 2
    assert len(entities) == 1
