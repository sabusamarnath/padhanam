"""LiteLLM-backed ThresholdBriefingComposer adapter (D130, D122, D153, S57).

Implements the ``ThresholdBriefingComposer`` port via the existing
``StructuredOutputPort`` (D130) at the ``REAL_TIME_REQUIRED`` latency tier
(D122) — mirroring the daily-briefing composer adapter. The structured
schema is a single prose field (``briefing``); the prompt template at
``contexts/threshold_briefing/prompts/compose_threshold_briefing.md``
carries the Private Assistant voice plus the read-only-surface restraint.

The adapter has no vendor dependency of its own (LiteLLM enters via the
StructuredOutputPort at the inference adapter). Stateless; one instance
serves every fire. The prompt template loads once at import time.
"""

from __future__ import annotations

from pathlib import Path

from contexts.threshold_briefing.domain.crossing import ThresholdCrossing
from shared_kernel import (
    LatencyTier,
    StructuredOutputPort,
    StructuredOutputRequest,
)

_PROMPT_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "prompts"
    / "compose_threshold_briefing.md"
)
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8")

THRESHOLD_BRIEFING_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "briefing": {
            "type": "string",
            "description": "The proactive threshold heads-up (1–3 sentences).",
        }
    },
    "required": ["briefing"],
}


def build_threshold_briefing_prompt(*, crossing: ThresholdCrossing) -> str:
    """Interpolate the crossing into the prompt template."""
    return (
        _PROMPT_TEMPLATE.replace("{rule_type}", crossing.rule_type or "(unknown)")
        .replace("{summary}", crossing.summary or "(no summary)")
        .replace("{title}", crossing.title or "(untitled)")
        .replace("{partner_title}", crossing.partner_title or "(none)")
        .replace("{cancelled_at}", crossing.cancelled_at or "(n/a)")
    )


class LiteLLMThresholdBriefingComposerAdapter:
    """LiteLLM-backed adapter for the ThresholdBriefingComposer port (D153)."""

    def __init__(
        self,
        *,
        structured_output_port: StructuredOutputPort,
        latency_tier: LatencyTier = LatencyTier.REAL_TIME_REQUIRED,
    ) -> None:
        self._structured_output = structured_output_port
        self._latency_tier = latency_tier

    async def compose(self, *, crossing: ThresholdCrossing) -> str:
        prompt = build_threshold_briefing_prompt(crossing=crossing)
        request = StructuredOutputRequest(
            prompt=prompt,
            schema=THRESHOLD_BRIEFING_SCHEMA,
            latency_tier=self._latency_tier,
            temperature=0.3,
        )
        result = await self._structured_output.generate_structured(request)
        narrative = str(result.value.get("briefing", "")).strip()
        # Defensive: a model returning an empty string still yields a
        # non-empty heads-up (the implementer also falls back to the
        # crossing summary, but keep the adapter honest too).
        return narrative or crossing.summary


__all__ = [
    "THRESHOLD_BRIEFING_SCHEMA",
    "LiteLLMThresholdBriefingComposerAdapter",
    "build_threshold_briefing_prompt",
]
