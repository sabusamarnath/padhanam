"""Unit tests for the intake_id field on Case and Assertion (D128, S44b)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from contexts.portfolio.domain import (
    Assertion,
    AssertionType,
    Case,
    CaseStatus,
    CaseType,
    DataPoint,
    DataPointType,
)
from shared_kernel import ActorReference, AssertionChange

_TS = datetime(2026, 5, 22, 12, 0, 0, tzinfo=timezone.utc)
_ACTOR = ActorReference(user_id="operator")


def test_case_intake_id_defaults_to_none() -> None:
    case = Case(
        id=uuid4(), tenant_id=uuid4(), jurisdiction="eu-west",
        title="t", case_type=CaseType.PORTFOLIO_ITEM,
        status=CaseStatus.OPEN, created_at=_TS, updated_at=_TS,
    )
    assert case.intake_id is None


def test_case_carries_intake_id_when_set() -> None:
    intake_id = uuid4()
    case = Case(
        id=uuid4(), tenant_id=uuid4(), jurisdiction="eu-west",
        title="t", case_type=CaseType.PORTFOLIO_ITEM,
        status=CaseStatus.OPEN, created_at=_TS, updated_at=_TS,
        intake_id=intake_id,
    )
    assert case.intake_id == intake_id


def test_assertion_intake_id_defaults_to_none() -> None:
    assertion = Assertion(
        id=uuid4(), data_point_id=uuid4(), tenant_id=uuid4(),
        jurisdiction="eu-west", assertion_type=AssertionType.INITIAL,
        revises_assertion_id=None, value={}, authored_by=_ACTOR,
        created_at=_TS,
    )
    assert assertion.intake_id is None


def test_assertion_carries_intake_id_when_set() -> None:
    intake_id = uuid4()
    assertion = Assertion(
        id=uuid4(), data_point_id=uuid4(), tenant_id=uuid4(),
        jurisdiction="eu-west", assertion_type=AssertionType.INITIAL,
        revises_assertion_id=None, value={}, authored_by=_ACTOR,
        created_at=_TS, intake_id=intake_id,
    )
    assert assertion.intake_id == intake_id


def _data_point(*, intake_id=None) -> DataPoint:
    dp_id = uuid4()
    initial = Assertion(
        id=uuid4(), data_point_id=dp_id, tenant_id=uuid4(),
        jurisdiction="eu-west", assertion_type=AssertionType.INITIAL,
        revises_assertion_id=None, value={"v": 0}, authored_by=_ACTOR,
        created_at=_TS, intake_id=intake_id,
    )
    return DataPoint(
        id=dp_id, case_id=uuid4(), tenant_id=initial.tenant_id,
        jurisdiction="eu-west", data_point_type=DataPointType.GOAL,
        value={"v": 0}, authored_by=_ACTOR, created_at=_TS,
        assertions=(initial,),
    )


def test_revise_default_leaves_revision_intake_id_none() -> None:
    """DataPoint.revise without intake_id satisfies the Revisable
    Protocol shape and leaves the REVISION assertion's intake_id null."""
    dp = _data_point()
    revised = dp.revise(AssertionChange(value={"v": 1}), _ACTOR)
    assert revised.assertions[-1].intake_id is None


def test_revise_stamps_intake_id_on_the_revision() -> None:
    """The intake-canonical path passes intake_id; the REVISION
    assertion carries it."""
    dp = _data_point()
    intake_id = uuid4()
    revised = dp.revise(
        AssertionChange(value={"v": 1}), _ACTOR, intake_id
    )
    assert revised.assertions[-1].intake_id == intake_id
    assert revised.assertions[-1].assertion_type is AssertionType.REVISION
