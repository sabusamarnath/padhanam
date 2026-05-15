"""Domain value-object tests for EvaluationRun aggregate (D110)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest

from contexts.retrieval_evaluation.domain import (
    EvaluationRun,
    EvaluationRunStatus,
)


_TENANT = UUID("00000000-0000-0000-0000-00000000a000")
_USER = "operator@tenant_a"


def _now() -> datetime:
    return datetime(2026, 5, 15, 12, 0, 0, tzinfo=timezone.utc)


def _later() -> datetime:
    return datetime(2026, 5, 15, 12, 5, 0, tzinfo=timezone.utc)


def _running_run() -> EvaluationRun:
    return EvaluationRun(
        id=uuid4(),
        tenant_id=_TENANT,
        jurisdiction="GB",
        gold_set_id=uuid4(),
        gold_set_revision_id=uuid4(),
        invoked_by_user_id=_USER,
        invoked_at=_now(),
        completed_at=None,
        status=EvaluationRunStatus.RUNNING,
    )


def test_running_run_has_no_completed_at() -> None:
    run = _running_run()
    assert run.status is EvaluationRunStatus.RUNNING
    assert run.completed_at is None
    assert not run.is_terminal


def test_completed_run_carries_completed_at() -> None:
    run = EvaluationRun(
        id=uuid4(),
        tenant_id=_TENANT,
        jurisdiction="GB",
        gold_set_id=uuid4(),
        gold_set_revision_id=uuid4(),
        invoked_by_user_id=_USER,
        invoked_at=_now(),
        completed_at=_later(),
        status=EvaluationRunStatus.COMPLETED,
    )
    assert run.is_terminal


def test_failed_run_carries_completed_at() -> None:
    run = EvaluationRun(
        id=uuid4(),
        tenant_id=_TENANT,
        jurisdiction="GB",
        gold_set_id=uuid4(),
        gold_set_revision_id=uuid4(),
        invoked_by_user_id=_USER,
        invoked_at=_now(),
        completed_at=_later(),
        status=EvaluationRunStatus.FAILED,
    )
    assert run.is_terminal


def test_running_with_completed_at_set_rejects() -> None:
    with pytest.raises(ValueError, match="completed_at must be None"):
        EvaluationRun(
            id=uuid4(),
            tenant_id=_TENANT,
            jurisdiction="GB",
            gold_set_id=uuid4(),
            gold_set_revision_id=uuid4(),
            invoked_by_user_id=_USER,
            invoked_at=_now(),
            completed_at=_later(),
            status=EvaluationRunStatus.RUNNING,
        )


def test_terminal_without_completed_at_rejects() -> None:
    with pytest.raises(ValueError, match="completed_at must be set"):
        EvaluationRun(
            id=uuid4(),
            tenant_id=_TENANT,
            jurisdiction="GB",
            gold_set_id=uuid4(),
            gold_set_revision_id=uuid4(),
            invoked_by_user_id=_USER,
            invoked_at=_now(),
            completed_at=None,
            status=EvaluationRunStatus.COMPLETED,
        )


def test_empty_jurisdiction_rejects() -> None:
    with pytest.raises(ValueError, match="jurisdiction"):
        EvaluationRun(
            id=uuid4(),
            tenant_id=_TENANT,
            jurisdiction="   ",
            gold_set_id=uuid4(),
            gold_set_revision_id=uuid4(),
            invoked_by_user_id=_USER,
            invoked_at=_now(),
            completed_at=None,
            status=EvaluationRunStatus.RUNNING,
        )


def test_empty_invoked_by_rejects() -> None:
    with pytest.raises(ValueError, match="invoked_by_user_id"):
        EvaluationRun(
            id=uuid4(),
            tenant_id=_TENANT,
            jurisdiction="GB",
            gold_set_id=uuid4(),
            gold_set_revision_id=uuid4(),
            invoked_by_user_id="",
            invoked_at=_now(),
            completed_at=None,
            status=EvaluationRunStatus.RUNNING,
        )
