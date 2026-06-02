"""Unit tests for CalendarConversationResponse (D138, D148, S55b-1)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contexts.calendar_conversation.application.response import (
    CalendarConversationResponse,
    meeting_citation,
    render_for_whatsapp,
)
from shared_kernel.conversation_flow import CitedResponse


def test_response_satisfies_cited_response_protocol() -> None:
    response = CalendarConversationResponse(text="x")
    assert isinstance(response, CitedResponse)


def test_meeting_citation_uses_meeting_discriminator() -> None:
    mid = uuid4()
    citation = meeting_citation(mid)
    assert citation.artefact_id == mid
    assert citation.artefact_type == "meeting"


def test_render_appends_citation_line_and_staleness_note() -> None:
    mid = uuid4()
    response = CalendarConversationResponse(
        text="Meetings today: 1 found.\n- 2026-06-02 15:00 Board sync",
        cited_artefacts=(meeting_citation(mid),),
        staleness_note="Showing cached calendar; live refresh timed out.",
    )
    rendered = render_for_whatsapp(
        response, composed_at=datetime(2026, 6, 2, 14, 30, tzinfo=timezone.utc)
    )
    assert "Board sync" in rendered
    assert "cached calendar" in rendered  # staleness note present
    assert f"meeting {mid.hex[:8]}" in rendered  # citation line
    assert "14:30 UTC" in rendered


def test_render_no_citation_is_text_only() -> None:
    response = CalendarConversationResponse(text="No meetings today.")
    rendered = render_for_whatsapp(
        response, composed_at=datetime(2026, 6, 2, 14, 30, tzinfo=timezone.utc)
    )
    assert rendered == "No meetings today."
