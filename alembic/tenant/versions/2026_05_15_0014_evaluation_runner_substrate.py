"""create evaluation_runs, evaluation_results, evaluation_aggregates (D110)

Revision ID: 0014_eval_runner_substrate
Revises: 0013_retrieval_eval_substrate
Create Date: 2026-05-15

Per-tenant substrate for the retrieval-evaluation runner per D110.
Three tables on each tenant's dedicated Postgres data plane per D32:

- ``evaluation_runs``: aggregate root. ``status`` CHECK pins
  {'running', 'completed', 'failed'} per D110 commitment 2; the
  parent aggregate is mutable for status transitions while the child
  records are append-only.

- ``evaluation_results``: per-query-per-strategy result rows per D110
  commitment 3. ``UNIQUE(evaluation_run_id, gold_set_entry_id,
  retrieval_strategy)`` makes the (entry × strategy) cell unique
  inside one run; the runner orchestrator at S40 exercises every
  cell exactly once. JSONB columns ``recall_at_k`` and
  ``precision_at_k`` store the per-k metric maps with the k value as
  the JSON object key (string).

- ``evaluation_aggregates``: per-strategy summary rows per D110
  commitment 4. ``UNIQUE(evaluation_run_id, retrieval_strategy)``
  enforces one aggregate row per (run × executing strategy);
  rebuilding aggregates with a fresh run produces a new row, never
  overwrites.

No foreign key from ``returned_chunk_ids`` to ``chunks.id`` per the
gold-set precedent at migration 0013: chunk lifecycle is independent
of evaluation history; runner records are evidence captured at run
time and survive subsequent chunk mutations.

CHECK-constraint naming follows the ``0011_create_run_history`` /
``0013_retrieval_eval_substrate`` patterns
(``<table>_<column>_<description>_check``).
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0014_eval_runner_substrate"
down_revision: Union[str, None] = "0013_retrieval_eval_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STATUSES = ("running", "completed", "failed")


def upgrade() -> None:
    # --- evaluation_runs ---
    op.create_table(
        "evaluation_runs",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
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
        sa.Column("invoked_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "invoked_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "completed_at", sa.TIMESTAMP(timezone=True), nullable=True
        ),
        sa.Column("status", sa.Text(), nullable=False),
    )
    op.create_check_constraint(
        "evaluation_runs_jurisdiction_nonempty_check",
        "evaluation_runs",
        "jurisdiction <> ''",
    )
    op.create_check_constraint(
        "evaluation_runs_invoked_by_user_id_nonempty_check",
        "evaluation_runs",
        "invoked_by_user_id <> ''",
    )
    op.create_check_constraint(
        "evaluation_runs_status_check",
        "evaluation_runs",
        "status IN (" + ", ".join(f"'{v}'" for v in _STATUSES) + ")",
    )
    # Pairing CHECK: terminal-status rows carry completed_at;
    # 'running' rows carry NULL completed_at. The application-layer
    # invariants on EvaluationRun per D110 commitment 2 enforce the
    # same shape; defence-in-depth at the schema layer.
    op.create_check_constraint(
        "evaluation_runs_terminal_completed_pairing_check",
        "evaluation_runs",
        (
            "(status = 'running' AND completed_at IS NULL) "
            "OR (status <> 'running' AND completed_at IS NOT NULL)"
        ),
    )
    op.create_index(
        "ix_evaluation_runs_tenant_invoked_at",
        "evaluation_runs",
        ["tenant_id", sa.text("invoked_at DESC")],
    )
    op.create_index(
        "ix_evaluation_runs_gold_set_id",
        "evaluation_runs",
        ["gold_set_id"],
    )

    # --- evaluation_results ---
    op.create_table(
        "evaluation_results",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
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
        sa.Column("retrieval_strategy", sa.Text(), nullable=False),
        sa.Column(
            "returned_chunk_ids",
            pg.ARRAY(pg.UUID(as_uuid=False)),
            nullable=False,
        ),
        sa.Column("recall_at_k", pg.JSONB(), nullable=False),
        sa.Column("precision_at_k", pg.JSONB(), nullable=False),
        sa.Column("mrr", sa.Numeric(6, 4), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
    )
    op.create_check_constraint(
        "evaluation_results_retrieval_strategy_nonempty_check",
        "evaluation_results",
        "retrieval_strategy <> ''",
    )
    op.create_check_constraint(
        "evaluation_results_mrr_range_check",
        "evaluation_results",
        "mrr >= 0 AND mrr <= 1",
    )
    op.create_check_constraint(
        "evaluation_results_latency_ms_nonnegative_check",
        "evaluation_results",
        "latency_ms >= 0",
    )
    op.create_unique_constraint(
        "evaluation_results_run_entry_strategy_unique",
        "evaluation_results",
        ["evaluation_run_id", "gold_set_entry_id", "retrieval_strategy"],
    )
    op.create_index(
        "ix_evaluation_results_run_id",
        "evaluation_results",
        ["evaluation_run_id"],
    )

    # --- evaluation_aggregates ---
    op.create_table(
        "evaluation_aggregates",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "evaluation_run_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("evaluation_runs.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("retrieval_strategy", sa.Text(), nullable=False),
        sa.Column("recall_at_k_mean", pg.JSONB(), nullable=False),
        sa.Column("precision_at_k_mean", pg.JSONB(), nullable=False),
        sa.Column("mrr_mean", sa.Numeric(6, 4), nullable=False),
        sa.Column("latency_ms_p50", sa.Integer(), nullable=False),
        sa.Column("latency_ms_p95", sa.Integer(), nullable=False),
        sa.Column("latency_ms_mean", sa.Integer(), nullable=False),
    )
    op.create_check_constraint(
        "evaluation_aggregates_retrieval_strategy_nonempty_check",
        "evaluation_aggregates",
        "retrieval_strategy <> ''",
    )
    op.create_check_constraint(
        "evaluation_aggregates_mrr_mean_range_check",
        "evaluation_aggregates",
        "mrr_mean >= 0 AND mrr_mean <= 1",
    )
    op.create_check_constraint(
        "evaluation_aggregates_latency_nonnegative_check",
        "evaluation_aggregates",
        (
            "latency_ms_p50 >= 0 AND latency_ms_p95 >= 0 "
            "AND latency_ms_mean >= 0"
        ),
    )
    op.create_unique_constraint(
        "evaluation_aggregates_run_strategy_unique",
        "evaluation_aggregates",
        ["evaluation_run_id", "retrieval_strategy"],
    )
    op.create_index(
        "ix_evaluation_aggregates_run_id",
        "evaluation_aggregates",
        ["evaluation_run_id"],
    )


def downgrade() -> None:
    # Forward-only per project discipline; downgrade left as a stub
    # so the alembic CLI does not error when invoked, but production
    # operation never exercises this path.
    op.drop_table("evaluation_aggregates")
    op.drop_table("evaluation_results")
    op.drop_table("evaluation_runs")
