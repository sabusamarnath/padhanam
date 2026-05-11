"""RoleRepositoryPort — the role persistence abstraction (D86).

The role repository is the source of truth for role templates and
their revisions on the dedicated control-plane Postgres instance per
D33. The S26a-1 adapter at
``contexts/methodology/adapters/outbound/postgres/role_repository.py``
implements this Protocol.

The port mirrors ``MethodologyRepositoryPort`` exactly. Role data is
structurally control-plane-scoped per D33 (same posture as methodology
per D86's role-first-aggregate-co-located-with-methodology choice);
mutation auth flows through the use case layer (operator-context
enforcement) mirroring ``register_tenant`` / ``update_tenant_status``
/ ``reveal_connection_config`` per D34.

Contract notes:

- The port carries **no ``TenantContext`` parameter on any method**.
  Role data is control-plane-scoped and platform-managed; read-side
  filtering by tenant is N/A. Mutation auth flows through the use
  case layer (operator-context required for writes).

- ``create_template`` accepts the parent template plus the initial
  revision (version 1). The implementation persists both atomically;
  the returned ``RoleTemplate`` carries the assigned id (server-
  generated UUID) and timestamps.

- ``get_template`` returns the template plus the named revision (by
  version) or the latest revision when ``version`` is None. The
  revision is paired with its template so callers receive the full
  aggregate without a follow-up read.

- ``list_templates`` enumerates non-archived templates. Archived
  templates remain queryable through ``get_template`` for audit
  purposes per D31's append-only-at-version-level discipline.

- ``add_revision`` appends a new revision to an existing template,
  incrementing the version and binding the previous_revision_hash to
  the latest existing revision's this_revision_hash. The caller passes
  both the revision and predecessor hash; the repository performs no
  chain computation, keeping hash logic in the domain.

- ``archive_template`` marks the parent template's archived_at;
  revisions are unaffected per D68 (existing methodology-references
  survive role archival because they reference revisions, not the
  template envelope).

The port is a Protocol so adapters need not inherit; satisfying the
methods is sufficient.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.methodology.domain.role import RoleRevision, RoleTemplate


class RoleRepositoryPort(Protocol):
    async def create_template(
        self,
        template: RoleTemplate,
        initial_revision: RoleRevision,
    ) -> RoleTemplate: ...

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[RoleTemplate, RoleRevision]: ...

    async def list_templates(self) -> list[RoleTemplate]: ...

    async def add_revision(
        self,
        template_id: UUID,
        revision: RoleRevision,
    ) -> RoleRevision: ...

    async def archive_template(
        self,
        template_id: UUID,
    ) -> RoleTemplate: ...
