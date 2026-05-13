"""Cross-context wiring adapter tests for ToolDefinitionsLookupAdapter
and ToolInvokerAdapter (S28b commit 7, D89).

Uses in-memory fake ToolRepositoryPort and AgentRetrievalClient to
exercise the adapter shape without docker dependencies. The
production wiring lives at apps/cli/_cross_context.py; these tests
verify the four key behaviours:

1. ToolDefinitionsLookupAdapter returns only Phase-1-visible tools.
2. ToolDefinitionsLookupAdapter translates tools-context
   ToolDefinition (4 fields) to inference-context ToolDefinition
   (3 fields).
3. ToolInvokerAdapter dispatches retrieval to AgentRetrievalClient.
4. ToolInvokerAdapter returns TOOL_NOT_REGISTERED for unknown tool
   names and INVARIANT_BLOCKED for high-classification tools.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from apps.cli._cross_context import (
    ToolDefinitionsLookupAdapter,
    ToolInvokerAdapter,
)
from contexts.agent.application.ports import (
    InvocationOutcome,
    RetrievedChunk,
)
from contexts.inference.domain.completion import ToolCall
from contexts.tools.domain.tool import (
    Classification,
    Tool,
    ToolRevision,
)
from contexts.tools.ports import RoleToolBinding
from padhanam.security.hash_chain import GENESIS_REVISION_HASH
from shared_kernel import TenantContext, ToolAllowlistEntry


_TENANT_A = TenantContext(
    tenant_id="00000000-0000-4000-8000-00000000a001",
    jurisdiction="eu-west",
    cost_attribution_id="00000000-0000-4000-8000-00000000a001",
)

_RETRIEVAL_TOOL_ID = UUID("00000000-0000-0000-0000-000000000001")
_RETRIEVAL_REVISION_ID = UUID("00000000-0000-0000-0000-000000000002")


def _make_tool(
    classification: Classification,
    name: str = "retrieval",
    tool_id: UUID | None = None,
) -> Tool:
    return Tool(
        id=tool_id or uuid4(),
        name=name,
        description=f"{name} description",
        classification=classification,
        created_by_user_id="op",
        created_at=datetime.now(timezone.utc),
    )


def _make_revision(
    tool: Tool,
    revision_id: UUID | None = None,
) -> ToolRevision:
    return ToolRevision(
        id=revision_id or uuid4(),
        tool_id=tool.id,
        version=1,
        parameters_schema={
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        returns_schema={"type": "string"},
        bc_result={},
        created_by_user_id="op",
        created_at=datetime.now(timezone.utc),
        previous_revision_hash=GENESIS_REVISION_HASH,
        this_revision_hash="hash-" + str(tool.id)[:8],
    )


class _FakeToolRepository:
    def __init__(self) -> None:
        self._by_id: dict[UUID, Tool] = {}
        self._revs_by_id: dict[UUID, ToolRevision] = {}

    def register(self, tool: Tool, revision: ToolRevision) -> None:
        self._by_id[tool.id] = tool
        self._revs_by_id[revision.id] = revision

    async def find_revision(self, revision_id: UUID):
        rev = self._revs_by_id[revision_id]
        return self._by_id[rev.tool_id], rev

    async def create_template(self, *a, **k): ...  # pragma: no cover
    async def get_template(self, *a, **k): ...  # pragma: no cover
    async def list_templates(self, *a, **k): ...  # pragma: no cover
    async def add_revision(self, *a, **k): ...  # pragma: no cover
    async def archive_template(self, *a, **k): ...  # pragma: no cover
    async def verify_chain_integrity(self, *a, **k): ...  # pragma: no cover
    async def list_roles_using_tool(self, *a, **k) -> list[RoleToolBinding]:
        return []  # pragma: no cover


class _ScriptedRetrievalClient:
    def __init__(
        self,
        chunks: tuple[RetrievedChunk, ...],
        citation_candidates: tuple = (),
    ) -> None:
        self._chunks = chunks
        self._candidates = citation_candidates
        self.calls: list[dict] = []

    async def __call__(self, **kwargs):
        from contexts.agent.application.ports import RetrievalResult

        self.calls.append(kwargs)
        return RetrievalResult(
            chunks=self._chunks, citation_candidates=self._candidates
        )


class TestToolDefinitionsLookupAdapter:
    def test_returns_only_visible_classifications(self) -> None:
        repo = _FakeToolRepository()
        # Read-only (visible)
        t_ro = _make_tool(Classification.READ_ONLY, "retrieval")
        r_ro = _make_revision(t_ro)
        repo.register(t_ro, r_ro)
        # Financial (high; not visible at Phase 1)
        t_fin = _make_tool(Classification.FINANCIAL, "transfer")
        r_fin = _make_revision(t_fin)
        repo.register(t_fin, r_fin)

        adapter = ToolDefinitionsLookupAdapter(tool_repository=repo)
        defs = asyncio.run(
            adapter(
                allowlist=(
                    ToolAllowlistEntry(tool_id=t_ro.id, revision_id=r_ro.id),
                    ToolAllowlistEntry(tool_id=t_fin.id, revision_id=r_fin.id),
                )
            )
        )
        names = {d.name for d in defs}
        assert names == {"retrieval"}

    def test_translates_to_inference_shape(self) -> None:
        repo = _FakeToolRepository()
        t = _make_tool(Classification.READ_ONLY, "retrieval")
        r = _make_revision(t)
        repo.register(t, r)
        adapter = ToolDefinitionsLookupAdapter(tool_repository=repo)
        defs = asyncio.run(
            adapter(
                allowlist=(
                    ToolAllowlistEntry(tool_id=t.id, revision_id=r.id),
                )
            )
        )
        assert len(defs) == 1
        d = defs[0]
        # The inference-context ToolDefinition has exactly three
        # fields (name, description, parameters); returns_schema and
        # classification do not leak through.
        assert d.name == "retrieval"
        assert d.parameters == r.parameters_schema
        assert hasattr(d, "description")
        assert not hasattr(d, "returns_schema")
        assert not hasattr(d, "classification")


class TestToolInvokerAdapter:
    def test_retrieval_dispatch_returns_ok_with_formatted_chunks(self) -> None:
        repo = _FakeToolRepository()
        t = _make_tool(
            Classification.READ_ONLY,
            "retrieval",
            tool_id=_RETRIEVAL_TOOL_ID,
        )
        r = _make_revision(t, revision_id=_RETRIEVAL_REVISION_ID)
        repo.register(t, r)

        chunks = (
            RetrievedChunk(
                text="relevant content",
                source_id=uuid4(),
                score=0.92,
            ),
        )
        retrieval = _ScriptedRetrievalClient(chunks)

        adapter = ToolInvokerAdapter(
            tool_repository=repo,
            retrieval_client=retrieval,
            retrieval_strategy={"primary": "vector"},
            filter_tree={},
            top_k=5,
            min_score=Decimal("0.5"),
        )

        result = asyncio.run(
            adapter(
                tool_call=ToolCall(
                    id="c1",
                    name="retrieval",
                    arguments_json='{"query": "test"}',
                ),
                tenant_context=_TENANT_A,
            )
        )

        assert result.outcome is InvocationOutcome.OK
        assert "relevant content" in result.payload
        assert "[score=0.920]" in result.payload
        assert retrieval.calls[0]["query"] == "test"

    def test_unknown_tool_name_returns_tool_not_registered(self) -> None:
        repo = _FakeToolRepository()
        retrieval = _ScriptedRetrievalClient(chunks=())
        adapter = ToolInvokerAdapter(
            tool_repository=repo,
            retrieval_client=retrieval,
            retrieval_strategy={"primary": "vector"},
            filter_tree={},
            top_k=5,
            min_score=Decimal("0.5"),
        )

        result = asyncio.run(
            adapter(
                tool_call=ToolCall(
                    id="c1",
                    name="unknown_tool",
                    arguments_json="{}",
                ),
                tenant_context=_TENANT_A,
            )
        )

        assert result.outcome is InvocationOutcome.TOOL_NOT_REGISTERED
        assert "unknown_tool" in result.message
        assert retrieval.calls == []

    def test_high_classification_returns_invariant_blocked(self) -> None:
        """If retrieval were ever reclassified to financial (synthetic
        scenario; D89 prohibits the actual authoring), the defensive
        check at invocation surfaces the block."""
        repo = _FakeToolRepository()
        t = _make_tool(
            Classification.FINANCIAL,
            "retrieval",
            tool_id=_RETRIEVAL_TOOL_ID,
        )
        r = _make_revision(t, revision_id=_RETRIEVAL_REVISION_ID)
        repo.register(t, r)
        retrieval = _ScriptedRetrievalClient(chunks=())
        adapter = ToolInvokerAdapter(
            tool_repository=repo,
            retrieval_client=retrieval,
            retrieval_strategy={"primary": "vector"},
            filter_tree={},
            top_k=5,
            min_score=Decimal("0.5"),
        )

        result = asyncio.run(
            adapter(
                tool_call=ToolCall(
                    id="c1",
                    name="retrieval",
                    arguments_json='{"query": "test"}',
                ),
                tenant_context=_TENANT_A,
            )
        )

        assert result.outcome is InvocationOutcome.INVARIANT_BLOCKED
        assert result.invariant_index == 1  # financial → invariant 1
        # Retrieval dispatch did not happen.
        assert retrieval.calls == []

    def test_malformed_retrieval_arguments_dispatch_with_empty_query(self) -> None:
        """The retrieval-specific JSON parser is defensive: malformed
        arguments yield an empty query string rather than raising,
        so the loop produces a structured no-result tool message."""
        repo = _FakeToolRepository()
        t = _make_tool(
            Classification.READ_ONLY,
            "retrieval",
            tool_id=_RETRIEVAL_TOOL_ID,
        )
        r = _make_revision(t, revision_id=_RETRIEVAL_REVISION_ID)
        repo.register(t, r)
        retrieval = _ScriptedRetrievalClient(chunks=())
        adapter = ToolInvokerAdapter(
            tool_repository=repo,
            retrieval_client=retrieval,
            retrieval_strategy={"primary": "vector"},
            filter_tree={},
            top_k=5,
            min_score=Decimal("0.5"),
        )

        result = asyncio.run(
            adapter(
                tool_call=ToolCall(
                    id="c1",
                    name="retrieval",
                    arguments_json="not valid json",
                ),
                tenant_context=_TENANT_A,
            )
        )

        assert result.outcome is InvocationOutcome.OK
        assert result.payload == "(no chunks matched the query)"
        assert retrieval.calls[0]["query"] == ""
