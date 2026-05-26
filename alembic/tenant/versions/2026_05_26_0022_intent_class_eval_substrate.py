"""create intent-classification evaluation substrate (D137, S48b)

Revision ID: 0022_intent_class_eval_substrate
Revises: 0021_pending_clarification
Create Date: 2026-05-26

Per-tenant substrate for intent-classification evaluation runs per
D137 / Option B. Three tables on each tenant's dedicated Postgres
data plane per D32:

- ``intent_class_evaluation_runs``: aggregate root with status
  lifecycle (running, completed, failed). CHECK constraints pin
  ``status`` and enforce the terminal-state shape (running ->
  completed_at NULL plus failure_reason NULL; completed ->
  completed_at NOT NULL plus failure_reason NULL; failed -> both
  NOT NULL). model_provider/model_account/model_version capture the
  D132 four-layer ontology for audit-trail dimension.

- ``intent_class_evaluation_results``: per-entry result rows;
  append-only. UNIQUE on (run_id, entry_index) prevents accidental
  re-classification within a run.

- ``intent_class_evaluation_aggregates``: per-intent-class summary
  rows; append-only. UNIQUE on (run_id, intent_class) prevents
  accidental double-aggregation.

The gold-set lives in the YAML fixture at
``tests/fixtures/intent_classification/gold_set.yaml`` at S48b per
Option B; the revision-lifecycle gold-set tables defer to the
multi-tenant-gold-set-authoring trigger per D137 alternative (c).

Every table carries ``tenant_id`` and ``jurisdiction`` per D12. The
revision string fits the 32-char alembic ceiling exactly (32 chars).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0022_intent_class_eval_substrate"
down_revision: Union[str, None] = "0021_pending_clarification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "intent_class_evaluation_runs",
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
    op.create_index(
        "ix_intent_class_eval_runs_started_at",
        "intent_class_evaluation_runs",
        ["started_at"],
    )

    op.create_table(
        "intent_class_evaluation_results",
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
    op.create_index(
        "ix_intent_class_eval_results_run",
        "intent_class_evaluation_results",
        ["evaluation_run_id"],
    )

    op.create_table(
        "intent_class_evaluation_aggregates",
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


def downgrade() -> None:
    op.drop_table("intent_class_evaluation_aggregates")
    op.drop_index(
        "ix_intent_class_eval_results_run",
        table_name="intent_class_evaluation_results",
    )
    op.drop_table("intent_class_evaluation_results")
    op.drop_index(
        "ix_intent_class_eval_runs_started_at",
        table_name="intent_class_evaluation_runs",
    )
    op.drop_table("intent_class_evaluation_runs")
