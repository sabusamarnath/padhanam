"""MethodologyRepositoryPort — the methodology persistence abstraction (D74).

The methodology repository is the source of truth for methodology
templates and their revisions on the dedicated control-plane Postgres
instance per D33. The S23 adapter at
``contexts/methodology/adapters/outbound/postgres/repository.py``
implements this Protocol.

Contract notes:

- The port carries **no ``TenantContext`` parameter on any method**.
  Methodology data is structurally control-plane-scoped per D33;
  read-side filtering by tenant happens at the agent context
  (tenant-scoped) at S24, not at the methodology context (platform-
  scoped). Mutation auth flows through the use case layer
  (operator-context enforcement) per D34, mirroring the tenancy
  ``register_tenant`` / ``update_tenant_status`` /
  ``reveal_connection_config`` rejection path.

- ``create_template`` accepts the parent template plus the initial
  revision (version 1). The implementation persists both atomically;
  the returned ``MethodologyTemplate`` carries the assigned id
  (server-generated UUID) and timestamps.

- ``get_template`` returns the template plus the named revision (by
  version) or the latest revision when ``version`` is None. The
  revision is paired with its template so callers receive the full
  aggregate without a follow-up read.

- ``list_templates`` enumerates non-archived templates. Archived
  templates remain queryable through ``get_template`` for audit
  purposes per D31's append-only-at-version-level discipline.

- ``add_revision`` appends a new revision to an existing template,
  incrementing the version and binding the previous_revision_hash
  to the latest existing revision's this_revision_hash (the
  caller passes both revision and predecessor hash; the repository
  performs no chain computation, keeping hash logic in the domain).

- ``archive_template`` marks the parent template's archived_at;
  revisions are unaffected per D68 (existing clones reference
  revisions, not the template envelope).

The port is a Protocol so adapters need not inherit; satisfying the
methods is sufficient.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
)


class MethodologyRepositoryPort(Protocol):
    async def create_template(
        self,
        template: MethodologyTemplate,
        initial_revision: MethodologyRevision,
    ) -> MethodologyTemplate: ...

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[MethodologyTemplate, MethodologyRevision]: ...

    async def list_templates(self) -> list[MethodologyTemplate]: ...

    async def add_revision(
        self,
        template_id: UUID,
        revision: MethodologyRevision,
    ) -> MethodologyRevision: ...

    async def archive_template(
        self,
        template_id: UUID,
    ) -> MethodologyTemplate: ...
