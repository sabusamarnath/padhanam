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
from datetime import datetime
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


def _short_hex(identifier: UUID) -> str:
    """Short-hex prefix of a UUID for a compact citation (D131 Shape 1)."""
    return identifier.hex[:8]


def render_for_whatsapp(
    response: AuditConversationResponse, *, composed_at: datetime
) -> str:
    """Render AuditConversationResponse to the WhatsApp surface text (D135).

    Mirrors the manual entry cell's ``render_for_whatsapp`` shape at
    ``contexts/messaging/application/cell_response.py``: when the response
    cites artefacts, the text is followed by a compact Shape-1 citation
    line (a short-hex prefix per cited audit event, intake record, and
    artefact) plus the composition timestamp. A no-citation response
    (clarification, no-results, or resolution-ambiguity prelude with no
    candidates) renders as its text alone.

    Per D135 domain-decides-content channel-decides-format pattern, the
    domain layer produces the channel-agnostic content (text + citation
    tuples); this renderer is the WhatsApp-specific affordance.
    """
    if not response.has_citations:
        return response.text

    parts: list[str] = []
    parts += [
        f"audit {_short_hex(e)}" for e in response.cited_audit_events
    ]
    parts += [
        f"ref {_short_hex(a.artefact_id)}" for a in response.cited_artefacts
    ]
    parts += [
        f"intake {_short_hex(i)}" for i in response.cited_intake_records
    ]
    citation_line = " · ".join(parts)
    stamp = composed_at.strftime("%H:%M UTC")
    return f"{response.text}\n\n— {citation_line} · {stamp}"


__all__ = ["AuditConversationResponse", "render_for_whatsapp"]
