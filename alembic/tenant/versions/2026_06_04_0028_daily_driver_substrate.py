"""create daily-driver substrate (D157)

Revision ID: 0028_daily_driver_substrate
Revises: 0027_email_substrate
Create Date: 2026-06-04

The P16/S58 daily-driver first slice substrate on every per-tenant
database (D157). Three tables:

- ``commitments`` — the minimal user-authored cadence (a name plus an
  expected interval in days) with its author and creation time.
- ``commitment_completions`` — the append-only completion log; FK to
  ``commitments`` ON DELETE CASCADE.
- ``day_item_states`` — the minimal Day concept: per-day ordering
  (``position``) and done-for-today marks (``done``), keyed on
  ``(tenant_id, user_id, day_date, item_kind, item_id)``. Status and
  overdue are computed at render, never stored (D157), so no status or
  overdue column exists.

Every table carries ``tenant_id`` and ``jurisdiction`` per D12. The
revision string ``0028_daily_driver_substrate`` is 27 chars, under the
alembic ceiling per the captures-documented migration name-length
convention.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0028_daily_driver_substrate"
down_revision: Union[str, None] = "0027_email_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ITEM_KINDS = ("CASE", "COMMITMENT")


def upgrade() -> None:
    op.create_table(
        "commitments",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("expected_interval_days", sa.Integer(), nullable=False),
        sa.Column("authored_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "commitments_name_nonempty_check", "commitments", "name <> ''"
    )
    op.create_check_constraint(
        "commitments_jurisdiction_nonempty_check",
        "commitments",
        "jurisdiction <> ''",
    )
    op.create_check_constraint(
        "commitments_interval_positive_check",
        "commitments",
        "expected_interval_days > 0",
    )
    op.create_index(
        "ix_commitments_tenant_id", "commitments", ["tenant_id"]
    )

    op.create_table(
        "commitment_completions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "commitment_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("commitments.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column(
            "completed_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_commitment_completions_commitment_id",
        "commitment_completions",
        ["commitment_id"],
    )
    op.create_index(
        "ix_commitment_completions_tenant_id",
        "commitment_completions",
        ["tenant_id"],
    )

    op.create_table(
        "day_item_states",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("day_date", sa.Date(), nullable=False),
        sa.Column("item_kind", sa.Text(), nullable=False),
        sa.Column("item_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column(
            "done",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "user_id",
            "day_date",
            "item_kind",
            "item_id",
            name="ux_day_item_states_tenant_user_day_item",
        ),
    )
    op.create_check_constraint(
        "day_item_states_item_kind_check",
        "day_item_states",
        "item_kind IN (" + ", ".join(f"'{k}'" for k in _ITEM_KINDS) + ")",
    )
    op.create_index(
        "ix_day_item_states_tenant_user_day",
        "day_item_states",
        ["tenant_id", "user_id", "day_date"],
    )


def downgrade() -> None:
    op.drop_table("day_item_states")
    op.drop_table("commitment_completions")
    op.drop_table("commitments")
