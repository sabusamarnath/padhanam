"""Agent Postgres adapter (D75).

Implements ``AgentRepositoryPort`` against per-tenant Postgres data
planes per D32. SQLAlchemy 2.0 Core (Table + select / insert / update
via AsyncSession), manual row-to-domain conversion; no DeclarativeBase,
no ORM. Mirrors the methodology adapter shape at
``contexts/methodology/adapters/outbound/postgres/repository.py``
inverted with TenantContext threading per the per-tenant pattern at
``contexts/audit/adapters/outbound/postgres/audit.py``.

Privileged actions (``create_template``, ``add_revision``,
``archive_template``) emit security events with
``category=privileged_action``. Read methods (``get_template``,
``list_templates``) do not emit; the use case layer at S24 commit 8
gates write paths with tenant-context-or-operator-context auth and
emits authz_denial events on rejection.

Per-tenant session-factory resolution flows through a callable
injected at construction: ``per_tenant_sessionmaker_resolver`` takes
a ``TenantId`` and returns the tenant's ``async_sessionmaker``. The
CLI at S24 commit 10 supplies a dev-shape resolver that uses the
test-set mapping at ``apps/cli/_runtime.py``; apps/api at a future
session would supply the tenancy context's session-factory cache.
The adapter is opaque to the resolver implementation; tenant
credentials never reach the adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Protocol
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.agent.domain.agent import AgentRevision, AgentTemplate
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from shared_kernel import TenantContext, TenantId, ToolAllowlistEntry


_metadata = sa.MetaData()


agent_templates = sa.Table(
    "agent_templates",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column(
        "source_methodology_template_id",
        pg.UUID(as_uuid=False),
        nullable=True,
    ),
    sa.Column(
        "source_methodology_template_version",
        sa.Integer,
        nullable=True,
    ),
    sa.Column(
        "source_role_id",
        pg.UUID(as_uuid=False),
        nullable=True,
    ),
    sa.Column(
        "source_role_version",
        sa.Integer,
        nullable=True,
    ),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
)


agent_revisions = sa.Table(
    "agent_revisions",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "agent_template_id",
        pg.UUID(as_uuid=False),
        nullable=False,
    ),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("system_prompt", sa.Text, nullable=False),
    sa.Column("source_ids", pg.JSONB, nullable=False),
    sa.Column("tool_allowlist", pg.JSONB, nullable=False),
    sa.Column("retrieval_strategy", pg.JSONB, nullable=False),
    sa.Column("filter_tree", pg.JSONB, nullable=False),
    sa.Column("top_k", sa.Integer, nullable=False),
    sa.Column("min_score", sa.Numeric, nullable=False),
    sa.Column("model_selection", sa.Text, nullable=False),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("previous_revision_hash", sa.Text, nullable=False),
    sa.Column("this_revision_hash", sa.Text, nullable=False),
)


class _SessionFactoryResolver(Protocol):
    """Resolver shape: given a TenantId, return the per-tenant
    ``async_sessionmaker``. The CLI at S24 commit 10 supplies a dev-
    shape resolver bound to ``TenantPostgresSettings.for_tenant``;
    apps/api at a future session would bind the tenancy context's
    session-factory cache. The Protocol keeps the agent context
    independent of tenancy internals (D17)."""

    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class AgentPostgresRepository:
    """Adapter implementation of ``AgentRepositoryPort`` (D75).

    Holds a per-tenant sessionmaker resolver as instance state plus the
    security-event sink. No tenant credentials, plaintext or otherwise,
    are kept on the instance — the resolver is opaque to this adapter,
    which receives only ``async_sessionmaker`` opaque handles.
    """

    def __init__(
        self,
        *,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
        security_events: SecurityEventLogger,
    ) -> None:
        self._resolve_per_tenant = per_tenant_sessionmaker_resolver
        self._security_events = security_events

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def create_template(
        self,
        template: AgentTemplate,
        initial_revision: AgentRevision,
        tenant_context: TenantContext,
    ) -> AgentTemplate:
        sessionmaker = await self._resolve_per_tenant(tenant_context.tenant_id)
        async with sessionmaker() as session:
            await session.execute(
                sa.insert(agent_templates).values(
                    id=str(template.id),
                    name=template.name,
                    description=template.description,
                    source_methodology_template_id=(
                        str(template.source_methodology_template_id)
                        if template.source_methodology_template_id is not None
                        else None
                    ),
                    source_methodology_template_version=(
                        template.source_methodology_template_version
                    ),
                    source_role_id=(
                        str(template.source_role_id)
                        if template.source_role_id is not None
                        else None
                    ),
                    source_role_version=template.source_role_version,
                    created_by_user_id=template.created_by_user_id,
                    created_at=template.created_at,
                    archived_at=template.archived_at,
                )
            )
            await session.execute(
                sa.insert(agent_revisions).values(
                    **_revision_insert_values(initial_revision)
                )
            )
            await session.commit()

        self._emit_privileged(
            tenant_id=tenant_context.tenant_id,
            action="agent.create_template",
            resource_ref=f"agent_template:{template.id}",
        )
        return template

    async def get_template(
        self,
        template_id: UUID,
        tenant_context: TenantContext,
        version: int | None = None,
    ) -> tuple[AgentTemplate, AgentRevision]:
        sessionmaker = await self._resolve_per_tenant(tenant_context.tenant_id)
        async with sessionmaker() as session:
            result = await session.execute(
                sa.select(agent_templates).where(
                    agent_templates.c.id == str(template_id)
                )
            )
            template_row = result.mappings().first()
            if template_row is None:
                raise LookupError(f"agent template {template_id} not found")

            if version is None:
                stmt = (
                    sa.select(agent_revisions)
                    .where(
                        agent_revisions.c.agent_template_id == str(template_id)
                    )
                    .order_by(agent_revisions.c.version.desc())
                    .limit(1)
                )
            else:
                stmt = sa.select(agent_revisions).where(
                    sa.and_(
                        agent_revisions.c.agent_template_id == str(template_id),
                        agent_revisions.c.version == version,
                    )
                )

            rev_result = await session.execute(stmt)
            rev_row = rev_result.mappings().first()
            if rev_row is None:
                raise LookupError(
                    f"agent revision for template {template_id} "
                    f"version {version} not found"
                )

        return _row_to_template(template_row), _row_to_revision(rev_row)

    async def list_templates(
        self,
        tenant_context: TenantContext,
        include_archived: bool = False,
    ) -> list[AgentTemplate]:
        sessionmaker = await self._resolve_per_tenant(tenant_context.tenant_id)
        async with sessionmaker() as session:
            stmt = sa.select(agent_templates).order_by(
                agent_templates.c.created_at
            )
            if not include_archived:
                stmt = stmt.where(agent_templates.c.archived_at.is_(None))
            result = await session.execute(stmt)
            rows = result.mappings().all()
        return [_row_to_template(r) for r in rows]

    async def add_revision(
        self,
        template_id: UUID,
        revision: AgentRevision,
        tenant_context: TenantContext,
    ) -> AgentRevision:
        sessionmaker = await self._resolve_per_tenant(tenant_context.tenant_id)
        async with sessionmaker() as session:
            await session.execute(
                sa.insert(agent_revisions).values(
                    **_revision_insert_values(revision)
                )
            )
            await session.commit()

        self._emit_privileged(
            tenant_id=tenant_context.tenant_id,
            action="agent.add_revision",
            resource_ref=f"agent_revision:{revision.id}",
        )
        return revision

    async def archive_template(
        self,
        template_id: UUID,
        tenant_context: TenantContext,
    ) -> AgentTemplate:
        archived_at = datetime.now(timezone.utc)
        sessionmaker = await self._resolve_per_tenant(tenant_context.tenant_id)
        async with sessionmaker() as session:
            existing = await session.execute(
                sa.select(agent_templates).where(
                    agent_templates.c.id == str(template_id)
                )
            )
            row = existing.mappings().first()
            if row is None:
                raise LookupError(f"agent template {template_id} not found")

            await session.execute(
                sa.update(agent_templates)
                .where(agent_templates.c.id == str(template_id))
                .values(archived_at=archived_at)
            )
            await session.commit()

            after = await session.execute(
                sa.select(agent_templates).where(
                    agent_templates.c.id == str(template_id)
                )
            )
            after_row = after.mappings().first()

        template = _row_to_template(after_row)
        self._emit_privileged(
            tenant_id=tenant_context.tenant_id,
            action="agent.archive_template",
            resource_ref=f"agent_template:{template.id}",
        )
        return template

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _emit_privileged(
        self, *, tenant_id: TenantId, action: str, resource_ref: str
    ) -> None:
        self._security_events.emit(
            SecurityEvent(
                category=SecurityEventCategory.PRIVILEGED_ACTION,
                principal_ref="system:agent_repository",
                tenant_id=str(tenant_id),
                action=action,
                resource_ref=resource_ref,
                outcome="allow",
            )
        )


def _revision_insert_values(rev: AgentRevision) -> dict:
    return {
        "id": str(rev.id),
        "agent_template_id": str(rev.agent_template_id),
        "version": rev.version,
        "system_prompt": rev.system_prompt,
        "source_ids": [str(s) for s in rev.source_ids],
        "tool_allowlist": [
            {"tool_id": str(e.tool_id), "revision_id": str(e.revision_id)}
            for e in rev.tool_allowlist
        ],
        "retrieval_strategy": dict(rev.retrieval_strategy),
        "filter_tree": dict(rev.filter_tree),
        "top_k": rev.top_k,
        "min_score": rev.min_score,
        "model_selection": rev.model_selection,
        "created_by_user_id": rev.created_by_user_id,
        "created_at": rev.created_at,
        "previous_revision_hash": rev.previous_revision_hash,
        "this_revision_hash": rev.this_revision_hash,
    }


def _row_to_template(row) -> AgentTemplate:
    methodology_id_raw = row["source_methodology_template_id"]
    role_id_raw = row["source_role_id"]
    return AgentTemplate(
        id=UUID(row["id"]),
        name=row["name"],
        description=row["description"],
        source_methodology_template_id=(
            UUID(methodology_id_raw) if methodology_id_raw is not None else None
        ),
        source_methodology_template_version=row[
            "source_methodology_template_version"
        ],
        source_role_id=(
            UUID(role_id_raw) if role_id_raw is not None else None
        ),
        source_role_version=row["source_role_version"],
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        archived_at=row["archived_at"],
    )


def _row_to_revision(row) -> AgentRevision:
    return AgentRevision(
        id=UUID(row["id"]),
        agent_template_id=UUID(row["agent_template_id"]),
        version=row["version"],
        system_prompt=row["system_prompt"],
        source_ids=tuple(UUID(s) for s in row["source_ids"]),
        tool_allowlist=tuple(
            ToolAllowlistEntry(
                tool_id=UUID(e["tool_id"]),
                revision_id=UUID(e["revision_id"]),
            )
            for e in row["tool_allowlist"]
        ),
        retrieval_strategy=row["retrieval_strategy"],
        filter_tree=row["filter_tree"],
        top_k=row["top_k"],
        min_score=row["min_score"],
        model_selection=row["model_selection"],
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        previous_revision_hash=row["previous_revision_hash"],
        this_revision_hash=row["this_revision_hash"],
    )
