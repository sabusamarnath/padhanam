"""SQLAlchemy Core table definition for the messaging per-tenant table.

One table per D129 — ``messages`` (the Message aggregate root).
Migration ``alembic/tenant/versions/0019_messaging_substrate`` ships
the table on every per-tenant database; the definition here must
stay in lockstep with that migration.

SQLAlchemy 2.0 Core — no DeclarativeBase, no ORM, mirroring the
intake precedent. CHECK constraints and the ``intake_id`` foreign
key live in the migration; this definition carries columns and
indexes for query building.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()


messages = sa.Table(
    "messages",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("direction", sa.Text, nullable=False),
    sa.Column("channel", sa.Text, nullable=False),
    sa.Column("body", sa.Text, nullable=False),
    sa.Column("from_address", sa.Text, nullable=False),
    sa.Column("to_address", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("external_id", sa.Text, nullable=True),
    sa.Column("intake_id", pg.UUID(as_uuid=False), nullable=True),
    sa.Column("actor_id", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Index("ix_messages_tenant_created_at", "tenant_id", "created_at"),
    sa.Index(
        "ix_messages_tenant_direction_channel",
        "tenant_id",
        "direction",
        "channel",
    ),
)


__all__ = ["messages", "metadata"]
