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
from uuid import UUID

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


__all__ = ["ThresholdEvaluationResponse", "evaluation_response_for"]
