"""list_sources — read-side use case at the application layer (D104, S38).

Ships at S38 as the application-layer surface for the HTTP
ingestion management API. The HTTP route at
``apps/api/routers/ingestion.py`` calls this use case directly per
Path A from S38 reconciliation: extend the existing
``SourceRepositoryPort`` with a list method and add the application
use case alongside the existing ``get_source`` and ``register_source``
use cases.

The use case is pure orchestration: it delegates to
``SourceRepositoryPort.list_sources`` with the tenant scope and
pagination parameters. Page-size defaulting and ceiling enforcement
live on the port's cursor value object
(``SourceListCursor.page_size`` validates in ``__post_init__``);
the use case is signature-thin and tenant-scoped per the existing
ingestion-context convention.

Signature mirrors the existing ingestion use cases (no
``principal`` parameter; auth is the HTTP layer's responsibility
per the api-facade-via-callable pattern at D17 and the existing
worker-side convention).
"""

from __future__ import annotations

from contexts.ingestion.domain.source_list import SourceListCursor, SourceListPage
from contexts.ingestion.ports.source_repository_port import SourceRepositoryPort


async def list_sources(
    *,
    repository: SourceRepositoryPort,
    tenant_id: str,
    cursor: SourceListCursor | None = None,
    page_size: int = 50,
) -> SourceListPage:
    """Return a paginated page of sources scoped to the tenant.

    Sort order is ``created_at DESC, id DESC`` enforced at the
    adapter. The returned page carries the loaded Source aggregates
    and an optional ``next_cursor``; the HTTP layer encodes the
    cursor through ``contexts.ingestion.application.cursor.encode``
    before returning to the consumer.
    """
    return await repository.list_sources(
        tenant_id=tenant_id,
        cursor=cursor,
        page_size=page_size,
    )
