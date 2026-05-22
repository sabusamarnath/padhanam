"""extend intake_source with WHATSAPP_INBOUND (D129)

Revision ID: 0020_intake_source_whatsapp
Revises: 0019_messaging_substrate
Create Date: 2026-05-22

Per D129's inbound-as-intake-orchestration: an inbound WhatsApp
message records an IntakeRecord with ``intake_source`` value
WHATSAPP_INBOUND ahead of the Message write. This migration extends
the ``intakes_intake_source_check`` CHECK constraint to admit the
new value alongside MANUAL_ENTRY (a Postgres CHECK cannot be
altered in place, so it is dropped and recreated).

The revision string stays under the 32-char alembic ceiling per the
captures-documented migration name-length convention.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op


revision: str = "0020_intake_source_whatsapp"
down_revision: Union[str, None] = "0019_messaging_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CONSTRAINT = "intakes_intake_source_check"
_OLD_SOURCES = ("MANUAL_ENTRY",)
_NEW_SOURCES = ("MANUAL_ENTRY", "WHATSAPP_INBOUND")


def _check_expr(values: tuple[str, ...]) -> str:
    return "intake_source IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "intakes", type_="check")
    op.create_check_constraint(
        _CONSTRAINT, "intakes", _check_expr(_NEW_SOURCES)
    )


def downgrade() -> None:
    op.drop_constraint(_CONSTRAINT, "intakes", type_="check")
    op.create_check_constraint(
        _CONSTRAINT, "intakes", _check_expr(_OLD_SOURCES)
    )
