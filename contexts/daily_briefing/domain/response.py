"""DailyBriefingResponse value object (D131, D138, D146, S54).

Satisfies the CitedResponse Protocol from
``shared_kernel/conversation_flow.py``: carries the three citation
tuple fields plus the implementer-specific ``briefing_period``
extension field for the channel render header (D135).

Citation population per D146:

- ``cited_intake_records`` carries the recent IntakeRecord ids the
  briefing summarised (the activity that entered the platform during
  the window) per D128's intake-canonical commitment.
- ``cited_audit_events`` carries the recent audit-event ids the
  briefing referenced (state changes during the window) plus the
  BROADCAST_INITIATED event the FireTrigger use case emitted, so the
  Phase 3 close audit can walk the citation back to the originating
  trigger per D147.
- ``cited_artefacts`` carries Case citations (artefact_type='case')
  for the active Cases the briefing surfaced against.

``briefing_period`` is the BriefingPeriod the composition covered;
the WhatsApp render surfaces it as the briefing-period header.

Application/domain code is framework-free here — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from contexts.daily_briefing.domain.briefing_period import BriefingPeriod
from shared_kernel.conversation_flow import ArtefactCitation


@dataclass(frozen=True)
class DailyBriefingResponse:
    """The daily-briefing's composed reply satisfying CitedResponse (D146)."""

    text: str
    briefing_period: BriefingPeriod
    cited_intake_records: tuple[UUID, ...] = field(default_factory=tuple)
    cited_audit_events: tuple[UUID, ...] = field(default_factory=tuple)
    cited_artefacts: tuple[ArtefactCitation, ...] = field(default_factory=tuple)

    @property
    def has_citations(self) -> bool:
        """True when the briefing cites at least one source artefact."""
        return bool(
            self.cited_intake_records
            or self.cited_audit_events
            or self.cited_artefacts
        )


def _short_hex(identifier: UUID) -> str:
    """Short-hex prefix of a UUID for a compact citation (D131 Shape 1)."""
    return identifier.hex[:8]


def render_for_whatsapp(
    response: DailyBriefingResponse, *, composed_at: datetime
) -> str:
    """Render DailyBriefingResponse to the WhatsApp surface text (D135).

    Per the D135 domain-decides-content channel-decides-format
    pattern: the domain produces the channel-agnostic content (text +
    period + citation tuples); this renderer is the WhatsApp-specific
    affordance. The render shape mirrors the audit/mirror-conversation
    precedent (D131 Shape 1 compact citation footer) with one
    broadcast-specific addition: a briefing-period header line at the
    top so the operator sees the window the briefing covered.

    An empty-day briefing (no recent activity; portfolio state only)
    still renders its prose plus the Case citations — the composer
    handles the empty-day prose adjustment per D146, not the render.
    """
    period = response.briefing_period
    header = (
        f"Daily briefing · {period.window_start.strftime('%b %d %H:%M')}"
        f"–{period.window_end.strftime('%b %d %H:%M')} UTC"
    )
    parts: list[str] = [header, response.text.rstrip()]

    if response.has_citations:
        segments: list[str] = []
        segments += [
            f"ref {_short_hex(a.artefact_id)}"
            for a in response.cited_artefacts
        ]
        segments += [
            f"intake {_short_hex(i)}" for i in response.cited_intake_records
        ]
        segments += [
            f"audit {_short_hex(e)}" for e in response.cited_audit_events
        ]
        stamp = composed_at.strftime("%H:%M UTC")
        parts.append(f"— {' · '.join(segments)} · {stamp}")

    return "\n\n".join(parts)


__all__ = ["DailyBriefingResponse", "render_for_whatsapp"]
