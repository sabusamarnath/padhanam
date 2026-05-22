"""Intake domain layer (D127).

- ``IntakeRecord`` (aggregate root) at ``intake_record.py`` — the
  canonical-entry record, with the ``IntakeSource`` enum.
- ``ManualEntryPayload`` — the Phase 2-A ``IntakePayload`` variant.
- ``IntakePayload`` — the payload type alias (single variant at
  S44b; widens to a Union when calendar-read / email-read land).

Domain code is framework-free per D16 — stdlib plus shared_kernel.
"""

from contexts.intake.domain.intake_record import (
    IntakePayload,
    IntakeRecord,
    IntakeSource,
    ManualEntryPayload,
)

__all__ = [
    "IntakePayload",
    "IntakeRecord",
    "IntakeSource",
    "ManualEntryPayload",
]
