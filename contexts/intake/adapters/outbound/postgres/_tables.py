"""SQLAlchemy Core table definition for the intake per-tenant table.

One table per D127 — ``intakes`` (the IntakeRecord aggregate root).
Migration ``alembic/tenant/versions/0017_intake_substrate`` ships
the table on every per-tenant database; the definition here must
stay in lockstep with that migration.

SQLAlchemy 2.0 Core — no DeclarativeBase, no ORM, mirroring the
portfolio precedent.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()


intakes = sa.Table(
    "intakes",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("intake_source", sa.Text, nullable=False),
    sa.Column("payload", pg.JSONB, nullable=False),
    sa.Column("authored_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Index("ix_intakes_tenant_created_at", "tenant_id", "created_at"),
    sa.Index("ix_intakes_tenant_source", "tenant_id", "intake_source"),
)


__all__ = ["intakes", "metadata"]
