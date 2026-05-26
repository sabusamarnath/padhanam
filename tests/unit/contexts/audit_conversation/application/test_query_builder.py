"""Unit tests for the audit_conversation query builder (S51)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest

from contexts.audit_conversation.application.query_builder import (
    build_filters_for_actor,
    build_filters_for_case,
    build_filters_for_combination,
    build_filters_for_date_range,
    build_filters_for_event_type,
    resolve_range_keyword,
)
from contexts.audit_conversation.domain.intent import (
    FindByActor,
    FindByCase,
    FindByCombination,
    FindByDateRange,
    FindByEventType,
)


_NOW = datetime(2026, 5, 26, 14, 30, tzinfo=timezone.utc)


def test_filters_for_case_uses_resource_type_and_id() -> None:
    case_id = uuid4()
    intent = FindByCase(case_reference="Q3")
    filters = build_filters_for_case(intent, resolved_case_id=case_id)
    assert filters.resource_type == "case"
    assert filters.resource_id == str(case_id)


def test_filters_for_date_range_today() -> None:
    intent = FindByDateRange(range_keyword="today")
    filters = build_filters_for_date_range(intent, now=_NOW)
    assert filters.timestamp_range is not None
    start, end = filters.timestamp_range
    assert start == datetime(2026, 5, 26, 0, 0, tzinfo=timezone.utc)
    assert end == _NOW


def test_filters_for_date_range_yesterday() -> None:
    intent = FindByDateRange(range_keyword="yesterday")
    filters = build_filters_for_date_range(intent, now=_NOW)
    assert filters.timestamp_range is not None
    start, end = filters.timestamp_range
    assert start == datetime(2026, 5, 25, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 26, 0, 0, tzinfo=timezone.utc)


def test_filters_for_date_range_last_month() -> None:
    intent = FindByDateRange(range_keyword="last_month")
    filters = build_filters_for_date_range(intent, now=_NOW)
    assert filters.timestamp_range is not None
    start, end = filters.timestamp_range
    assert start == datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 5, 1, 0, 0, tzinfo=timezone.utc)


def test_filters_for_actor() -> None:
    intent = FindByActor(actor="alice")
    filters = build_filters_for_actor(intent)
    assert filters.actor == "alice"


def test_filters_for_event_type() -> None:
    intent = FindByEventType(event_type="portfolio.case.create")
    filters = build_filters_for_event_type(intent)
    assert filters.action_verbs == ("portfolio.case.create",)


def test_filters_for_combination_partial_fields() -> None:
    case_id = uuid4()
    intent = FindByCombination(
        case_reference="Q3",
        range_keyword="this_week",
        actor="alice",
    )
    filters = build_filters_for_combination(
        intent, resolved_case_id=case_id, now=_NOW
    )
    assert filters.resource_type == "case"
    assert filters.resource_id == str(case_id)
    assert filters.timestamp_range is not None
    assert filters.actor == "alice"
    assert filters.action_verbs is None


def test_resolve_range_keyword_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="Unknown range_keyword"):
        resolve_range_keyword("never", now=_NOW)
