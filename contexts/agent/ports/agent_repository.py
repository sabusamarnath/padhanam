"""AgentRepositoryPort — the agent persistence abstraction (D75).

The agent repository is the source of truth for agent templates and
their revisions on each tenant's dedicated Postgres data plane per
D32. The S24 adapter at
``contexts/agent/adapters/outbound/postgres/repository.py``
implements this Protocol.

Contract notes:

- The port carries a **``TenantContext`` parameter on every method**.
  Agent data is structurally per-tenant-scoped per D32; routing
  flows through TenantContext per D50, mirroring the existing per-
  tenant adapters at ``contexts/audit/``, ``contexts/evaluation/``,
  ``contexts/ingestion/``. The methodology context's port (control-
  plane-scoped per D74) carries no TenantContext parameter; the
  inverted shape here matches the inverted scope.

- Auth posture per D75: agent CRUD use cases accept either tenant-
  context or operator-context as valid authentication. Both produce
  authorised access via the use case layer; the repository sees only
  the resolved TenantContext routing target.

- ``create_template`` accepts the parent template plus the initial
  revision (version 1). The implementation persists both atomically;
  the returned ``AgentTemplate`` carries the assigned id (server-
  generated UUID) and timestamps. Methodology lineage fields populate
  for clone-created agents (S25 cross-context flow); both NULL for
  blank-created agents at S24.

- ``get_template`` returns the template plus the named revision (by
  version) or the latest revision when ``version`` is None.

- ``list_templates`` enumerates templates within the tenant.
  ``include_archived=False`` (default) excludes templates with a
  populated archived_at; pass ``True`` to include them for audit
  views.

- ``add_revision`` appends a new revision to an existing template
  within the tenant. Caller passes the full revision (including the
  precomputed previous and this hashes); the repository performs no
  chain computation, keeping hash logic in the application layer.

- ``archive_template`` marks the parent template's archived_at;
  revisions are unaffected per D31's append-only-at-version-level
  discipline.

The port is a Protocol so adapters need not inherit; satisfying the
methods is sufficient. The runtime tripwire test verifies that
importing this module does not pull in sqlalchemy, alembic, or
asyncpg — keeping the port framework-free per D16.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from contexts.agent.domain.agent import AgentRevision, AgentTemplate
from shared_kernel import TenantContext


class AgentRepositoryPort(Protocol):
    async def create_template(
        self,
        template: AgentTemplate,
        initial_revision: AgentRevision,
        tenant_context: TenantContext,
    ) -> AgentTemplate: ...

    async def get_template(
        self,
        template_id: UUID,
        tenant_context: TenantContext,
        version: int | None = None,
    ) -> tuple[AgentTemplate, AgentRevision]: ...

    async def list_templates(
        self,
        tenant_context: TenantContext,
        include_archived: bool = False,
    ) -> list[AgentTemplate]: ...

    async def add_revision(
        self,
        template_id: UUID,
        revision: AgentRevision,
        tenant_context: TenantContext,
    ) -> AgentRevision: ...

    async def archive_template(
        self,
        template_id: UUID,
        tenant_context: TenantContext,
    ) -> AgentTemplate: ...
