"""Threshold-briefing response value objects (D138, D142, D153, S57).

Two BroadcastResponse-satisfying value objects, one per implementer:

- ``ThresholdEvaluationResponse`` — the evaluator's return. Not a
  user-facing briefing; it records what the scan matched (so the dispatch
  layer and tests can see the outcome) and satisfies BroadcastResponse by
  carrying the three citation tuples (it cites the matched meetings as
  artefacts; no intake/audit citations — the evaluator reads state, and
  the audit record of the crossing is emitted downstream by FireTrigger).
- ``ThresholdBriefingResponse`` — the briefing's user-facing reply (added
  at Commit 3 / S57). It cites the affected meeting plus the
  BROADCAST_INITIATED audit event of its own fire.

Both satisfy the CitedResponse Protocol structurally (three citation
tuples). Domain code is framework-free per D16 — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from contexts.threshold_briefing.domain.crossing import ThresholdCrossing
from contexts.threshold_briefing.domain.rule_match import RuleMatch
from shared_kernel.conversation_flow import ArtefactCitation


@dataclass(frozen=True)
class ThresholdEvaluationResponse:
    """The ThresholdEvaluator's BroadcastResponse — the scan outcome (D153).

    ``matched`` is the tuple of crossings the scan emitted. ``cited_artefacts``
    carries the matched meetings (artefact_type='meeting') for chain
    traversability; the intake/audit citation tuples are empty (the
    evaluator reads state; the crossing's audit record is emitted by the
    downstream FireTrigger flow, not by the evaluator).
    """

    matched: tuple[RuleMatch, ...] = ()
    cited_intake_records: tuple[UUID, ...] = field(default_factory=tuple)
    cited_audit_events: tuple[UUID, ...] = field(default_factory=tuple)
    cited_artefacts: tuple[ArtefactCitation, ...] = field(default_factory=tuple)

    @property
    def crossed(self) -> bool:
        """True when the scan found at least one crossing."""
        return bool(self.matched)


def evaluation_response_for(matches: tuple[RuleMatch, ...]) -> ThresholdEvaluationResponse:
    """Build the evaluation response from the scan's matches."""
    return ThresholdEvaluationResponse(
        matched=matches,
        cited_artefacts=tuple(
            ArtefactCitation(artefact_id=m.meeting_id, artefact_type="meeting")
            for m in matches
        ),
    )


@dataclass(frozen=True)
class ThresholdBriefingResponse:
    """The threshold-briefing's user-facing reply satisfying CitedResponse (D153).

    ``text`` is the composed prose. ``crossing`` is the crossing the
    briefing surfaced (for the render header). ``cited_artefacts`` carries
    the affected meeting (artefact_type='meeting'); the audit record of
    the crossing is the BROADCAST_INITIATED event the FireTrigger flow
    emitted upstream (resource_id = the trigger_id), traversable via the
    trigger chain — the briefing itself reads the crossing from the
    trigger metadata, so it carries no audit-event id of its own.
    """

    text: str
    crossing: ThresholdCrossing
    cited_intake_records: tuple[UUID, ...] = field(default_factory=tuple)
    cited_audit_events: tuple[UUID, ...] = field(default_factory=tuple)
    cited_artefacts: tuple[ArtefactCitation, ...] = field(default_factory=tuple)


def briefing_response_for(*, text: str, crossing: ThresholdCrossing) -> ThresholdBriefingResponse:
    """Build the briefing response, citing the affected meeting."""
    return ThresholdBriefingResponse(
        text=text,
        crossing=crossing,
        cited_artefacts=(
            ArtefactCitation(artefact_id=crossing.meeting_id, artefact_type="meeting"),
        ),
    )


def _short_hex(identifier: UUID) -> str:
    """Short-hex prefix of a UUID for a compact citation (D131 Shape 1)."""
    return identifier.hex[:8]


def render_for_whatsapp(
    response: ThresholdBriefingResponse, *, composed_at: datetime
) -> str:
    """Render ThresholdBriefingResponse to the WhatsApp surface (D135).

    A proactive heads-up: an attention header, the composed prose, and a
    compact citation footer (the affected meeting + the compose stamp),
    mirroring the daily-briefing render with a threshold-specific header.
    """
    header = "⚠ Heads-up"
    parts: list[str] = [header, response.text.rstrip()]
    segments = [
        f"ref {_short_hex(a.artefact_id)}" for a in response.cited_artefacts
    ]
    stamp = composed_at.strftime("%H:%M UTC")
    parts.append(f"— {' · '.join(segments)} · {stamp}" if segments else f"— {stamp}")
    return "\n\n".join(parts)


__all__ = [
    "ThresholdBriefingResponse",
    "ThresholdEvaluationResponse",
    "briefing_response_for",
    "evaluation_response_for",
    "render_for_whatsapp",
]
