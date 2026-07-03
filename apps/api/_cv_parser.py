"""PdfCvParserAdapter — the pdfplumber implementation of ``CvParserPort`` (S103af, D238).

pdfplumber (MIT via pdfminer.six) is confined to this apps/infra adapter; the
daily-driver context speaks only to ``CvParserPort`` (no vendor SDK in domain, D4/D16).
The parse resolves **multi-column reading order** from word x-positions (a clean
midline gutter splits into two columns, each read top-to-bottom, left column first),
because a styled two-column CV extracts scrambled otherwise. A PDF with no extractable
text (a scanned image) yields ``has_text_layer=False`` — flagged for re-export, not
OCR'd (OCR deferred).
"""

from __future__ import annotations

import asyncio
from io import BytesIO

import pdfplumber

from contexts.daily_driver.domain.cv import CvParseError, ParsedCv

_LINE_Y_TOL = 3.0  # words within this vertical distance are the same line
_GUTTER_STRADDLE = 0.08  # ≤8% of words may straddle the midline for a 2-column split


def _line_text(words: list[dict]) -> str:
    return " ".join(w["text"] for w in sorted(words, key=lambda w: w["x0"]))


def _column_text(words: list[dict]) -> str:
    """Group a column's words into lines (cluster by ``top``), top-to-bottom."""
    if not words:
        return ""
    words = sorted(words, key=lambda w: (w["top"], w["x0"]))
    lines: list[list[dict]] = []
    cur: list[dict] = []
    cur_top: float | None = None
    for w in words:
        if cur_top is None or abs(w["top"] - cur_top) <= _LINE_Y_TOL:
            cur.append(w)
            cur_top = w["top"] if cur_top is None else cur_top
        else:
            lines.append(cur)
            cur, cur_top = [w], w["top"]
    if cur:
        lines.append(cur)
    return "\n".join(_line_text(line) for line in lines)


def _page_text(page) -> str:
    """One page in reading order: two columns when a clean midline gutter exists,
    else a single column."""
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    if not words:
        return ""
    width = page.width or max((w["x1"] for w in words), default=0.0)
    mid = width / 2
    left = [w for w in words if (w["x0"] + w["x1"]) / 2 < mid]
    right = [w for w in words if (w["x0"] + w["x1"]) / 2 >= mid]
    straddlers = [w for w in words if w["x0"] < mid < w["x1"]]
    two_column = (
        len(left) > 5 and len(right) > 5
        and len(straddlers) <= _GUTTER_STRADDLE * len(words)
    )
    if two_column:
        return _column_text(left) + "\n" + _column_text(right)
    return _column_text(words)


def _parse_sync(pdf_bytes: bytes) -> ParsedCv:
    parts: list[str] = []
    page_count = 0
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page_count = len(pdf.pages)
            for page in pdf.pages:
                t = _page_text(page)
                if t.strip():
                    parts.append(t)
    except CvParseError:
        raise
    except Exception as e:  # pdfminer/pdfplumber raise a family of exceptions
        # Not a readable PDF — surface a domain error, never a vendor exception.
        raise CvParseError(str(e)) from e
    text = "\n\n".join(parts).strip()
    return ParsedCv(
        text=text, has_text_layer=bool(text), page_count=page_count,
    )


class PdfCvParserAdapter:
    """apps/ adapter implementing ``CvParserPort`` over pdfplumber (S103af, D238)."""

    async def parse(self, *, pdf_bytes: bytes) -> ParsedCv:
        # PDF parsing is CPU-bound and synchronous — run it off the event loop.
        return await asyncio.to_thread(_parse_sync, pdf_bytes)


def build_cv_parser() -> PdfCvParserAdapter:
    """Wire the daily-driver ``CvParserPort`` over pdfplumber."""
    return PdfCvParserAdapter()


__all__ = ["PdfCvParserAdapter", "build_cv_parser"]
