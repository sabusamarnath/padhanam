"""EmailConversationResponse satisfying CitedResponse (D131, D138, D151, P15, S56b).

Mirrors CalendarConversationResponse, but cites Emails **directly** via the
``email`` discriminator with no citation-time snapshot — email content is
immutable once received (D151), so the live row IS the evidence; the
two-store split stays calendar-only. ``cited_audit_events`` and
``cited_intake_records`` stay empty. A ``staleness_note`` (D152 fallback)
is appended by the renderer. Framework-free — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from shared_kernel.conversation_flow import ArtefactCitation


@dataclass(frozen=True)
class EmailConversationResponse:
    text: str
    cited_intake_records: tuple[UUID, ...] = field(default_factory=tuple)
    cited_audit_events: tuple[UUID, ...] = field(default_factory=tuple)
    cited_artefacts: tuple[ArtefactCitation, ...] = field(default_factory=tuple)
    staleness_note: str | None = None

    @property
    def has_citations(self) -> bool:
        return bool(
            self.cited_intake_records or self.cited_audit_events or self.cited_artefacts
        )


def email_citation(email_id: UUID) -> ArtefactCitation:
    """A typed ``email``-discriminated citation for an Email (D151)."""
    return ArtefactCitation(artefact_id=email_id, artefact_type="email")


def _short_hex(identifier: UUID) -> str:
    return identifier.hex[:8]


def render_for_whatsapp(
    response: EmailConversationResponse, *, composed_at: datetime
) -> str:
    """Render to the WhatsApp surface (D135): body + optional staleness note + citation line."""
    body = response.text
    if response.staleness_note:
        body = f"{body}\n\n⚠ {response.staleness_note}"
    if not response.has_citations:
        return body
    parts = [f"email {_short_hex(a.artefact_id)}" for a in response.cited_artefacts]
    stamp = composed_at.strftime("%H:%M UTC")
    return f"{body}\n\n— {' · '.join(parts)} · {stamp}"


__all__ = ["EmailConversationResponse", "email_citation", "render_for_whatsapp"]
