"""CvExtractorPort — the LLM extraction of a skills profile from CV text, behind the
inference seam (S103af, D238).

Mirrors ``JdExtractorPort`` (S103ad, D236): the extraction calls the provider-agnostic
``StructuredOutputPort`` (the inference LiteLLM adapter), so the daily-driver context
speaks to a small consumer port and never holds the adapter or imports a vendor SDK.
The apps composition root binds this port to an adapter that assembles the request
from the pure domain schema/prompt (``contexts.daily_driver.domain.cv_extraction``)
and parses the response into an ``ExtractedProfile``.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.cv_extraction import ExtractedProfile


class CvExtractorPort(Protocol):
    """Extract a skills profile (skills + experiences) from CV text (S103af, D238)."""

    async def extract(self, *, cv_text: str) -> ExtractedProfile | None:
        """Return the drafted profile for the CV text, or ``None`` when the model
        produced no schema-conforming output (the caller persists nothing)."""
        ...


__all__ = ["CvExtractorPort"]
