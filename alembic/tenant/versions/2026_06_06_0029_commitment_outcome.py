"""add expected-versus-observed outcome fields to commitments (D162)

Revision ID: 0029_commitment_outcome
Revises: 0028_daily_driver_substrate
Create Date: 2026-06-06

The P16/S61 minimal expected-versus-observed loop (D162). Four columns on
the existing ``commitments`` table on every per-tenant database — the
primitive is extended, not a parallel entity:

- ``expected_outcome`` — free text, captured forward at creation; nullable
  (existing commitments and unset captures carry NULL).
- ``observed_outcome`` — free text, captured after the fact; nullable.
- ``outcome_status`` — a coarse human-set status; nullable until an
  observation is recorded (no "pending" value), constrained to the D162
  enum (met / partial / missed / changed / dropped).
- ``observed_at`` — the timestamp of the observation capture; the only new
  real progress signal (``last_progress_at`` is otherwise derived from the
  completion log at render, so no progress column is added).

Outcomes are plaintext, consistent with the daily-driver store's existing
posture (the context is not D21-classified). The revision string
``0029_commitment_outcome`` is 23 chars, under the alembic ceiling per the
captures-documented migration name-length convention.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0029_commitment_outcome"
down_revision: Union[str, None] = "0028_daily_driver_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_OUTCOME_STATUSES = ("met", "partial", "missed", "changed", "dropped")


def upgrade() -> None:
    op.add_column(
        "commitments",
        sa.Column("expected_outcome", sa.Text(), nullable=True),
    )
    op.add_column(
        "commitments",
        sa.Column("observed_outcome", sa.Text(), nullable=True),
    )
    op.add_column(
        "commitments",
        sa.Column("outcome_status", sa.Text(), nullable=True),
    )
    op.add_column(
        "commitments",
        sa.Column(
            "observed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "commitments_outcome_status_check",
        "commitments",
        "outcome_status IS NULL OR outcome_status IN ("
        + ", ".join(f"'{s}'" for s in _OUTCOME_STATUSES)
        + ")",
    )


def downgrade() -> None:
    op.drop_constraint(
        "commitments_outcome_status_check", "commitments", type_="check"
    )
    op.drop_column("commitments", "observed_at")
    op.drop_column("commitments", "outcome_status")
    op.drop_column("commitments", "observed_outcome")
    op.drop_column("commitments", "expected_outcome")
