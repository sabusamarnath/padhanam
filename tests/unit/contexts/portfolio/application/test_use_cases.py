"""Unit tests for the portfolio application use cases (D124, D125, D126).

S44a (D126): the use cases consume an ActorContext and enforce
authorisation at the use-case boundary via the ``requires_authorisation``
decorator. Happy-path tests pass an ActorContext carrying the full
operator authorisation set; deny-path tests pass one with an empty set
and assert ``AuthorisationDenied`` plus no persistence side effect.
"""

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
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import (
    ROLE_OPERATOR,
    AuthorisationDenied,
    authorisations_for_roles,
)
from tests.unit.contexts.portfolio.application._fakes import (
    FakeAuditPort,
    FakeReader,
    FakeRepository,
    FakeStore,
)

_TENANT_ID = "00000000-0000-4000-8000-00000000a001"


def _ctx() -> TenantContext:
    return TenantContext(
        tenant_id=_TENANT_ID,
        jurisdiction="eu-west",
        cost_attribution_id=_TENANT_ID,
    )


def _actor(*, authorisation_set: frozenset[str] | None = None) -> ActorContext:
    """An ActorContext for the use-case tests.

    Defaults to the full operator authorisation set; pass an explicit
    ``authorisation_set`` (e.g. ``frozenset()``) to exercise the
    decorator's deny path.
    """
    role_list = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=_ctx(),
        actor_id="operator",
        role_list=role_list,
        authorisation_set=(
            authorisations_for_roles(role_list)
            if authorisation_set is None
            else authorisation_set
        ),
    )


def _run(coro):
    return asyncio.run(coro)


# --- happy paths ---------------------------------------------------


def test_create_case_persists_and_audits() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    case = _run(
        create_case(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            title="Q3 board deck",
        )
    )
    assert case.id in store.cases
    assert case.title == "Q3 board deck"
    assert case.status is CaseStatus.OPEN
    assert [e.action_verb for e in audit.events] == ["portfolio.case.create"]


def test_create_case_stamps_actor_id_as_authored_identity() -> None:
    """The use case derives the persisted authoring identity from
    ActorContext.actor_id — the audit event records it."""
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    _run(
        create_case(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            title="case",
        )
    )
    assert audit.events[-1].actor == "operator"


def test_create_data_point_persists_initial_assertion_and_audits() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    case = _run(
        create_case(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            title="case",
        )
    )
    dp = _run(
        create_data_point(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            case_id=case.id,
            data_point_type=DataPointType.GOAL,
            value={"progress": 0},
        )
    )
    assert dp.id in store.data_points
    assert len(dp.assertions) == 1
    assert dp.assertions[0].assertion_type is AssertionType.INITIAL
    assert dp.authored_by.user_id == "operator"
    assert audit.events[-1].action_verb == "portfolio.data_point.create"


def test_revise_data_point_appends_and_audits() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    reader = FakeReader(store)
    audit = FakeAuditPort()
    case = _run(
        create_case(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            title="case",
        )
    )
    dp = _run(
        create_data_point(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            case_id=case.id,
            data_point_type=DataPointType.STATUS,
            value={"v": 1},
        )
    )
    revised = _run(
        revise_data_point(
            repository=repo,
            reader=reader,
            audit_port=audit,
            actor=_actor(),
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
                repository=repo,
                reader=reader,
                audit_port=audit,
                actor=_actor(),
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
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            title="case",
        )
    )
    _run(
        create_data_point(
            repository=repo,
            audit_port=audit,
            actor=_actor(),
            case_id=case.id,
            data_point_type=DataPointType.GOAL,
            value={},
        )
    )
    detail = _run(
        get_case_detail(reader=reader, actor=_actor(), case_id=case.id)
    )
    assert isinstance(detail, CaseDetail)
    assert detail.case.id == case.id
    assert len(detail.data_points) == 1


def test_get_case_detail_unknown_returns_none() -> None:
    store = FakeStore()
    reader = FakeReader(store)
    detail = _run(
        get_case_detail(reader=reader, actor=_actor(), case_id=uuid4())
    )
    assert detail is None


def test_list_cases_returns_all_seeded() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    for i in range(3):
        _run(
            create_case(
                repository=repo,
                audit_port=audit,
                actor=_actor(),
                title=f"case {i}",
            )
        )
    reader = FakeReader(store)
    page = _run(list_cases(reader=reader, actor=_actor(), page_size=10))
    assert len(page.cases) == 3


# --- deny paths: the use-case-boundary decorator (D126) ------------


def test_create_case_denied_without_permission() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            create_case(
                repository=repo,
                audit_port=audit,
                actor=_actor(authorisation_set=frozenset()),
                title="case",
            )
        )
    assert excinfo.value.permission == "portfolio.case.create"
    # The decorator fires before any persistence or audit side effect.
    assert store.cases == {}
    assert audit.events == []


def test_create_data_point_denied_without_permission() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    audit = FakeAuditPort()
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            create_data_point(
                repository=repo,
                audit_port=audit,
                actor=_actor(authorisation_set=frozenset()),
                case_id=uuid4(),
                data_point_type=DataPointType.GOAL,
                value={},
            )
        )
    assert excinfo.value.permission == "portfolio.data_point.create"
    assert store.data_points == {}


def test_revise_data_point_denied_without_permission() -> None:
    store = FakeStore()
    repo = FakeRepository(store)
    reader = FakeReader(store)
    audit = FakeAuditPort()
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            revise_data_point(
                repository=repo,
                reader=reader,
                audit_port=audit,
                actor=_actor(authorisation_set=frozenset()),
                data_point_id=uuid4(),
                value={},
            )
        )
    assert excinfo.value.permission == "portfolio.data_point.revise"


def test_list_cases_denied_without_permission() -> None:
    store = FakeStore()
    reader = FakeReader(store)
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            list_cases(
                reader=reader,
                actor=_actor(authorisation_set=frozenset()),
                page_size=10,
            )
        )
    assert excinfo.value.permission == "portfolio.case.list"


def test_get_case_detail_denied_without_permission() -> None:
    store = FakeStore()
    reader = FakeReader(store)
    with pytest.raises(AuthorisationDenied) as excinfo:
        _run(
            get_case_detail(
                reader=reader,
                actor=_actor(authorisation_set=frozenset()),
                case_id=uuid4(),
            )
        )
    assert excinfo.value.permission == "portfolio.case.get"


def test_partial_authorisation_set_denies_only_the_missing_permission() -> None:
    """An actor authorised for reads but not writes passes list_cases
    and is denied create_case."""
    store = FakeStore()
    repo = FakeRepository(store)
    reader = FakeReader(store)
    audit = FakeAuditPort()
    reads_only = _actor(authorisation_set=frozenset({"portfolio.case.list"}))

    page = _run(list_cases(reader=reader, actor=reads_only, page_size=10))
    assert page.cases == ()

    with pytest.raises(AuthorisationDenied):
        _run(
            create_case(
                repository=repo,
                audit_port=audit,
                actor=reads_only,
                title="case",
            )
        )
