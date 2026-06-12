"""The recommendations category CHECK constraint must list every enum value.

Regression for the S91a/S91b gap: MATCHER_SUPPRESSION was added to the domain
enum + the citation union, but the live ``recommendations_category_check``
constraint still allowed only the four inference categories, so ``optimization
run`` failed to persist the matcher recommendation (CheckViolationError). The
unit tests used in-memory fakes and never exercised the constraint. This test
ties the table constraint to the enum so any future category addition that
forgets the migration fails here, not in production.
"""

from __future__ import annotations

from contexts.optimization.adapters.outbound.postgres._tables import (
    recommendations,
)
from contexts.optimization.domain import RecommendationCategory


def test_category_check_lists_every_recommendation_category() -> None:
    checks = [
        str(c.sqltext)
        for c in recommendations.constraints
        if getattr(c, "name", None) == "recommendations_category_check"
    ]
    assert checks, "recommendations_category_check constraint not found"
    sqltext = checks[0]
    for category in RecommendationCategory:
        assert category.value in sqltext, (
            f"category {category.value!r} is in the enum but not in the "
            "recommendations_category_check constraint — add it to the table "
            "definition AND a migration"
        )
