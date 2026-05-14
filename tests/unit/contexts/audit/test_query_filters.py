"""Unit tests for AuditEventListFilters / AuditEventListCursor invariants (D102, S36)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.chain_integrity import ChainIntegrityVerification
from contexts.audit.domain.query_filters import (
    PAGE_SIZE_CEILING,
    AuditEventListCursor,
    AuditEventListFilters,
    AuditEventListPage,
)


# AuditEventListFilters -----------------------------------------------------


def test_empty_filters_are_valid() -> None:
    filters = AuditEventListFilters()
    assert filters.timestamp_range is None
    assert filters.actor is None
    assert filters.action_verbs is None


def test_empty_tuple_action_verbs_normalises_to_none() -> None:
    filters = AuditEventListFilters(action_verbs=())
    assert filters.action_verbs is None


def test_empty_tuple_jurisdiction_normalises_to_none() -> None:
    filters = AuditEventListFilters(jurisdiction=())
    assert filters.jurisdiction is None


def test_timestamp_range_lower_must_be_strictly_earlier() -> None:
    t = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="timestamp_range"):
        AuditEventListFilters(timestamp_range=(t, t))


def test_timestamp_range_lower_greater_than_upper_raises() -> None:
    lower = datetime(2026, 5, 14, 13, 0, 0, tzinfo=timezone.utc)
    upper = datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="timestamp_range"):
        AuditEventListFilters(timestamp_range=(lower, upper))


def test_resource_id_without_resource_type_raises() -> None:
    with pytest.raises(ValueError, match="resource_id filter requires resource_type"):
        AuditEventListFilters(resource_id="abc")


def test_resource_id_with_resource_type_accepted() -> None:
    filters = AuditEventListFilters(resource_type="agent_run", resource_id="abc")
    assert filters.resource_type == "agent_run"
    assert filters.resource_id == "abc"


def test_resource_type_without_resource_id_accepted() -> None:
    filters = AuditEventListFilters(resource_type="agent_run")
    assert filters.resource_type == "agent_run"
    assert filters.resource_id is None


@pytest.mark.parametrize(
    "field",
    ["actor", "resource_type", "correlation_id"],
)
def test_empty_string_on_single_value_field_raises(field: str) -> None:
    kwargs: dict = {}
    if field == "resource_type":
        kwargs[field] = ""
    elif field == "actor":
        kwargs["actor"] = ""
    elif field == "correlation_id":
        kwargs["correlation_id"] = ""
    with pytest.raises(ValueError, match=field):
        AuditEventListFilters(**kwargs)


def test_filters_frozen() -> None:
    filters = AuditEventListFilters(actor="user:alice")
    with pytest.raises(Exception):
        filters.actor = "user:mallory"  # type: ignore[misc]


# AuditEventListCursor ------------------------------------------------------


def test_cursor_page_size_at_one_accepted() -> None:
    cursor = AuditEventListCursor(
        timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
        id=uuid4(),
        page_size=1,
    )
    assert cursor.page_size == 1


def test_cursor_page_size_at_ceiling_accepted() -> None:
    cursor = AuditEventListCursor(
        timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
        id=uuid4(),
        page_size=PAGE_SIZE_CEILING,
    )
    assert cursor.page_size == PAGE_SIZE_CEILING


def test_cursor_page_size_zero_raises() -> None:
    with pytest.raises(ValueError, match="page_size"):
        AuditEventListCursor(
            timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
            id=uuid4(),
            page_size=0,
        )


def test_cursor_page_size_above_ceiling_raises() -> None:
    with pytest.raises(ValueError, match="page_size"):
        AuditEventListCursor(
            timestamp=datetime(2026, 5, 14, 12, 0, 0, tzinfo=timezone.utc),
            id=uuid4(),
            page_size=PAGE_SIZE_CEILING + 1,
        )


# AuditEventListPage --------------------------------------------------------


def test_page_constructs_with_chain_integrity_status() -> None:
    page = AuditEventListPage(
        events=(),
        next_cursor=None,
        chain_integrity=ChainIntegrityVerification(status="partial"),
    )
    assert page.chain_integrity.status == "partial"
    assert page.events == ()
    assert page.next_cursor is None
