"""Methodology Postgres adapter (D74).

Implements ``MethodologyRepositoryPort`` against the control-plane
Postgres instance per D33. SQLAlchemy 2.0 Core (Table + select / insert
/ update via AsyncConnection.execute), manual row-to-domain conversion;
no DeclarativeBase, no ORM. Mirrors the tenancy registry adapter shape
at ``contexts/tenancy/adapters/outbound/postgres/registry.py`` per D34.

Privileged actions (``create_template``, ``add_revision``,
``archive_template``) emit security events with
``category=privileged_action``. Read methods (``get_template``,
``list_templates``) do not emit; the use case layer at S23 commit 8
gates write paths with operator-context auth and emits authz_denial
events on rejection.

Per D74, the port carries no ``TenantContext`` parameter; the
methodology data is structurally control-plane-scoped, so the
adapter holds only the engine and session factory plus the security-
event sink.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from contexts.methodology.domain.methodology import (
    MethodologyRevision,
    MethodologyTemplate,
    RoleRef,
)
from padhanam.config import ControlPlaneSettings
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)


_metadata = sa.MetaData()


methodology_templates = sa.Table(
    "methodology_templates",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("description", sa.Text, nullable=True),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
)


methodology_revisions = sa.Table(
    "methodology_revisions",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "methodology_template_id",
        pg.UUID(as_uuid=False),
        nullable=False,
    ),
    sa.Column("version", sa.Integer, nullable=False),
    sa.Column("role_refs", pg.JSONB, nullable=False),
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


class MethodologyPostgresRepository:
    """Adapter implementation of ``MethodologyRepositoryPort`` (D74)."""

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
    ) -> "MethodologyPostgresRepository":
        engine = create_async_engine(_async_url(settings), pool_pre_ping=True)
        return cls(engine=engine, security_events=security_events)

    async def dispose(self) -> None:
        await self._engine.dispose()

    # ------------------------------------------------------------------
    # Port implementation
    # ------------------------------------------------------------------

    async def create_template(
        self,
        template: MethodologyTemplate,
        initial_revision: MethodologyRevision,
    ) -> MethodologyTemplate:
        async with self._sessionmaker() as session:
            await session.execute(
                sa.insert(methodology_templates).values(
                    id=str(template.id),
                    name=template.name,
                    description=template.description,
                    created_by_user_id=template.created_by_user_id,
                    created_at=template.created_at,
                    archived_at=template.archived_at,
                )
            )
            await session.execute(
                sa.insert(methodology_revisions).values(
                    **_revision_insert_values(initial_revision)
                )
            )
            await session.commit()

        self._emit_privileged(
            action="methodology.create_template",
            resource_ref=f"methodology_template:{template.id}",
        )
        return template

    async def get_template(
        self,
        template_id: UUID,
        version: int | None = None,
    ) -> tuple[MethodologyTemplate, MethodologyRevision]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                sa.select(methodology_templates).where(
                    methodology_templates.c.id == str(template_id)
                )
            )
            template_row = result.mappings().first()
            if template_row is None:
                raise LookupError(f"methodology template {template_id} not found")

            if version is None:
                stmt = (
                    sa.select(methodology_revisions)
                    .where(
                        methodology_revisions.c.methodology_template_id
                        == str(template_id)
                    )
                    .order_by(methodology_revisions.c.version.desc())
                    .limit(1)
                )
            else:
                stmt = sa.select(methodology_revisions).where(
                    sa.and_(
                        methodology_revisions.c.methodology_template_id
                        == str(template_id),
                        methodology_revisions.c.version == version,
                    )
                )

            rev_result = await session.execute(stmt)
            rev_row = rev_result.mappings().first()
            if rev_row is None:
                raise LookupError(
                    f"methodology revision for template {template_id} "
                    f"version {version} not found"
                )

        return _row_to_template(template_row), _row_to_revision(rev_row)

    async def list_templates(self) -> list[MethodologyTemplate]:
        async with self._sessionmaker() as session:
            result = await session.execute(
                sa.select(methodology_templates)
                .where(methodology_templates.c.archived_at.is_(None))
                .order_by(methodology_templates.c.created_at)
            )
            rows = result.mappings().all()
        return [_row_to_template(r) for r in rows]

    async def add_revision(
        self,
        template_id: UUID,
        revision: MethodologyRevision,
    ) -> MethodologyRevision:
        async with self._sessionmaker() as session:
            await session.execute(
                sa.insert(methodology_revisions).values(
                    **_revision_insert_values(revision)
                )
            )
            await session.commit()

        self._emit_privileged(
            action="methodology.add_revision",
            resource_ref=f"methodology_revision:{revision.id}",
        )
        return revision

    async def archive_template(
        self,
        template_id: UUID,
    ) -> MethodologyTemplate:
        archived_at = datetime.now(timezone.utc)
        async with self._sessionmaker() as session:
            existing = await session.execute(
                sa.select(methodology_templates).where(
                    methodology_templates.c.id == str(template_id)
                )
            )
            row = existing.mappings().first()
            if row is None:
                raise LookupError(f"methodology template {template_id} not found")

            await session.execute(
                sa.update(methodology_templates)
                .where(methodology_templates.c.id == str(template_id))
                .values(archived_at=archived_at)
            )
            await session.commit()

            after = await session.execute(
                sa.select(methodology_templates).where(
                    methodology_templates.c.id == str(template_id)
                )
            )
            after_row = after.mappings().first()

        template = _row_to_template(after_row)
        self._emit_privileged(
            action="methodology.archive_template",
            resource_ref=f"methodology_template:{template.id}",
        )
        return template

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _emit_privileged(self, *, action: str, resource_ref: str) -> None:
        self._security_events.emit(
            SecurityEvent(
                category=SecurityEventCategory.PRIVILEGED_ACTION,
                principal_ref="system:methodology_repository",
                tenant_id=None,
                action=action,
                resource_ref=resource_ref,
                outcome="allow",
            )
        )


def _revision_insert_values(rev: MethodologyRevision) -> dict:
    return {
        "id": str(rev.id),
        "methodology_template_id": str(rev.methodology_template_id),
        "version": rev.version,
        "role_refs": [
            {
                "role_id": str(r.role_id),
                "role_version": r.role_version,
                "overrides": (
                    None if r.overrides is None else dict(r.overrides)
                ),
            }
            for r in rev.role_refs
        ],
        "created_by_user_id": rev.created_by_user_id,
        "created_at": rev.created_at,
        "previous_revision_hash": rev.previous_revision_hash,
        "this_revision_hash": rev.this_revision_hash,
    }


def _row_to_template(row) -> MethodologyTemplate:
    return MethodologyTemplate(
        id=UUID(row["id"]),
        name=row["name"],
        description=row["description"],
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        archived_at=row["archived_at"],
    )


def _row_to_revision(row) -> MethodologyRevision:
    return MethodologyRevision(
        id=UUID(row["id"]),
        methodology_template_id=UUID(row["methodology_template_id"]),
        version=row["version"],
        role_refs=tuple(
            RoleRef(
                role_id=UUID(r["role_id"]),
                role_version=r["role_version"],
                overrides=r.get("overrides"),
            )
            for r in row["role_refs"]
        ),
        created_by_user_id=row["created_by_user_id"],
        created_at=row["created_at"],
        previous_revision_hash=row["previous_revision_hash"],
        this_revision_hash=row["this_revision_hash"],
    )
