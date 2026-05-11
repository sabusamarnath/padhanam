"""Cross-context lookup adapters for the CLI (S25 / D79).

The agent context's create-from-methodology flow consumes two
callable Protocol ports defined at
``contexts/agent/application/ports/``: MethodologyLookup and
SourceLookup. This module wires the producer contexts' application-
layer use cases into the consumer-shaped Protocol calls. Per D17 the
adapters live at the apps/cli wiring layer — that boundary is the
legitimate seam where one context's public surface translates into
another's consumer-side abstraction.

Each adapter is constructed per-command invocation by the CLI
(commit 8) and disposed alongside the engines it closes over. The
adapters do not own engine lifecycles; the CLI command does.

MethodologyLookupAdapter wraps
``contexts.methodology.application.get_methodology_template`` (a
control-plane read) and translates the producer's
(MethodologyTemplate, MethodologyRevision) tuple into the consumer-
shaped MethodologyView DTO. version=None resolves to the latest
revision at the underlying repository; the resolved integer is what
populates the returned view.

SourceLookupAdapter wraps the application-layer
``contexts.ingestion.application.get_source`` use case (shipped at
the S25 reconciliation-2 sub-commit) and synthesises the assert
behaviour by iterating per-id. Missing ids accumulate and a single
SourceNotFoundError surfaces at the end so the operator sees the
full set of failures in one error message rather than one-at-a-time.
"""

from __future__ import annotations

from uuid import UUID

from contexts.agent.application.ports import (
    MethodologyView,
    SourceNotFoundError,
)
from contexts.ingestion.application.get_source import get_source
from contexts.ingestion.ports.source_repository_port import SourceRepositoryPort
from contexts.methodology.application.use_cases import get_methodology_template
from contexts.methodology.ports import MethodologyRepositoryPort
from padhanam.security import Principal
from shared_kernel import TenantContext


class MethodologyLookupAdapter:
    """Adapter from MethodologyRepositoryPort to the agent context's
    MethodologyLookup Protocol.

    Closes over the methodology repository so the CLI command can
    construct the adapter once per invocation; the __call__ method
    is the Protocol surface the agent use case invokes.
    """

    def __init__(self, *, repository: MethodologyRepositoryPort) -> None:
        self._repository = repository

    async def __call__(
        self,
        *,
        template_id: UUID,
        version: int | None,
        principal: Principal,
    ) -> MethodologyView:
        template, revision = await get_methodology_template(
            principal=principal,
            repository=self._repository,
            template_id=template_id,
            version=version,
        )
        return MethodologyView(
            methodology_template_id=template.id,
            methodology_version=revision.version,
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
