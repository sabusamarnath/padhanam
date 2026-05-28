"""SQLAlchemy Core table definitions for the messaging per-tenant tables.

Three tables — ``messages`` (the Message aggregate root per D129),
``pending_clarifications`` (the multi-turn conversation state per
D134, S47), and ``fired_triggers`` (the broadcast idempotency
substrate per D147, S54). Migrations
``alembic/tenant/versions/0019_messaging_substrate``,
``0021_pending_clarifications``, and ``0025_fired_triggers`` ship the
tables on every per-tenant database; the definitions here must stay
in lockstep with those migrations.

SQLAlchemy 2.0 Core — no DeclarativeBase, no ORM, mirroring the
intake precedent. CHECK constraints, the ``intake_id`` foreign key,
the PENDING-status partial unique index, and the fired_triggers
UNIQUE constraint live in the migrations; these definitions carry
columns and indexes for query building.
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
    sa.Column("cell_payload", pg.JSONB, nullable=True),
    sa.Index("ix_messages_tenant_created_at", "tenant_id", "created_at"),
    sa.Index(
        "ix_messages_tenant_direction_channel",
        "tenant_id",
        "direction",
        "channel",
    ),
)


pending_clarifications = sa.Table(
    "pending_clarifications",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("user_id", sa.Text, nullable=False),
    sa.Column("originating_channel", sa.Text, nullable=False),
    sa.Column("originating_user_address", sa.Text, nullable=False),
    sa.Column(
        "originating_intake_id", pg.UUID(as_uuid=False), nullable=False
    ),
    sa.Column("proposed_intent", pg.JSONB, nullable=False),
    sa.Column("proposed_action_summary", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("target_cell", sa.Text, nullable=False),
    sa.Column(
        "created_at", sa.TIMESTAMP(timezone=True), nullable=False
    ),
    sa.Column(
        "expires_at", sa.TIMESTAMP(timezone=True), nullable=False
    ),
    sa.Column(
        "resolved_at", sa.TIMESTAMP(timezone=True), nullable=True
    ),
    sa.Index(
        "ix_pending_clarifications_tenant_user",
        "tenant_id",
        "user_id",
    ),
)


fired_triggers = sa.Table(
    "fired_triggers",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("user_id", sa.Text, nullable=False),
    sa.Column("trigger_type", sa.Text, nullable=False),
    sa.Column("idempotency_key", sa.Text, nullable=True),
    sa.Column(
        "fired_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Index(
        "ix_fired_triggers_tenant_user_type",
        "tenant_id",
        "user_id",
        "trigger_type",
    ),
)


__all__ = ["fired_triggers", "messages", "metadata", "pending_clarifications"]
