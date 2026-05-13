"""Postgres adapter for the run-history repository port (D95, S31 commit 4).

Implements ``RunHistoryRepositoryPort`` against per-tenant Postgres
data planes per D32 / D34 / D36. SQLAlchemy 2.0 Core (Table + insert
via AsyncSession), manual record-to-row conversion; no
DeclarativeBase, no ORM. Mirrors the agent context's adapter shape
at ``contexts/agent/adapters/outbound/postgres/repository.py``.

Per-tenant session-factory resolution flows through a callable
injected at construction: ``per_tenant_sessionmaker_resolver``
takes a ``TenantId`` and returns the tenant's
``async_sessionmaker``. The wiring layer at
``apps/cli/_cross_context.py`` (``RunHistoryWriterAdapter``, S31
commit 5) supplies the resolver bound to the runtime's
``tenant_context``; ``apps/api/_agent_runtime_wiring.py`` uses the
tenancy context's session-factory cache per the S30b cross-app
re-use pattern.

At S31 the adapter writes runs rows only — citation tables exist
but the citation-row persistence shape lands at S32. The
``persist`` method opens a per-call session, executes a single
INSERT into ``runs``, and commits. Tenant defence-in-depth: the
adapter verifies the record's ``tenant_id`` matches the bound
tenant's id before insert; mismatch raises ``ValueError`` so a
mis-routed call cannot land a row on the wrong tenant's
database (D24 / D32).
"""

from __future__ import annotations

from typing import Protocol

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.run_history.domain.run_record import RunRecord
from shared_kernel import TenantId


_metadata = sa.MetaData()


runs = sa.Table(
    "runs",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column(
        "agent_template_id", pg.UUID(as_uuid=False), nullable=False
    ),
    sa.Column("agent_template_version", sa.Integer, nullable=False),
    sa.Column("input_message", sa.Text, nullable=False),
    sa.Column("output_content", sa.Text, nullable=False),
    sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=False),
    sa.Column("termination_reason", sa.Text, nullable=False),
    sa.Column("iteration_count", sa.Integer, nullable=False),
    sa.Column("total_cost_usd", sa.Numeric, nullable=False),
    sa.Column("trace_id", sa.Text, nullable=True),
    sa.Column("audit_start_hash", sa.Text, nullable=False),
    sa.Column("audit_end_hash", sa.Text, nullable=True),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
)


run_chunk_citations = sa.Table(
    "run_chunk_citations",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("run_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("chunk_id", pg.UUID(as_uuid=False), nullable=True),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("chunk_excerpt", sa.Text, nullable=False),
    sa.Column("source_citation", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
)


run_entity_citations = sa.Table(
    "run_entity_citations",
    _metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("run_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("entity_tenant_id", sa.Text, nullable=False),
    sa.Column("entity_name", sa.Text, nullable=False),
    sa.Column("entity_type", sa.Text, nullable=False),
    sa.Column("tenant_id", sa.Text, nullable=False),
    sa.Column("entity_display_label", sa.Text, nullable=False),
    sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
)


class _SessionFactoryResolver(Protocol):
    """Resolver shape: given a ``TenantId``, return the per-tenant
    ``async_sessionmaker``. The wiring layer binds this; the
    adapter is opaque to the resolver implementation."""

    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresRunHistoryAdapter:
    """Adapter implementation of ``RunHistoryRepositoryPort`` (D95).

    Constructor takes the per-tenant session-factory resolver and
    a bound tenant_id; ``persist`` validates the record's tenant_id
    against the bound tenant before insert. The validation is
    defence-in-depth alongside D32's per-tenant database routing.
    """

    def __init__(
        self,
        *,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
        bound_tenant_id: TenantId,
    ) -> None:
        self._resolve_per_tenant = per_tenant_sessionmaker_resolver
        self._bound_tenant_id = bound_tenant_id

    async def persist(self, record: RunRecord) -> None:
        if record.tenant_id != str(self._bound_tenant_id):
            raise ValueError(
                f"RunRecord.tenant_id={record.tenant_id!r} does not match "
                f"adapter's bound tenant {self._bound_tenant_id!r}; "
                "tenant-isolation defence-in-depth per D24 / D32"
            )

        sessionmaker = await self._resolve_per_tenant(self._bound_tenant_id)
        async with sessionmaker() as session:
            await session.execute(
                sa.insert(runs).values(
                    id=str(record.id),
                    tenant_id=record.tenant_id,
                    jurisdiction=record.jurisdiction,
                    agent_template_id=str(record.agent_template_id),
                    agent_template_version=record.agent_template_version,
                    input_message=record.input_message,
                    output_content=record.output_content,
                    started_at=record.started_at,
                    completed_at=record.completed_at,
                    termination_reason=record.termination_reason,
                    iteration_count=record.iteration_count,
                    total_cost_usd=record.total_cost_usd,
                    trace_id=record.trace_id,
                    audit_start_hash=record.audit_start_hash,
                    audit_end_hash=record.audit_end_hash,
                    created_at=record.created_at,
                )
            )
            await session.commit()
