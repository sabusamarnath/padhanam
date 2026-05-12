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

from decimal import Decimal
from typing import Any, Mapping
from uuid import UUID

from contexts.agent.application.ports import (
    AgentRetrievalClient,
    MethodologyOverridesLookup,
    MethodologyView,
    RetrievedChunk,
    RoleView,
    SourceNotFoundError,
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
from padhanam.security import Principal
from shared_kernel import TenantContext


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
    ) -> tuple[RetrievedChunk, ...]:
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
            return tuple(
                RetrievedChunk(
                    text=r.content,
                    source_id=r.source_id,
                    score=r.similarity_score,
                )
                for r in filtered
            )

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
            # Map each entity to a chunk-shaped result. Phase 1 score
            # is a conventional 1.0; without similarity at the graph
            # side, min_score filtering is a no-op for graph results.
            return tuple(
                RetrievedChunk(
                    text=str(e.name),
                    source_id=e.source_ids[0]
                    if getattr(e, "source_ids", None)
                    else UUID(int=0),
                    score=1.0,
                )
                for e in entities
            )

        # Unknown strategy: return empty. The integration evidence at
        # S30b will surface if this branch fires in practice.
        return ()


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
