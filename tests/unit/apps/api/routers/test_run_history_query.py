"""Unit tests for the run-history query-string parser (S34, D98).

The parser is a FastAPI dependency that maps query params to
RunListFilters and RunListCursor. We exercise it as a plain function
call here; the route-level integration tests exercise the FastAPI
binding.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from apps.api.routers._run_history_query import (
    InvalidFilterRangeError,
    parse_run_list_query,
)
from contexts.run_history.application.cursor import encode as encode_cursor
from contexts.run_history.domain.query_filters import (
    PAGE_SIZE_CEILING,
    MalformedCursorError,
    RunListCursor,
    RunListFilters,
)


_NOW = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)


# --------------------------------------------------------------------
# No filters, no cursor.
# --------------------------------------------------------------------


def test_parse_with_no_query_params_returns_empty_filters_and_no_cursor() -> None:
    filters, cursor = parse_run_list_query()
    assert filters == RunListFilters()
    assert filters.agent_template_ids is None
    assert filters.agent_template_versions is None
    assert filters.started_at_range is None
    assert filters.termination_reasons is None
    assert cursor is None


# --------------------------------------------------------------------
# Empty repeated params collapse to None.
# --------------------------------------------------------------------


def test_parse_empty_repeated_params_collapse_to_none() -> None:
    filters, cursor = parse_run_list_query(
        agent_template_id=[],
        agent_template_version=[],
        termination_reason=[],
    )
    assert filters.agent_template_ids is None
    assert filters.agent_template_versions is None
    assert filters.termination_reasons is None
    assert cursor is None


# --------------------------------------------------------------------
# Each filter dimension alone.
# --------------------------------------------------------------------


def test_parse_agent_template_id_filter() -> None:
    tid_a = uuid4()
    tid_b = uuid4()
    filters, _ = parse_run_list_query(agent_template_id=[tid_a, tid_b])
    assert filters.agent_template_ids == (tid_a, tid_b)


def test_parse_agent_template_version_filter() -> None:
    filters, _ = parse_run_list_query(agent_template_version=[1, 2, 3])
    assert filters.agent_template_versions == (1, 2, 3)


def test_parse_termination_reason_filter() -> None:
    filters, _ = parse_run_list_query(termination_reason=["content", "max_iterations"])
    assert filters.termination_reasons == ("content", "max_iterations")


def test_parse_termination_reason_rejects_unknown_value() -> None:
    """RunListFilters.__post_init__ enforces the D95 six-value CHECK set."""
    with pytest.raises(ValueError, match="termination_reasons"):
        parse_run_list_query(termination_reason=["not_a_real_value"])


def test_parse_date_range_with_both_bounds_in_order() -> None:
    after = _NOW
    before = _NOW.replace(hour=18)
    filters, _ = parse_run_list_query(
        started_at_after=after, started_at_before=before
    )
    assert filters.started_at_range == (after, before)


# --------------------------------------------------------------------
# Date-range validation.
# --------------------------------------------------------------------


def test_parse_date_range_with_only_after_raises_invalid_filter_range() -> None:
    with pytest.raises(InvalidFilterRangeError, match="both be provided"):
        parse_run_list_query(started_at_after=_NOW)


def test_parse_date_range_with_only_before_raises_invalid_filter_range() -> None:
    with pytest.raises(InvalidFilterRangeError, match="both be provided"):
        parse_run_list_query(started_at_before=_NOW)


def test_parse_date_range_with_wrong_order_raises_invalid_filter_range() -> None:
    after = _NOW.replace(hour=18)
    before = _NOW.replace(hour=12)
    with pytest.raises(InvalidFilterRangeError, match="strictly earlier"):
        parse_run_list_query(started_at_after=after, started_at_before=before)


def test_parse_date_range_with_equal_bounds_raises_invalid_filter_range() -> None:
    with pytest.raises(InvalidFilterRangeError, match="strictly earlier"):
        parse_run_list_query(started_at_after=_NOW, started_at_before=_NOW)


# --------------------------------------------------------------------
# All filters together.
# --------------------------------------------------------------------


def test_parse_all_four_filters_together() -> None:
    tid = uuid4()
    after = _NOW
    before = _NOW.replace(hour=18)
    filters, cursor = parse_run_list_query(
        agent_template_id=[tid],
        agent_template_version=[1],
        started_at_after=after,
        started_at_before=before,
        termination_reason=["content"],
    )
    assert filters.agent_template_ids == (tid,)
    assert filters.agent_template_versions == (1,)
    assert filters.started_at_range == (after, before)
    assert filters.termination_reasons == ("content",)
    assert cursor is None


# --------------------------------------------------------------------
# Cursor handling.
# --------------------------------------------------------------------


def test_parse_cursor_decodes_opaque_string() -> None:
    original = RunListCursor(started_at=_NOW, id=uuid4(), page_size=10)
    encoded = encode_cursor(original)
    _, cursor = parse_run_list_query(cursor=encoded)
    assert cursor is not None
    assert cursor.started_at == original.started_at
    assert cursor.id == original.id
    assert cursor.page_size == original.page_size


def test_parse_malformed_cursor_raises_malformed_cursor_error() -> None:
    with pytest.raises(MalformedCursorError):
        parse_run_list_query(cursor="not-a-valid-base64-cursor!@#")


# --------------------------------------------------------------------
# Page-size threading on the initial page.
# --------------------------------------------------------------------


def test_parse_page_size_alone_constructs_sentinel_cursor() -> None:
    """page_size without cursor builds a synthetic max-value cursor.

    The adapter's WHERE (started_at, id) < (cursor.started_at, cursor.id)
    clause is trivially satisfied for any real row; the user-requested
    page_size threads through to the LIMIT step.
    """
    _, cursor = parse_run_list_query(page_size=5)
    assert cursor is not None
    assert cursor.page_size == 5
    assert cursor.started_at.year == 9999
    assert cursor.id == UUID(int=(1 << 128) - 1)


def test_parse_page_size_and_cursor_uses_cursor_page_size() -> None:
    """page_size query param is ignored when a real cursor is provided."""
    original = RunListCursor(started_at=_NOW, id=uuid4(), page_size=10)
    encoded = encode_cursor(original)
    _, cursor = parse_run_list_query(cursor=encoded, page_size=5)
    assert cursor is not None
    assert cursor.page_size == 10  # the cursor's value, not the query param's


def test_parse_no_page_size_no_cursor_returns_none() -> None:
    """The adapter falls back to PAGE_SIZE_CEILING when cursor is None."""
    _, cursor = parse_run_list_query()
    assert cursor is None


def test_parse_page_size_at_ceiling() -> None:
    _, cursor = parse_run_list_query(page_size=PAGE_SIZE_CEILING)
    assert cursor is not None
    assert cursor.page_size == PAGE_SIZE_CEILING
