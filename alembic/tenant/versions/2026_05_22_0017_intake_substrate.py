"""create intakes (D127)

Revision ID: 0017_intake_substrate
Revises: 0016_portfolio_substrate
Create Date: 2026-05-22

Per-tenant substrate for the intake context per D127. One table on
each tenant's dedicated Postgres data plane per D32:

- ``intakes``: the IntakeRecord aggregate root. A CHECK constraint
  pins ``intake_source`` to the single Phase 2-A value MANUAL_ENTRY;
  ``payload`` is JSONB carrying the serialised IntakePayload
  variant. IntakeRecords are immutable — no update path.

Every table carries ``tenant_id`` and ``jurisdiction`` per D12.
CHECK-constraint naming follows the ``0016_portfolio_substrate``
pattern. The revision string stays under the 32-char alembic
ceiling per the captures-documented migration name-length
convention.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0017_intake_substrate"
down_revision: Union[str, None] = "0016_portfolio_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_INTAKE_SOURCES = ("MANUAL_ENTRY",)


def upgrade() -> None:
    op.create_table(
        "intakes",
        sa.Column(
            "id",
            pg.UUID(as_uuid=False),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", pg.UUID(as_uuid=False), nullable=False),
        sa.Column("jurisdiction", sa.Text(), nullable=False),
        sa.Column("intake_source", sa.Text(), nullable=False),
        sa.Column("payload", pg.JSONB(), nullable=False),
        sa.Column("authored_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_check_constraint(
        "intakes_jurisdiction_nonempty_check", "intakes", "jurisdiction <> ''"
    )
    op.create_check_constraint(
        "intakes_authored_by_nonempty_check",
        "intakes",
        "authored_by_user_id <> ''",
    )
    op.create_check_constraint(
        "intakes_intake_source_check",
        "intakes",
        "intake_source IN ("
        + ", ".join(f"'{v}'" for v in _INTAKE_SOURCES)
        + ")",
    )
    op.create_index(
        "ix_intakes_tenant_created_at",
        "intakes",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_intakes_tenant_source", "intakes", ["tenant_id", "intake_source"]
    )


def downgrade() -> None:
    op.drop_table("intakes")
