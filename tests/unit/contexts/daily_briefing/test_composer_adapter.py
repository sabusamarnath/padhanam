"""Unit tests for the LiteLLM daily-briefing composer adapter (D130, D146, S54)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from contexts.daily_briefing.adapters.llm.litellm_daily_briefing_composer_adapter import (  # noqa: E501
    DAILY_BRIEFING_SCHEMA,
    LiteLLMDailyBriefingComposerAdapter,
    build_daily_briefing_prompt,
)
from contexts.daily_briefing.application.ports.daily_briefing_reader import (
    DailyBriefingAuditEvent,
    DailyBriefingCase,
    DailyBriefingIntakeRecord,
)
from contexts.daily_briefing.domain.briefing_period import BriefingPeriod
from shared_kernel import StructuredOutputRequest, StructuredOutputResponse


def _period() -> BriefingPeriod:
    end = datetime(2026, 5, 28, 6, 0, tzinfo=timezone.utc)
    return BriefingPeriod(window_start=end - timedelta(hours=24), window_end=end)


class _FakeStructuredOutput:
    def __init__(self, value: dict) -> None:
        self._value = value
        self.requests: list[StructuredOutputRequest] = []

    async def generate_structured(
        self, request: StructuredOutputRequest
    ) -> StructuredOutputResponse[dict]:
        self.requests.append(request)
        return StructuredOutputResponse(
            value=self._value, confidence=None, provider_metadata={}
        )


def test_prompt_interpolates_all_sections() -> None:
    prompt = build_daily_briefing_prompt(
        briefing_period=_period(),
        intake_records=(
            DailyBriefingIntakeRecord(
                intake_id=uuid4(),
                intake_source="WHATSAPP_INBOUND",
                summary="logged revenue",
                created_at=datetime(2026, 5, 28, 5, 0, tzinfo=timezone.utc),
            ),
        ),
        audit_events=(),
        active_cases=(
            DailyBriefingCase(
                case_id=uuid4(),
                title="Q3 review",
                status="OPEN",
                created_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
            ),
        ),
    )
    assert "logged revenue" in prompt
    assert "Q3 review" in prompt
    assert "(no state changes recorded during the window)" in prompt
    assert "{window}" not in prompt  # all placeholders interpolated


def test_compose_returns_model_narrative() -> None:
    fake = _FakeStructuredOutput({"briefing": "Two changes; 3 active cases."})
    adapter = LiteLLMDailyBriefingComposerAdapter(structured_output_port=fake)
    content = asyncio.run(
        adapter.compose(
            briefing_period=_period(),
            intake_records=(),
            audit_events=(),
            active_cases=(),
        )
    )
    assert content.prose_narrative == "Two changes; 3 active cases."
    # the request used the briefing schema
    assert fake.requests[0].schema == DAILY_BRIEFING_SCHEMA


def test_compose_falls_back_when_model_returns_empty() -> None:
    """An empty model narrative still yields a non-empty briefing (D146 always-send)."""
    fake = _FakeStructuredOutput({"briefing": "   "})
    adapter = LiteLLMDailyBriefingComposerAdapter(structured_output_port=fake)
    content = asyncio.run(
        adapter.compose(
            briefing_period=_period(),
            intake_records=(),
            audit_events=(),
            active_cases=(),
        )
    )
    assert content.prose_narrative
    assert "active case" in content.prose_narrative
