"""Unit tests for the optimization query parsers (D112, S42)."""

from __future__ import annotations

import pytest

from apps.api.routers._optimization_query import (
    InvalidOptimizationFilterError,
    parse_optimization_run_list_query,
    parse_recommendation_list_query,
)
from contexts.optimization.domain.category import RecommendationCategory
from contexts.optimization.domain.recommendation_status import (
    RecommendationStatus,
)


# ---------------------------------------------------------------------------
# parse_optimization_run_list_query
# ---------------------------------------------------------------------------


def test_parse_optimization_run_list_defaults() -> None:
    cursor, page_size = parse_optimization_run_list_query()
    assert cursor is None
    assert page_size == 20


def test_parse_optimization_run_list_forwards_cursor() -> None:
    cursor, page_size = parse_optimization_run_list_query(
        cursor="opaque-cursor", page_size=10
    )
    assert cursor == "opaque-cursor"
    assert page_size == 10


# ---------------------------------------------------------------------------
# parse_recommendation_list_query — basics
# ---------------------------------------------------------------------------


def test_parse_recommendation_list_no_filters_collapses_to_none() -> None:
    filters, cursor, page_size = parse_recommendation_list_query()
    assert filters.categories is None
    assert filters.statuses is None
    assert cursor is None
    assert page_size == 20


def test_parse_recommendation_list_with_one_category() -> None:
    filters, _, _ = parse_recommendation_list_query(
        category=["retrieval_strategy"]
    )
    assert filters.categories == (RecommendationCategory.RETRIEVAL_STRATEGY,)
    assert filters.statuses is None


def test_parse_recommendation_list_with_multiple_categories() -> None:
    filters, _, _ = parse_recommendation_list_query(
        category=["retrieval_strategy", "cost_optimization"]
    )
    assert filters.categories == (
        RecommendationCategory.RETRIEVAL_STRATEGY,
        RecommendationCategory.COST_OPTIMIZATION,
    )


def test_parse_recommendation_list_with_status_filters() -> None:
    filters, _, _ = parse_recommendation_list_query(
        status=["generated", "acknowledged"]
    )
    assert filters.statuses == (
        RecommendationStatus.GENERATED,
        RecommendationStatus.ACKNOWLEDGED,
    )


def test_parse_recommendation_list_with_combined_filters() -> None:
    filters, cursor, page_size = parse_recommendation_list_query(
        cursor="opaque",
        page_size=10,
        category=["retrieval_strategy"],
        status=["applied"],
    )
    assert filters.categories == (RecommendationCategory.RETRIEVAL_STRATEGY,)
    assert filters.statuses == (RecommendationStatus.APPLIED,)
    assert cursor == "opaque"
    assert page_size == 10


# ---------------------------------------------------------------------------
# parse_recommendation_list_query — validation
# ---------------------------------------------------------------------------


def test_parse_recommendation_list_unknown_category_raises() -> None:
    with pytest.raises(InvalidOptimizationFilterError) as exc_info:
        parse_recommendation_list_query(category=["nonsense"])
    assert "unknown category 'nonsense'" in str(exc_info.value)
    assert "retrieval_strategy" in str(exc_info.value)


def test_parse_recommendation_list_unknown_status_raises() -> None:
    with pytest.raises(InvalidOptimizationFilterError) as exc_info:
        parse_recommendation_list_query(status=["pending"])
    assert "unknown status 'pending'" in str(exc_info.value)
    assert "generated" in str(exc_info.value)


def test_parse_recommendation_list_empty_filter_lists_collapse_to_none() -> None:
    filters, _, _ = parse_recommendation_list_query(
        category=[], status=[]
    )
    assert filters.categories is None
    assert filters.statuses is None
