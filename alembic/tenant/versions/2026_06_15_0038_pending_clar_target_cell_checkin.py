"""pending_clarification target_cell: admit the checkin cell

Revision ID: 0038_pending_clar_target_cell_checkin
Revises: 0037_checkin_responses
Create Date: 2026-06-15

S97b adds the ``checkin`` ConversationFlow cell — the daily three-state
check-in (D192). Unlike the five inbound-initiated cells, ``checkin`` is
**outbound-initiated** (D194): the DAILY_SCHEDULED composer creates its
PendingClarification and the operator's reply routes to it by the active-
pending path (D140). It is therefore never meta-routed, but it *does* own a
PendingClarification, so its identifier must be admitted by the
``pending_clar_target_cell_check`` constraint or the composer's INSERT 500s
(the S80 regression class the constraint-sync tripwire guards).

This widens the constraint to the seven-identifier ``CellIdentifier`` set.
Additive — relaxing a check, so no existing row is rejected. Mirrors 0032's
shape.

Per-tenant only per D32. Source of truth for the allowed set is
``contexts/messaging/domain/cell_identifier.py`` (CellIdentifier).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0038_target_cell_checkin"
down_revision: Union[str, None] = "0037_checkin_responses"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The full CellIdentifier set — every cell that can own a PendingClarification.
_TARGET_CELLS = (
    "manual_entry",
    "audit_conversation",
    "mirror_conversation",
    "calendar_conversation",
    "email_conversation",
    "dispatch_clarification",
    "checkin",
)

# The 0032 set, for the downgrade.
_TARGET_CELLS_0032 = (
    "manual_entry",
    "audit_conversation",
    "mirror_conversation",
    "calendar_conversation",
    "email_conversation",
    "dispatch_clarification",
)


def _in_clause(column: str, values: tuple[str, ...]) -> str:
    return column + " IN (" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    op.drop_constraint(
        "pending_clar_target_cell_check",
        "pending_clarifications",
        type_="check",
    )
    op.create_check_constraint(
        "pending_clar_target_cell_check",
        "pending_clarifications",
        _in_clause("target_cell", _TARGET_CELLS),
    )


def downgrade() -> None:
    # Reverting fails if any row carries a checkin target_cell (the very rows
    # this migration exists to permit) — the honest behaviour.
    op.drop_constraint(
        "pending_clar_target_cell_check",
        "pending_clarifications",
        type_="check",
    )
    op.create_check_constraint(
        "pending_clar_target_cell_check",
        "pending_clarifications",
        _in_clause("target_cell", _TARGET_CELLS_0032),
    )
