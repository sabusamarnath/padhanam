"""Intake bounded context (D127, D128).

The Phase 2-A canonical-entry substrate — per-tenant persistence of
the IntakeRecord aggregate, the record captured when work enters the
system ahead of any downstream portfolio write. Hexagonal layers
within: ``domain`` / ``ports`` / ``application`` / ``adapters``.

D128 commits the intake-canonical posture: every persisted state
change at the platform's write surfaces traces to an IntakeRecord
via the ``intake_id`` field on the persisted entity.
"""
