"""Unit tests for the mirror-conversation WhatsApp render (D131, D135, D141, P14, S52)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from contexts.mirror_conversation.application.response import (
    MirrorConversationResponse,
    render_for_whatsapp,
)
from shared_kernel.conversation_flow import ArtefactCitation


_COMPOSED_AT = datetime(2026, 5, 27, 14, 30, tzinfo=timezone.utc)


def test_clarification_response_renders_as_text_only() -> None:
    response = MirrorConversationResponse(text="Could you clarify?")
    rendered = render_for_whatsapp(response, composed_at=_COMPOSED_AT)
    assert rendered == "Could you clarify?"


def test_cited_response_appends_shape_one_citation_line() -> None:
    artefact_id = UUID("12345678-1234-4abc-9def-abcdef123456")
    response = MirrorConversationResponse(
        text="You have 1 case: Q3 review.",
        cited_artefacts=(
            ArtefactCitation(artefact_id=artefact_id, artefact_type="case"),
        ),
    )
    rendered = render_for_whatsapp(response, composed_at=_COMPOSED_AT)
    assert "You have 1 case" in rendered
    assert "ref 12345678" in rendered
    assert "14:30 UTC" in rendered


def test_focus_only_response_renders_breadcrumb() -> None:
    case_id = UUID("87654321-4321-4abc-9def-abcdef654321")
    response = MirrorConversationResponse(
        text="No siblings here.",
        current_focus_artefact=ArtefactCitation(
            artefact_id=case_id, artefact_type="data_point"
        ),
    )
    rendered = render_for_whatsapp(response, composed_at=_COMPOSED_AT)
    assert "No siblings here." in rendered
    assert "↳ context: data point 87654321" in rendered


def test_cited_plus_focus_renders_both_lines() -> None:
    case_id = uuid4()
    dp_id = uuid4()
    response = MirrorConversationResponse(
        text="Q3 review (OPEN). 1 data point: revenue.",
        cited_artefacts=(
            ArtefactCitation(artefact_id=case_id, artefact_type="case"),
            ArtefactCitation(artefact_id=dp_id, artefact_type="data_point"),
        ),
        current_focus_artefact=ArtefactCitation(
            artefact_id=case_id, artefact_type="case"
        ),
    )
    rendered = render_for_whatsapp(response, composed_at=_COMPOSED_AT)
    lines = rendered.split("\n\n")
    assert len(lines) == 3
    assert lines[0].startswith("Q3 review")
    assert lines[1].startswith("—")
    assert "ref" in lines[1]
    assert lines[2].startswith("↳ context:")


def test_intake_and_audit_citations_render_with_prefixes() -> None:
    intake_id = UUID("aaaaaaaa-aaaa-4aaa-9aaa-aaaaaaaaaaaa")
    audit_id = UUID("bbbbbbbb-bbbb-4bbb-9bbb-bbbbbbbbbbbb")
    response = MirrorConversationResponse(
        text="audit query result.",
        cited_intake_records=(intake_id,),
        cited_audit_events=(audit_id,),
    )
    rendered = render_for_whatsapp(response, composed_at=_COMPOSED_AT)
    assert "intake aaaaaaaa" in rendered
    assert "audit bbbbbbbb" in rendered
