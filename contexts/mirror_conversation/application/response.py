"""MirrorConversationResponse value object (D131, D138, D141, P14, S52).

Satisfies the CitedResponse Protocol from
``shared_kernel/conversation_flow.py``: carries the three citation
tuple fields plus the implementer-specific ``current_focus_artefact``
extension field used by the D141 cell_payload persistence mechanism
for drill-down anchor extraction on the next turn.

``cited_artefacts`` populates heterogeneously per the symmetric-with-
audit-conversation shape committed at D138: Case citations
(artefact_type='case') for case-listing and case-showing responses;
DataPoint citations (artefact_type='data_point') for data-point-
showing responses; both for drill-down responses that surface a child
within a parent context.

``cited_intake_records`` carries the inbound IntakeRecord id so the
read-side traces back to the message that triggered the query per
D128's intake-canonical commitment.

``cited_audit_events`` stays empty per the mirror-conversation
disposition committed at D138: mirror reads current state; the audit
chain reaches its events transitively through cited IntakeRecord
anchoring per D128.

``current_focus_artefact`` is the navigation anchor for the next
turn: when an outbound surfaces a case or data point the user might
drill into, this field carries the ArtefactCitation that the cell
persists into the outbound message's ``cell_payload`` column. On a
subsequent relative-intent turn the cell extracts this value to
resolve "tell me about revenue" against the prior focus.

The ``has_focus`` and ``has_citations`` properties simplify rendering
decisions at the channel adapter without leaking the dataclass shape.

Application code is framework-free here — stdlib only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from shared_kernel.conversation_flow import ArtefactCitation


@dataclass(frozen=True)
class MirrorConversationResponse:
    """The mirror-conversation cell's composed reply satisfying CitedResponse."""

    text: str
    cited_intake_records: tuple[UUID, ...] = field(default_factory=tuple)
    cited_audit_events: tuple[UUID, ...] = field(default_factory=tuple)
    cited_artefacts: tuple[ArtefactCitation, ...] = field(default_factory=tuple)
    current_focus_artefact: ArtefactCitation | None = None

    @property
    def has_citations(self) -> bool:
        """True when the response cites at least one source artefact."""
        return bool(
            self.cited_intake_records
            or self.cited_audit_events
            or self.cited_artefacts
        )

    @property
    def has_focus(self) -> bool:
        """True when the response carries a drill-down focus for the next turn."""
        return self.current_focus_artefact is not None


def _short_hex(identifier: UUID) -> str:
    """Short-hex prefix of a UUID for a compact citation (D131 Shape 1)."""
    return identifier.hex[:8]


def render_for_whatsapp(
    response: MirrorConversationResponse,
    *,
    composed_at: datetime,
) -> str:
    """Render MirrorConversationResponse to the WhatsApp surface text (D135).

    Mirrors the audit-conversation render shape at
    ``contexts/audit_conversation/application/response.py`` with one
    mirror-conversation-specific addition: when the response carries a
    ``current_focus_artefact`` (the navigation anchor for the next
    turn's relative-intent resolution per D141), the rendered text
    surfaces a breadcrumb line at the bottom so the operator sees
    the active drill-down context.

    Per D135 domain-decides-content channel-decides-format pattern,
    the domain layer produces the channel-agnostic content (text +
    citation tuples + focus artefact); this renderer is the WhatsApp-
    specific affordance.
    """
    parts: list[str] = [response.text.rstrip()]

    if response.has_citations:
        citation_segments: list[str] = []
        citation_segments += [
            f"ref {_short_hex(a.artefact_id)}"
            for a in response.cited_artefacts
        ]
        citation_segments += [
            f"intake {_short_hex(i)}"
            for i in response.cited_intake_records
        ]
        citation_segments += [
            f"audit {_short_hex(e)}"
            for e in response.cited_audit_events
        ]
        stamp = composed_at.strftime("%H:%M UTC")
        parts.append(f"— {' · '.join(citation_segments)} · {stamp}")

    if response.has_focus and response.current_focus_artefact is not None:
        focus = response.current_focus_artefact
        kind_label = (
            "case" if focus.artefact_type == "case" else "data point"
        )
        parts.append(
            f"↳ context: {kind_label} {_short_hex(focus.artefact_id)}"
        )

    return "\n\n".join(parts)


def serialise_focus_to_cell_payload(
    focus: ArtefactCitation,
) -> dict[str, object]:
    """Serialise an ArtefactCitation into the D141 cell_payload shape.

    The cell calls this when constructing outbound messages so the
    next turn can extract the focus from the prior outbound's
    cell_payload column. The serialised shape is the implementer-
    specific structure committed at D141: a single
    ``current_focus_artefact`` key whose value is a dict carrying the
    artefact id and discriminator.
    """
    return {
        "current_focus_artefact": {
            "artefact_id": str(focus.artefact_id),
            "artefact_type": focus.artefact_type,
        },
    }


def extract_focus_from_cell_payload(
    payload: dict | None,
) -> ArtefactCitation | None:
    """Extract the focus from a prior mirror-conversation outbound's cell_payload.

    Implementer-side validation per D141: when the payload's shape does
    not match the expected structure (e.g., the prior outbound was
    written by a different ConversationFlow implementer), return
    ``None`` so the cell treats the absence as no-prior-focus and
    routes through D139 to D134 clarification per the no-prior-focus
    edge case.
    """
    if not payload or not isinstance(payload, dict):
        return None
    raw = payload.get("current_focus_artefact")
    if not isinstance(raw, dict):
        return None
    artefact_id = raw.get("artefact_id")
    artefact_type = raw.get("artefact_type")
    if (
        not isinstance(artefact_id, str)
        or not isinstance(artefact_type, str)
        or not artefact_type
    ):
        return None
    try:
        return ArtefactCitation(
            artefact_id=UUID(artefact_id),
            artefact_type=artefact_type,
        )
    except (ValueError, TypeError):
        return None


__all__ = [
    "MirrorConversationResponse",
    "extract_focus_from_cell_payload",
    "render_for_whatsapp",
    "serialise_focus_to_cell_payload",
]
