"""Agent runtime production wiring for the SSE endpoint (S30b, D90 follow-on).

The S29b commit shipped the SSE endpoint at
``POST /agents/{agent_id}/invoke`` plus the ``AgentRuntimeComposition``
dataclass on ``app.state.agent_runtime``. The default composition built
by ``_build_default_compositions`` left ``agent_runtime=None``; the
S29b live-stack e2e test wired the runtime in-test. S30b lands the
production-shaped wiring so the new ``padhanam agent run`` CLI (and any
future SSE consumer) reaches a real runtime through the standard API
entry point.

Three pieces compose the wiring:

1. **TenantRoutingRetrievalClient** — implements ``RetrievalClient`` by
   routing per-tenant at call time. The CLI constructs ``PgVectorSearch``
   per command against a tenant-bound session factory; the API server
   sees many tenants across requests, so the retrieval client resolves
   the per-tenant session factory via the existing
   ``TenantSessionFactoryCache`` for each call.

2. **Agent-runtime composition** — the
   ``AgentRepositoryPort + RoleLookup + MethodologyOverridesLookup +
   ToolDefinitionsLookup + AgentExecutor + SecurityEventLogger`` bundle
   wired to talk to the control plane (methodology, role, tool) and
   per-tenant data plane (agent rows, retrieval).

3. **Phase 1 ToolInvoker constants** — the ``ToolInvokerAdapter``
   constructor takes retrieval constraints (top_k, min_score,
   retrieval_strategy, filter_tree) which Phase 1 stores at composition
   time rather than per-invocation. The constants here match the
   migration-seeded role defaults (top_k=8, min_score=0.5, vector
   primary). A captures entry queues per-invocation retrieval-constraint
   threading as Phase 2 work.

Cross-app imports: this module imports the wiring adapters
(``RoleLookupAdapter``, ``MethodologyOverridesLookupAdapter``,
``ToolDefinitionsLookupAdapter``, ``ToolInvokerAdapter``) from
``apps/cli/_cross_context.py``. The adapter classes have no CLI-specific
dependencies — they translate context-shaped use cases into agent-
context Protocol ports. Phase 2 cleanup may relocate them to a shared
``apps/`` module; for S30b the cross-app import is the pragmatic call
since the alternative (duplicating 200+ lines of wiring) is worse.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from contexts.agent.adapters.outbound.agent_loop_executor import (
    AgentLoopExecutor,
)
from contexts.agent.adapters.outbound.postgres import AgentPostgresRepository
from contexts.audit.domain.ports import AuditPort
from contexts.ingestion.adapters.outbound.embedding import LiteLLMChunkEmbedder
from contexts.ingestion.adapters.outbound.neo4j import (
    Neo4jGraphRepository,
    make_async_driver,
)
from contexts.ingestion.adapters.outbound.retrieval import (
    Neo4jTraverse,
    PgVectorSearch,
)
from contexts.ingestion.domain.chunk_result import ChunkResult
from contexts.ingestion.domain.entity_result import EntityResult
from contexts.inference.ports import InferencePort
from contexts.methodology.adapters.outbound.postgres import (
    MethodologyPostgresRepository,
    RolePostgresRepository,
)
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application.connection_resolution import (
    TenantSessionFactoryCache,
)
from contexts.tools.adapters.outbound.postgres import ToolPostgresRepository
from padhanam.config import ControlPlaneSettings, Neo4jSettings
from padhanam.observability.security_events import SecurityEventLogger
from padhanam.security import Principal
from shared_kernel import TenantContext, TenantId

from apps.api.routers.agent import AgentRuntimeComposition
from apps.cli._cross_context import (
    AuditEventReaderAdapter,
    MethodologyOverridesLookupAdapter,
    RoleLookupAdapter,
    RunHistoryReaderAdapter,
    RunHistoryWriterAdapter,
    ToolDefinitionsLookupAdapter,
    ToolInvokerAdapter,
)


# Phase 1 retrieval constants. These match the migration-seeded role
# defaults in alembic/control_plane/versions/2026_05_12_0008_create_
# mckinsey_7_step.py's _ROLE_BUNDLE_DEFAULTS and the LVTGuide role's
# constraint bundle. The ToolInvokerAdapter consumes these at
# construction time; per-role retrieval-constraint threading is a
# Phase 2 follow-on.
_PHASE1_TOP_K: int = 8
_PHASE1_MIN_SCORE: Decimal = Decimal("0.5")
_PHASE1_RETRIEVAL_STRATEGY: dict = {"primary": "vector"}
_PHASE1_FILTER_TREE: dict = {"node": {}}


class TenantRoutingRetrievalClient:
    """Implements ``RetrievalClient`` by routing per-tenant at call time.

    The CLI constructs a fresh ``PgVectorSearch`` per command against a
    tenant-bound session factory; the API server sees many tenants
    across requests, so this wrapper resolves the per-tenant session
    factory via the existing ``TenantSessionFactoryCache`` on each
    call. The result is a single composed RetrievalClient instance that
    the agent runtime holds on ``app.state.agent_runtime`` and uses
    across requests.
    """

    def __init__(
        self,
        *,
        cache: TenantSessionFactoryCache,
        embedder: LiteLLMChunkEmbedder,
        registry: PostgresTenantRegistry,
        operator_principal: Principal,
        security_events: SecurityEventLogger,
        neo4j_settings: Neo4jSettings,
    ) -> None:
        self._cache = cache
        self._embedder = embedder
        self._registry = registry
        self._operator_principal = operator_principal
        self._security_events = security_events
        # The Neo4j driver is shared across tenants per D63 (Phase 1
        # shared-instance + property-based scoping). Constructed lazily
        # on first traverse_graph call so the wiring stays cheap when
        # the agent runtime never exercises graph retrieval (the Phase 1
        # demos at S30b run with empty tool_allowlists, so traverse is
        # not called; the construction surface is in place for Phase 2).
        self._neo4j_settings = neo4j_settings
        self._neo4j_driver = None

    async def search_vector(
        self,
        query: str,
        scope: TenantContext,
        limit: int,
    ) -> Sequence[ChunkResult]:
        session_factory = await self._cache.get(
            tenant_id=TenantId(str(scope.tenant_id)),
            principal=self._operator_principal,
            registry=self._registry,
            security_events=self._security_events,
        )
        adapter = PgVectorSearch(
            session_factory=session_factory,
            embedder=self._embedder,
        )
        return await adapter.search_vector(
            query=query, scope=scope, limit=limit
        )

    async def traverse_graph(
        self,
        seed: str,
        scope: TenantContext,
        depth: int,
    ) -> Sequence[EntityResult]:
        if self._neo4j_driver is None:
            self._neo4j_driver = make_async_driver(self._neo4j_settings)
        session_factory = await self._cache.get(
            tenant_id=TenantId(str(scope.tenant_id)),
            principal=self._operator_principal,
            registry=self._registry,
            security_events=self._security_events,
        )
        adapter = Neo4jTraverse(
            driver=self._neo4j_driver,
            pg_session_factory=session_factory,
        )
        return await adapter.traverse_graph(
            seed=seed, scope=scope, depth=depth
        )


def build_agent_runtime_composition(
    *,
    inference_port: InferencePort,
    audit_port: AuditPort,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
    control_plane_settings: ControlPlaneSettings,
    neo4j_settings: Neo4jSettings,
) -> AgentRuntimeComposition:
    """Wire the production agent runtime composition for the SSE endpoint.

    The composition assembles a single ``AgentRuntimeComposition`` that
    the SSE route at ``apps/api/routers/agent.py`` reads from
    ``app.state.agent_runtime``. All component repositories construct
    their own engines via ``from_settings``; engine lifecycles are
    inherited by the FastAPI app and disposed at shutdown via the
    existing lifespan hook.
    """
    methodology_repository = MethodologyPostgresRepository.from_settings(
        settings=control_plane_settings, security_events=security_events
    )
    role_repository = RolePostgresRepository.from_settings(
        settings=control_plane_settings, security_events=security_events
    )
    tool_repository = ToolPostgresRepository.from_settings(
        settings=control_plane_settings, security_events=security_events
    )

    async def _resolve_per_tenant(tenant_id):
        return await session_factory_cache.get(
            tenant_id=tenant_id,
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    agent_repository = AgentPostgresRepository(
        per_tenant_sessionmaker_resolver=_resolve_per_tenant,
        security_events=security_events,
    )

    embedder = LiteLLMChunkEmbedder()
    retrieval_client = TenantRoutingRetrievalClient(
        cache=session_factory_cache,
        embedder=embedder,
        registry=tenant_registry,
        operator_principal=operator_principal,
        security_events=security_events,
        neo4j_settings=neo4j_settings,
    )

    # The retrieval client this wraps is the agent-context port; the
    # ToolInvokerAdapter expects an AgentRetrievalClient (the agent-
    # context Protocol). The AgentRetrievalClientAdapter in apps/cli/
    # _cross_context.py translates ingestion's RetrievalClient (two
    # methods) into the agent-context single-call signature with
    # strategy translation. Wire it here too.
    from apps.cli._cross_context import AgentRetrievalClientAdapter

    agent_retrieval_client = AgentRetrievalClientAdapter(
        retrieval_client=retrieval_client,
    )

    role_lookup = RoleLookupAdapter(role_repository=role_repository)
    methodology_overrides_lookup = MethodologyOverridesLookupAdapter(
        methodology_repository=methodology_repository,
    )
    tool_definitions_lookup = ToolDefinitionsLookupAdapter(
        tool_repository=tool_repository,
    )
    tool_invoker = ToolInvokerAdapter(
        tool_repository=tool_repository,
        retrieval_client=agent_retrieval_client,
        retrieval_strategy=_PHASE1_RETRIEVAL_STRATEGY,
        filter_tree=_PHASE1_FILTER_TREE,
        top_k=_PHASE1_TOP_K,
        min_score=_PHASE1_MIN_SCORE,
    )

    executor = AgentLoopExecutor(
        inference_port=inference_port,
        tool_invoker=tool_invoker,
        audit_port=audit_port,
    )

    # RunHistoryWriterAdapter resolves the per-tenant session
    # factory at call time via the existing
    # TenantSessionFactoryCache; matches the
    # TenantRoutingRetrievalClient pattern above.
    async def _session_factory_for_tenant(tenant_context):
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    run_history_writer = RunHistoryWriterAdapter(
        session_factory_for_tenant=_session_factory_for_tenant,
        security_events=security_events,
    )

    return AgentRuntimeComposition(
        agent_repository=agent_repository,
        role_lookup=role_lookup,
        methodology_overrides_lookup=methodology_overrides_lookup,
        tool_definitions_lookup=tool_definitions_lookup,
        executor=executor,
        run_history_writer=run_history_writer,
        security_events=security_events,
    )


def build_run_history_reader(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> RunHistoryReaderAdapter:
    """Wire the run-history read surface for the production composition (S33, D97).

    Mirrors the writer wiring shape: the adapter holds a callable
    that resolves the per-tenant session factory at call time via
    the existing ``TenantSessionFactoryCache``. No consumer at S33
    calls the returned adapter; the wiring is the substrate the
    HTTP layer at S34/S35 dependency-injects against.

    Per D97's port-location call, the read surface is a producer-
    side port at ``contexts.run_history.ports.reader`` consumed by
    a composition surface (apps/api) rather than a bounded context.
    The wiring lives alongside ``build_agent_runtime_composition``
    in this module because the same session-factory cache,
    operator principal, and security-events logger compose both
    the write surface (on the agent runtime) and the read surface
    (off-runtime, for the future HTTP layer).
    """

    async def _session_factory_for_tenant(tenant_context):
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    return RunHistoryReaderAdapter(
        session_factory_for_tenant=_session_factory_for_tenant,
    )


def build_audit_event_reader(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
    control_plane_sessionmaker,
) -> AuditEventReaderAdapter:
    """Wire the audit read surface for the production composition (S36, D102).

    Mirrors ``build_run_history_reader``'s shape but adds the
    control-plane sessionmaker as a separate construction-time
    dependency because the audit reader handles two destinations
    (per-tenant and control-plane) per D102.

    The per-tenant ``session_factory_for_tenant`` callable closes
    over the same ``TenantSessionFactoryCache`` the writer and
    run-history-reader factories use. The control-plane
    sessionmaker is the same one the write-side audit adapter
    uses (caller supplies it from ``AppCompositions`` so both
    halves of the audit context route to the same instance).

    No consumer at S36 calls the returned adapter; the wiring is
    the substrate the HTTP layer at S37 will dependency-inject
    against. Per D102 the audit reader is a producer-side port
    (consumer is the HTTP API at S37, not a bounded context); the
    wiring layer is the composition surface that constructs it.
    """

    async def _session_factory_for_tenant(tenant_context):
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    return AuditEventReaderAdapter(
        session_factory_for_tenant=_session_factory_for_tenant,
        control_plane_sessionmaker=control_plane_sessionmaker,
    )


__all__ = [
    "TenantRoutingRetrievalClient",
    "build_agent_runtime_composition",
    "build_audit_event_reader",
    "build_run_history_reader",
]
