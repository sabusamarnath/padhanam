"""SQLAlchemy Core table definitions for optimization per-tenant tables.

Three tables per D111 commitments 2, 3, 4:

- ``optimization_runs`` (aggregate root; status lifecycle plus
  ``skipped_categories`` JSONB).
- ``recommendations`` (single-aggregate-with-category-discriminator;
  append-only content; mutable status).
- ``recommendation_status_transitions`` (append-only audit table
  for status history).

Migration: ``alembic/tenant/versions/0015_optimization_substrate``
ships these tables on every per-tenant database.

SQLAlchemy 2.0 Core — no DeclarativeBase, no ORM, mirroring the
retrieval_evaluation and run_history precedents.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


metadata = sa.MetaData()


optimization_runs = sa.Table(
    "optimization_runs",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("invoked_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "invoked_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column(
        "skipped_categories",
        pg.JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
    ),
    sa.CheckConstraint(
        "status IN ('running', 'completed', 'failed')",
        name="optimization_runs_status_check",
    ),
    sa.CheckConstraint(
        "jurisdiction <> ''",
        name="optimization_runs_jurisdiction_nonempty",
    ),
)


recommendations = sa.Table(
    "recommendations",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("category", sa.Text, nullable=False),
    sa.Column("subject", sa.Text, nullable=False),
    sa.Column("text", sa.Text, nullable=False),
    sa.Column("evidence_citations", pg.JSONB, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column(
        "generated_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column(
        "generated_by_run_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("optimization_runs.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "last_transition_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("last_transition_by_user_id", sa.Text, nullable=True),
    sa.CheckConstraint(
        "category IN ('retrieval_strategy', 'model_choice', "
        "'prompt_revision', 'cost_optimization', 'matcher_suppression')",
        name="recommendations_category_check",
    ),
    sa.CheckConstraint(
        "status IN ('generated', 'acknowledged', 'applied', 'rejected')",
        name="recommendations_status_check",
    ),
    sa.CheckConstraint(
        "jurisdiction <> ''",
        name="recommendations_jurisdiction_nonempty",
    ),
    sa.Index(
        "recommendations_tenant_status_category_idx",
        "tenant_id",
        "status",
        "category",
    ),
)


recommendation_status_transitions = sa.Table(
    "recommendation_status_transitions",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "recommendation_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("recommendations.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("from_status", sa.Text, nullable=False),
    sa.Column("to_status", sa.Text, nullable=False),
    sa.Column("transitioned_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "transitioned_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Index(
        "recommendation_status_transitions_recommendation_idx",
        "recommendation_id",
        "transitioned_at",
    ),
)


__all__ = [
    "metadata",
    "optimization_runs",
    "recommendation_status_transitions",
    "recommendations",
]
