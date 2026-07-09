"""CriticalityPort — the LLM criticality assessment of a role's requirements against the
addressable demand spec, behind the inference seam (S103ai, D241).

Mirrors ``MatchPort`` (D239) / ``JdExtractorPort`` (D236): the assessment calls the
provider-agnostic ``StructuredOutputPort``, so the daily-driver context speaks to a small
consumer port and never holds the adapter or imports a vendor SDK. The apps composition
root binds this port to an adapter that assembles the request from the pure domain
schema/prompt (``contexts.daily_driver.domain.criticality``) and parses the response,
grounded-strict (references validated to resolve against the spec index), into one
criticality assessment per requirement.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.demand_spec import DemandSpecIndex


class CriticalityPort(Protocol):
    """Assess each requirement's criticality against the addressable demand spec
    (S103ai, D241)."""

    async def assess(
        self, *, requirement_texts: tuple[str, ...], spec_index: DemandSpecIndex,
    ) -> dict[str, dict] | None:
        """Return a parsed, grounded-strict criticality assessment per requirement, keyed
        by normalized requirement text (spans validated to resolve; ungrounded claims
        forced low-confidence), or ``None`` when the model produced no schema-conforming
        output (the caller persists nothing)."""
        ...


__all__ = ["CriticalityPort"]
