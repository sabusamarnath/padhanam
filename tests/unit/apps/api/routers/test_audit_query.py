"""Unit tests for the audit query-string parser (D103, S37).

Covers the eight-filter query vocabulary, the timestamp_range pairing
constraint, the resource_id-without-resource_type guard, cursor
decoding (happy path + malformed), and page_size default behaviour.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

import pytest

from apps.api.routers._audit_query import (
    InvalidAuditFilterError,
    parse_audit_list_query,
)
from contexts.audit.application.cursor import encode as encode_cursor
from contexts.audit.domain.query_filters import (
    PAGE_SIZE_CEILING,
    AuditEventListCursor,
    MalformedCursorError,
)


def test_no_args_returns_no_filters_no_cursor_default_page_size() -> None:
    filters, cursor, page_size = parse_audit_list_query()
    assert filters.timestamp_range is None
    assert filters.actor is None
    assert filters.action_verbs is None
    assert filters.resource_type is None
    assert filters.resource_id is None
    assert filters.correlation_id is None
    assert filters.jurisdiction is None
    assert cursor is None
    assert page_size == PAGE_SIZE_CEILING


def test_all_filters_collapse_into_filters_dataclass() -> None:
    filters, cursor, page_size = parse_audit_list_query(
        timestamp_range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        timestamp_range_end=datetime(2026, 5, 14, tzinfo=timezone.utc),
        actor="user:alice",
        action_verb=["agent.invoke.start", "agent.invoke.completed"],
        resource_type="agent",
        resource_id="agent-1",
        correlation_id="corr-1",
        jurisdiction=["UK", "DE"],
        cursor=None,
        page_size=10,
    )
    assert filters.timestamp_range == (
        datetime(2026, 5, 1, tzinfo=timezone.utc),
        datetime(2026, 5, 14, tzinfo=timezone.utc),
    )
    assert filters.actor == "user:alice"
    assert filters.action_verbs == ("agent.invoke.start", "agent.invoke.completed")
    assert filters.resource_type == "agent"
    assert filters.resource_id == "agent-1"
    assert filters.correlation_id == "corr-1"
    assert filters.jurisdiction == ("UK", "DE")
    assert cursor is None
    assert page_size == 10


def test_timestamp_range_only_start_raises_invalid_audit_filter() -> None:
    with pytest.raises(InvalidAuditFilterError, match="both be provided"):
        parse_audit_list_query(
            timestamp_range_start=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )


def test_timestamp_range_only_end_raises_invalid_audit_filter() -> None:
    with pytest.raises(InvalidAuditFilterError, match="both be provided"):
        parse_audit_list_query(
            timestamp_range_end=datetime(2026, 5, 14, tzinfo=timezone.utc),
        )


def test_timestamp_range_inverted_raises_invalid_audit_filter() -> None:
    with pytest.raises(InvalidAuditFilterError, match="strictly earlier"):
        parse_audit_list_query(
            timestamp_range_start=datetime(2026, 5, 14, tzinfo=timezone.utc),
            timestamp_range_end=datetime(2026, 5, 1, tzinfo=timezone.utc),
        )


def test_resource_id_without_resource_type_raises_invalid_audit_filter() -> None:
    with pytest.raises(InvalidAuditFilterError, match="resource_id filter requires resource_type"):
        parse_audit_list_query(resource_id="agent-1")


def test_cursor_decodes_to_audit_event_list_cursor() -> None:
    domain_cursor = AuditEventListCursor(
        timestamp=datetime(2026, 5, 14, 10, 30, 0, tzinfo=timezone.utc),
        id=UUID("00000000-0000-0000-0000-000000000099"),
        page_size=10,
    )
    encoded = encode_cursor(domain_cursor)
    _, cursor, _ = parse_audit_list_query(cursor=encoded)
    assert cursor == domain_cursor


def test_malformed_cursor_propagates_malformed_cursor_error() -> None:
    with pytest.raises(MalformedCursorError):
        parse_audit_list_query(cursor="not-base64-but-cursor-string")


def test_action_verb_empty_list_normalises_to_none() -> None:
    filters, _, _ = parse_audit_list_query(action_verb=[])
    assert filters.action_verbs is None


def test_jurisdiction_empty_list_normalises_to_none() -> None:
    filters, _, _ = parse_audit_list_query(jurisdiction=[])
    assert filters.jurisdiction is None
