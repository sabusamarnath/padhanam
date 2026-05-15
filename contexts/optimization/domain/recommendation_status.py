"""Recommendation status enum (D108, D111 commitment 3).

Four lifecycle states per D108: generated (engine-written initial
state), acknowledged (user reviewed), applied (user committed to
the recommendation), rejected (user dismissed). The parent
aggregate's status mutates as user actions land; the recommendation
content (text, evidence_citations) is append-only per D111
alternative (g).

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from enum import Enum


class RecommendationStatus(str, Enum):
    """Recommendation lifecycle status (D111 commitment 3)."""

    GENERATED = "generated"
    ACKNOWLEDGED = "acknowledged"
    APPLIED = "applied"
    REJECTED = "rejected"


# Forward-only transition map per D111 commitment 3. The engine
# writes `generated`; user actions transition to one of the three
# user-driven states. Transitions out of terminal states are not
# permitted at the application layer.
_ALLOWED_TRANSITIONS: dict[RecommendationStatus, frozenset[RecommendationStatus]] = {
    RecommendationStatus.GENERATED: frozenset(
        {
            RecommendationStatus.ACKNOWLEDGED,
            RecommendationStatus.APPLIED,
            RecommendationStatus.REJECTED,
        }
    ),
    RecommendationStatus.ACKNOWLEDGED: frozenset(
        {
            RecommendationStatus.APPLIED,
            RecommendationStatus.REJECTED,
        }
    ),
    RecommendationStatus.APPLIED: frozenset(),
    RecommendationStatus.REJECTED: frozenset(),
}


def can_transition(
    *,
    from_status: RecommendationStatus,
    to_status: RecommendationStatus,
) -> bool:
    """Return True if the transition is permitted per the lifecycle map."""
    return to_status in _ALLOWED_TRANSITIONS[from_status]


__all__ = ["RecommendationStatus", "can_transition"]
