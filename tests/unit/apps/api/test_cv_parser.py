"""The pdfplumber CV parser adapter: multi-column reading order + the not-a-PDF
error (S103af, D238). The column logic is tested on fake pages (no PDF fixture);
the vendor-error path is tested on real garbage bytes through pdfplumber."""

from __future__ import annotations

import asyncio

import pytest

from apps.api._cv_parser import (
    _column_text,
    _page_text,
    build_cv_parser,
)
from contexts.daily_driver.domain.cv import CvParseError


def _w(text: str, x0: float, top: float) -> dict:
    return {"text": text, "x0": x0, "x1": x0 + 20, "top": top, "bottom": top + 10}


class _FakePage:
    def __init__(self, words: list[dict], width: float = 600.0) -> None:
        self._words = words
        self.width = width

    def extract_words(self, **_kw) -> list[dict]:
        return self._words


def test_column_text_groups_lines_top_to_bottom_and_joins_by_x() -> None:
    words = [_w("world", 120, 0), _w("hello", 100, 0), _w("next", 100, 30)]
    assert _column_text(words) == "hello world\nnext"


def test_page_text_two_columns_reads_whole_left_then_whole_right() -> None:
    # left column at x~50, right column at x~400 on a 600-wide page; a clean gutter.
    left = [_w(f"L{i}", 50, i * 20) for i in range(6)]
    right = [_w(f"R{i}", 400, i * 20) for i in range(6)]
    page = _FakePage(left + right, width=600)
    out = _page_text(page)
    assert out.index("L5") < out.index("R0")  # all left before any right


def test_page_text_single_column_when_no_clean_gutter() -> None:
    # words spread across the midline (straddlers / centred) -> single column, so
    # reading order is purely top-to-bottom regardless of x.
    words = [_w("top", 280, 0), _w("mid", 320, 20), _w("bot", 300, 40)]
    page = _FakePage(words, width=600)
    assert _page_text(page) == "top\nmid\nbot"


def test_empty_page_yields_empty_string() -> None:
    assert _page_text(_FakePage([], width=600)) == ""


def test_not_a_pdf_raises_cv_parse_error_not_a_vendor_exception() -> None:
    with pytest.raises(CvParseError):
        asyncio.run(build_cv_parser().parse(pdf_bytes=b"this is not a pdf"))
