"""SQLAlchemy Core table definitions for the retrieval_evaluation per-tenant tables.

Six tables across two substrate sessions:

S39 / D109 — gold-set authoring:
  - ``gold_sets`` (aggregate root)
  - ``gold_set_revisions`` (append-only revision rows)
  - ``gold_set_entries`` (ordered (query, expected_chunk_ids) pairs)
  Migration: ``alembic/tenant/versions/0013_retrieval_eval_substrate``.

S40 / D110 — runner substrate:
  - ``evaluation_runs`` (aggregate root with status lifecycle)
  - ``evaluation_results`` (per-query-per-strategy result rows;
    append-only)
  - ``evaluation_aggregates`` (per-strategy summary rows; append-only)
  Migration: ``alembic/tenant/versions/0014_eval_runner_substrate``.

Shared between the repository (writer) and reader adapters; both
consume the same Table objects to keep the row-shape contract
single-sourced.

SQLAlchemy 2.0 Core — no DeclarativeBase, no ORM, per the
run_history precedent at S31.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


metadata = sa.MetaData()


gold_sets = sa.Table(
    "gold_sets",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("current_revision_id", pg.UUID(as_uuid=False), nullable=True),
    sa.UniqueConstraint(
        "tenant_id", "name", name="gold_sets_tenant_name_unique"
    ),
)


gold_set_revisions = sa.Table(
    "gold_set_revisions",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "gold_set_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("gold_sets.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("revision_number", sa.Integer, nullable=False),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("created_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "created_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("finalized_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("this_event_hash", sa.Text, nullable=True),
    sa.Column("previous_event_hash", sa.Text, nullable=True),
    sa.UniqueConstraint(
        "gold_set_id",
        "revision_number",
        name="gold_set_revisions_gold_set_revision_unique",
    ),
    sa.CheckConstraint(
        "status IN ('draft', 'finalized')",
        name="gold_set_revisions_status_check",
    ),
)


gold_set_entries = sa.Table(
    "gold_set_entries",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "gold_set_revision_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("gold_set_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("entry_index", sa.Integer, nullable=False),
    sa.Column("query", sa.Text, nullable=False),
    sa.Column(
        "expected_chunk_ids",
        pg.ARRAY(pg.UUID(as_uuid=False)),
        nullable=False,
    ),
    sa.UniqueConstraint(
        "gold_set_revision_id",
        "entry_index",
        name="gold_set_entries_revision_entry_unique",
    ),
)


evaluation_runs = sa.Table(
    "evaluation_runs",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column(
        "gold_set_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("gold_sets.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "gold_set_revision_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("gold_set_revisions.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("invoked_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "invoked_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("status", sa.Text, nullable=False),
    sa.CheckConstraint(
        "status IN ('running', 'completed', 'failed')",
        name="evaluation_runs_status_check",
    ),
)


evaluation_results = sa.Table(
    "evaluation_results",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "evaluation_run_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column(
        "gold_set_entry_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("gold_set_entries.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("retrieval_strategy", sa.Text, nullable=False),
    sa.Column(
        "returned_chunk_ids",
        pg.ARRAY(pg.UUID(as_uuid=False)),
        nullable=False,
    ),
    sa.Column("recall_at_k", pg.JSONB, nullable=False),
    sa.Column("precision_at_k", pg.JSONB, nullable=False),
    sa.Column("mrr", sa.Numeric(6, 4), nullable=False),
    sa.Column("latency_ms", sa.Integer, nullable=False),
    sa.UniqueConstraint(
        "evaluation_run_id",
        "gold_set_entry_id",
        "retrieval_strategy",
        name="evaluation_results_run_entry_strategy_unique",
    ),
)


evaluation_aggregates = sa.Table(
    "evaluation_aggregates",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "evaluation_run_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"),
        nullable=False,
    ),
    sa.Column("retrieval_strategy", sa.Text, nullable=False),
    sa.Column("recall_at_k_mean", pg.JSONB, nullable=False),
    sa.Column("precision_at_k_mean", pg.JSONB, nullable=False),
    sa.Column("mrr_mean", sa.Numeric(6, 4), nullable=False),
    sa.Column("latency_ms_p50", sa.Integer, nullable=False),
    sa.Column("latency_ms_p95", sa.Integer, nullable=False),
    sa.Column("latency_ms_mean", sa.Integer, nullable=False),
    sa.UniqueConstraint(
        "evaluation_run_id",
        "retrieval_strategy",
        name="evaluation_aggregates_run_strategy_unique",
    ),
)


__all__ = [
    "evaluation_aggregates",
    "evaluation_results",
    "evaluation_runs",
    "gold_set_entries",
    "gold_set_revisions",
    "gold_sets",
    "metadata",
]
