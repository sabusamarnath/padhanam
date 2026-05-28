"""LiteLLM-backed DailyBriefingComposer adapter (D130, D122, D146, S54).

Implements the ``DailyBriefingComposer`` port via the existing
``StructuredOutputPort`` (D130) at the ``REAL_TIME_REQUIRED`` latency
tier (D122). The structured-output schema is a single prose field
(``briefing``); the prompt template at
``contexts/daily_briefing/prompts/compose_daily_briefing.md`` carries
the Private Assistant voice plus the empty-day-prose-adjustment
instruction.

Sits at ``contexts/daily_briefing/adapters/llm/`` — the adapter has no
vendor dependency of its own (LiteLLM enters via the StructuredOutputPort
implementation at the inference adapter). The adapter is stateless; one
instance serves every fire. The prompt template loads once at import
time from disk (mirroring the ingestion extractor's prompts/ pattern).
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from contexts.daily_briefing.application.ports.daily_briefing_composer import (
    DailyBriefingComposedContent,
)
from contexts.daily_briefing.application.ports.daily_briefing_reader import (
    DailyBriefingAuditEvent,
    DailyBriefingCase,
    DailyBriefingIntakeRecord,
)
from contexts.daily_briefing.domain.briefing_period import BriefingPeriod
from shared_kernel import (
    LatencyTier,
    StructuredOutputPort,
    StructuredOutputRequest,
)

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts"
    / "compose_daily_briefing.md"
)
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

DAILY_BRIEFING_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "briefing": {
            "type": "string",
            "description": "The prose daily briefing (2–5 sentences).",
        }
    },
    "required": ["briefing"],
}


def _format_window(period: BriefingPeriod) -> str:
    return (
        f"{period.window_start.isoformat()} to {period.window_end.isoformat()}"
    )


def _format_activity(records: tuple[DailyBriefingIntakeRecord, ...]) -> str:
    if not records:
        return "(no items entered the platform during the window)"
    lines = [
        f"- [{r.created_at.isoformat()}] {r.intake_source}: {r.summary}"
        for r in records
    ]
    return "\n".join(lines)


def _format_changes(events: tuple[DailyBriefingAuditEvent, ...]) -> str:
    if not events:
        return "(no state changes recorded during the window)"
    lines = [
        f"- [{e.timestamp.isoformat()}] {e.action_verb} on {e.resource_type}"
        for e in events
    ]
    return "\n".join(lines)


def _format_snapshot(cases: tuple[DailyBriefingCase, ...]) -> str:
    if not cases:
        return "(no active cases)"
    lines = [f"- {c.title} ({c.status})" for c in cases]
    return "\n".join(lines)


def build_daily_briefing_prompt(
    *,
    briefing_period: BriefingPeriod,
    intake_records: tuple[DailyBriefingIntakeRecord, ...],
    audit_events: tuple[DailyBriefingAuditEvent, ...],
    active_cases: tuple[DailyBriefingCase, ...],
) -> str:
    """Interpolate the briefing inputs into the prompt template."""
    return (
        _PROMPT_TEMPLATE.replace("{window}", _format_window(briefing_period))
        .replace("{recent_activity}", _format_activity(intake_records))
        .replace("{recent_changes}", _format_changes(audit_events))
        .replace("{portfolio_snapshot}", _format_snapshot(active_cases))
    )


class LiteLLMDailyBriefingComposerAdapter:
    """LiteLLM-backed adapter for the DailyBriefingComposer port (D146)."""

    def __init__(
        self,
        *,
        structured_output_port: StructuredOutputPort,
        latency_tier: LatencyTier = LatencyTier.REAL_TIME_REQUIRED,
    ) -> None:
        self._structured_output = structured_output_port
        self._latency_tier = latency_tier

    async def compose(
        self,
        *,
        briefing_period: BriefingPeriod,
        intake_records: tuple[DailyBriefingIntakeRecord, ...],
        audit_events: tuple[DailyBriefingAuditEvent, ...],
        active_cases: tuple[DailyBriefingCase, ...],
    ) -> DailyBriefingComposedContent:
        prompt = build_daily_briefing_prompt(
            briefing_period=briefing_period,
            intake_records=intake_records,
            audit_events=audit_events,
            active_cases=active_cases,
        )
        request = StructuredOutputRequest(
            prompt=prompt,
            schema=DAILY_BRIEFING_SCHEMA,
            latency_tier=self._latency_tier,
            temperature=0.3,
        )
        result = await self._structured_output.generate_structured(request)
        narrative = str(result.value.get("briefing", "")).strip()
        if not narrative:
            # Defensive: the schema requires the field, but a model that
            # returns an empty string still gets a non-empty briefing so
            # the always-send commitment (D146) holds.
            narrative = (
                f"Briefing for {_format_window(briefing_period)}: "
                f"{len(active_cases)} active case(s); "
                f"{len(intake_records)} new item(s); "
                f"{len(audit_events)} change(s) recorded."
            )
        return DailyBriefingComposedContent(prose_narrative=narrative)


__all__ = [
    "DAILY_BRIEFING_SCHEMA",
    "LiteLLMDailyBriefingComposerAdapter",
    "build_daily_briefing_prompt",
]
