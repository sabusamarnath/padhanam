"""JdExtractorPort — the LLM extraction of a job description, behind the inference
seam (S103ad, D236).

Mirrors ``CddDrafterPort`` (S102, D200): the extraction calls the provider-agnostic
``StructuredOutputPort`` (the inference LiteLLM adapter), so the daily-driver context
speaks to a small consumer port and never holds the adapter or imports a vendor SDK.
The apps composition root binds this port to an adapter that assembles the request
from the pure domain schema/prompt (``contexts.daily_driver.domain.jd_extraction``)
and parses the response into an ``ExtractedDemand``.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.jd_extraction import ExtractedDemand


class JdExtractorPort(Protocol):
    """Extract the demand (two context fields + N discrete requirements) from a job
    description (S103ad/D236, deepened S103ah/D240)."""

    async def extract(self, *, jd_text: str) -> ExtractedDemand | None:
        """Return the extracted demand for the job description, or ``None`` when the
        model produced no schema-conforming output (the caller persists nothing)."""
        ...


__all__ = ["JdExtractorPort"]
