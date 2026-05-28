"""Daily-briefing domain layer (D146, S54).

- ``BriefingPeriod`` — the look-back window the briefing composed over.
- ``DailyBriefingResponse`` — the composed reply satisfying CitedResponse
  (D138) plus the ``briefing_period`` extension field; ``render_for_whatsapp``
  is the D135 channel render.

Domain code is framework-free per D16 — stdlib plus shared_kernel.
"""

from contexts.daily_briefing.domain.briefing_period import BriefingPeriod
from contexts.daily_briefing.domain.response import (
    DailyBriefingResponse,
    render_for_whatsapp,
)

__all__ = [
    "BriefingPeriod",
    "DailyBriefingResponse",
    "render_for_whatsapp",
]
