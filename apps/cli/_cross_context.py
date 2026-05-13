"""Cross-context lookup adapters for the CLI (S25 / D79, S26a-1 / D86, S26a-2 / D86, S27b / D88).

The agent context's create-from-methodology, create-from-role, and
runtime invocation flows consume five callable Protocol ports defined
at ``contexts/agent/application/ports/``: MethodologyLookup, RoleLookup,
SourceLookup, AgentRetrievalClient, and MethodologyOverridesLookup.
This module wires the producer contexts' application-layer use cases
(methodology, ingestion) into the consumer-shaped Protocol calls.
Per D17 the adapters live at the apps/cli wiring layer — that
boundary is the legitimate seam where one context's public surface
translates into another's consumer-side abstraction.

S26a-1 refactor per D86: the methodology aggregate becomes a playbook
composing roles. The ``MethodologyLookupAdapter`` now resolves
``role_refs`` at lookup time by calling the role context's
``get_role_template`` use case (over the role repository) so the
consumer-side ``MethodologyView`` carries the resolved role's content
bundle plus the resolved role id and version (the latter landing at
S26a-2 so create_agent_from_methodology populates both lineage pairs
from a single cross-context hop). Phase 1 has single-role
methodologies, so the adapter reads the first role_ref; per-role-
overrides Phase 2 work will lift this resolution policy out into a
methodology-shape-aware codepath. The resolution happens at the
adapter (wiring layer), not in the agent context's use case, so the
use case stays consumer-shape-aware without needing the role
context's API.

S26a-2 adds ``RoleLookupAdapter`` for the direct role-clone flow.
The two consumer ports (MethodologyLookup, RoleLookup) share the
api-facade-via-callable pattern from D17; the second consumer
reinforces the pattern's value but the structural duplication is a
Patterns-observed candidate worth tracking at phase audit time if a
third cross-context lookup with the same shape lands.

S27b adds two more wiring adapters at the same seam per D88:

- ``AgentRetrievalClientAdapter`` consumes the ingestion context's
  split ``search_vector`` / ``traverse_graph`` methods and exposes a
  unified retrieval surface per the role's effective retrieval
  constraints. Strategy translation lives here at the wiring layer,
  not in the agent context, per D5 / D65's hybrid-as-agent-layer-concern.
- ``MethodologyOverridesLookupAdapter`` consumes the methodology
  context's ``get_methodology_template`` use case and scans the
  resolved revision's ``role_refs`` for the entry matching the
  agent's ``source_role_id``, returning that entry's ``overrides``
  dict for the D87 composition resolver.

Each adapter is constructed per-command invocation by the CLI and
disposed alongside the engines it closes over. The adapters do not
own engine lifecycles; the CLI command does.
"""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Awaitable, Callable, Mapping, Sequence
from uuid import UUID, uuid4

from contexts.agent.application.ports import (
    AgentRetrievalClient,
    AgentRunRecord,
    InvocationOutcome,
    MethodologyOverridesLookup,
    MethodologyView,
    RetrievalResult,
    RetrievedChunk,
    RoleView,
    SourceNotFoundError,
    ToolInvocationResult,
)
from contexts.agent.domain.citation_candidates import (
    ChunkCitationCandidate,
    CitationCandidate,
    EntityCitationCandidate,
)
from contexts.inference.domain.completion import (
    ToolCall,
    ToolDefinition as InferenceToolDefinition,
)
from contexts.ingestion.application.get_source import get_source
from contexts.ingestion.ports.retrieval_client import RetrievalClient
from contexts.ingestion.ports.source_repository_port import SourceRepositoryPort
from contexts.methodology.application.use_cases import (
    get_methodology_template,
    get_role_template,
)
from contexts.methodology.ports import (
    MethodologyRepositoryPort,
    RoleRepositoryPort,
)
from contexts.run_history.adapters.outbound.postgres import (
    PostgresRunHistoryAdapter,
)
from contexts.run_history.api import record_run as _record_run_use_case
from contexts.run_history.domain import (
    ChunkCitationRecord,
    EntityCitationRecord,
    RunRecord,
)
from contexts.tools.application.tool_invocation_service import (
    InvocationCheckOutcome,
    check_invocation_admissibility,
    list_visible_definitions as tools_list_visible_definitions,
)
from contexts.tools.ports import ToolRepositoryPort
from padhanam.observability.security_events import SecurityEventLogger
from padhanam.security import Principal
from shared_kernel import TenantContext, TenantId, ToolAllowlistEntry
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


_log = logging.getLogger("apps.cli.cross_context")


# Well-known retrieval tool UUID seeded by Alembic
# 0009_create_tools_tables per D89. The ToolInvokerAdapter routes
# tool_call.name == "retrieval" via AgentRetrievalClient; future
# Phase 2 tools register here without changing the agent context's
# port shape.
_RETRIEVAL_TOOL_ID = UUID("00000000-0000-0000-0000-000000000001")
_RETRIEVAL_TOOL_NAME = "retrieval"


class MethodologyLookupAdapter:
    """Adapter from MethodologyRepositoryPort + RoleRepositoryPort to
    the agent context's MethodologyLookup Protocol (S26a-1 / D86).

    Closes over both repositories so the CLI command can construct
    the adapter once per invocation; the ``__call__`` method is the
    Protocol surface the agent use case invokes.

    The adapter resolves ``role_refs[0]`` to a role revision via
    ``get_role_template`` and populates the consumer-side
    MethodologyView with the role's bundle content. Phase 1 has
    single-role methodologies so the first role_ref is the canonical
    role for the methodology; multi-role resolution defers to Phase 2
    alongside per-role-overrides.
    """

    def __init__(
        self,
        *,
        methodology_repository: MethodologyRepositoryPort,
        role_repository: RoleRepositoryPort,
    ) -> None:
        self._methodology_repository = methodology_repository
        self._role_repository = role_repository

    async def __call__(
        self,
        *,
        template_id: UUID,
        version: int | None,
        principal: Principal,
    ) -> MethodologyView:
        template, revision = await get_methodology_template(
            principal=principal,
            repository=self._methodology_repository,
            template_id=template_id,
            version=version,
        )
        if not revision.role_refs:
            raise LookupError(
                f"methodology revision {revision.id} carries no role_refs; "
                "cannot resolve clone-from-methodology content (D86)"
            )

        first_ref = revision.role_refs[0]
        _, role_revision = await get_role_template(
            principal=principal,
            repository=self._role_repository,
            template_id=first_ref.role_id,
            version=first_ref.role_version,
        )

        # Phase 1: overrides ignored per D86 (no consumer yet). Phase 2
        # applies hard-tightens-only + soft-replaces semantics here.

        return MethodologyView(
            methodology_template_id=template.id,
            methodology_version=revision.version,
            role_id=role_revision.role_template_id,
            role_version=role_revision.version,
            description=template.description,
            system_prompt=role_revision.system_prompt,
            tool_allowlist=role_revision.tool_allowlist,
            retrieval_strategy=role_revision.retrieval_strategy,
            filter_tree=role_revision.filter_tree,
            top_k=role_revision.top_k,
            min_score=role_revision.min_score,
            model_selection=role_revision.model_selection,
        )


class RoleLookupAdapter:
    """Adapter from RoleRepositoryPort to the agent context's
    RoleLookup Protocol (S26a-2 / D86).

    Closes over the role repository so the CLI command can construct
    the adapter once per invocation; the ``__call__`` method is the
    Protocol surface the agent use case invokes. Mirrors
    MethodologyLookupAdapter's shape per the api-facade-via-callable
    pattern from D17, except resolution is single-hop (no role_refs
    join because the consumer asked for the role directly).
    """

    def __init__(
        self,
        *,
        role_repository: RoleRepositoryPort,
    ) -> None:
        self._role_repository = role_repository

    async def __call__(
        self,
        *,
        role_id: UUID,
        version: int | None,
        principal: Principal,
    ) -> RoleView:
        template, revision = await get_role_template(
            principal=principal,
            repository=self._role_repository,
            template_id=role_id,
            version=version,
        )
        return RoleView(
            role_id=template.id,
            role_version=revision.version,
            description=template.description,
            system_prompt=revision.system_prompt,
            tool_allowlist=revision.tool_allowlist,
            retrieval_strategy=revision.retrieval_strategy,
            filter_tree=revision.filter_tree,
            top_k=revision.top_k,
            min_score=revision.min_score,
            model_selection=revision.model_selection,
        )


class SourceLookupAdapter:
    """Adapter from SourceRepositoryPort to the agent context's
    SourceLookup Protocol.

    Closes over the tenant-routed source repository (constructed
    against the tenant's data plane at the CLI boundary) and
    synthesises ``assert_sources_exist`` by calling the application-
    layer ``get_source`` use case per id. The underlying use case
    raises ``LookupError`` for both missing-id and wrong-tenant cases
    (D24 tenant isolation makes the two indistinguishable); the
    adapter collects offending ids and surfaces a single
    SourceNotFoundError at the end.

    The per-id call is acceptable at S25 because source-existence
    validation runs at clone time on a small N. If a future
    consumer needs higher throughput, a batch ``get_sources`` method
    can land on the port without changing the adapter's external
    Protocol contract.
    """

    def __init__(self, *, repository: SourceRepositoryPort) -> None:
        self._repository = repository

    async def assert_sources_exist(
        self,
        *,
        source_ids: tuple[UUID, ...],
        tenant_context: TenantContext,
        principal: Principal,
    ) -> None:
        missing: list[UUID] = []
        for sid in source_ids:
            try:
                await get_source(
                    repository=self._repository,
                    source_id=sid,
                    tenant_id=str(tenant_context.tenant_id),
                )
            except LookupError:
                missing.append(sid)
        if missing:
            raise SourceNotFoundError(missing_source_ids=tuple(missing))


class AgentRetrievalClientAdapter:
    """Adapter from ingestion's RetrievalClient to the agent-context
    ``AgentRetrievalClient`` Protocol (S27b / D88).

    The agent runtime wants a unified retrieval surface: given a query
    and the role's effective retrieval constraints, return a sequence
    of chunk results. The ingestion port from D5 / D65 splits retrieval
    into ``search_vector`` and ``traverse_graph`` with no hybrid method
    because D5 / D65 explicitly committed hybrid composition as an
    agent-layer concern. This adapter is where strategy translation
    lives.

    Phase 1 strategy keys (per D66's three-strategy starter catalogue):

    - ``{"primary": "vector"}``: invoke search_vector only.
    - ``{"primary": "vector", "secondary": "graph"}``: invoke
      search_vector primarily; graph is reserved for future expansion
      but at Phase 1 only the primary executes (graph traversal needs
      a seed entity which the agent runtime does not yet derive from
      free-form queries; S30b's full demonstration moment is the
      forcing function for graph dispatch).
    - ``{"primary": "graph"}``: invoke traverse_graph with the query
      as the seed entity name; graph results are mapped to chunk-shaped
      RetrievedChunks via the entity's text representation. (Phase 1
      best-effort; the integration test exercises the vector path.)

    ``filter_tree`` is opaque per D67 at Phase 1: the ingestion adapters
    do not yet honor filter_tree (queued for the data-retrieval design
    session's full implementation). The adapter accepts and discards;
    the structural commitment per D88 keeps the port surface stable as
    ingestion gains filter capability.

    ``top_k`` is honored as the ingestion search limit; ``min_score``
    filters results post-search so the agent runtime sees only chunks
    meeting the role's quality floor.
    """

    def __init__(self, *, retrieval_client: RetrievalClient) -> None:
        self._retrieval_client = retrieval_client

    async def __call__(
        self,
        *,
        query: str,
        tenant_context: TenantContext,
        retrieval_strategy: Mapping[str, Any],
        filter_tree: Mapping[str, Any],
        top_k: int,
        min_score: Decimal,
    ) -> RetrievalResult:
        primary = str(retrieval_strategy.get("primary", "vector"))

        if primary == "vector":
            raw_results = await self._retrieval_client.search_vector(
                query=query,
                scope=tenant_context,
                limit=top_k,
            )
            filtered = [
                r for r in raw_results
                if Decimal(str(r.similarity_score)) >= min_score
            ]
            chunks = tuple(
                RetrievedChunk(
                    text=r.content,
                    source_id=r.source_id,
                    score=r.similarity_score,
                )
                for r in filtered
            )
            # D96: produce ChunkCitationCandidate per retrieved chunk
            # from the same ChunkResult set so the citation surface
            # is single-pass. The source_snapshot dict carries the
            # file_name and file_type joined from sources at retrieval
            # time per D96's Phase 1 snapshot key set.
            candidates: tuple[CitationCandidate, ...] = tuple(
                ChunkCitationCandidate(
                    chunk_id=r.chunk_id,
                    source_id=r.source_id,
                    chunk_index=r.chunk_index,
                    content_snapshot=r.content,
                    source_snapshot=dict(r.source_snapshot),
                    tenant_id=r.tenant_id,
                    jurisdiction=r.jurisdiction,
                )
                for r in filtered
            )
            return RetrievalResult(chunks=chunks, citation_candidates=candidates)

        if primary == "graph":
            # Phase 1: graph dispatch uses the query string as the seed
            # entity name. Per D66 the three-strategy starter catalogue
            # acknowledges this is a coarse interpretation; the
            # data-retrieval design session's full implementation
            # introduces seed-entity derivation. The agent runtime
            # surfaces empty results gracefully via the loop's tool-
            # result formatter.
            entities = await self._retrieval_client.traverse_graph(
                seed=query,
                scope=tenant_context,
                depth=int(retrieval_strategy.get("depth", 1)),
            )
            # Map each entity to a chunk-shaped result for the LLM
            # surface. Phase 1 score is a conventional 1.0; without
            # similarity at the graph side, min_score filtering is a
            # no-op for graph results.
            chunks = tuple(
                RetrievedChunk(
                    text=str(e.name),
                    source_id=(
                        e.source_chunk_ids[0]
                        if getattr(e, "source_chunk_ids", None)
                        else UUID(int=0)
                    ),
                    score=1.0,
                )
                for e in entities
            )
            # D96: produce EntityCitationCandidate per entity. The
            # source_chunk_ids snapshot preserves the entity's
            # provenance trail back to per-tenant Postgres chunks per
            # D96; the (entity_tenant_id, entity_name, entity_type)
            # composite is the documented join key per D64.
            entity_candidates: tuple[CitationCandidate, ...] = tuple(
                EntityCitationCandidate(
                    entity_tenant_id=e.tenant_id,
                    entity_name=e.name,
                    entity_type=e.entity_type,
                    source_chunk_ids=tuple(e.source_chunk_ids or ()),
                    tenant_id=e.tenant_id,
                    jurisdiction=e.jurisdiction,
                )
                for e in entities
            )
            return RetrievalResult(
                chunks=chunks, citation_candidates=entity_candidates
            )

        # Unknown strategy: return empty. The integration evidence at
        # S30b will surface if this branch fires in practice.
        return RetrievalResult()


class MethodologyOverridesLookupAdapter:
    """Adapter from the methodology repository to the agent-context
    ``MethodologyOverridesLookup`` Protocol (S27b / D88).

    Runtime per-role override resolution distinct from the clone-time
    ``MethodologyLookup``: where clone-time fetches the methodology's
    first role's content, runtime fetches the methodology revision's
    ``role_refs`` entry for the agent's specific role and returns just
    that entry's ``overrides`` dict per D87.

    The adapter reads the methodology revision via the methodology
    repository, scans ``role_refs`` for the matching role_id, and
    returns the overrides as-is (D87's structured
    ``{field: {"mode": <str>, "value": <any>}}`` shape). Returns an
    empty dict when no entry matches (the agent's role is not part of
    this methodology) or when the matching entry's ``overrides`` is
    empty.

    ``LookupError`` propagates from the repository on unknown
    methodology id or version. The agent runtime's caller handles
    missing-methodology errors.
    """

    def __init__(
        self,
        *,
        methodology_repository: MethodologyRepositoryPort,
    ) -> None:
        self._methodology_repository = methodology_repository

    async def __call__(
        self,
        *,
        methodology_template_id: UUID,
        methodology_version: int | None,
        role_id: UUID,
        principal: Principal,
    ) -> dict[str, dict[str, Any]]:
        _, revision = await get_methodology_template(
            principal=principal,
            repository=self._methodology_repository,
            template_id=methodology_template_id,
            version=methodology_version,
        )
        for ref in revision.role_refs:
            if ref.role_id == role_id:
                return dict(ref.overrides)
        return {}


class ToolDefinitionsLookupAdapter:
    """Adapter from tools-context invocation service to the agent-context
    ``ToolDefinitionsLookup`` Protocol (S28b commit 7, D89).

    The agent runtime resolves a role's pinned ``tool_allowlist`` into
    the LLM-ready inference-context ``ToolDefinition`` tuple at
    invocation time. This adapter:

    1. Calls the tools-context ``list_visible_definitions`` with the
       allowlist references; the tools-context filters by Phase 1
       classification policy (excludes financial, communication,
       legal classifications) and returns the tools-context
       ``ToolDefinition`` value object.

    2. Translates the tools-context ``ToolDefinition`` (4 fields:
       tool_id, revision_id, name, description, classification,
       parameters_schema, returns_schema) into the inference-context
       ``ToolDefinition`` (3 fields: name, description, parameters)
       that LiteLLM consumes.

    The translation is the agent context's responsibility: the tools
    context owns its consumer surface (returns its own VO); the
    inference context owns its wire format (the OpenAI function-
    calling shape that LiteLLM normalises). The adapter bridges the
    two without leaking either context's types into the other.
    """

    def __init__(
        self,
        *,
        tool_repository: ToolRepositoryPort,
    ) -> None:
        self._tool_repository = tool_repository

    async def __call__(
        self,
        *,
        allowlist: Sequence[ToolAllowlistEntry],
    ) -> tuple[InferenceToolDefinition, ...]:
        references = [(e.tool_id, e.revision_id) for e in allowlist]
        tools_defs = await tools_list_visible_definitions(
            repository=self._tool_repository,
            references=references,
        )
        return tuple(
            InferenceToolDefinition(
                name=td.name,
                description=td.description,
                parameters=dict(td.parameters_schema),
            )
            for td in tools_defs
        )


class ToolInvokerAdapter:
    """Adapter from ToolRepositoryPort + AgentRetrievalClient to the
    agent-context ``ToolInvoker`` Protocol (S28b commit 7, D89).

    Two-step dispatch per call:

    1. Defensive invariant check via the tools-context invocation
       service. Rejects high-classification calls (financial,
       communication, legal) with ``INVARIANT_BLOCKED`` and the
       three-to-three invariant_index per D89. Phase 1 has no
       authored high-classification tools (the CLI rejects them per
       commit 8), so this branch fires defensively for future
       scenarios where the filter is bypassed.

    2. Tool-specific dispatch. Phase 1 has retrieval as the only
       registered tool; the adapter routes ``tool_call.name ==
       "retrieval"`` to the ``AgentRetrievalClient`` (consuming the
       role's effective retrieval constraints from the closure). Any
       other name returns ``TOOL_NOT_REGISTERED``. Future Phase 2
       tools (calendar, email, etc.) register here without changing
       the agent context's port shape.

    The retrieval-specific parsing (``_parse_retrieval_query``) and
    chunk-formatting (``_format_chunks_as_tool_result``) relocate
    here from the executor per D89's tool-agnostic-executor
    architecture.

    The adapter receives the role's retrieval constraints
    (retrieval_strategy, filter_tree, top_k, min_score) at
    construction time because the executor doesn't pass them through
    on each invocation (the executor is tool-agnostic). The CLI
    command builds a fresh adapter per agent invocation closing over
    the bundle's retrieval constraints; future Phase 2 tools that
    need different per-invocation context settle the constructor
    shape at their landing session.
    """

    def __init__(
        self,
        *,
        tool_repository: ToolRepositoryPort,
        retrieval_client: AgentRetrievalClient,
        retrieval_strategy: Mapping[str, Any],
        filter_tree: Mapping[str, Any],
        top_k: int,
        min_score: Decimal,
    ) -> None:
        self._tool_repository = tool_repository
        self._retrieval_client = retrieval_client
        self._retrieval_strategy = dict(retrieval_strategy)
        self._filter_tree = dict(filter_tree)
        self._top_k = top_k
        self._min_score = min_score

    async def __call__(
        self,
        *,
        tool_call: ToolCall,
        tenant_context: TenantContext,
    ) -> ToolInvocationResult:
        # Phase 1 retrieval dispatch by name. Future Phase 2 tools
        # may dispatch by (tool_id, revision_id) once the LLM-issued
        # tool_call carries those identifiers; the name-based shape
        # is the OpenAI function-calling format LiteLLM normalises.
        if tool_call.name == _RETRIEVAL_TOOL_NAME:
            return await self._dispatch_retrieval(
                tool_call=tool_call,
                tenant_context=tenant_context,
            )

        # Unknown tool name: surface as TOOL_NOT_REGISTERED. The
        # executor translates to TerminationReason.TOOL_NOT_REGISTERED.
        return ToolInvocationResult(
            outcome=InvocationOutcome.TOOL_NOT_REGISTERED,
            payload=(
                f"(tool {tool_call.name!r} is not registered at Phase 1)"
            ),
            message=f"tool {tool_call.name!r} not in registry",
        )

    async def _dispatch_retrieval(
        self,
        *,
        tool_call: ToolCall,
        tenant_context: TenantContext,
    ) -> ToolInvocationResult:
        # Defensive invariant check via the tools-context invocation
        # service. Retrieval is classification read-only so this
        # always passes at Phase 1; the call exercises the seam for
        # future tools.
        admissibility = await check_invocation_admissibility(
            repository=self._tool_repository,
            tool_id=_RETRIEVAL_TOOL_ID,
            revision_id=UUID("00000000-0000-0000-0000-000000000002"),
        )
        if admissibility.outcome is InvocationCheckOutcome.INVARIANT_BLOCKED:
            return ToolInvocationResult(
                outcome=InvocationOutcome.INVARIANT_BLOCKED,
                payload=admissibility.message,
                message=admissibility.message,
                invariant_index=admissibility.invariant_index,
            )

        query = _parse_retrieval_query(tool_call.arguments_json)
        try:
            result = await self._retrieval_client(
                query=query,
                tenant_context=tenant_context,
                retrieval_strategy=self._retrieval_strategy,
                filter_tree=self._filter_tree,
                top_k=self._top_k,
                min_score=self._min_score,
            )
        except Exception as exc:  # pragma: no cover - defensive
            _log.exception("retrieval dispatch failed")
            return ToolInvocationResult(
                outcome=InvocationOutcome.ERROR,
                payload=f"(retrieval failed: {exc!r})",
                message=str(exc),
            )

        # D96: thread citation candidates from the retrieval envelope
        # onto ToolInvocationResult so the executor can populate the
        # ToolCallCompleted event's citation_candidates field. The
        # LLM-facing payload remains the formatted-text projection
        # over result.chunks.
        return ToolInvocationResult(
            outcome=InvocationOutcome.OK,
            payload=_format_chunks_as_tool_result(result.chunks),
            citation_candidates=result.citation_candidates,
        )


class RunHistoryWriterAdapter:
    """Adapter from run-history's record_run use case to the agent-
    context ``RunHistoryWriter`` Protocol (S31 commit 5, D95).

    The agent runtime's ``invoke_agent`` use case calls this after
    yielding the terminal event per D95's shape-B write-timing
    commitment. The adapter:

    1. Translates the agent-context ``AgentRunRecord`` DTO into the
       run-history domain ``RunRecord``. The translation is field-
       for-field; the DTO-versus-domain boundary keeps the agent
       context independent of ``contexts.run_history.domain`` per
       D17.
    2. Resolves a tenant-bound ``async_sessionmaker`` via the
       injected ``session_factory_for_tenant`` callable; the
       resolution per call rather than per construction matches
       the existing apps/api retrieval-client cross-tenant pattern
       from S30b.
    3. Constructs a per-call ``PostgresRunHistoryAdapter`` bound to
       the runtime's tenant_id and calls
       ``contexts.run_history.api.record_run`` with the
       authenticated principal threaded through from
       ``invoke_agent``.

    The adapter does not own engine lifecycles; the
    ``session_factory_for_tenant`` callable opaquely returns the
    tenant's existing ``async_sessionmaker``. The CLI command
    binds a dev-shape resolver via ``apps/cli/_runtime.py``;
    ``apps/api/_agent_runtime_wiring.py`` binds the tenancy
    context's session-factory cache per the S30b cross-app
    re-use pattern.

    This is the eighth consumer-port-plus-wiring-adapter class on
    apps/cli/_cross_context.py (after MethodologyLookup,
    RoleLookup, SourceLookup, AgentRetrievalClient,
    MethodologyOverridesLookup, ToolDefinitionsLookup,
    ToolInvoker) — the pattern's altitude-agnostic shape continues
    to do load-bearing work per D95.
    """

    def __init__(
        self,
        *,
        session_factory_for_tenant: Callable[
            [TenantContext], Awaitable[async_sessionmaker[AsyncSession]]
        ],
        security_events: SecurityEventLogger,
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant
        self._security_events = security_events

    async def record_run(
        self,
        record: AgentRunRecord,
        *,
        principal: Principal,
    ) -> None:
        tenant_context = TenantContext(
            tenant_id=record.tenant_id,
            jurisdiction=record.jurisdiction,
            cost_attribution_id=record.tenant_id,
        )
        sessionmaker = await self._session_factory_for_tenant(tenant_context)

        async def _resolver(
            _tid: TenantId,
        ) -> async_sessionmaker[AsyncSession]:
            return sessionmaker

        repository = PostgresRunHistoryAdapter(
            per_tenant_sessionmaker_resolver=_resolver,
            bound_tenant_id=TenantId(record.tenant_id),
        )

        # D96 / S32: translate agent-context citation candidates to
        # run-history-context citation records one-for-one. The
        # mirror-types-at-context-boundaries pattern (D54) keeps the
        # producer context's domain shape independent of the
        # consumer context's; the wiring adapter does the
        # field-for-field translation including the run_id binding.
        chunk_records = tuple(
            ChunkCitationRecord(
                id=uuid4(),
                run_id=record.id,
                chunk_id=candidate.chunk_id,
                tenant_id=candidate.tenant_id,
                jurisdiction=candidate.jurisdiction,
                chunk_excerpt=candidate.content_snapshot,
                source_snapshot=dict(candidate.source_snapshot),
            )
            for candidate in record.chunk_citations
        )
        entity_records = tuple(
            EntityCitationRecord(
                id=uuid4(),
                run_id=record.id,
                entity_tenant_id=candidate.entity_tenant_id,
                entity_name=candidate.entity_name,
                entity_type=candidate.entity_type,
                tenant_id=candidate.tenant_id,
                source_chunk_ids=candidate.source_chunk_ids,
            )
            for candidate in record.entity_citations
        )

        run_record = RunRecord(
            id=record.id,
            tenant_id=record.tenant_id,
            jurisdiction=record.jurisdiction,
            agent_template_id=record.agent_template_id,
            agent_template_version=record.agent_template_version,
            input_message=record.input_message,
            output_content=record.output_content,
            started_at=record.started_at,
            completed_at=record.completed_at,
            termination_reason=record.termination_reason,
            iteration_count=record.iteration_count,
            total_cost_usd=record.total_cost_usd,
            trace_id=record.trace_id,
            audit_start_hash=record.audit_start_hash,
            audit_end_hash=record.audit_end_hash,
            created_at=record.created_at,
            chunk_citations=chunk_records,
            entity_citations=entity_records,
        )
        await _record_run_use_case(
            principal=principal,
            repository=repository,
            security_events=self._security_events,
            run_record=run_record,
        )


def _parse_retrieval_query(arguments_json: str) -> str:
    """Parse the model-issued retrieval-tool arguments (relocated D89 commit 7).

    Was in the executor at S27b; moved here when commit 5 made the
    executor tool-agnostic. Malformed JSON yields an empty query
    string so the loop produces a structured no-result tool message
    rather than terminating with an error.
    """
    try:
        parsed = json.loads(arguments_json)
    except (ValueError, TypeError):
        _log.warning(
            "retrieval tool arguments not parseable as JSON: %r",
            arguments_json,
        )
        return ""
    if not isinstance(parsed, dict):
        return ""
    query = parsed.get("query", "")
    return str(query) if query is not None else ""


def _format_chunks_as_tool_result(
    chunks: tuple[RetrievedChunk, ...],
) -> str:
    """Format retrieved chunks as a single tool-result string
    (relocated D89 commit 7).

    Empty results produce a structured empty marker so the LLM
    distinguishes a successful no-match from a tool execution failure.
    """
    if not chunks:
        return "(no chunks matched the query)"
    return "\n\n".join(
        f"[score={c.score:.3f}] {c.text}" for c in chunks
    )
