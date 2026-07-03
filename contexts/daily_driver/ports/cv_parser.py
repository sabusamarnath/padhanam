"""CvParserPort — parse a CV PDF behind the vendor seam (S103af, D238).

The daily-driver context calls this small consumer port; the PDF library (pdfplumber,
MIT via pdfminer.six) lives in an apps/infra adapter, so no vendor SDK enters domain
code (D4/D16). The adapter resolves text-layer + multi-column reading order; OCR is
deferred — a scanned PDF returns ``has_text_layer=False`` to be flagged for re-export.
"""

from __future__ import annotations

from typing import Protocol

from contexts.daily_driver.domain.cv import ParsedCv


class CvParserPort(Protocol):
    """Parse a CV PDF's text (S103af, D238)."""

    async def parse(self, *, pdf_bytes: bytes) -> ParsedCv:
        """Return the parsed CV. When the PDF has no text layer (scanned), returns
        ``ParsedCv(text="", has_text_layer=False, ...)`` — the caller flags it for a
        text-layer re-export (OCR deferred)."""
        ...


__all__ = ["CvParserPort"]
