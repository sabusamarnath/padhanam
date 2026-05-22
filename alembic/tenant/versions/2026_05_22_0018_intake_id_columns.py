"""add intake_id to cases and assertions (D128)

Revision ID: 0018_intake_id_columns
Revises: 0017_intake_substrate
Create Date: 2026-05-22

Per D128's intake-canonical commitment: a persisted portfolio state
change traces to an IntakeRecord via an ``intake_id`` foreign key.
This migration adds a nullable ``intake_id`` column to ``cases`` and
to ``assertions``, each a foreign key to ``intakes(id)`` ON DELETE
RESTRICT.

The column is nullable at the persistence layer for migration
safety and nullable at the domain layer per D128: the
intake-canonical orchestration paths populate it; direct domain
construction outside an orchestration leaves it null. The revision
string stays under the 32-char alembic ceiling per the
captures-documented migration name-length convention.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg


revision: str = "0018_intake_id_columns"
down_revision: Union[str, None] = "0017_intake_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLES = ("cases", "assertions")


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "intake_id", pg.UUID(as_uuid=False), nullable=True
            ),
        )
        op.create_foreign_key(
            f"fk_{table}_intake_id",
            table,
            "intakes",
            ["intake_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index(
            f"ix_{table}_intake_id", table, ["intake_id"]
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_index(f"ix_{table}_intake_id", table_name=table)
        op.drop_constraint(
            f"fk_{table}_intake_id", table, type_="foreignkey"
        )
        op.drop_column(table, "intake_id")
