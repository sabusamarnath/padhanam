"""SQLAlchemy Core table for the matcher_evaluation per-tenant table (D185).

One table, ``matcher_quality_runs`` — one row per matcher measurement. The six
counts are the source of truth; the three rates are stored alongside for direct
query (they are derived, but persisting them keeps the read trivial and the
trend queryable without recomputation). **Counts and rates only** — no title,
sender, subject, unit id, or any content reaches this row (D185, the no-content
guarantee).

Migration: ``alembic/tenant/versions/2026_06_12_0034_matcher_quality_runs``.

Shared between the repository (writer) and reader adapters so the row-shape
contract is single-sourced. SQLAlchemy 2.0 Core — no ORM, per the
``retrieval_evaluation`` / ``run_history`` precedent.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg

metadata = sa.MetaData()


matcher_quality_runs = sa.Table(
    "matcher_quality_runs",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column(
        "computed_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    # Counts — the source of truth.
    sa.Column("edge_count", sa.Integer, nullable=False),
    sa.Column("unit_count", sa.Integer, nullable=False),
    sa.Column("orphan_count", sa.Integer, nullable=False),
    sa.Column("single_signal_count", sa.Integer, nullable=False),
    sa.Column("candidate_count", sa.Integer, nullable=False),
    sa.Column("confirmed_count", sa.Integer, nullable=False),
    # Rates — derived, persisted for direct query.
    sa.Column("single_signal_share", sa.Float, nullable=False),
    sa.Column("candidate_to_confirmed_ratio", sa.Float, nullable=False),
    sa.Column("orphan_rate", sa.Float, nullable=False),
    sa.Index("ix_matcher_quality_runs_tenant_time", "tenant_id", "computed_at"),
)


__all__ = ["matcher_quality_runs", "metadata"]
