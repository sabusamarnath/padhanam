"""SourceLookup Protocol port + SourceNotFoundError exception (D79).

The create-from-methodology flow validates that every source_id in
the clone request exists for the routed tenant before constructing
the AgentTemplate. Validation at the use case boundary fails fast on
bad inputs rather than after AgentTemplate construction, which would
leave orphan-reference revisions if persistence ran first; the
boundary also surfaces tenant-routing errors (source belongs to a
different tenant) at the same point as missing-id errors per D79.

The port is a Protocol the wiring layer (apps/cli) implements as an
adapter over ``contexts.ingestion.api.get_source`` (shipped at the
S25 reconciliation-2 sub-commit). The adapter calls the ingestion
use case once per requested source id and translates the producer's
``LookupError`` into the consumer-side ``SourceNotFoundError``
defined here; the per-id call is acceptable because source-existence
validation runs at clone time on a small N (the typical agent has
a handful of sources, not thousands).

SourceNotFoundError inherits from LookupError so that callers
catching the platform's generic not-found convention (the same shape
``get_agent`` and ``get_methodology_template`` use) continue to
work; the more specific class lets the consumer distinguish
source-existence failures from other LookupError shapes at sites
where the distinction matters.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from padhanam.security import Principal
from shared_kernel import TenantContext


class SourceNotFoundError(LookupError):
    """Raised by SourceLookup adapters when one or more requested
    source ids do not resolve for the routed tenant.

    The exception carries the offending ids so the caller can render
    a precise error to the operator without re-querying.
    """

    def __init__(self, missing_source_ids: tuple[UUID, ...]) -> None:
        self.missing_source_ids = missing_source_ids
        super().__init__(
            f"source(s) not found: {sorted(str(s) for s in missing_source_ids)}"
        )


class SourceLookup(Protocol):
    """Callable port for source-existence validation at clone time.

    The adapter at apps/cli implements ``assert_sources_exist`` by
    invoking the ingestion ``get_source`` use case per id and
    translating the underlying ``LookupError`` (which the ingestion
    use case raises for both missing-id and wrong-tenant cases) into
    a ``SourceNotFoundError`` carrying the offending ids.

    The Protocol takes ``tenant_context`` (not just ``tenant_id``)
    so the adapter can route the lookup through the tenant's data
    plane and remain symmetric with the agent-context use cases'
    tenant-context-on-every-method convention (D75). The
    ``principal`` parameter threads the operator/tenant identity
    through for audit-trail consistency; the underlying ingestion
    use case discards it but the boundary keeps the shape uniform
    with the methodology lookup port.
    """

    async def assert_sources_exist(
        self,
        *,
        source_ids: tuple[UUID, ...],
        tenant_context: TenantContext,
        principal: Principal,
    ) -> None: ...
