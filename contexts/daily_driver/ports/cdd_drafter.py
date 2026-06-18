"""CddDrafterPort — the LLM draft of a goal's CDD, behind the inference seam (S102, D200).

The draft calls the provider-agnostic ``StructuredOutputPort`` (the inference
LiteLLM adapter), so the daily-driver context speaks to a small consumer port and
never holds the adapter or imports a vendor SDK — the checkin reply-parse
precedent. The apps composition root binds this port to an adapter that assembles
the request from the pure domain schema/prompt (``contexts.daily_driver.domain.cdd``)
and parses the response back into a ``DraftedCdd``.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.cdd import DraftedCdd


class CddDrafterPort(Protocol):
    """Draft a goal's CDD through the structured-output seam (S102, D200)."""

    async def draft(
        self, *, goal_name: str, mode: str, lever_names: tuple[str, ...]
    ) -> DraftedCdd | None:
        """Return the LLM's drafted CDD for the goal, or ``None`` when the model
        produced no schema-conforming output (the caller persists nothing)."""
        ...


__all__ = ["CddDrafterPort"]
