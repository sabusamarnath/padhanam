"""create optimization_runs, recommendations, recommendation_status_transitions (D111)

Revision ID: 0015_optimization_substrate
Revises: 0014_eval_runner_substrate
Create Date: 2026-05-15

Per-tenant substrate for the optimization context per D111. Three
tables on each tenant's dedicated Postgres data plane per D32:

- ``optimization_runs``: aggregate root (D111 commitment 2). Status
  CHECK pins {'running', 'completed', 'failed'}; ``skipped_categories``
  JSONB defaults to ``{}`` and carries the structured skip-reasons
  captured during rule iteration when rules raise SubstrateGapError.

- ``recommendations``: single-aggregate-with-category-discriminator
  per D111 commitment 3. CHECK constraints pin category to the four
  D108 values and status to the four lifecycle values. NOT NULL FK
  to ``optimization_runs.id`` because Phase 1 has no user-initiated
  recommendations per D111 commitment 3.

- ``recommendation_status_transitions``: append-only audit table per
  D111 commitment 4. One row per status change; the parent
  recommendation row's ``last_transition_at`` / ``last_transition_by``
  fields mirror the most recent transition for read-time convenience.

CHECK-constraint naming follows the
``0014_eval_runner_substrate`` pattern.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0015_optimization_substrate"
down_revision: Union[str, None] = "0014_eval_runner_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_RUN_STATUSES = ("running", "completed", "failed")
_CATEGORIES = (
    "retrieval_strategy",
    "model_choice",
    "prompt_revision",
    "cost_optimization",
)
_REC_STATUSES = ("generated", "acknowledged", "applied", "rejected")


def upgrade() -> None:
    # --- optimization_runs ---
    op.create_table(
        "optimization_runs",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
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
        sa.Column(
            "skipped_categories",
            pg.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_check_constraint(
        "optimization_runs_jurisdiction_nonempty_check",
        "optimization_runs",
        "jurisdiction <> ''",
    )
    op.create_check_constraint(
        "optimization_runs_invoked_by_user_id_nonempty_check",
        "optimization_runs",
        "invoked_by_user_id <> ''",
    )
    op.create_check_constraint(
        "optimization_runs_status_check",
        "optimization_runs",
        "status IN (" + ", ".join(f"'{v}'" for v in _RUN_STATUSES) + ")",
    )
    op.create_check_constraint(
        "optimization_runs_terminal_completed_pairing_check",
        "optimization_runs",
        (
            "(status = 'running' AND completed_at IS NULL) "
            "OR (status <> 'running' AND completed_at IS NOT NULL)"
        ),
    )
    op.create_index(
        "ix_optimization_runs_tenant_invoked_at",
        "optimization_runs",
        ["tenant_id", sa.text("invoked_at DESC")],
    )

    # --- recommendations ---
    op.create_table(
        "recommendations",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("evidence_citations", pg.JSONB(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
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
        sa.Column(
            "last_transition_by_user_id", sa.Text(), nullable=True
        ),
    )
    op.create_check_constraint(
        "recommendations_jurisdiction_nonempty_check",
        "recommendations",
        "jurisdiction <> ''",
    )
    op.create_check_constraint(
        "recommendations_subject_nonempty_check",
        "recommendations",
        "subject <> ''",
    )
    op.create_check_constraint(
        "recommendations_text_nonempty_check",
        "recommendations",
        "text <> ''",
    )
    op.create_check_constraint(
        "recommendations_category_check",
        "recommendations",
        "category IN (" + ", ".join(f"'{v}'" for v in _CATEGORIES) + ")",
    )
    op.create_check_constraint(
        "recommendations_status_check",
        "recommendations",
        "status IN (" + ", ".join(f"'{v}'" for v in _REC_STATUSES) + ")",
    )
    # Pairing CHECK: generated status carries no transition user;
    # any other status requires last_transition_by_user_id non-empty.
    op.create_check_constraint(
        "recommendations_status_transition_user_pairing_check",
        "recommendations",
        (
            "(status = 'generated' AND last_transition_by_user_id IS NULL) "
            "OR (status <> 'generated' "
            "AND last_transition_by_user_id IS NOT NULL "
            "AND last_transition_by_user_id <> '')"
        ),
    )
    op.create_index(
        "recommendations_tenant_status_category_idx",
        "recommendations",
        ["tenant_id", "status", "category"],
    )
    op.create_index(
        "ix_recommendations_tenant_generated_at",
        "recommendations",
        ["tenant_id", sa.text("generated_at DESC")],
    )
    op.create_index(
        "ix_recommendations_generated_by_run_id",
        "recommendations",
        ["generated_by_run_id"],
    )

    # --- recommendation_status_transitions ---
    op.create_table(
        "recommendation_status_transitions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "recommendation_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("recommendations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("from_status", sa.Text(), nullable=False),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("transitioned_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "transitioned_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "recommendation_status_transitions_user_nonempty_check",
        "recommendation_status_transitions",
        "transitioned_by_user_id <> ''",
    )
    op.create_check_constraint(
        "recommendation_status_transitions_status_distinct_check",
        "recommendation_status_transitions",
        "from_status <> to_status",
    )
    op.create_check_constraint(
        "recommendation_status_transitions_from_status_check",
        "recommendation_status_transitions",
        "from_status IN (" + ", ".join(f"'{v}'" for v in _REC_STATUSES) + ")",
    )
    op.create_check_constraint(
        "recommendation_status_transitions_to_status_check",
        "recommendation_status_transitions",
        "to_status IN (" + ", ".join(f"'{v}'" for v in _REC_STATUSES) + ")",
    )
    op.create_index(
        "recommendation_status_transitions_recommendation_idx",
        "recommendation_status_transitions",
        ["recommendation_id", "transitioned_at"],
    )


def downgrade() -> None:
    # Forward-only per project discipline; downgrade is a stub so
    # the alembic CLI does not error when invoked.
    op.drop_table("recommendation_status_transitions")
    op.drop_table("recommendations")
    op.drop_table("optimization_runs")
