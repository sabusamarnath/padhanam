"""Tool Postgres adapter (D89).

Implements ``ToolRepositoryPort`` against the control-plane Postgres
instance per D33 and D89's storage-location resolution. SQLAlchemy 2.0
Core (Table + select / insert / update via AsyncConnection.execute),
manual row-to-domain conversion; no DeclarativeBase, no ORM. Symmetric
to the methodology / role adapters from S23 / S26a-1.

Privileged actions (``create_template``, ``add_revision``,
``archive_template``) emit security events with
``category=privileged_action``. Read methods do not emit; the use case
layer gates write paths with operator-context auth.

Per D89, tool data is control-plane-scoped; the adapter holds only the
engine, session factory, and security-event sink — no
``TenantContext`` parameter on any method.

The ``list_roles_using_tool`` query operates against both ``tools`` /
``tool_revisions`` and ``role_revisions`` on the same control-plane
Postgres instance. The SQL spans both tables but the Python module
does not import from ``contexts.methodology``; cross-context
independence per D17 is preserved at the import boundary. The
adapter's knowledge of the ``role_revisions`` table schema is the
acceptable seam given both aggregates live on the same DB and the
binding query is a structural cross-aggregate concern.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from contexts.tools.domain.exceptions import (
    RevisionNotFoundError,
    ToolNotFoundError,
)
from contexts.tools.domain.tool import (
    Classification,
    Tool,
    ToolRevision,
)
from contexts.tools.ports.tool_repository import RoleToolBinding
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from padhanam.security.hash_chain import (
    GENESIS_REVISION_HASH,
    compute_revision_hash,
)


_log = logging.getLogger("contexts.tools.adapters.postgres")
_metadata = sa.MetaData()


tools = sa.Table(
    "tools",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("classification", sa.Text, nullable=False),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
)


tool_revisions = sa.Table(
    "tool_revisions",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "tool_id",
        pg.UUID(as_uuid=False),
        nullable=False,
    ),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("parameters_schema", pg.JSONB, nullable=False),
    sa.Column("returns_schema", pg.JSONB, nullable=False),
    sa.Column("bc_result", pg.JSONB, nullable=False),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("previous_revision_hash", sa.Text, nullable=False),
    sa.Column("this_revision_hash", sa.Text, nullable=False),
)


# The methodology context's role_revisions table. Defined here for SQL
# cross-table queries (``list_roles_using_tool``); the Python module
# does not import ``contexts.methodology`` types. Same control-plane
# DB hosts both per D89.
_role_revisions = sa.Table(
    "role_revisions",
    sa.MetaData(),
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("role_template_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("tool_allowlist", pg.JSONB, nullable=False),
)


def _async_url(settings: ControlPlaneSettings) -> str:
    return (
        f"postgresql+asyncpg://{settings.user}:{settings.password}"
        f"@{settings.host}:{settings.port}/{settings.db}"
    )


class ToolPostgresRepository:
    """Adapter implementation of ``ToolRepositoryPort`` (D89)."""

    def __init__(
        self,
        *,
        engine: AsyncEngine,
        security_events: SecurityEventLogger,
    ) -> None:
        self._engine = engine
        self._sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        self._security_events = security_events

    @classmethod
    def from_settings(
        cls,
        *,
        settings: ControlPlaneSettings,
        security_events: SecurityEventLogger,
    ) -> "ToolPostgresRepository":
        engine = create_async_engine(_async_url(settings), pool_pre_ping=True)
        return cls(engine=engine, security_events=security_events)

    async def dispose(self) -> None:
        await self._engine.dispose()

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def create_template(
        self,
        template: Tool,
        initial_revision: ToolRevision,
    ) -> Tool:
        async with self._sessionmaker() as session:
            await session.execute(
                sa.insert(tools).values(
                    id=str(template.id),
                    name=template.name,
                    description=template.description,
                    classification=template.classification.value,
                    created_by_user_id=template.created_by_user_id,
                    created_at=template.created_at,
                    archived_at=template.archived_at,
                )
            )
            await session.execute(
                sa.insert(tool_revisions).values(
                    **_revision_insert_values(initial_revision)
                )
            )
            await session.commit()

        self._emit_privileged(
            action="tool.create_template",
            resource_ref=f"tool:{template.id}",
        )
        return template

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[Tool, ToolRevision]:
        async with self._sessionmaker() as session:
            tool_result = await session.execute(
                sa.select(tools).where(tools.c.id == str(template_id))
            )
            tool_row = tool_result.mappings().first()
            if tool_row is None:
                raise ToolNotFoundError(f"tool {template_id} not found")

            if version is None:
                stmt = (
                    sa.select(tool_revisions)
                    .where(tool_revisions.c.tool_id == str(template_id))
                    .order_by(tool_revisions.c.version.desc())
                    .limit(1)
                )
            else:
                stmt = sa.select(tool_revisions).where(
                    sa.and_(
                        tool_revisions.c.tool_id == str(template_id),
                        tool_revisions.c.version == version,
                    )
                )

            rev_result = await session.execute(stmt)
            rev_row = rev_result.mappings().first()
            if rev_row is None:
                raise RevisionNotFoundError(
                    f"tool revision for tool {template_id} version "
                    f"{version} not found"
                )

        return _row_to_tool(tool_row), _row_to_revision(rev_row)

    async def list_templates(self) -> list[Tool]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                sa.select(tools)
                .where(tools.c.archived_at.is_(None))
                .order_by(tools.c.created_at)
            )
            rows = result.mappings().all()
        return [_row_to_tool(r) for r in rows]

    async def find_revision(
        self,
        revision_id: UUID,
    ) -> tuple[Tool, ToolRevision]:
        async with self._sessionmaker() as session:
            rev_result = await session.execute(
                sa.select(tool_revisions).where(
                    tool_revisions.c.id == str(revision_id)
                )
            )
            rev_row = rev_result.mappings().first()
            if rev_row is None:
                raise RevisionNotFoundError(
                    f"tool revision {revision_id} not found"
                )

            tool_result = await session.execute(
                sa.select(tools).where(tools.c.id == rev_row["tool_id"])
            )
            tool_row = tool_result.mappings().first()
            if tool_row is None:
                raise ToolNotFoundError(
                    f"tool {rev_row['tool_id']} (parent of revision "
                    f"{revision_id}) not found"
                )

        return _row_to_tool(tool_row), _row_to_revision(rev_row)

    async def add_revision(
        self,
        template_id: UUID,
        revision: ToolRevision,
    ) -> ToolRevision:
        async with self._sessionmaker() as session:
            await session.execute(
                sa.insert(tool_revisions).values(
                    **_revision_insert_values(revision)
                )
            )
            await session.commit()

        self._emit_privileged(
            action="tool.add_revision",
            resource_ref=f"tool_revision:{revision.id}",
        )
        return revision

    async def archive_template(
        self,
        template_id: UUID,
    ) -> Tool:
        archived_at = datetime.now(timezone.utc)
        async with self._sessionmaker() as session:
            existing = await session.execute(
                sa.select(tools).where(tools.c.id == str(template_id))
            )
            row = existing.mappings().first()
            if row is None:
                raise ToolNotFoundError(f"tool {template_id} not found")

            await session.execute(
                sa.update(tools)
                .where(tools.c.id == str(template_id))
                .values(archived_at=archived_at)
            )
            await session.commit()

            after = await session.execute(
                sa.select(tools).where(tools.c.id == str(template_id))
            )
            after_row = after.mappings().first()

        template = _row_to_tool(after_row)
        self._emit_privileged(
            action="tool.archive_template",
            resource_ref=f"tool:{template.id}",
        )
        return template

    async def verify_chain_integrity(
        self,
        template_id: UUID,
    ) -> None:
        """Walk the revision chain and verify each stored hash matches.

        Reads the parent template plus the full ordered chain of
        revisions, recomputes each revision's hash from its persisted
        content payload (denormalising name + description +
        classification from the parent template per D74's chain-self-
        containment pattern), and raises ``ValueError`` on the first
        divergence. The genesis sentinel anchors the chain head; each
        subsequent revision's ``previous_revision_hash`` must equal the
        prior revision's ``this_revision_hash``.
        """
        async with self._sessionmaker() as session:
            tool_result = await session.execute(
                sa.select(tools).where(tools.c.id == str(template_id))
            )
            tool_row = tool_result.mappings().first()
            if tool_row is None:
                raise ToolNotFoundError(f"tool {template_id} not found")

            rev_result = await session.execute(
                sa.select(tool_revisions)
                .where(tool_revisions.c.tool_id == str(template_id))
                .order_by(tool_revisions.c.version.asc())
            )
            rev_rows = rev_result.mappings().all()

        if not rev_rows:
            raise ValueError(
                f"tool {template_id} has no revisions; chain incomplete"
            )

        tool = _row_to_tool(tool_row)
        expected_prev = GENESIS_REVISION_HASH
        for rev_row in rev_rows:
            if rev_row["previous_revision_hash"] != expected_prev:
                raise ValueError(
                    f"tool {template_id} revision {rev_row['version']}: "
                    f"previous_revision_hash {rev_row['previous_revision_hash']!r} "
                    f"does not chain from prior {expected_prev!r}"
                )

            recomputed = compute_revision_hash(
                content_payload={
                    "name": tool.name,
                    "description": tool.description,
                    "classification": tool.classification.value,
                    "parameters_schema": dict(rev_row["parameters_schema"]),
                    "returns_schema": dict(rev_row["returns_schema"]),
                },
                previous_hash=rev_row["previous_revision_hash"],
            )
            if recomputed != rev_row["this_revision_hash"]:
                raise ValueError(
                    f"tool {template_id} revision {rev_row['version']}: "
                    f"recomputed hash {recomputed!r} does not match "
                    f"stored hash {rev_row['this_revision_hash']!r} "
                    f"(tamper-evidence per D26)"
                )
            expected_prev = rev_row["this_revision_hash"]

    async def list_roles_using_tool(
        self,
        tool_id: UUID,
    ) -> list[RoleToolBinding]:
        """Return role-tool bindings for the named tool (D89).

        Joins the control-plane ``role_revisions`` against the tool
        revision chain. Per D89 commit 6, ``can_auto_adopt`` is
        computed from the BC chain between
        ``current_revision_id`` and ``latest_revision_id``: every
        intervening revision's ``bc_result`` must be ``passed`` for
        the binding to auto-adopt safely. The flag drives the Phase 2
        adoption UX per the automated-adoption-flow deferred-decisions
        entry.

        The query is structurally cross-aggregate (joins
        ``role_revisions`` against ``tool_revisions`` on the same
        control-plane DB); cross-context independence per D17 is
        preserved at the import boundary (no
        ``contexts.methodology`` imports in this module).
        """
        async with self._sessionmaker() as session:
            # Load the full ordered chain so can_auto_adopt computation
            # has access to every intermediate revision's bc_result.
            rev_chain_result = await session.execute(
                sa.select(
                    tool_revisions.c.id,
                    tool_revisions.c.version,
                    tool_revisions.c.bc_result,
                )
                .where(tool_revisions.c.tool_id == str(tool_id))
                .order_by(tool_revisions.c.version.asc())
            )
            rev_chain = rev_chain_result.mappings().all()
            if not rev_chain:
                raise ToolNotFoundError(
                    f"tool {tool_id} has no revisions; cannot enumerate "
                    f"role bindings"
                )

            latest_row = rev_chain[-1]
            latest_revision_id = UUID(latest_row["id"])
            # Map version-ordered (id, bc_outcome) so the BC chain
            # walk between current and latest is O(N) across the
            # ordered list.
            chain_order: list[tuple[UUID, str]] = [
                (
                    UUID(r["id"]),
                    str((r["bc_result"] or {}).get("outcome", "passed")),
                )
                for r in rev_chain
            ]

            role_stmt = sa.select(
                _role_revisions.c.id,
                _role_revisions.c.role_template_id,
                _role_revisions.c.version,
                _role_revisions.c.tool_allowlist,
            )
            role_result = await session.execute(role_stmt)
            role_rows = role_result.mappings().all()

        bindings: list[RoleToolBinding] = []
        for row in role_rows:
            allowlist = row["tool_allowlist"]
            current_revision_id = _extract_pinned_revision_id(
                allowlist=allowlist,
                tool_id=tool_id,
            )
            if current_revision_id is None:
                continue
            can_auto_adopt = _can_auto_adopt(
                chain_order=chain_order,
                current_revision_id=current_revision_id,
                latest_revision_id=latest_revision_id,
            )
            bindings.append(
                RoleToolBinding(
                    role_id=UUID(row["role_template_id"]),
                    role_revision_id=UUID(row["id"]),
                    role_version=row["version"],
                    tool_id=tool_id,
                    current_revision_id=current_revision_id,
                    latest_revision_id=latest_revision_id,
                    can_auto_adopt=can_auto_adopt,
                )
            )
        return bindings

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _emit_privileged(self, *, action: str, resource_ref: str) -> None:
        self._security_events.emit(
            SecurityEvent(
                category=SecurityEventCategory.PRIVILEGED_ACTION,
                principal_ref="system:tool_repository",
                tenant_id=None,
                action=action,
                resource_ref=resource_ref,
                outcome="allow",
            )
        )


def _can_auto_adopt(
    *,
    chain_order: list[tuple[UUID, str]],
    current_revision_id: UUID,
    latest_revision_id: UUID,
) -> bool:
    """Compute can_auto_adopt by walking the BC chain (D89 commit 6).

    The binding can auto-adopt if every revision between current and
    latest has ``bc_result.outcome == 'passed'``. If current equals
    latest, the binding is already at the latest revision (no
    adoption needed); return True for "no work to do, no risk
    introduced" semantics.
    """
    if current_revision_id == latest_revision_id:
        return True

    seen_current = False
    for rev_id, outcome in chain_order:
        if rev_id == current_revision_id:
            seen_current = True
            continue
        if not seen_current:
            continue
        if outcome != "passed":
            return False
        if rev_id == latest_revision_id:
            return True

    # current_revision_id not in chain (binding points at a
    # revision not present in the tool's chain — structural
    # inconsistency). Be conservative.
    return False


def _extract_pinned_revision_id(
    *,
    allowlist: Any,
    tool_id: UUID,
) -> UUID | None:
    """Extract the pinned revision id for ``tool_id`` from a role allowlist.

    Handles two shapes:

    - Commit 2 / pre-migration (string list): every entry is an
      opaque name string. No UUID match possible; return None.

    - Commit 4 / post-migration (object list): each entry is
      ``{"tool_id": "<uuid>", "revision_id": "<uuid>"}``. Match on
      ``tool_id`` and return the revision_id.

    The helper supports the forward-compatibility commitment in the
    query's docstring.
    """
    if not isinstance(allowlist, list):
        return None
    target = str(tool_id)
    for entry in allowlist:
        if isinstance(entry, dict) and entry.get("tool_id") == target:
            rev = entry.get("revision_id")
            if rev:
                try:
                    return UUID(str(rev))
                except (ValueError, TypeError):
                    return None
    return None


def _revision_insert_values(rev: ToolRevision) -> dict:
    return {
        "id": str(rev.id),
        "tool_id": str(rev.tool_id),
        "version": rev.version,
        "parameters_schema": dict(rev.parameters_schema),
        "returns_schema": dict(rev.returns_schema),
        "bc_result": dict(rev.bc_result),
        "created_by_user_id": rev.created_by_user_id,
        "created_at": rev.created_at,
        "previous_revision_hash": rev.previous_revision_hash,
        "this_revision_hash": rev.this_revision_hash,
    }


def _row_to_tool(row) -> Tool:
    return Tool(
        id=UUID(row["id"]),
        name=row["name"],
        description=row["description"],
        classification=Classification(row["classification"]),
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        archived_at=row["archived_at"],
    )


def _row_to_revision(row) -> ToolRevision:
    return ToolRevision(
        id=UUID(row["id"]),
        tool_id=UUID(row["tool_id"]),
        version=row["version"],
        parameters_schema=row["parameters_schema"],
        returns_schema=row["returns_schema"],
        bc_result=row["bc_result"],
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        previous_revision_hash=row["previous_revision_hash"],
        this_revision_hash=row["this_revision_hash"],
    )
