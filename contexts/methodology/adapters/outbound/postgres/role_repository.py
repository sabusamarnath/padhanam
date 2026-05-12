"""Role Postgres adapter (D86).

Implements ``RoleRepositoryPort`` against the control-plane Postgres
instance per D33, mirroring the methodology adapter shape from D74
exactly. SQLAlchemy 2.0 Core (Table + select / insert / update via
AsyncConnection.execute), manual row-to-domain conversion; no
DeclarativeBase, no ORM. The two adapters share the engine factory
(``ControlPlaneSettings`` + ``create_async_engine``) but hold their
own ``MetaData`` to keep the table definitions co-located with their
adapter for audit clarity.

Privileged actions (``create_template``, ``add_revision``,
``archive_template``) emit security events with
``category=privileged_action``. Read methods (``get_template``,
``list_templates``) do not emit; the use case layer gates write paths
with operator-context auth and emits ``authz_denial`` events on
rejection.

Per D86, the port carries no ``TenantContext`` parameter; role data is
control-plane-scoped, so the adapter holds only the engine, session
factory, and security-event sink — symmetric to the methodology
adapter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from contexts.methodology.domain.role import RoleRevision, RoleTemplate
from padhanam.config import ControlPlaneSettings
from shared_kernel import ToolAllowlistEntry
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)


_metadata = sa.MetaData()


role_templates = sa.Table(
    "role_templates",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
)


role_revisions = sa.Table(
    "role_revisions",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "role_template_id",
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


def _async_url(settings: ControlPlaneSettings) -> str:
    return (
        f"postgresql+asyncpg://{settings.user}:{settings.password}"
        f"@{settings.host}:{settings.port}/{settings.db}"
    )


class RolePostgresRepository:
    """Adapter implementation of ``RoleRepositoryPort`` (D86)."""

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
    ) -> "RolePostgresRepository":
        engine = create_async_engine(_async_url(settings), pool_pre_ping=True)
        return cls(engine=engine, security_events=security_events)

    async def dispose(self) -> None:
        await self._engine.dispose()

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def create_template(
        self,
        template: RoleTemplate,
        initial_revision: RoleRevision,
    ) -> RoleTemplate:
        async with self._sessionmaker() as session:
            await session.execute(
                sa.insert(role_templates).values(
                    id=str(template.id),
                    name=template.name,
                    description=template.description,
                    created_by_user_id=template.created_by_user_id,
                    created_at=template.created_at,
                    archived_at=template.archived_at,
                )
            )
            await session.execute(
                sa.insert(role_revisions).values(
                    **_revision_insert_values(initial_revision)
                )
            )
            await session.commit()

        self._emit_privileged(
            action="role.create_template",
            resource_ref=f"role_template:{template.id}",
        )
        return template

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[RoleTemplate, RoleRevision]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                sa.select(role_templates).where(
                    role_templates.c.id == str(template_id)
                )
            )
            template_row = result.mappings().first()
            if template_row is None:
                raise LookupError(f"role template {template_id} not found")

            if version is None:
                stmt = (
                    sa.select(role_revisions)
                    .where(
                        role_revisions.c.role_template_id == str(template_id)
                    )
                    .order_by(role_revisions.c.version.desc())
                    .limit(1)
                )
            else:
                stmt = sa.select(role_revisions).where(
                    sa.and_(
                        role_revisions.c.role_template_id == str(template_id),
                        role_revisions.c.version == version,
                    )
                )

            rev_result = await session.execute(stmt)
            rev_row = rev_result.mappings().first()
            if rev_row is None:
                raise LookupError(
                    f"role revision for template {template_id} "
                    f"version {version} not found"
                )

        return _row_to_template(template_row), _row_to_revision(rev_row)

    async def list_templates(self) -> list[RoleTemplate]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                sa.select(role_templates)
                .where(role_templates.c.archived_at.is_(None))
                .order_by(role_templates.c.created_at)
            )
            rows = result.mappings().all()
        return [_row_to_template(r) for r in rows]

    async def add_revision(
        self,
        template_id: UUID,
        revision: RoleRevision,
    ) -> RoleRevision:
        async with self._sessionmaker() as session:
            await session.execute(
                sa.insert(role_revisions).values(
                    **_revision_insert_values(revision)
                )
            )
            await session.commit()

        self._emit_privileged(
            action="role.add_revision",
            resource_ref=f"role_revision:{revision.id}",
        )
        return revision

    async def archive_template(
        self,
        template_id: UUID,
    ) -> RoleTemplate:
        archived_at = datetime.now(timezone.utc)
        async with self._sessionmaker() as session:
            existing = await session.execute(
                sa.select(role_templates).where(
                    role_templates.c.id == str(template_id)
                )
            )
            row = existing.mappings().first()
            if row is None:
                raise LookupError(f"role template {template_id} not found")

            await session.execute(
                sa.update(role_templates)
                .where(role_templates.c.id == str(template_id))
                .values(archived_at=archived_at)
            )
            await session.commit()

            after = await session.execute(
                sa.select(role_templates).where(
                    role_templates.c.id == str(template_id)
                )
            )
            after_row = after.mappings().first()

        template = _row_to_template(after_row)
        self._emit_privileged(
            action="role.archive_template",
            resource_ref=f"role_template:{template.id}",
        )
        return template

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _emit_privileged(self, *, action: str, resource_ref: str) -> None:
        self._security_events.emit(
            SecurityEvent(
                category=SecurityEventCategory.PRIVILEGED_ACTION,
                principal_ref="system:role_repository",
                tenant_id=None,
                action=action,
                resource_ref=resource_ref,
                outcome="allow",
            )
        )


def _revision_insert_values(rev: RoleRevision) -> dict:
    return {
        "id": str(rev.id),
        "role_template_id": str(rev.role_template_id),
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


def _row_to_template(row) -> RoleTemplate:
    return RoleTemplate(
        id=UUID(row["id"]),
        name=row["name"],
        description=row["description"],
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        archived_at=row["archived_at"],
    )


def _row_to_revision(row) -> RoleRevision:
    return RoleRevision(
        id=UUID(row["id"]),
        role_template_id=UUID(row["role_template_id"]),
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
