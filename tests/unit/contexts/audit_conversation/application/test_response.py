"""Unit tests for the AuditConversationResponse CitedResponse-conformance + render (S51)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contexts.audit_conversation.application.response import (
    AuditConversationResponse,
    render_for_whatsapp,
)
from shared_kernel.conversation_flow import ArtefactCitation, CitedResponse


def test_audit_response_satisfies_cited_response_protocol() -> None:
    response = AuditConversationResponse(text="x")
    assert isinstance(response, CitedResponse)


def test_audit_response_has_citations_property() -> None:
    response_empty = AuditConversationResponse(text="x")
    assert not response_empty.has_citations

    citation = ArtefactCitation(artefact_id=uuid4(), artefact_type="case")
    response_full = AuditConversationResponse(
        text="x",
        cited_audit_events=(uuid4(),),
        cited_artefacts=(citation,),
    )
    assert response_full.has_citations


def test_audit_response_holds_heterogeneous_artefact_citations() -> None:
    case_cit = ArtefactCitation(artefact_id=uuid4(), artefact_type="case")
    dp_cit = ArtefactCitation(artefact_id=uuid4(), artefact_type="data_point")
    response = AuditConversationResponse(
        text="x", cited_artefacts=(case_cit, dp_cit)
    )
    assert response.cited_artefacts == (case_cit, dp_cit)
    assert response.cited_artefacts[0].artefact_type == "case"
    assert response.cited_artefacts[1].artefact_type == "data_point"


_COMPOSED_AT = datetime(2026, 5, 26, 14, 30, tzinfo=timezone.utc)


def test_render_for_whatsapp_no_citations_returns_text_alone() -> None:
    response = AuditConversationResponse(text="No audit events matched.")
    rendered = render_for_whatsapp(response, composed_at=_COMPOSED_AT)
    assert rendered == "No audit events matched."


def test_render_for_whatsapp_with_audit_events_and_artefacts_shape_1() -> None:
    audit_id = uuid4()
    case_cit = ArtefactCitation(artefact_id=uuid4(), artefact_type="case")
    response = AuditConversationResponse(
        text="Audit events: 1 found.",
        cited_audit_events=(audit_id,),
        cited_artefacts=(case_cit,),
    )
    rendered = render_for_whatsapp(response, composed_at=_COMPOSED_AT)
    assert "Audit events: 1 found." in rendered
    assert f"audit {audit_id.hex[:8]}" in rendered
    assert f"ref {case_cit.artefact_id.hex[:8]}" in rendered
    assert "14:30 UTC" in rendered
    # Citation line uses the middle-dot separator.
    assert "·" in rendered
