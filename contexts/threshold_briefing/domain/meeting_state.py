"""MeetingState — a current-state projection of a stored Meeting (D153, S57).

The domain value object the evaluator matches rules against. Per D153 the
evaluator reads the calendar *state* store (not the audit chain), and per
the consumer-port-returns-local-DTO discipline the threshold context owns
this projection rather than importing the calendar ``Meeting`` type — the
``apps/`` wiring adapter maps ``Meeting`` → ``MeetingState``.

It lives in the domain layer (not the port module) because the pure
evaluation functions in ``domain/evaluation.py`` consume it; the
``CalendarStateReader`` consumer port in the application layer returns it.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class MeetingState:
    """A current-state projection of one stored Meeting for evaluation.

    Carries only the fields the Phase 2-A rules need: identity
    (``google_event_id``/``meeting_id``/``title``), the time window
    (``start_at``/``end_at``) for the conflict overlap query, and the
    lifecycle marker (``status``/``cancelled_at``) for the cancellation
    query. Content (description/location/attendees) is deliberately
    omitted — the evaluator matches on schedule shape, not content.
    """

    google_event_id: str
    meeting_id: UUID
    title: str
    status: str
    start_at: datetime | None
    end_at: datetime | None
    cancelled_at: datetime | None


__all__ = ["MeetingState"]
