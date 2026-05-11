"""Cross-context lookup adapters for the CLI (S25 / D79, S26a-1 / D86).

The agent context's create-from-methodology flow consumes two
callable Protocol ports defined at
``contexts/agent/application/ports/``: MethodologyLookup and
SourceLookup. This module wires the producer contexts' application-
layer use cases into the consumer-shaped Protocol calls. Per D17 the
adapters live at the apps/cli wiring layer — that boundary is the
legitimate seam where one context's public surface translates into
another's consumer-side abstraction.

S26a-1 refactor per D86: the methodology aggregate becomes a playbook
composing roles. The ``MethodologyLookupAdapter`` now resolves
``role_refs`` at lookup time by calling the role context's
``get_role_template`` use case (over the role repository) so the
consumer-side ``MethodologyView`` carries the resolved role's content
bundle. Phase 1 has single-role methodologies, so the adapter reads
the first role_ref; per-role-overrides Phase 2 work will lift this
resolution policy out into a methodology-shape-aware codepath. The
resolution happens at the adapter (wiring layer), not in the agent
context's use case, so the use case stays consumer-shape-aware
without needing the role context's API.

Each adapter is constructed per-command invocation by the CLI and
disposed alongside the engines it closes over. The adapters do not
own engine lifecycles; the CLI command does.
"""

from __future__ import annotations

from uuid import UUID

from contexts.agent.application.ports import (
    MethodologyView,
    SourceNotFoundError,
)
from contexts.ingestion.application.get_source import get_source
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
