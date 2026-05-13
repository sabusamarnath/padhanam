"""Unit tests for RunListFilters and RunListCursor invariants (D97, S33).

Fences the value-object invariants the read port and adapter depend
on. Empty-tuple normalisation, range-order validation, CHECK-set
membership, and page-size ceiling are the load-bearing rules.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.run_history.domain.query_filters import (
    PAGE_SIZE_CEILING,
    MalformedCursorError,
    RunListCursor,
    RunListFilters,
)


_AGENT_ID_A = UUID("11111111-1111-4111-8111-111111111111")
_AGENT_ID_B = UUID("22222222-2222-4222-8222-222222222222")


# --------------------------------------------------------------------
# RunListFilters: default + per-field invariants.
# --------------------------------------------------------------------


def test_run_list_filters_defaults_to_all_none() -> None:
    """Empty constructor yields no-filter on every dimension."""
    filters = RunListFilters()
    assert filters.agent_template_ids is None
    assert filters.agent_template_versions is None
    assert filters.started_at_range is None
    assert filters.termination_reasons is None


def test_run_list_filters_accepts_populated_tuples() -> None:
    """Populated tuples on every dimension pass through unchanged."""
    started_at_range = (
        datetime(2026, 5, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 31, tzinfo=timezone.utc),
    )
    filters = RunListFilters(
        agent_template_ids=(_AGENT_ID_A, _AGENT_ID_B),
        agent_template_versions=(1, 2),
        started_at_range=started_at_range,
        termination_reasons=("content", "error"),
    )
    assert filters.agent_template_ids == (_AGENT_ID_A, _AGENT_ID_B)
    assert filters.agent_template_versions == (1, 2)
    assert filters.started_at_range == started_at_range
    assert filters.termination_reasons == ("content", "error")


def test_empty_agent_template_ids_normalises_to_none() -> None:
    """Empty tuple on agent_template_ids means no-filter not match-nothing."""
    filters = RunListFilters(agent_template_ids=())
    assert filters.agent_template_ids is None


def test_empty_agent_template_versions_normalises_to_none() -> None:
    filters = RunListFilters(agent_template_versions=())
    assert filters.agent_template_versions is None


def test_empty_termination_reasons_normalises_to_none() -> None:
    filters = RunListFilters(termination_reasons=())
    assert filters.termination_reasons is None


def test_started_at_range_lower_must_be_strictly_earlier_than_upper() -> None:
    """Reversed bounds raise; equal bounds also raise (strictly earlier)."""
    upper = datetime(2026, 5, 31, tzinfo=timezone.utc)
    lower = datetime(2026, 5, 1, tzinfo=timezone.utc)

    with pytest.raises(ValueError, match="lower bound must be strictly earlier"):
        RunListFilters(started_at_range=(upper, lower))

    same = datetime(2026, 5, 15, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="lower bound must be strictly earlier"):
        RunListFilters(started_at_range=(same, same))


def test_termination_reasons_must_be_members_of_d95_check_set() -> None:
    """Six values match D95 plus the synthesised failed; anything else raises."""
    valid = {"content", "max_iterations", "tool_not_registered", "error",
             "invariant_blocked", "failed"}
    # Each valid value accepted alone
    for reason in valid:
        filters = RunListFilters(termination_reasons=(reason,))
        assert filters.termination_reasons == (reason,)
    # An unknown value raises
    with pytest.raises(ValueError, match="termination_reasons"):
        RunListFilters(termination_reasons=("not_a_real_reason",))
    # Mix of valid and invalid raises on the invalid one
    with pytest.raises(ValueError, match="termination_reasons"):
        RunListFilters(termination_reasons=("content", "unknown"))


def test_filters_are_immutable() -> None:
    """Frozen dataclass — direct field assignment raises."""
    filters = RunListFilters()
    with pytest.raises(Exception):
        filters.termination_reasons = ("content",)  # type: ignore[misc]


# --------------------------------------------------------------------
# RunListCursor: page-size invariants.
# --------------------------------------------------------------------


def _valid_cursor(page_size: int = 50) -> RunListCursor:
    return RunListCursor(
        started_at=datetime(2026, 5, 13, 10, 30, 0, tzinfo=timezone.utc),
        id=uuid4(),
        page_size=page_size,
    )


def test_cursor_accepts_page_size_at_ceiling() -> None:
    cursor = _valid_cursor(page_size=PAGE_SIZE_CEILING)
    assert cursor.page_size == PAGE_SIZE_CEILING


def test_cursor_accepts_page_size_one() -> None:
    cursor = _valid_cursor(page_size=1)
    assert cursor.page_size == 1


def test_cursor_rejects_page_size_zero() -> None:
    with pytest.raises(ValueError, match="page_size"):
        _valid_cursor(page_size=0)


def test_cursor_rejects_negative_page_size() -> None:
    with pytest.raises(ValueError, match="page_size"):
        _valid_cursor(page_size=-1)


def test_cursor_rejects_page_size_above_ceiling() -> None:
    with pytest.raises(ValueError, match="page_size"):
        _valid_cursor(page_size=PAGE_SIZE_CEILING + 1)


def test_cursor_is_immutable() -> None:
    cursor = _valid_cursor()
    with pytest.raises(Exception):
        cursor.page_size = 100  # type: ignore[misc]


# --------------------------------------------------------------------
# MalformedCursorError: domain exception is importable and raisable.
# --------------------------------------------------------------------


def test_malformed_cursor_error_is_an_exception() -> None:
    err = MalformedCursorError("bad cursor")
    assert isinstance(err, Exception)
    assert str(err) == "bad cursor"
