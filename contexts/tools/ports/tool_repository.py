"""ToolRepositoryPort — the tool registry persistence abstraction (D89).

The tool repository is the source of truth for tool templates and
their revisions on the dedicated control-plane Postgres instance per
D33 and D89's storage-location resolution (alongside methodologies
and roles). The Postgres adapter at
``contexts/tools/adapters/outbound/postgres/tool_repository.py``
implements this Protocol.

The port mirrors ``RoleRepositoryPort`` exactly for the CRUD surface
plus two tool-registry-specific methods: ``verify_chain_integrity``
(hash-chain audit per D26's tamper-evidence posture) and
``list_roles_using_tool`` (the role-tool adoption-candidate query
that drives the Phase 2 adoption UX per D89's deferred-decisions
entry).

Contract notes:

- The port carries **no ``TenantContext`` parameter on any method**.
  Tool data is control-plane-scoped and platform-managed per D89's
  alternative (h) resolution; per-tenant tool authoring lifts at
  Phase 2 when consumer evidence demands. Mutation auth flows
  through the use case layer.

- ``create_template`` accepts the parent template plus the initial
  revision (version 1). The implementation persists both atomically;
  the returned ``Tool`` carries the assigned id (server-generated
  UUID) and timestamps.

- ``get_template`` returns the template plus the named revision
  (by version) or the latest revision when ``version`` is None.

- ``list_templates`` enumerates non-archived templates. Archived
  templates remain queryable through ``get_template`` for audit
  purposes per D31's append-only-at-version-level discipline.

- ``find_revision`` looks up a specific revision by id; raises
  ``RevisionNotFoundError`` if not found.

- ``add_revision`` appends a new revision to an existing template,
  incrementing the version and binding the previous_revision_hash to
  the latest existing revision's this_revision_hash.

- ``verify_chain_integrity`` walks the revision chain for a tool and
  recomputes each revision's hash from its persisted content payload;
  raises if any computed hash diverges from the stored hash. The
  method exists at commit 2 as the tamper-evidence audit surface
  per D26 / D89.

- ``list_roles_using_tool`` returns the set of role revisions whose
  ``tool_allowlist`` references the given tool. Each binding carries
  the role's currently-pinned revision id, the tool's latest revision
  id, and ``can_auto_adopt``. At commit 2 / 3, ``can_auto_adopt``
  defaults to False (the BC computation lands at commit 6 alongside
  the schema-diff stub). The query operates against the same
  control-plane DB that holds both ``tools`` and ``role_revisions``;
  the SQL spans both tables but the Python module does not import
  from ``contexts.methodology`` (cross-context independence preserved
  per D17 — the adapter knows the table name, not the methodology
  context's Python types).

The port is a Protocol so adapters need not inherit; satisfying the
methods is sufficient.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from contexts.tools.domain.tool import Tool, ToolRevision


@dataclass(frozen=True)
class RoleToolBinding:
    """Cross-context binding view used by the adoption-candidate query (D89).

    Returned by ``ToolRepository.list_roles_using_tool``. Carries
    enough information for the Phase 2 adoption UX (deferred per the
    automated-adoption-flow deferred-decisions entry) to render
    "which roles can adopt revision Rn+1?" without follow-up reads.

    The role identifiers (``role_id``, ``role_revision_id``,
    ``role_version``) are opaque UUIDs / integers from the
    methodology context's perspective — this DTO does not import
    ``RoleTemplate`` or ``RoleRevision`` types to preserve cross-
    context independence per D17.

    ``can_auto_adopt`` defaults to False at commits 2 / 3 (no BC
    computation yet); commit 6 introduces the schema-diff stub and
    sets this flag from the BC chain between ``current_revision_id``
    and ``latest_revision_id``.
    """

    role_id: UUID
    role_revision_id: UUID
    role_version: int
    tool_id: UUID
    current_revision_id: UUID
    latest_revision_id: UUID
    can_auto_adopt: bool


class ToolRepositoryPort(Protocol):
    async def create_template(
        self,
        template: Tool,
        initial_revision: ToolRevision,
    ) -> Tool: ...

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[Tool, ToolRevision]: ...

    async def list_templates(self) -> list[Tool]: ...

    async def find_revision(
        self,
        revision_id: UUID,
    ) -> tuple[Tool, ToolRevision]: ...

    async def add_revision(
        self,
        template_id: UUID,
        revision: ToolRevision,
    ) -> ToolRevision: ...

    async def archive_template(
        self,
        template_id: UUID,
    ) -> Tool: ...

    async def verify_chain_integrity(
        self,
        template_id: UUID,
    ) -> None: ...

    async def list_roles_using_tool(
        self,
        tool_id: UUID,
    ) -> list[RoleToolBinding]: ...
