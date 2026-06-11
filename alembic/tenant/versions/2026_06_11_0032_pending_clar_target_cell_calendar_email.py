"""pending_clarification target_cell: admit calendar/email cells

Revision ID: 0032_pending_clar_target_cell_calendar_email
Revises: 0031_calendar_multi_connection
Create Date: 2026-06-11

Bug fix. The ``pending_clar_target_cell_check`` constraint (0023, P14 close)
admitted four cell identifiers: manual_entry, audit_conversation,
mirror_conversation, dispatch_clarification. The ``calendar_conversation``
(S55b/S60) and ``email_conversation`` (S56) cells were added afterward and were
never added to the constraint, so when either cell persists a resolution
clarification — a calendar query matching many meetings (a recurring event's
~120 instances), or an email title matching several — the INSERT violates the
check and the request 500s (CheckViolationError on target_cell).

This widens the constraint to the full ``CellIdentifier`` set (six). Additive —
relaxing a check, so no existing row is rejected. Mirrors 0023's shape.

Per-tenant only per D32. Source of truth for the allowed set is
``contexts/messaging/domain/cell_identifier.py`` (CellIdentifier).
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "0032_target_cell_calendar_email"
down_revision: Union[str, None] = "0031_calendar_multi_connection"
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
)

# The 0023 set, for the downgrade.
_TARGET_CELLS_0023 = (
    "manual_entry",
    "audit_conversation",
    "mirror_conversation",
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
    # Reverting fails if any row carries a calendar/email target_cell (the very
    # rows this migration exists to permit) — the honest behaviour.
    op.drop_constraint(
        "pending_clar_target_cell_check",
        "pending_clarifications",
        type_="check",
    )
    op.create_check_constraint(
        "pending_clar_target_cell_check",
        "pending_clarifications",
        _in_clause("target_cell", _TARGET_CELLS_0023),
    )
