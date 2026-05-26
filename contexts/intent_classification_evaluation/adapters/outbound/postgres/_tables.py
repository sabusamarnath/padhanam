"""SQLAlchemy Core table definitions for intent-classification evaluation (D137).

Three tables per the Option B simplification at S48b — gold sets
live in a YAML fixture in the repo, not in per-tenant tables (the
revision-lifecycle gold-set authoring defers to the multi-tenant-
gold-set trigger):

- ``intent_class_evaluation_runs`` (aggregate root with status
  lifecycle)
- ``intent_class_evaluation_results`` (per-entry result rows;
  append-only)
- ``intent_class_evaluation_aggregates`` (per-intent-class summary
  rows; append-only)

Migration: ``alembic/tenant/versions/0022_intent_class_eval_substrate``.

SQLAlchemy 2.0 Core — no DeclarativeBase, no ORM, per the
retrieval-evaluation precedent at S40.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


metadata = sa.MetaData()


intent_class_evaluation_runs = sa.Table(
    "intent_class_evaluation_runs",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
    sa.Column("jurisdiction", sa.Text, nullable=False),
    sa.Column("gold_set_name", sa.Text, nullable=False),
    sa.Column("model_provider", sa.Text, nullable=False),
    sa.Column("model_account", sa.Text, nullable=False),
    sa.Column("model_version", sa.Text, nullable=False),
    sa.Column("latency_tier", sa.Text, nullable=False),
    sa.Column("invoked_by_user_id", sa.Text, nullable=False),
    sa.Column(
        "started_at",
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    ),
    sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column("status", sa.Text, nullable=False),
    sa.Column("failure_reason", sa.Text, nullable=True),
    sa.CheckConstraint(
        "status IN ('running', 'completed', 'failed')",
        name="intent_class_eval_runs_status_check",
    ),
    sa.CheckConstraint(
        "(status = 'running' AND completed_at IS NULL AND failure_reason IS NULL)"
        " OR (status = 'completed' AND completed_at IS NOT NULL AND failure_reason IS NULL)"
        " OR (status = 'failed' AND completed_at IS NOT NULL AND failure_reason IS NOT NULL)",
        name="intent_class_eval_runs_terminal_state_check",
    ),
)


intent_class_evaluation_results = sa.Table(
    "intent_class_evaluation_results",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "evaluation_run_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey(
            "intent_class_evaluation_runs.id", ondelete="RESTRICT"
        ),
        nullable=False,
    ),
    sa.Column("entry_index", sa.Integer, nullable=False),
    sa.Column("input_phrasing", sa.Text, nullable=False),
    sa.Column("expected_intent_class", sa.Text, nullable=False),
    sa.Column("classified_intent_class", sa.Text, nullable=False),
    sa.Column("confidence", sa.Numeric(6, 4), nullable=True),
    sa.Column("latency_ms", sa.Integer, nullable=False),
    sa.Column("parse_failure", sa.Boolean, nullable=False),
    sa.Column("is_correct", sa.Boolean, nullable=False),
    sa.UniqueConstraint(
        "evaluation_run_id",
        "entry_index",
        name="intent_class_eval_results_run_entry_unique",
    ),
)


intent_class_evaluation_aggregates = sa.Table(
    "intent_class_evaluation_aggregates",
    metadata,
    sa.Column("id", pg.UUID(as_uuid=False), primary_key=True),
    sa.Column(
        "evaluation_run_id",
        pg.UUID(as_uuid=False),
        sa.ForeignKey(
            "intent_class_evaluation_runs.id", ondelete="RESTRICT"
        ),
        nullable=False,
    ),
    sa.Column("intent_class", sa.Text, nullable=False),
    sa.Column("support", sa.Integer, nullable=False),
    sa.Column("correct_count", sa.Integer, nullable=False),
    sa.Column("parse_failure_count", sa.Integer, nullable=False),
    sa.Column("accuracy", sa.Numeric(6, 4), nullable=False),
    sa.Column("recall", sa.Numeric(6, 4), nullable=False),
    sa.Column("precision", sa.Numeric(6, 4), nullable=False),
    sa.UniqueConstraint(
        "evaluation_run_id",
        "intent_class",
        name="intent_class_eval_aggs_run_class_unique",
    ),
)


__all__ = [
    "intent_class_evaluation_aggregates",
    "intent_class_evaluation_results",
    "intent_class_evaluation_runs",
    "metadata",
]
