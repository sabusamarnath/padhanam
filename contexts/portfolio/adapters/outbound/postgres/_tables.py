"""SQLAlchemy Core table definitions for the portfolio per-tenant tables.

Three tables per D124 — ``cases`` (aggregate root), ``data_points``
(entity within the Case aggregate), ``assertions`` (append-only
revision unit). Migration
``alembic/tenant/versions/0016_portfolio_substrate`` ships these
tables on every per-tenant database; the definitions here must
stay in lockstep with that migration.

SQLAlchemy 2.0 Core — no DeclarativeBase, no ORM, mirroring the
optimization and retrieval_evaluation precedents.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()


cases = sa.Table(
    "cases",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("title", sa.Text, nullable=False),
    sa.Column("case_type", sa.Text, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column(
        "updated_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    # intake_id (D128, migration 0018): FK to intakes(id); the FK
    # constraint is enforced by the migration. The Core mirror omits
    # the ForeignKey object because `intakes` lives in the intake
    # context's separate MetaData.
    sa.Column("intake_id", pg.UUID(as_uuid=False), nullable=True),
    sa.Index("ix_cases_tenant_status", "tenant_id", "status"),
)


data_points = sa.Table(
    "data_points",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "case_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("data_point_type", sa.Text, nullable=False),
    sa.Column("value", pg.JSONB, nullable=False),
    sa.Column("authored_by_user_id", sa.Text, nullable=False),
    sa.Column("certainty", sa.Float, nullable=True),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Index("ix_data_points_case_id", "case_id"),
    sa.Index("ix_data_points_tenant_id", "tenant_id"),
)


assertions = sa.Table(
    "assertions",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "data_point_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("data_points.id", ondelete="CASCADE"),
        nullable=False,
    ),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("assertion_type", sa.Text, nullable=False),
    sa.Column(
        "revises_assertion_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("assertions.id", ondelete="RESTRICT"),
        nullable=True,
    ),
    sa.Column("value", pg.JSONB, nullable=False),
    sa.Column("authored_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    # intake_id (D128, migration 0018): FK to intakes(id), enforced
    # by the migration; the Core mirror omits the ForeignKey object.
    sa.Column("intake_id", pg.UUID(as_uuid=False), nullable=True),
    sa.Index(
        "ix_assertions_data_point_created_at", "data_point_id", "created_at"
    ),
)


__all__ = ["assertions", "cases", "data_points", "metadata"]
