"""In-memory fakes for intake application-layer unit tests (S44b)."""

from __future__ import annotations

from uuid import UUID

from contexts.audit.domain.events import AuditEvent

from contexts.intake.domain import IntakeRecord
from contexts.intake.domain.query_filters import (
    IntakeListCursor,
    IntakeListFilters,
)
from contexts.intake.ports.intake_repository import IntakeListPage
from shared_kernel import TenantContext


class FakeAuditPort:
    def __init__(self) -> None:
        self.events: list[AuditEvent] = []

    async def emit(self, event: AuditEvent) -> AuditEvent:
        self.events.append(event)
        return event


class FakeIntakeRepository:
    def __init__(self) -> None:
        self.intakes: dict[UUID, IntakeRecord] = {}

    async def save(
        self, *, tenant_context: TenantContext, intake: IntakeRecord
    ) -> None:
        self.intakes[intake.id] = intake

    async def get_by_id(
        self, *, tenant_context: TenantContext, intake_id: UUID
    ) -> IntakeRecord | None:
        return self.intakes.get(intake_id)

    async def list_for_tenant(
        self,
        *,
        tenant_context: TenantContext,
        filters: IntakeListFilters | None,
        cursor: IntakeListCursor | None,
        page_size: int,
    ) -> IntakeListPage:
        rows = sorted(
            self.intakes.values(),
            key=lambda i: (i.created_at, str(i.id)),
            reverse=True,
        )
        if filters is not None and filters.intake_sources is not None:
            rows = [
                i for i in rows if i.intake_source in filters.intake_sources
            ]
        return IntakeListPage(
            intakes=tuple(rows[:page_size]), next_cursor=None
        )
