"""Unit tests for the tool aggregates (D89).

Mirrors `tests/unit/contexts/methodology/domain/test_role.py` shape:
factory functions for the two aggregates with default fixture values,
plus tests for the classification enum, the Phase 1 classification
sets, and the canonical hash-payload contract (which the postgres
adapter and migration both rely on for chain integrity).
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from uuid import UUID

import pytest

from contexts.tools.domain.tool import (
    Classification,
    PHASE_1_PROHIBITED_CLASSIFICATIONS,
    PHASE_1_VISIBLE_CLASSIFICATIONS,
    Tool,
    ToolDefinition,
    ToolRevision,
)
from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)


_TOOL_ID = UUID("00000000-0000-4000-8000-0000000d0001")
_REV_ID = UUID("00000000-0000-4000-8000-0000000d0002")


def _tool(**overrides) -> Tool:
    defaults = dict(
        id=_TOOL_ID,
        name="retrieval",
        description="Search grounded knowledge.",
        classification=Classification.READ_ONLY,
        created_by_user_id="alice",
        created_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Tool(**defaults)


def _revision(**overrides) -> ToolRevision:
    defaults = dict(
        id=_REV_ID,
        tool_id=_TOOL_ID,
        version=1,
        parameters_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        returns_schema={"type": "string"},
        bc_result={},
        created_by_user_id="alice",
        created_at=datetime(2026, 5, 12, tzinfo=timezone.utc),
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash="placeholder",
    )
    defaults.update(overrides)
    return ToolRevision(**defaults)


class TestToolAggregateCreation:
    def test_tool_template_holds_metadata(self) -> None:
        t = _tool()
        assert t.id == _TOOL_ID
        assert t.name == "retrieval"
        assert t.classification is Classification.READ_ONLY
        assert t.archived_at is None

    def test_tool_template_is_frozen(self) -> None:
        t = _tool()
        with pytest.raises(dataclasses.FrozenInstanceError):
            t.name = "rebound"  # type: ignore[misc]

    def test_tool_template_supports_archival_field(self) -> None:
        archived = datetime(2026, 6, 1, tzinfo=timezone.utc)
        t = _tool(archived_at=archived)
        assert t.archived_at == archived


class TestToolRevisionCreation:
    def test_revision_holds_schemas(self) -> None:
        r = _revision()
        assert r.tool_id == _TOOL_ID
        assert r.version == 1
        assert r.parameters_schema["properties"]["query"]["type"] == "string"
        assert r.returns_schema == {"type": "string"}
        assert r.bc_result == {}

    def test_revision_is_frozen(self) -> None:
        r = _revision()
        with pytest.raises(dataclasses.FrozenInstanceError):
            r.version = 2  # type: ignore[misc]


class TestClassificationEnum:
    def test_all_six_classifications_present(self) -> None:
        assert {c.value for c in Classification} == {
            "read-only",
            "drafting",
            "user-affecting-with-consent",
            "financial",
            "communication",
            "legal",
        }

    def test_phase_1_prohibited_set_matches_d89(self) -> None:
        assert PHASE_1_PROHIBITED_CLASSIFICATIONS == frozenset(
            {
                Classification.FINANCIAL,
                Classification.COMMUNICATION,
                Classification.LEGAL,
            }
        )

    def test_phase_1_visible_set_matches_d89(self) -> None:
        assert PHASE_1_VISIBLE_CLASSIFICATIONS == frozenset(
            {
                Classification.READ_ONLY,
                Classification.DRAFTING,
                Classification.USER_AFFECTING_WITH_CONSENT,
            }
        )

    def test_prohibited_and_visible_sets_disjoint(self) -> None:
        assert (
            PHASE_1_PROHIBITED_CLASSIFICATIONS
            & PHASE_1_VISIBLE_CLASSIFICATIONS
            == frozenset()
        )

    def test_prohibited_and_visible_sets_cover_taxonomy(self) -> None:
        all_classes = set(Classification)
        union = PHASE_1_PROHIBITED_CLASSIFICATIONS | PHASE_1_VISIBLE_CLASSIFICATIONS
        assert union == all_classes


class TestToolDefinitionValueObject:
    def test_tool_definition_carries_full_surface(self) -> None:
        td = ToolDefinition(
            tool_id=_TOOL_ID,
            revision_id=_REV_ID,
            name="retrieval",
            description="Search grounded knowledge.",
            classification=Classification.READ_ONLY,
            parameters_schema={"type": "object"},
            returns_schema={"type": "string"},
        )
        assert td.tool_id == _TOOL_ID
        assert td.revision_id == _REV_ID
        assert td.classification is Classification.READ_ONLY

    def test_tool_definition_is_frozen(self) -> None:
        td = ToolDefinition(
            tool_id=_TOOL_ID,
            revision_id=_REV_ID,
            name="retrieval",
            description="Search.",
            classification=Classification.READ_ONLY,
            parameters_schema={},
            returns_schema={},
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            td.name = "rebound"  # type: ignore[misc]


class TestRevisionHashChainContract:
    """The canonical hash payload is what the postgres adapter's
    ``verify_chain_integrity`` recomputes against. The migration's
    seed routine for retrieval composes the same payload inline; the
    test holds the contract."""

    def test_payload_field_set_documented(self) -> None:
        """The hash spans these fields per the D89 schema.md section."""
        tool = _tool()
        rev = _revision()
        payload = {
            "name": tool.name,
            "description": tool.description,
            "classification": tool.classification.value,
            "parameters_schema": dict(rev.parameters_schema),
            "returns_schema": dict(rev.returns_schema),
        }
        result = compute_revision_hash(
            content_payload=payload,
            previous_hash=rev.previous_revision_hash,
        )
        # Two genuine properties of the hash function: determinism +
        # length. Sensitivity to content is exercised by
        # test_hash_changes_when_field_value_changes below.
        assert len(result) == 64
        assert (
            compute_revision_hash(
                content_payload=payload,
                previous_hash=rev.previous_revision_hash,
            )
            == result
        )

    def test_hash_changes_when_field_value_changes(self) -> None:
        tool = _tool()
        rev = _revision()
        base_payload = {
            "name": tool.name,
            "description": tool.description,
            "classification": tool.classification.value,
            "parameters_schema": dict(rev.parameters_schema),
            "returns_schema": dict(rev.returns_schema),
        }
        h1 = compute_revision_hash(
            content_payload=base_payload,
            previous_hash=rev.previous_revision_hash,
        )

        mutated = {**base_payload, "description": "Different description."}
        h2 = compute_revision_hash(
            content_payload=mutated,
            previous_hash=rev.previous_revision_hash,
        )
        assert h1 != h2

    def test_classification_string_value_appears_in_payload(self) -> None:
        """Sanity check: the classification enum's ``.value`` is what
        the migration writes; storing the Python enum object would
        produce a different canonical-JSON encoding and silently break
        chain integrity at verify time."""
        tool = _tool(classification=Classification.READ_ONLY)
        rev = _revision()
        h_value = compute_revision_hash(
            content_payload={
                "name": tool.name,
                "description": tool.description,
                "classification": tool.classification.value,
                "parameters_schema": dict(rev.parameters_schema),
                "returns_schema": dict(rev.returns_schema),
            },
            previous_hash=rev.previous_revision_hash,
        )
        h_str = compute_revision_hash(
            content_payload={
                "name": tool.name,
                "description": tool.description,
                "classification": "read-only",
                "parameters_schema": dict(rev.parameters_schema),
                "returns_schema": dict(rev.returns_schema),
            },
            previous_hash=rev.previous_revision_hash,
        )
        assert h_value == h_str
