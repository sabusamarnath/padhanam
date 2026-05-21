"""Unit tests for the portfolio application use cases (D124, D125)."""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

from contexts.portfolio.application import (
    CaseDetail,
    DataPointNotFoundError,
    create_case,
    create_data_point,
    get_case_detail,
    list_cases,
    revise_data_point,
)
from contexts.portfolio.domain import AssertionType, CaseStatus, DataPointType
from shared_kernel import ActorReference, TenantContext
from tests.unit.contexts.portfolio.application._fakes import (
    FakeAuditPort,
    FakeReader,
    FakeRepository,
    FakeStore,
)

_ACTOR = ActorReference(user_id="operator")
_TENANT_ID = "00000000-0000-4000-8000-00000000a001"


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )


def _run(coro):
    return asyncio.run(coro)


def test_create_case_persists_and_audits() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    case = _run(
        create_case(
            tenant_context=_ctx(),
            repository=repo,
            audit_port=audit,
            actor=_ACTOR,
            title="Q3 board deck",
        )
    )
    assert case.id in store.cases
    assert case.title == "Q3 board deck"
    assert case.status is CaseStatus.OPEN
    assert [e.action_verb for e in audit.events] == ["portfolio.case.create"]


def test_create_data_point_persists_initial_assertion_and_audits() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    case = _run(
        create_case(
            tenant_context=_ctx(),
            repository=repo,
            audit_port=audit,
            actor=_ACTOR,
            title="case",
        )
    )
    dp = _run(
        create_data_point(
            tenant_context=_ctx(),
            repository=repo,
            audit_port=audit,
            actor=_ACTOR,
            case_id=case.id,
            data_point_type=DataPointType.GOAL,
            value={"progress": 0},
        )
    )
    assert dp.id in store.data_points
    assert len(dp.assertions) == 1
    assert dp.assertions[0].assertion_type is AssertionType.INITIAL
    assert audit.events[-1].action_verb == "portfolio.data_point.create"


def test_revise_data_point_appends_and_audits() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    reader = FakeReader(store)
    audit = FakeAuditPort()
    case = _run(
        create_case(
            tenant_context=_ctx(),
            repository=repo,
            audit_port=audit,
            actor=_ACTOR,
            title="case",
        )
    )
    dp = _run(
        create_data_point(
            tenant_context=_ctx(),
            repository=repo,
            audit_port=audit,
            actor=_ACTOR,
            case_id=case.id,
            data_point_type=DataPointType.STATUS,
            value={"v": 1},
        )
    )
    revised = _run(
        revise_data_point(
            tenant_context=_ctx(),
            repository=repo,
            reader=reader,
            audit_port=audit,
            actor=_ACTOR,
            data_point_id=dp.id,
            value={"v": 2},
        )
    )
    assert len(revised.assertions) == 2
    assert revised.current_value == {"v": 2}
    assert len(store.data_points[dp.id].assertions) == 2
    assert audit.events[-1].action_verb == "portfolio.data_point.revise"


def test_revise_unknown_data_point_raises() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    reader = FakeReader(store)
    audit = FakeAuditPort()
    with pytest.raises(DataPointNotFoundError):
        _run(
            revise_data_point(
                tenant_context=_ctx(),
                repository=repo,
                reader=reader,
                audit_port=audit,
                actor=_ACTOR,
                data_point_id=uuid4(),
                value={},
            )
        )


def test_get_case_detail_composes_case_and_data_points() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    reader = FakeReader(store)
    audit = FakeAuditPort()
    case = _run(
        create_case(
            tenant_context=_ctx(),
            repository=repo,
            audit_port=audit,
            actor=_ACTOR,
            title="case",
        )
    )
    _run(
        create_data_point(
            tenant_context=_ctx(),
            repository=repo,
            audit_port=audit,
            actor=_ACTOR,
            case_id=case.id,
            data_point_type=DataPointType.GOAL,
            value={},
        )
    )
    detail = _run(
        get_case_detail(
            tenant_context=_ctx(), reader=reader, case_id=case.id
        )
    )
    assert isinstance(detail, CaseDetail)
    assert detail.case.id == case.id
    assert len(detail.data_points) == 1


def test_get_case_detail_unknown_returns_none() -> None:
    store = FakeStore()
    reader = FakeReader(store)
    detail = _run(
        get_case_detail(
            tenant_context=_ctx(), reader=reader, case_id=uuid4()
        )
    )
    assert detail is None


def test_list_cases_returns_all_seeded() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    for i in range(3):
        _run(
            create_case(
                tenant_context=_ctx(),
                repository=repo,
                audit_port=audit,
                actor=_ACTOR,
                title=f"case {i}",
            )
        )
    reader = FakeReader(store)
    page = _run(
        list_cases(tenant_context=_ctx(), reader=reader, page_size=10)
    )
    assert len(page.cases) == 3
