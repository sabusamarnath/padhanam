"""add target_cell to pending_clarifications (D140, S52)

Revision ID: 0023_pending_clar_target_cell
Revises: 0022_intent_class_eval_substrate
Create Date: 2026-05-27

D140's PendingClarification target_cell extension: the field that
identifies which ConversationFlow implementer owns the pending. The
dispatch_inbound use case consults this field on active-pending
routing per D140's dispatch flow Step 2.

Backfill strategy: every existing pending_clarifications row was
created by the manual entry cell at S47/S50 (the only ConversationFlow
implementer in production before S52 build). Audit-conversation at
S51 does not create PendingClarification rows at the in-tenant data
plane (the S51 cell synthesises a fresh UUID for originating_intake_id
when run outside a webhook context per the cell's contract-harness
fallback; the production webhook path lands at S52). Backfill therefore
sets target_cell='manual_entry' on every existing row.

CHECK constraint admits four identifiers at P14 close: manual_entry,
audit_conversation, mirror_conversation, dispatch_clarification. The
constraint widens additively at P15+ when new ConversationFlow
implementers register.

Revision id stays under the 32-char alembic ceiling per the captures-
documented migration name-length convention.

Per Finding 1 at S52 pre-write reconciliation: the brief's framing-time
number 0022 collided with S48b's intent_class_eval_substrate migration;
renumbered to 0023 at operator approval 2026-05-27.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0023_pending_clar_target_cell"
down_revision: Union[str, None] = "0022_intent_class_eval_substrate"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_TARGET_CELLS = (
    "manual_entry",
    "audit_conversation",
    "mirror_conversation",
    "dispatch_clarification",
)


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    return column + " IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    # 1) Add the column nullable so the backfill UPDATE can run.
    op.add_column(
        "pending_clarifications",
        sa.Column("target_cell", sa.Text(), nullable=True),
    )

    # 2) Backfill existing rows. Every PendingClarification before S52
    #    came from the manual entry cell at S47/S50.
    op.execute(
        "UPDATE pending_clarifications "
        "SET target_cell = 'manual_entry' "
        "WHERE target_cell IS NULL"
    )

    # 3) Alter to NOT NULL now that every row has a value.
    op.alter_column(
        "pending_clarifications",
        "target_cell",
        existing_type=sa.Text(),
        nullable=False,
    )

    # 4) CHECK constraint accepting the four known identifiers.
    op.create_check_constraint(
        "pending_clar_target_cell_check",
        "pending_clarifications",
        _in_clause("target_cell", _TARGET_CELLS),
    )


def downgrade() -> None:
    op.drop_constraint(
        "pending_clar_target_cell_check",
        "pending_clarifications",
        type_="check",
    )
    op.drop_column("pending_clarifications", "target_cell")
