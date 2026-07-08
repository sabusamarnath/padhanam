"""Enforcement (S103ah, D240): the correlation engine names no specific job goal.

The one core leak — a hardcoded ``_JOB_SEARCH_GOAL_NAME = "get a job"`` inside the
otherwise goal-agnostic engine — is retired to the per-goal ``:Outcome.ingests_source_class``
flag. This guard fails if a job goal name (or the retired symbol) is reintroduced into the
engine's domain/application modules, so the genericity cannot silently regress.

Ops scripts (dogfood provisioning) legitimately name the goal and are out of scope; this
guards only the generic engine.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from contexts.daily_driver.application.correlate_goal_facets import (
    _goal_for_source_class,
)
from contexts.daily_driver.ports.email_job_search_source import (
    EMAIL_JOB_SEARCH_SOURCE_CLASS,
)

# The generic correlation engine — must name no specific job goal.
_ENGINE_MODULES = (
    "contexts/daily_driver/application/correlate_goal_facets.py",
    "contexts/daily_driver/domain/goal_assessment.py",
)
_REPO_ROOT = Path(__file__).resolve().parents[4]


def _source(rel: str) -> str:
    return (_REPO_ROOT / rel).read_text(encoding="utf-8").lower()


def test_retired_symbol_absent_from_the_engine() -> None:
    for rel in _ENGINE_MODULES:
        assert "_job_search_goal_name" not in _source(rel), rel


def test_no_hardcoded_job_goal_name_at_the_binding_site() -> None:
    # The binding site (correlate) binds by the per-goal source-class flag, never a
    # literal goal name. (goal_assessment's binding functions are already goal-agnostic —
    # they take an ``outcome_id`` and may name "Get a job" only in an illustrative
    # docstring, which is documentation, not a binding key.)
    src = _source("contexts/daily_driver/application/correlate_goal_facets.py")
    assert '"get a job"' not in src
    assert "'get a job'" not in src


def test_engine_binds_by_the_source_class_flag() -> None:
    # The positive assertion: correlation reads the per-goal source-class flag.
    src = _source("contexts/daily_driver/application/correlate_goal_facets.py")
    assert "email_job_search_source_class" in src
    assert "ingests_source_class" in src


def test_goal_for_source_class_selects_the_flagged_goal() -> None:
    # The selection binds to whichever goal declares the source class — by the flag,
    # not by name (both goals could be named anything).
    flagged = SimpleNamespace(
        ingests_source_class=EMAIL_JOB_SEARCH_SOURCE_CLASS, id="flagged"
    )
    other = SimpleNamespace(ingests_source_class=None, id="other")
    assert _goal_for_source_class([other, flagged], EMAIL_JOB_SEARCH_SOURCE_CLASS) is flagged
    # No goal carries the flag → no binding target (the moat simply does not bind).
    assert _goal_for_source_class([other], EMAIL_JOB_SEARCH_SOURCE_CLASS) is None
