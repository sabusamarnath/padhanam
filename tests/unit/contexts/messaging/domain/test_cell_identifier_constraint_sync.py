"""Tripwire: the pending_clarifications target_cell DB constraint must admit
every CellIdentifier (the S80 500 regression).

A PendingClarification's ``target_cell`` is constrained at the DB by
``pending_clar_target_cell_check`` (alembic 0023, widened at 0032). The
constraint was frozen at four identifiers while ``calendar_conversation``
(S55b/S60) and ``email_conversation`` (S56) were added as cells — so a calendar
or email *resolution clarification* (a recurring event's many same-titled
instances) violated the check and 500'd. If a new cell is added to
``CellIdentifier`` below, add an alembic migration widening the constraint to
match, or that cell's clarifications will 500 the same way.
"""

from __future__ import annotations

from contexts.messaging.domain.cell_identifier import CellIdentifier

# The set the live DB constraint admits (alembic 0032). Keep in lockstep.
_DB_CONSTRAINT_TARGET_CELLS = {
    "manual_entry",
    "audit_conversation",
    "mirror_conversation",
    "calendar_conversation",
    "email_conversation",
    "dispatch_clarification",
}


def test_every_cell_identifier_is_admitted_by_the_target_cell_constraint():
    assert {c.value for c in CellIdentifier} == _DB_CONSTRAINT_TARGET_CELLS
