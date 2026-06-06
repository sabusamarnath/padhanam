"""SQLAlchemy Core table definitions for the daily-driver per-tenant tables.

Three tables per D157 — ``commitments`` (the user-authored cadence),
``commitment_completions`` (the append-only completion log), and
``day_item_states`` (the minimal Day concept: per-day ordering and
done-for-today marks). Migration
``alembic/tenant/versions/0028_daily_driver_substrate`` ships these on
every per-tenant database; the definitions here must stay in lockstep
with that migration.

SQLAlchemy 2.0 Core — no DeclarativeBase, no ORM, mirroring the
portfolio precedent. Every table carries ``tenant_id`` and
``jurisdiction`` per D12. Overdue/status are never stored (D157): the
``day_item_states`` table holds only ``position`` and ``done``.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()


commitments = sa.Table(
    "commitments",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("expected_interval_days", sa.Integer, nullable=False),
    sa.Column("authored_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    # S61 (D162): the minimal expected-versus-observed loop. Free text to
    # keep capture near-frictionless; outcome_status nullable until an
    # observation is recorded. These are record-level fields, not
    # completion-log rows. Migration 0029 ALTERs this table to add them.
    sa.Column("expected_outcome", sa.Text, nullable=True),
    sa.Column("observed_outcome", sa.Text, nullable=True),
    sa.Column("outcome_status", sa.Text, nullable=True),
    sa.Column("observed_at", sa.TIMESTAMP(timezone=True), nullable=True),
)


commitment_completions = sa.Table(
    "commitment_completions",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "commitment_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("commitments.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column(
        "completed_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
)


day_item_states = sa.Table(
    "day_item_states",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("user_id", sa.Text, nullable=False),
    sa.Column("day_date", sa.Date, nullable=False),
    sa.Column("item_kind", sa.Text, nullable=False),
    sa.Column("item_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("position", sa.Integer, nullable=True),
    sa.Column(
        "done", sa.Boolean, nullable=False, server_default=sa.text("false")
    ),
    sa.Column(
        "updated_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.UniqueConstraint(
        "tenant_id",
        "user_id",
        "day_date",
        "item_kind",
        "item_id",
        name="ux_day_item_states_tenant_user_day_item",
    ),
)


__all__ = ["commitment_completions", "commitments", "day_item_states"]
