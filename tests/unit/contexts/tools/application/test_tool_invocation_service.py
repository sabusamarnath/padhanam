"""Unit tests for the tool invocation service (D89).

Covers the classification filter at the definitions surface and the
defensive invariant check at the invocation boundary. Uses the
same fake repository pattern as ``test_use_cases.py``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.tools.application.tool_invocation_service import (
    InvocationAdmissibility,
    InvocationCheckOutcome,
    check_invocation_admissibility,
    list_visible_definitions,
)
from contexts.tools.domain.exceptions import (
    RevisionNotFoundError,
    ToolNotFoundError,
)
from contexts.tools.domain.tool import (
    Classification,
    Tool,
    ToolRevision,
)
from contexts.tools.ports import RoleToolBinding
from padhanam.security.hash_chain import GENESIS_REVISION_HASH


_PARAMS = {"type": "object", "properties": {"q": {"type": "string"}}}
_RETURNS = {"type": "string"}


def _make_tool(classification: Classification, name: str = "t") -> Tool:
    return Tool(
        id=uuid4(),
        name=name,
        description=f"{name} description",
        classification=classification,
        created_by_user_id="op",
        created_at=datetime.now(timezone.utc),
    )


def _make_revision(tool: Tool) -> ToolRevision:
    return ToolRevision(
        id=uuid4(),
        tool_id=tool.id,
        version=1,
        parameters_schema=_PARAMS,
        returns_schema=_RETURNS,
        bc_result={},
        created_by_user_id="op",
        created_at=datetime.now(timezone.utc),
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash="hash-" + str(tool.id)[:8],
    )


class _FakeToolRepository:
    def __init__(self) -> None:
        self.tools_by_id: dict[UUID, Tool] = {}
        self.revisions_by_id: dict[UUID, ToolRevision] = {}

    def register(self, tool: Tool, revision: ToolRevision) -> None:
        self.tools_by_id[tool.id] = tool
        self.revisions_by_id[revision.id] = revision

    async def find_revision(
        self, revision_id: UUID,
    ) -> tuple[Tool, ToolRevision]:
        if revision_id not in self.revisions_by_id:
            raise RevisionNotFoundError(
                f"revision {revision_id} not found"
            )
        rev = self.revisions_by_id[revision_id]
        if rev.tool_id not in self.tools_by_id:
            raise ToolNotFoundError(
                f"tool {rev.tool_id} not found"
            )
        return self.tools_by_id[rev.tool_id], rev

    # Stub remaining ports for Protocol satisfaction.
    async def create_template(self, *a, **k): ...  # pragma: no cover
    async def get_template(self, *a, **k): ...  # pragma: no cover
    async def list_templates(self, *a, **k): ...  # pragma: no cover
    async def add_revision(self, *a, **k): ...  # pragma: no cover
    async def archive_template(self, *a, **k): ...  # pragma: no cover
    async def verify_chain_integrity(self, *a, **k): ...  # pragma: no cover
    async def list_roles_using_tool(self, *a, **k) -> list[RoleToolBinding]:
        return []  # pragma: no cover


class TestListVisibleDefinitions:
    def test_filters_out_high_classification_tools(self) -> None:
        repo = _FakeToolRepository()
        # Phase-1 visible
        t_read = _make_tool(Classification.READ_ONLY, "retrieval")
        r_read = _make_revision(t_read)
        repo.register(t_read, r_read)
        t_draft = _make_tool(Classification.DRAFTING, "drafter")
        r_draft = _make_revision(t_draft)
        repo.register(t_draft, r_draft)
        t_user = _make_tool(
            Classification.USER_AFFECTING_WITH_CONSENT, "updater"
        )
        r_user = _make_revision(t_user)
        repo.register(t_user, r_user)
        # Phase-1 prohibited (cannot be authored at Phase 1 per D89,
        # but the registry could hold legacy or test rows; the filter
        # excludes them defensively)
        t_fin = _make_tool(Classification.FINANCIAL, "transfer")
        r_fin = _make_revision(t_fin)
        repo.register(t_fin, r_fin)
        t_com = _make_tool(Classification.COMMUNICATION, "send-email")
        r_com = _make_revision(t_com)
        repo.register(t_com, r_com)
        t_leg = _make_tool(Classification.LEGAL, "accept-terms")
        r_leg = _make_revision(t_leg)
        repo.register(t_leg, r_leg)

        references = [
            (t_read.id, r_read.id),
            (t_draft.id, r_draft.id),
            (t_user.id, r_user.id),
            (t_fin.id, r_fin.id),
            (t_com.id, r_com.id),
            (t_leg.id, r_leg.id),
        ]
        defs = asyncio.run(
            list_visible_definitions(
                repository=repo, references=references,
            )
        )
        names = {d.name for d in defs}
        assert names == {"retrieval", "drafter", "updater"}

    def test_skips_missing_references(self) -> None:
        repo = _FakeToolRepository()
        t = _make_tool(Classification.READ_ONLY)
        r = _make_revision(t)
        repo.register(t, r)
        defs = asyncio.run(
            list_visible_definitions(
                repository=repo,
                references=[
                    (t.id, r.id),
                    (uuid4(), uuid4()),  # unknown
                ],
            )
        )
        assert len(defs) == 1

    def test_skips_inconsistent_revision_tool_binding(self) -> None:
        """An allowlist entry claiming tool X but revision_id belongs
        to tool Y is structurally inconsistent. The service skips
        rather than raises."""
        repo = _FakeToolRepository()
        t1 = _make_tool(Classification.READ_ONLY, "one")
        r1 = _make_revision(t1)
        repo.register(t1, r1)
        t2 = _make_tool(Classification.READ_ONLY, "two")
        r2 = _make_revision(t2)
        repo.register(t2, r2)

        defs = asyncio.run(
            list_visible_definitions(
                repository=repo,
                references=[
                    (t1.id, r2.id),  # mismatched binding
                ],
            )
        )
        assert defs == ()


class TestCheckInvocationAdmissibility:
    def test_read_only_permitted(self) -> None:
        repo = _FakeToolRepository()
        t = _make_tool(Classification.READ_ONLY)
        r = _make_revision(t)
        repo.register(t, r)
        result = asyncio.run(
            check_invocation_admissibility(
                repository=repo, tool_id=t.id, revision_id=r.id,
            )
        )
        assert result.outcome is InvocationCheckOutcome.PERMITTED
        assert result.invariant_index is None
        assert result.tool is not None and result.tool.id == t.id

    @pytest.mark.parametrize(
        "classification,expected_index",
        [
            (Classification.FINANCIAL, 1),
            (Classification.COMMUNICATION, 2),
            (Classification.LEGAL, 3),
        ],
    )
    def test_high_classification_blocked_with_invariant_index(
        self, classification: Classification, expected_index: int,
    ) -> None:
        repo = _FakeToolRepository()
        t = _make_tool(classification)
        r = _make_revision(t)
        repo.register(t, r)
        result = asyncio.run(
            check_invocation_admissibility(
                repository=repo, tool_id=t.id, revision_id=r.id,
            )
        )
        assert result.outcome is InvocationCheckOutcome.INVARIANT_BLOCKED
        assert result.invariant_index == expected_index
        assert classification.value in result.message
        assert f"invariant {expected_index}" in result.message

    def test_unknown_revision_surfaces_outcome(self) -> None:
        repo = _FakeToolRepository()
        result = asyncio.run(
            check_invocation_admissibility(
                repository=repo, tool_id=uuid4(), revision_id=uuid4(),
            )
        )
        assert result.outcome is InvocationCheckOutcome.REVISION_NOT_FOUND

    def test_inconsistent_binding_surfaces_outcome(self) -> None:
        repo = _FakeToolRepository()
        t1 = _make_tool(Classification.READ_ONLY, "one")
        r1 = _make_revision(t1)
        repo.register(t1, r1)
        # Caller names tool t2 but supplies revision_id of t1
        result = asyncio.run(
            check_invocation_admissibility(
                repository=repo, tool_id=uuid4(), revision_id=r1.id,
            )
        )
        assert result.outcome is InvocationCheckOutcome.REVISION_NOT_FOUND
        assert "binding inconsistent" in result.message
