"""ThresholdCrossing — the briefing-side read-model of a crossing (D153, S57).

The threshold-briefing implementer reads the crossing out of the
``THRESHOLD_CROSSED`` trigger metadata (placed there by the emitter via
``RuleMatch.to_trigger_metadata``) and composes from it — it never
re-reads the calendar store, so the briefing is decoupled from the state
the evaluator read. This value object is that read-model: the displayable
fields plus the meeting id for the artefact citation.

Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class ThresholdCrossing:
    """The crossing the threshold-briefing composes a briefing for."""

    rule_id: str
    rule_type: str
    google_event_id: str
    meeting_id: UUID
    title: str
    summary: str
    cancelled_at: str
    partner_event_id: str
    partner_title: str
    crossing_identity: str

    @classmethod
    def from_metadata(cls, metadata: dict[str, Any]) -> "ThresholdCrossing":
        """Reconstruct the crossing from the THRESHOLD_CROSSED trigger metadata.

        Tolerant of a missing meeting_id (mints a placeholder) so a
        malformed trigger does not crash the briefing — the displayable
        fields carry the operator-facing content regardless.
        """
        raw_meeting_id = str(metadata.get("meeting_id", "")).strip()
        try:
            meeting_id = UUID(raw_meeting_id)
        except (ValueError, AttributeError):
            meeting_id = UUID(int=0)
        return cls(
            rule_id=str(metadata.get("rule_id", "")),
            rule_type=str(metadata.get("rule_type", "")),
            google_event_id=str(metadata.get("google_event_id", "")),
            meeting_id=meeting_id,
            title=str(metadata.get("title", "")),
            summary=str(metadata.get("summary", "")),
            cancelled_at=str(metadata.get("cancelled_at", "")),
            partner_event_id=str(metadata.get("partner_event_id", "")),
            partner_title=str(metadata.get("partner_title", "")),
            crossing_identity=str(metadata.get("crossing_identity", "")),
        )


__all__ = ["ThresholdCrossing"]
