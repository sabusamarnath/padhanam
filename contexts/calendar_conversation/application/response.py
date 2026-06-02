"""CalendarConversationResponse satisfying CitedResponse Protocol (D131, D138, D148, P15, S55b-1).

The calendar-conversation cell composes a ``CalendarConversationResponse``
— the operator-facing ``text`` plus the three D131/D138 citation tuple
fields — and satisfies the runtime-checkable ``CitedResponse`` Protocol
from ``shared_kernel/conversation_flow.py``.

``cited_artefacts`` populates with ``ArtefactCitation`` carrying the
``meeting`` discriminator (D148): each Meeting surfaced in an answer
contributes ``ArtefactCitation(artefact_id=<meeting.id>,
artefact_type="meeting")``. The citation points at the live Meeting
search-cache row; the immutable citation-time audit-snapshot evidence
record (the two-store split, D148) wires at S55b-2.

``cited_audit_events`` and ``cited_intake_records`` stay empty at
calendar-conversation: the operator asked about calendar meetings, not
audit or intake history. A clarification, no-results, or resolution-
ambiguity response carries no citations.

Application code is framework-free here — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from shared_kernel.conversation_flow import ArtefactCitation


@dataclass(frozen=True)
class CalendarConversationResponse:
    """The calendar-conversation cell's composed reply satisfying CitedResponse.

    A query response carries ``meeting`` citations for the meetings
    surfaced; a clarification, empty-result, or resolution-ambiguity
    response may carry none. A ``staleness_note`` (D150) is set when the
    refresh fell back to the cached store; the renderer appends it.
    """

    text: str
    cited_intake_records: tuple[UUID, ...] = field(default_factory=tuple)
    cited_audit_events: tuple[UUID, ...] = field(default_factory=tuple)
    cited_artefacts: tuple[ArtefactCitation, ...] = field(default_factory=tuple)
    staleness_note: str | None = None

    @property
    def has_citations(self) -> bool:
        """True when the response cites at least one source artefact."""
        return bool(
            self.cited_intake_records
            or self.cited_audit_events
            or self.cited_artefacts
        )


def meeting_citation(meeting_id: UUID) -> ArtefactCitation:
    """A typed ``meeting``-discriminated citation for a Meeting (D148)."""
    return ArtefactCitation(artefact_id=meeting_id, artefact_type="meeting")


def _short_hex(identifier: UUID) -> str:
    """Short-hex prefix of a UUID for a compact citation (D131 Shape 1)."""
    return identifier.hex[:8]


def render_for_whatsapp(
    response: CalendarConversationResponse, *, composed_at: datetime
) -> str:
    """Render CalendarConversationResponse to the WhatsApp surface text (D135).

    Mirrors the audit-conversation renderer: a cited response is followed
    by a compact Shape-1 citation line (a short-hex prefix per cited
    meeting) plus the composition timestamp. A staleness note (D150
    fallback) is appended ahead of the citation line so the operator sees
    the freshness caveat. A no-citation response (clarification, no
    results, or resolution-ambiguity prelude) renders as its text alone
    plus any staleness note.
    """
    body = response.text
    if response.staleness_note:
        body = f"{body}\n\n⚠ {response.staleness_note}"

    if not response.has_citations:
        return body

    parts = [f"meeting {_short_hex(a.artefact_id)}" for a in response.cited_artefacts]
    citation_line = " · ".join(parts)
    stamp = composed_at.strftime("%H:%M UTC")
    return f"{body}\n\n— {citation_line} · {stamp}"


__all__ = [
    "CalendarConversationResponse",
    "meeting_citation",
    "render_for_whatsapp",
]
