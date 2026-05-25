"""create pending_clarifications (D134, S47)

Revision ID: 0021_pending_clarification
Revises: 0020_intake_source_whatsapp
Create Date: 2026-05-25

Per-tenant substrate for multi-turn conversation state per D134. One
table on each tenant's dedicated Postgres data plane per D32:

- ``pending_clarifications``: the PendingClarification aggregate. CHECK
  constraints pin ``status`` and enforce non-empty text fields. The
  D134 invariant — at most one PENDING per ``(tenant_id, user_id)`` —
  is enforced structurally by a partial unique index. ``proposed_intent``
  carries the cell's structured best-guess intent as JSONB.

Every table carries ``tenant_id`` and ``jurisdiction`` per D12. The
revision string stays under the 32-char alembic ceiling per the
captures-documented migration name-length convention.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0021_pending_clarification"
down_revision: Union[str, None] = "0020_intake_source_whatsapp"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_STATUSES = ("PENDING", "RESOLVED", "EXPIRED")


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    return column + " IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.create_table(
        "pending_clarifications",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("originating_channel", sa.Text(), nullable=False),
        sa.Column(
            "originating_user_address", sa.Text(), nullable=False
        ),
        sa.Column(
            "originating_intake_id",
            pg.UUID(as_uuid=False),
            nullable=False,
        ),
        sa.Column("proposed_intent", pg.JSONB, nullable=False),
        sa.Column(
            "proposed_action_summary", sa.Text(), nullable=False
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "resolved_at",
            sa.TIMESTAMP(timezone=True),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["originating_intake_id"],
            ["intakes.id"],
            name="fk_pending_clar_intake_id",
            ondelete="RESTRICT",
        ),
    )
    op.create_check_constraint(
        "pending_clar_jurisdiction_nonempty_check",
        "pending_clarifications",
        "jurisdiction <> ''",
    )
    op.create_check_constraint(
        "pending_clar_user_id_nonempty_check",
        "pending_clarifications",
        "user_id <> ''",
    )
    op.create_check_constraint(
        "pending_clar_channel_nonempty_check",
        "pending_clarifications",
        "originating_channel <> ''",
    )
    op.create_check_constraint(
        "pending_clar_user_address_nonempty_check",
        "pending_clarifications",
        "originating_user_address <> ''",
    )
    op.create_check_constraint(
        "pending_clar_summary_nonempty_check",
        "pending_clarifications",
        "proposed_action_summary <> ''",
    )
    op.create_check_constraint(
        "pending_clar_status_check",
        "pending_clarifications",
        _in_clause("status", _STATUSES),
    )
    op.create_check_constraint(
        "pending_clar_expires_after_created_check",
        "pending_clarifications",
        "expires_at > created_at",
    )
    op.create_check_constraint(
        "pending_clar_resolved_at_status_check",
        "pending_clarifications",
        "(status = 'PENDING' AND resolved_at IS NULL) "
        "OR (status <> 'PENDING' AND resolved_at IS NOT NULL)",
    )
    op.create_index(
        "ix_pending_clar_tenant_user",
        "pending_clarifications",
        ["tenant_id", "user_id"],
    )
    # D134 invariant: at most one PENDING per (tenant_id, user_id).
    op.create_index(
        "ux_pending_clar_one_pending_per_user",
        "pending_clarifications",
        ["tenant_id", "user_id"],
        unique=True,
        postgresql_where=sa.text("status = 'PENDING'"),
    )


def downgrade() -> None:
    op.drop_table("pending_clarifications")
