"""In-memory fakes for portfolio application-layer unit tests (S43).

The fake repository and reader share one ``FakeStore`` so a use case
that writes through the repository and reads back through the reader
sees a consistent view. The fake audit port records emitted events.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from uuid import UUID

from contexts.audit.domain.events import AuditEvent

from contexts.portfolio.domain import Assertion, Case, DataPoint
from contexts.portfolio.domain.query_filters import (
    CaseListCursor,
    CaseListFilters,
)
from contexts.portfolio.ports import CaseListPage
from shared_kernel import TenantContext


@dataclass
class FakeStore:
    cases: dict[UUID, Case] = field(default_factory=dict)
    data_points: dict[UUID, DataPoint] = field(default_factory=dict)


class FakeAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event


class FakeRepository:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def save_case(
        self, *, tenant_context: TenantContext, case: Case
    ) -> None:
        self._store.cases[case.id] = case

    async def save_data_point(
        self, *, tenant_context: TenantContext, data_point: DataPoint
    ) -> None:
        self._store.data_points[data_point.id] = data_point

    async def save_assertion(
        self, *, tenant_context: TenantContext, assertion: Assertion
    ) -> None:
        existing = self._store.data_points[assertion.data_point_id]
        self._store.data_points[existing.id] = replace(
            existing, assertions=existing.assertions + (assertion,)
        )


class FakeReader:
    def __init__(self, store: FakeStore) -> None:
        self._store = store

    async def get_case(
        self, *, tenant_context: TenantContext, case_id: UUID
    ) -> Case | None:
        return self._store.cases.get(case_id)

    async def list_cases(
        self,
        *,
        tenant_context: TenantContext,
        filters: CaseListFilters | None,
        cursor: CaseListCursor | None,
        page_size: int,
    ) -> CaseListPage:
        rows = sorted(
            self._store.cases.values(),
            key=lambda c: (c.created_at, str(c.id)),
            reverse=True,
        )
        if filters is not None and filters.case_types is not None:
            rows = [c for c in rows if c.case_type in filters.case_types]
        if filters is not None and filters.statuses is not None:
            rows = [c for c in rows if c.status in filters.statuses]
        return CaseListPage(cases=tuple(rows[:page_size]), next_cursor=None)

    async def get_data_point(
        self, *, tenant_context: TenantContext, data_point_id: UUID
    ) -> DataPoint | None:
        return self._store.data_points.get(data_point_id)

    async def list_data_points(
        self, *, tenant_context: TenantContext, case_id: UUID
    ) -> tuple[DataPoint, ...]:
        return tuple(
            dp
            for dp in self._store.data_points.values()
            if dp.case_id == case_id
        )

    async def assertion_history(
        self, *, tenant_context: TenantContext, data_point_id: UUID
    ) -> tuple[Assertion, ...]:
        dp = self._store.data_points.get(data_point_id)
        return dp.assertions if dp is not None else ()
