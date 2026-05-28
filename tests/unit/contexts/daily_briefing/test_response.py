"""Unit tests for DailyBriefingResponse + BriefingPeriod (D138, D146, S54)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from contexts.daily_briefing.domain import (
    BriefingPeriod,
    DailyBriefingResponse,
    render_for_whatsapp,
)
from shared_kernel.conversation_flow import ArtefactCitation, CitedResponse


def _period() -> BriefingPeriod:
    end = datetime(2026, 5, 28, 6, 0, tzinfo=timezone.utc)
    return BriefingPeriod(window_start=end - timedelta(hours=24), window_end=end)


def test_briefing_period_rejects_inverted_window() -> None:
    end = datetime(2026, 5, 28, 6, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="strictly after"):
        BriefingPeriod(window_start=end, window_end=end - timedelta(hours=1))


def test_response_satisfies_cited_response_protocol() -> None:
    """DailyBriefingResponse satisfies CitedResponse structurally (D138)."""
    response = DailyBriefingResponse(
        text="Your portfolio stands at 3 cases.",
        briefing_period=_period(),
        cited_artefacts=(
            ArtefactCitation(artefact_id=uuid4(), artefact_type="case"),
        ),
    )
    assert isinstance(response, CitedResponse)


def test_empty_day_response_still_satisfies_protocol() -> None:
    """An empty-day briefing (no citations) still satisfies the Protocol."""
    response = DailyBriefingResponse(
        text="Nothing changed in the last 24 hours.",
        briefing_period=_period(),
    )
    assert isinstance(response, CitedResponse)
    assert response.has_citations is False


def test_render_includes_briefing_period_header() -> None:
    response = DailyBriefingResponse(
        text="One new data point on the Q3 review.",
        briefing_period=_period(),
        cited_intake_records=(uuid4(),),
        cited_artefacts=(
            ArtefactCitation(artefact_id=uuid4(), artefact_type="case"),
        ),
    )
    rendered = render_for_whatsapp(
        response, composed_at=datetime(2026, 5, 28, 6, 0, tzinfo=timezone.utc)
    )
    assert rendered.startswith("Daily briefing · ")
    assert "One new data point" in rendered
    assert "ref " in rendered
    assert "intake " in rendered


def test_render_empty_day_has_header_and_prose_no_citation_line() -> None:
    response = DailyBriefingResponse(
        text="Quiet day. Your portfolio stands at 2 cases.",
        briefing_period=_period(),
    )
    rendered = render_for_whatsapp(
        response, composed_at=datetime(2026, 5, 28, 6, 0, tzinfo=timezone.utc)
    )
    assert rendered.startswith("Daily briefing · ")
    assert "Quiet day" in rendered
    assert "—" not in rendered  # no citation footer when no citations
