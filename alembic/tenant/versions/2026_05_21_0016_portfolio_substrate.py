"""create cases, data_points, assertions (D124)

Revision ID: 0016_portfolio_substrate
Revises: 0015_optimization_substrate
Create Date: 2026-05-21

Per-tenant substrate for the portfolio context per D124. Three
tables on each tenant's dedicated Postgres data plane per D32:

- ``cases``: the aggregate root. CHECK constraints pin
  ``case_type`` to the single Phase 2-A value PORTFOLIO_ITEM and
  ``status`` to OPEN/CLOSED/ARCHIVED.

- ``data_points``: an entity within the Case aggregate, FK to
  ``cases.id`` ON DELETE CASCADE. ``data_point_type`` pinned to
  GOAL/STATUS/METHODOLOGY_APPLICATION; ``certainty`` is nullable
  with a CHECK pinning it to [0, 1] when set (D117 reserve).

- ``assertions``: the append-only revision unit, FK to
  ``data_points.id`` ON DELETE CASCADE plus a self-referential FK
  ``revises_assertion_id`` ON DELETE RESTRICT. A pairing CHECK
  pins INITIAL assertions to a null ``revises_assertion_id`` and
  REVISION assertions to a non-null one.

Every table carries ``tenant_id`` and ``jurisdiction`` per D12.
CHECK-constraint naming follows the
``0015_optimization_substrate`` pattern.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0016_portfolio_substrate"
down_revision: Union[str, None] = "0015_optimization_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CASE_TYPES = ("PORTFOLIO_ITEM",)
_CASE_STATUSES = ("OPEN", "CLOSED", "ARCHIVED")
_DATA_POINT_TYPES = ("GOAL", "STATUS", "METHODOLOGY_APPLICATION")
_ASSERTION_TYPES = ("INITIAL", "REVISION")


def upgrade() -> None:
    # --- cases ---
    op.create_table(
        "cases",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("case_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "cases_jurisdiction_nonempty_check", "cases", "jurisdiction <> ''"
    )
    op.create_check_constraint(
        "cases_title_nonempty_check", "cases", "title <> ''"
    )
    op.create_check_constraint(
        "cases_case_type_check",
        "cases",
        "case_type IN (" + ", ".join(f"'{v}'" for v in _CASE_TYPES) + ")",
    )
    op.create_check_constraint(
        "cases_status_check",
        "cases",
        "status IN (" + ", ".join(f"'{v}'" for v in _CASE_STATUSES) + ")",
    )
    op.create_index(
        "ix_cases_tenant_status", "cases", ["tenant_id", "status"]
    )
    op.create_index(
        "ix_cases_tenant_created_at",
        "cases",
        ["tenant_id", sa.text("created_at DESC")],
    )

    # --- data_points ---
    op.create_table(
        "data_points",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "case_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("data_point_type", sa.Text(), nullable=False),
        sa.Column("value", pg.JSONB(), nullable=False),
        sa.Column("authored_by_user_id", sa.Text(), nullable=False),
        sa.Column("certainty", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "data_points_jurisdiction_nonempty_check",
        "data_points",
        "jurisdiction <> ''",
    )
    op.create_check_constraint(
        "data_points_authored_by_nonempty_check",
        "data_points",
        "authored_by_user_id <> ''",
    )
    op.create_check_constraint(
        "data_points_data_point_type_check",
        "data_points",
        "data_point_type IN ("
        + ", ".join(f"'{v}'" for v in _DATA_POINT_TYPES)
        + ")",
    )
    op.create_check_constraint(
        "data_points_certainty_range_check",
        "data_points",
        "certainty IS NULL OR (certainty >= 0 AND certainty <= 1)",
    )
    op.create_index("ix_data_points_case_id", "data_points", ["case_id"])
    op.create_index("ix_data_points_tenant_id", "data_points", ["tenant_id"])

    # --- assertions ---
    op.create_table(
        "assertions",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "data_point_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("data_points.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("assertion_type", sa.Text(), nullable=False),
        sa.Column(
            "revises_assertion_id",
            pg.UUID(as_uuid=False),
            sa.ForeignKey("assertions.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("value", pg.JSONB(), nullable=False),
        sa.Column("authored_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "assertions_jurisdiction_nonempty_check",
        "assertions",
        "jurisdiction <> ''",
    )
    op.create_check_constraint(
        "assertions_authored_by_nonempty_check",
        "assertions",
        "authored_by_user_id <> ''",
    )
    op.create_check_constraint(
        "assertions_assertion_type_check",
        "assertions",
        "assertion_type IN ("
        + ", ".join(f"'{v}'" for v in _ASSERTION_TYPES)
        + ")",
    )
    # Pairing CHECK: INITIAL carries no parent; REVISION must point at one.
    op.create_check_constraint(
        "assertions_type_revises_pairing_check",
        "assertions",
        (
            "(assertion_type = 'INITIAL' AND revises_assertion_id IS NULL) "
            "OR (assertion_type = 'REVISION' "
            "AND revises_assertion_id IS NOT NULL)"
        ),
    )
    op.create_index(
        "ix_assertions_data_point_created_at",
        "assertions",
        ["data_point_id", "created_at"],
    )
    op.create_index(
        "ix_assertions_tenant_id", "assertions", ["tenant_id"]
    )


def downgrade() -> None:
    # Reverse FK order: assertions -> data_points -> cases.
    op.drop_table("assertions")
    op.drop_table("data_points")
    op.drop_table("cases")
