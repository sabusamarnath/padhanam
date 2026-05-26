"""CellResponse and citation rendering for the manual entry cell (D131, S46; D138, S51).

D131 commits provenance-aware response composition: a response to a
user carries explicit citation links to the source artefacts that
contributed. The manual entry cell is D131's first implementer.

D138 commits the cross-cutting structural enforcement at S51: a
runtime-checkable ``CitedResponse`` Protocol at ``shared_kernel/
conversation_flow.py`` carrying three citation tuple fields, with
``cited_artefacts`` as ``tuple[ArtefactCitation, ...]`` (the typed
value object with an artefact-type discriminator). CellResponse
refactored at S51 commit 2 to satisfy the Protocol structurally —
the ``cited_artefacts`` field type changes from ``tuple[UUID, ...]``
to ``tuple[ArtefactCitation, ...]``; five cite sites at
``manual_entry_cell.py`` wrap UUIDs as ``ArtefactCitation``; the
render layer here calls ``_short_hex(a.artefact_id)``.

``CellResponse`` is the cell's composed reply — the operator-facing
``text`` plus three citation tuples. ``render_for_whatsapp`` renders
it to the WhatsApp surface in D131 Shape 1: compact textual citations
(a short-hex prefix per cited artefact and intake record, plus the
composition timestamp).

``cited_audit_events`` stays empty at S46/S51 for CellResponse — the
intake-owned write-result DTOs do not surface audit-event ids
(recorded at ``charter/captures.md``; closed-at-read-side per the
P14 framing captures entry; audit-conversation populates the field
at S51 from its query result). The field exists on the value object
so the Protocol shape is satisfied.

Application code is framework-free here — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from shared_kernel.conversation_flow import ArtefactCitation


@dataclass(frozen=True)
class CellResponse:
    """The cell's composed reply satisfying the CitedResponse Protocol.

    A confirmation response (a successful write) carries citations; a
    clarification response (UnclearIntent, an ambiguous or unresolved
    target) carries none.
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
    """The short-hex prefix of a UUID for a compact citation (Shape 1)."""
    return identifier.hex[:8]


def render_for_whatsapp(
    response: CellResponse, *, composed_at: datetime
) -> str:
    """Render a CellResponse to the WhatsApp surface text.

    D131 Shape 1: a response that cites artefacts renders its text
    followed by a compact citation line — a short-hex prefix per cited
    artefact, intake record, and audit event, plus the composition
    time. A clarification response (no citations) renders as its text
    alone.
    """
    if not response.has_citations:
        return response.text
    parts: list[str] = [
        f"ref {_short_hex(a.artefact_id)}" for a in response.cited_artefacts
    ]
    parts += [
        f"intake {_short_hex(i)}" for i in response.cited_intake_records
    ]
    parts += [
        f"audit {_short_hex(e)}" for e in response.cited_audit_events
    ]
    citation_line = " · ".join(parts)
    stamp = composed_at.strftime("%H:%M UTC")
    return f"{response.text}\n\n— {citation_line} · {stamp}"


__all__ = ["CellResponse", "render_for_whatsapp"]
