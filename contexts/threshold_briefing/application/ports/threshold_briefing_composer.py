"""ThresholdBriefingComposer consumer port — LLM composition (D130, D153, S57).

The threshold-briefing's LLM-call surface. It takes the crossing
read-model and returns the proactive prose the operator reads. Per D130
the composition uses the StructuredOutputPort substrate at the
REAL_TIME_REQUIRED latency tier (D122); the LiteLLM-backed adapter lives
at ``contexts/threshold_briefing/adapters/llm/``.

The composer consumes the threshold-owned ``ThresholdCrossing`` read-model
(not calendar domain types). It always returns a non-empty narrative; an
unavailable composer is handled by the implementer falling back to the
crossing's own summary, not by this port returning empty.

Framework-free per D16 — stdlib plus shared_kernel only.
"""

from __future__ import annotations

from typing import Protocol

from contexts.threshold_briefing.domain.crossing import ThresholdCrossing


class ThresholdBriefingComposer(Protocol):
    """LLM composition port for the threshold-briefing implementer (D153)."""

    async def compose(self, *, crossing: ThresholdCrossing) -> str:
        """Compose the proactive briefing prose for one crossing.

        Returns a non-empty narrative describing what changed and why it
        is surfaced now.
        """
        ...


__all__ = ["ThresholdBriefingComposer"]
