"""CellResponse and citation rendering for the manual entry cell (D131, S46).

D131 commits provenance-aware response composition: a response to a
user carries explicit citation links to the source artefacts that
contributed. The manual entry cell is D131's first implementer.

``CellResponse`` is the cell's composed reply — the operator-facing
``text`` plus three citation-id tuples. ``render_for_whatsapp``
renders it to the WhatsApp surface in D131 Shape 1: compact textual
citations (a short-hex prefix per cited artefact and intake record,
plus the composition timestamp).

``cited_audit_events`` stays empty at S46 — the intake-owned
write-result DTOs do not surface audit-event ids (recorded at
`charter/captures.md`). The field exists on the value object so the
shape is stable for the P14+ implementer that fills it.

Application code is framework-free here — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class CellResponse:
    """The cell's composed reply with D131 citation fields.

    A confirmation response (a successful write) carries citations; a
    clarification response (UnclearIntent, an ambiguous or unresolved
    target) carries none.
    """

    text: str
    cited_intake_records: tuple[UUID, ...] = field(default_factory=tuple)
    cited_audit_events: tuple[UUID, ...] = field(default_factory=tuple)
    cited_artefacts: tuple[UUID, ...] = field(default_factory=tuple)

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
        f"ref {_short_hex(a)}" for a in response.cited_artefacts
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
