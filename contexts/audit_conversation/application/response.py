"""AuditConversationResponse satisfying CitedResponse Protocol (D131, D138, P14, S51).

The audit-conversation cell composes an ``AuditConversationResponse`` —
the operator-facing ``text`` plus the three D131/D138 citation tuple
fields — and satisfies the runtime-checkable ``CitedResponse`` Protocol
from ``shared_kernel/conversation_flow.py``.

``cited_audit_events`` populates from the AuditEventListPage's events'
ids directly; this closes the S46 empty-field gap on the read-side at
audit-conversation's natural composition (the audit chain's events are
the response's primary content, so the citation tuple is non-empty by
construction when the query returns any events).

``cited_artefacts`` populates heterogeneously per the symmetric-with-
mirror architectural shape (S51 framing Finding 4): when a returned
event references a Case (``resource_type='case'``), the cell adds
``ArtefactCitation(artefact_id=<case_uuid>, artefact_type='case')``;
when an event references a DataPoint (``resource_type='data_point'``),
the cell adds ``ArtefactCitation(artefact_id=<dp_uuid>,
artefact_type='data_point')``. The render layer iterates
``cited_artefacts`` uniformly with the type self-contained on each
citation.

``cited_intake_records`` stays empty at audit-conversation: the audit
chain reaches intake records transitively through ``IntakeRecord``
audit anchoring per D128, but audit-conversation does not directly
cite intake records (the user asked about audit events, not about
intake history).

Application code is framework-free here — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from shared_kernel.conversation_flow import ArtefactCitation


@dataclass(frozen=True)
class AuditConversationResponse:
    """The audit-conversation cell's composed reply satisfying CitedResponse.

    A query response carries citations for the events surfaced; a
    clarification response (UnclearAuditIntent, an empty result set, or
    resolution-ambiguity routing) may carry none.
    """

    text: str
    cited_intake_records: tuple[UUID, ...] = field(default_factory=tuple)
    cited_audit_events: tuple[UUID, ...] = field(default_factory=tuple)
    cited_artefacts: tuple[ArtefactCitation, ...] = field(default_factory=tuple)

    @property
    def has_citations(self) -> bool:
        """True when the response cites at least one source artefact."""
        return bool(
            self.cited_intake_records
            or self.cited_audit_events
            or self.cited_artefacts
        )


__all__ = ["AuditConversationResponse"]
