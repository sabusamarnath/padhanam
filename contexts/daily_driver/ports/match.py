"""MatchPort — the LLM match of a role's selection criteria against the confirmed
skills profile, behind the inference seam (S103ag, D239). Matching-engine leg 3.

Mirrors ``JdExtractorPort`` (S103ad, D236) / ``CvExtractorPort`` (S103af, D238): the
match calls the provider-agnostic ``StructuredOutputPort`` (the inference LiteLLM
adapter), so the daily-driver context speaks to a small consumer port and never
holds the adapter or imports a vendor SDK. The apps composition root binds this port
to an adapter that assembles the request from the pure domain schema/prompt
(``contexts.daily_driver.domain.matching``) and parses the response, grounded-strict,
into per-criterion coverages.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.matching import CriterionCoverage


class MatchPort(Protocol):
    """Assess each selection criterion against the confirmed profile (S103ag, D239)."""

    async def match(
        self, *, criteria: tuple[str, ...], skills: tuple[str, ...],
        experiences: tuple[str, ...],
    ) -> tuple[CriterionCoverage, ...] | None:
        """Return one coverage verdict per input criterion (grounded-strict), or
        ``None`` when the model produced no schema-conforming output (the caller
        persists nothing)."""
        ...


__all__ = ["MatchPort"]
