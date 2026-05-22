"""In-memory fakes for intake application-layer unit tests (S44b)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from contexts.audit.domain.events import AuditEvent

from contexts.intake.application.ports.portfolio_writer import (
    CaseWriteResult,
    DataPointWriteResult,
)
from contexts.intake.domain import IntakeRecord
from contexts.intake.domain.query_filters import (
    IntakeListCursor,
    IntakeListFilters,
)
from contexts.intake.ports.intake_repository import IntakeListPage
from shared_kernel import ActorContext, TenantContext


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


class FakePortfolioWriter:
    """In-memory PortfolioWriter port double.

    Records the calls it receives plus the ``intake_id`` each carried;
    ``fail`` flips it to raise, exercising the downstream-failure path.
    """

    def __init__(self) -> None:
        self.created_cases: list[CaseWriteResult] = []
        self.created_data_points: list[DataPointWriteResult] = []
        self.revised_data_points: list[DataPointWriteResult] = []
        self.fail: bool = False

    @staticmethod
    def _tenant_uuid(actor: ActorContext) -> UUID:
        return UUID(actor.tenant_context.tenant_id)

    async def create_case(
        self, *, actor: ActorContext, title: str, intake_id: UUID
    ) -> CaseWriteResult:
        if self.fail:
            raise RuntimeError("downstream portfolio write failed")
        now = datetime.now(timezone.utc)
        result = CaseWriteResult(
            case_id=uuid4(),
            tenant_id=self._tenant_uuid(actor),
            jurisdiction=actor.tenant_context.jurisdiction,
            title=title,
            case_type="PORTFOLIO_ITEM",
            status="OPEN",
            created_at=now,
            updated_at=now,
            intake_id=intake_id,
        )
        self.created_cases.append(result)
        return result

    async def create_data_point(
        self,
        *,
        actor: ActorContext,
        case_id: UUID,
        data_point_type: str,
        value: dict[str, Any],
        intake_id: UUID,
    ) -> DataPointWriteResult:
        if self.fail:
            raise RuntimeError("downstream portfolio write failed")
        result = DataPointWriteResult(
            data_point_id=uuid4(),
            case_id=case_id,
            data_point_type=data_point_type,
            current_value=value,
            assertion_ids=(uuid4(),),
            intake_id=intake_id,
        )
        self.created_data_points.append(result)
        return result

    async def revise_data_point(
        self,
        *,
        actor: ActorContext,
        data_point_id: UUID,
        value: dict[str, Any],
        intake_id: UUID,
    ) -> DataPointWriteResult:
        if self.fail:
            raise RuntimeError("downstream portfolio write failed")
        result = DataPointWriteResult(
            data_point_id=data_point_id,
            case_id=uuid4(),
            data_point_type="GOAL",
            current_value=value,
            assertion_ids=(uuid4(), uuid4()),
            intake_id=intake_id,
        )
        self.revised_data_points.append(result)
        return result
