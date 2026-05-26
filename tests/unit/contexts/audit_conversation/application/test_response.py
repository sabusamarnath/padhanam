"""Unit tests for the AuditConversationResponse CitedResponse-conformance (S51)."""

from __future__ import annotations

from uuid import uuid4

from contexts.audit_conversation.application.response import (
    AuditConversationResponse,
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
