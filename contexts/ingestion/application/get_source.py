"""get_source — read-side use case at the application layer.

Ships at S25 as the cross-context consumer surface the new
``create_agent_from_methodology`` flow at S25 consumes. Prior to S25
the ingestion context's read needs were intra-context only
(the worker stages reading their own sources), and the port-layer
``get_source`` method was sufficient. S25's cross-context flow needs
an application-layer wrapper so the apps/cli SourceLookup adapter
calls through the api facade rather than reaching into the
repository directly.

The use case is pure orchestration: it calls
``SourceRepositoryPort.get_source`` and upgrades the port's
not-found sentinel (``None``) into a ``LookupError`` so the cross-
context adapter can translate the ingestion-side error into the
consumer-shaped ``SourceNotFoundError`` defined at
``contexts/agent/application/ports/source_lookup.py``. The
ingestion context does not own the consumer's exception type per
D17's independence contracts.

Signature mirrors the existing ingestion use cases (no ``principal``
parameter; auth is the cross-context adapter's responsibility per
the api-facade-via-callable pattern at D17 and the established
worker-side ingestion convention).
"""

from __future__ import annotations

from uuid import UUID

from contexts.ingestion.domain.source import Source
from contexts.ingestion.ports.source_repository_port import SourceRepositoryPort


async def get_source(
    *,
    repository: SourceRepositoryPort,
    source_id: UUID,
    tenant_id: str,
) -> Source:
    """Retrieve a Source by id, scoped to the tenant.

    Raises ``LookupError`` when no source row matches the (id, tenant)
    pair — covers both the missing-id case and the wrong-tenant case
    (the repository's ``get_source`` returns ``None`` for both;
    distinguishing the two would require a cross-tenant query that
    violates tenant isolation per D24).
    """
    source = await repository.get_source(source_id, tenant_id)
    if source is None:
        raise LookupError(
            f"source {source_id} not found for tenant {tenant_id}"
        )
    return source
