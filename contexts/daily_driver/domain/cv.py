"""CV parsing value objects — pure (S103af, D238). Stdlib only (D16); no PDF SDK here.

The PDF parse (text-layer + multi-column reading order) happens in the apps/infra
adapter behind ``CvParserPort``; this holds only the parsed-result shape the domain
and use cases speak in. A CV with no text layer (a scanned image) is not OCR'd —
``has_text_layer=False`` flags it for the operator to re-export a text-layer PDF.
"""

from __future__ import annotations

from dataclasses import dataclass


class CvParseError(Exception):
    """The uploaded bytes are not a readable PDF (S103af, D238) — the adapter raises
    this instead of leaking a vendor exception, so the caller can return a 422. A
    *readable* PDF with no text layer is not an error — that is ``has_text_layer=False``."""


@dataclass(frozen=True)
class ParsedCv:
    """The result of parsing a CV PDF (S103af, D238).

    ``text`` is the extracted text in reading order (multi-column resolved by the
    adapter). ``has_text_layer`` is False when the PDF yielded no extractable text
    (a scanned/image PDF) — the caller flags it for re-export rather than OCR'ing
    (OCR deferred). ``page_count`` is informational.
    """

    text: str
    has_text_layer: bool
    page_count: int = 0


__all__ = ["CvParseError", "ParsedCv"]
