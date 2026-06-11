"""Composition wiring for the daily-driver context (D157, S58).

Three per-request-tenant-resolving wrappers live on ``app.state`` and
are dependency-injected by the daily-driver routes:

- ``CommitmentRepositoryRouter`` / ``DayRepositoryRouter`` — each call
  resolves the request's per-tenant session factory and delegates to a
  freshly-constructed bound Postgres adapter (the
  ``PortfolioReaderAdapter`` precedent: one composed instance, many
  tenants across requests).
- ``OpenCasesReaderAdapter`` — implements the daily-driver
  ``OpenCasesReader`` consumer port (the D17 cross-context seam) by
  composing the portfolio ``list_cases`` use case filtered to OPEN and
  mapping each ``Case`` onto the daily-driver-local ``OpenCase``
  projection. Mirrors the daily-briefing ``DailyBriefingReaderAdapter``
  precedent: ``apps/`` may import producer-context application modules
  directly.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Awaitable, Callable
from uuid import UUID

from contexts.calendar.adapters.outbound.postgres.meeting_store import (
    PostgresMeetingStore,
)
from contexts.calendar.domain.meeting import Meeting
from contexts.daily_driver.adapters.outbound.postgres.commitment_repository import (  # noqa: E501
    PostgresCommitmentRepository,
)
from contexts.daily_driver.adapters.outbound.postgres.day_repository import (
    PostgresDayRepository,
)
from contexts.daily_driver.domain.calendar_domain import resolve_calendar_domain
from contexts.daily_driver.domain.commitment import (
    Commitment,
    CommitmentActivity,
    CommitmentCompletion,
    OutcomeStatus,
)
from contexts.daily_driver.domain.day import DayItemState
from contexts.daily_driver.domain.goal import (
    ControlAxis,
    Goal,
    GoalMode,
    LevelLadder,
    LeverStep,
    StepState,
    Subject,
    Terminal,
    TerminalState,
)
from contexts.daily_driver.domain.today_item import (
    CalendarToday,
    ItemKind,
    OpenCase,
)
from contexts.daily_driver.domain.goal_assessment import GoalEdge
from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
    WorkFacet,
    WorkUnit,
)
from contexts.daily_driver.ports.unit_graph import UnitFacetRef, UnitRecord
from contexts.email.adapters.outbound.postgres.email_store import (
    PostgresEmailStore,
)
from contexts.portfolio.adapters.outbound.postgres.portfolio_reader import (
    PostgresPortfolioReader,
)
from contexts.ingestion.ports.unit_graph_port import (
    FacetLinkWrite,
    GoalEdgeWrite,
    UnitWrite,
)
from contexts.tasks.adapters.outbound.postgres.task_store import (
    PostgresTaskStore,
)
from contexts.tasks.domain.task import Task
from contexts.portfolio.application.list_cases import list_cases
from contexts.portfolio.domain.case import CaseStatus
from contexts.portfolio.domain.query_filters import CaseListFilters
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application.connection_resolution import (
    TenantSessionFactoryCache,
)
from padhanam.observability.security_events import SecurityEventLogger
from padhanam.security import Principal
from shared_kernel import ActorContext, TenantContext, TenantId

_SessionFactoryForTenant = Callable[[TenantContext], Awaitable[Any]]

_OPEN_CASE_PAGE_SIZE = 200


def _session_factory_builder(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> _SessionFactoryForTenant:
    async def _session_factory_for_tenant(
        tenant_context: TenantContext,
    ) -> Any:
        return await session_factory_cache.get(
            tenant_id=TenantId(str(tenant_context.tenant_id)),
            principal=operator_principal,
            registry=tenant_registry,
            security_events=security_events,
        )

    return _session_factory_for_tenant


def _resolver_for(sessionmaker: object) -> Callable[[TenantId], Awaitable[object]]:
    async def _resolver(_tid: TenantId) -> object:
        return sessionmaker

    return _resolver


class CommitmentRepositoryRouter:
    """Per-request-tenant-resolving ``CommitmentRepository`` (D157)."""

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def _build(
        self, tenant_context: TenantContext
    ) -> PostgresCommitmentRepository:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)
        return PostgresCommitmentRepository(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def add_commitment(
        self, *, tenant_context: TenantContext, commitment: Commitment
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.add_commitment(
            tenant_context=tenant_context, commitment=commitment
        )

    async def add_completion(
        self,
        *,
        tenant_context: TenantContext,
        completion: CommitmentCompletion,
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.add_completion(
            tenant_context=tenant_context, completion=completion
        )

    async def get_commitment(
        self, *, tenant_context: TenantContext, commitment_id: UUID
    ) -> Commitment | None:
        repo = await self._build(tenant_context)
        return await repo.get_commitment(
            tenant_context=tenant_context, commitment_id=commitment_id
        )

    async def list_with_activity(
        self, *, tenant_context: TenantContext
    ) -> tuple[CommitmentActivity, ...]:
        repo = await self._build(tenant_context)
        return await repo.list_with_activity(tenant_context=tenant_context)

    async def record_observed_outcome(
        self,
        *,
        tenant_context: TenantContext,
        commitment_id: UUID,
        observed_outcome: str | None,
        outcome_status: OutcomeStatus,
        observed_at: datetime,
    ) -> Commitment | None:
        repo = await self._build(tenant_context)
        return await repo.record_observed_outcome(
            tenant_context=tenant_context,
            commitment_id=commitment_id,
            observed_outcome=observed_outcome,
            outcome_status=outcome_status,
            observed_at=observed_at,
        )


class DayRepositoryRouter:
    """Per-request-tenant-resolving ``DayRepository`` (D157)."""

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def _build(
        self, tenant_context: TenantContext
    ) -> PostgresDayRepository:
        sessionmaker = await self._session_factory_for_tenant(tenant_context)
        return PostgresDayRepository(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(tenant_context.tenant_id)),
        )

    async def get_states(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
    ) -> tuple[DayItemState, ...]:
        repo = await self._build(tenant_context)
        return await repo.get_states(
            tenant_context=tenant_context,
            user_id=user_id,
            day_date=day_date,
        )

    async def set_positions(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
        ordered_keys: tuple[tuple[ItemKind, UUID], ...],
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.set_positions(
            tenant_context=tenant_context,
            user_id=user_id,
            day_date=day_date,
            ordered_keys=ordered_keys,
        )

    async def set_done(
        self,
        *,
        tenant_context: TenantContext,
        user_id: str,
        day_date: date,
        kind: ItemKind,
        item_id: UUID,
        done: bool,
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.set_done(
            tenant_context=tenant_context,
            user_id=user_id,
            day_date=day_date,
            kind=kind,
            item_id=item_id,
            done=done,
        )


class OpenCasesReaderAdapter:
    """apps/ adapter implementing daily-driver's ``OpenCasesReader`` (D157, D17)."""

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def list_open_cases(
        self, *, actor: ActorContext
    ) -> tuple[OpenCase, ...]:
        sessionmaker = await self._session_factory_for_tenant(
            actor.tenant_context
        )
        reader = PostgresPortfolioReader(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(actor.tenant_context.tenant_id)),
        )
        page = await list_cases(
            reader=reader,
            actor=actor,
            filters=CaseListFilters(statuses=(CaseStatus.OPEN,)),
            page_size=_OPEN_CASE_PAGE_SIZE,
        )
        return tuple(
            OpenCase(
                case_id=case.id,
                title=case.title,
                created_at=case.created_at,
            )
            for case in page.cases
        )


class CalendarEventsReaderAdapter:
    """apps/ adapter implementing daily-driver's ``CalendarEventsReader`` (D159, D17).

    Composes the calendar context's ``PostgresMeetingStore`` (bound to the
    request's tenant — the isolation defence-in-depth), lists the stored
    Meetings, filters to the events occurring on ``day_date`` (UTC), and
    maps each onto the daily-driver-local ``CalendarToday`` projection
    carrying the connection's resolved domain tag. Cancelled meetings are
    excluded (the store tombstones them out of ``list_meetings``).
    """

    def __init__(
        self,
        *,
        session_factory_for_tenant: _SessionFactoryForTenant,
        domain_tag: str,
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant
        self._domain_tag = domain_tag

    async def list_today_events(
        self, *, actor: ActorContext, day_date: date
    ) -> tuple[CalendarToday, ...]:
        sessionmaker = await self._session_factory_for_tenant(
            actor.tenant_context
        )
        store = PostgresMeetingStore(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(actor.tenant_context.tenant_id)),
        )
        meetings = await store.list_meetings(
            tenant_context=actor.tenant_context, include_cancelled=False
        )
        day_start = datetime.combine(day_date, time.min, tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)
        domain = resolve_calendar_domain(self._domain_tag)
        events = [
            _calendar_today(meeting, domain=domain)
            for meeting in meetings
            if _starts_on_day(meeting, day_start=day_start, day_end=day_end)
        ]
        return tuple(events)


def _starts_on_day(
    meeting: Meeting, *, day_start: datetime, day_end: datetime
) -> bool:
    """True when the meeting's start falls within the [day_start, day_end) window."""
    start = meeting.start_at
    if start is None:
        return False
    return day_start <= start < day_end


def _calendar_today(meeting: Meeting, *, domain: str) -> CalendarToday:
    return CalendarToday(
        meeting_id=meeting.id,
        google_event_id=meeting.google_event_id,
        title=meeting.title or "(untitled meeting)",
        start_at=meeting.start_at,
        end_at=meeting.end_at,
        domain=domain,
    )


class GoalGraphAdapter:
    """apps/ adapter implementing daily-driver's ``GoalGraphPort`` over
    ingestion's ``OutcomeGraphPort`` (D163, D17).

    The bridge from the daily-driver goal layer to the shared graph: it maps
    the generic ``OutcomeGraphRecord`` rows ingestion returns onto the
    daily-driver ``Goal`` domain (the calendar ``MeetingGraphIndexBridge``
    precedent). The underlying ``Neo4jGraphRepository`` is process-shared;
    tenant scoping flows through the ``tenant_context`` on every call.
    """

    def __init__(self, *, outcome_graph: Any) -> None:
        self._outcome_graph = outcome_graph

    @staticmethod
    def _to_goal(record: Any, *, tenant_context: TenantContext) -> Goal:
        mode = GoalMode(record.mode)
        ladder = None
        lever_commitment_id = None
        lever_commitment_ids: tuple[UUID, ...] = ()
        terminal = None
        steps: tuple[LeverStep, ...] = ()
        if mode is GoalMode.PROGRESSIVE:
            if record.ladder and record.current_target_level:
                ladder = LevelLadder(
                    levels=tuple(record.ladder),
                    current_target_level=record.current_target_level,
                )
            # A progressive goal's primary lever is the first; D177 carries the
            # whole set so the confirmed tier matches a unit against any.
            if record.levers:
                lever_commitment_id = record.levers[0].commitment_id
                lever_commitment_ids = tuple(
                    lever.commitment_id for lever in record.levers
                )
        elif mode is GoalMode.SEQUENCE:
            if record.terminal_target:
                terminal = Terminal(
                    target=record.terminal_target,
                    state=TerminalState(record.terminal_state or "pending"),
                )
            steps = tuple(
                LeverStep(
                    commitment_id=lever.commitment_id,
                    order=lever.step_order or (idx + 1),
                    state=StepState(lever.step_state or "ready"),
                )
                for idx, lever in enumerate(record.levers)
            )
        else:
            # Homeostatic (and any other cadence mode): D177 — a regimen carries
            # a lever-commitment per work-type (the health regimen's four
            # medications). The primary is the first; the whole set is extracted
            # so the confirmed tier (D169) matches a unit against any, not one
            # (S69 took only the first, which understated multi-facet coverage).
            if record.levers:
                lever_commitment_id = record.levers[0].commitment_id
                lever_commitment_ids = tuple(
                    lever.commitment_id for lever in record.levers
                )
        return Goal(
            id=record.outcome_id,
            tenant_id=UUID(str(tenant_context.tenant_id)),
            jurisdiction=tenant_context.jurisdiction,
            name=record.name,
            mode=mode,
            control=ControlAxis(record.control),
            subject=Subject(record.subject),
            lever_commitment_id=lever_commitment_id,
            lever_commitment_ids=lever_commitment_ids,
            ladder=ladder,
            terminal=terminal,
            steps=steps,
            aliases=tuple(getattr(record, "aliases", ()) or ()),
            domain=getattr(record, "domain", None),
        )

    async def list_goals(
        self, *, tenant_context: TenantContext
    ) -> tuple[Goal, ...]:
        records = await self._outcome_graph.list_outcomes(
            tenant_context=tenant_context
        )
        return tuple(
            self._to_goal(record, tenant_context=tenant_context)
            for record in records
        )

    async def raise_target_level(
        self,
        *,
        tenant_context: TenantContext,
        outcome_id: UUID,
        new_target_level: str,
    ) -> str | None:
        return await self._outcome_graph.set_outcome_target(
            tenant_context=tenant_context,
            outcome_id=outcome_id,
            current_target_level=new_target_level,
        )


class TasksReaderAdapter:
    """apps/ adapter reading the tasks cache for the daily-driver Tasks view (D167).

    Composes the tasks context's ``PostgresTaskStore`` (bound to the request's
    tenant — isolation defence-in-depth) and lists the non-deleted tasks. The
    Tasks view is **its own list**, uncorrelated to calendar or goals (D167);
    correlation into units of work is P18, so this reader does not touch
    ``build_today_view`` or the goal graph. apps/ may import a producer
    context's adapter directly (the calendar ``PostgresMeetingStore`` precedent).
    """

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def list_tasks(
        self, *, actor: ActorContext, include_completed: bool = True
    ) -> tuple[Task, ...]:
        sessionmaker = await self._session_factory_for_tenant(
            actor.tenant_context
        )
        store = PostgresTaskStore(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(actor.tenant_context.tenant_id)),
        )
        return await store.list_tasks(
            tenant_context=actor.tenant_context,
            include_completed=include_completed,
        )


def build_tasks_reader(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> TasksReaderAdapter:
    """Wire the daily-driver Tasks reader over the tasks cache (D167)."""
    return TasksReaderAdapter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


class FacetSourceAdapter:
    """apps/ adapter implementing daily-driver's ``FacetSource`` (D168, D17).

    Composes the three read-only ingested caches (tasks, calendar, email — each
    store bound to the request's tenant, the isolation defence-in-depth) into the
    flat ``WorkFacet`` list the correlation matcher consumes. The stores decrypt
    content on read, so the matcher sees plaintext titles. Only correlation
    candidates are surfaced: open tasks, non-cancelled meetings, non-deleted
    emails. apps/ may import a producer context's adapter directly (the calendar
    ``PostgresMeetingStore`` precedent).
    """

    def __init__(
        self, *, session_factory_for_tenant: _SessionFactoryForTenant
    ) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def list_facets(
        self, *, actor: ActorContext
    ) -> tuple[WorkFacet, ...]:
        sessionmaker = await self._session_factory_for_tenant(
            actor.tenant_context
        )
        bound = TenantId(str(actor.tenant_context.tenant_id))
        resolver = _resolver_for(sessionmaker)
        tasks = PostgresTaskStore(
            per_tenant_sessionmaker_resolver=resolver, bound_tenant_id=bound
        )
        meetings = PostgresMeetingStore(
            per_tenant_sessionmaker_resolver=resolver, bound_tenant_id=bound
        )
        emails = PostgresEmailStore(
            per_tenant_sessionmaker_resolver=resolver, bound_tenant_id=bound
        )
        facets: list[WorkFacet] = []
        for task in await tasks.list_tasks(
            tenant_context=actor.tenant_context, include_completed=False
        ):
            facets.append(
                WorkFacet(
                    facet_type=FacetType.TASK,
                    facet_id=task.id,
                    title=task.title or "",
                    occurred_at=task.due_at,
                )
            )
        for meeting in await meetings.list_meetings(
            tenant_context=actor.tenant_context, include_cancelled=False
        ):
            facets.append(
                WorkFacet(
                    facet_type=FacetType.MEETING,
                    facet_id=meeting.id,
                    title=meeting.title or "",
                    occurred_at=meeting.start_at,
                    # The recurring-series id for read-time grouping (D175);
                    # None for a one-off meeting.
                    series_id=meeting.recurring_event_id,
                )
            )
        for email in await emails.list_emails(
            tenant_context=actor.tenant_context, include_deleted=False
        ):
            facets.append(
                WorkFacet(
                    facet_type=FacetType.EMAIL,
                    facet_id=email.id,
                    title=email.subject or "",
                    occurred_at=email.received_at,
                )
            )
        return tuple(facets)


class UnitGraphAdapter:
    """apps/ adapter implementing daily-driver's ``UnitGraphPort`` over
    ingestion's ``UnitGraphPort`` (D168, D17).

    The bridge from the daily-driver unit layer to the shared graph: maps the
    daily-driver ``WorkUnit`` onto ingestion's primitive ``UnitWrite`` for the
    write, and ingestion's ``UnitGraphRecord`` onto the daily-driver
    ``UnitRecord`` for the read (the ``GoalGraphAdapter`` precedent). The
    underlying ``Neo4jGraphRepository`` is process-shared; tenant scoping flows
    through ``tenant_context`` on every call.
    """

    def __init__(self, *, unit_graph: Any) -> None:
        self._unit_graph = unit_graph

    async def replace_units(
        self, *, tenant_context: TenantContext, units: Any
    ) -> None:
        writes = [
            UnitWrite(
                unit_id=unit.unit_id,
                links=tuple(
                    FacetLinkWrite(
                        facet_type=link.facet.facet_type.value,
                        facet_id=link.facet.facet_id,
                        confidence=link.confidence,
                        status=link.status.value,
                        basis=link.basis,
                    )
                    for link in unit.links
                ),
            )
            for unit in units
        ]
        await self._unit_graph.replace_units(
            tenant_context=tenant_context, units=writes
        )

    async def list_units(
        self, *, tenant_context: TenantContext
    ) -> tuple[UnitRecord, ...]:
        records = await self._unit_graph.list_units(
            tenant_context=tenant_context
        )
        return tuple(
            UnitRecord(
                unit_id=record.unit_id,
                facets=tuple(
                    UnitFacetRef(
                        facet_type=FacetType(link.facet_type),
                        facet_id=link.facet_id,
                        confidence=link.confidence,
                        status=LinkStatus(link.status),
                        basis=link.basis,
                    )
                    for link in record.links
                ),
            )
            for record in records
        )

    async def replace_goal_edges(
        self, *, tenant_context: TenantContext, edges: Any
    ) -> None:
        writes = [
            GoalEdgeWrite(
                unit_id=edge.unit_id,
                outcome_id=edge.outcome_id,
                confidence=edge.confidence,
                status=edge.status.value,
                basis=edge.basis,
            )
            for edge in edges
        ]
        await self._unit_graph.replace_goal_edges(
            tenant_context=tenant_context, edges=writes
        )

    async def list_goal_edges(
        self, *, tenant_context: TenantContext
    ) -> tuple[GoalEdge, ...]:
        records = await self._unit_graph.list_goal_edges(
            tenant_context=tenant_context
        )
        return tuple(
            GoalEdge(
                unit_id=record.unit_id,
                outcome_id=record.outcome_id,
                confidence=record.confidence,
                status=LinkStatus(record.status),
                basis=record.basis,
            )
            for record in records
        )


def build_facet_source(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> FacetSourceAdapter:
    """Wire the daily-driver FacetSource over the three caches (D168, D17)."""
    return FacetSourceAdapter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


def build_unit_graph() -> UnitGraphAdapter:
    """Wire the daily-driver UnitGraphPort over the shared graph (D168, D17).

    The ``Neo4jGraphRepository`` is process-shared (the ``build_goal_graph``
    precedent) and imported lazily so this module stays importable without a live
    Neo4j; tenant scoping flows through the ``tenant_context`` on each call.
    """
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings

    return UnitGraphAdapter(
        unit_graph=Neo4jGraphRepository.from_settings(Neo4jSettings())
    )


def build_commitment_repository(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> CommitmentRepositoryRouter:
    """Wire the daily-driver CommitmentRepository (D157)."""
    return CommitmentRepositoryRouter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


def build_day_repository(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> DayRepositoryRouter:
    """Wire the daily-driver DayRepository (D157)."""
    return DayRepositoryRouter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


def build_open_cases_reader(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> OpenCasesReaderAdapter:
    """Wire the daily-driver OpenCasesReader consumer adapter (D157, D17)."""
    return OpenCasesReaderAdapter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


def build_calendar_events_reader(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
    domain_tag: str,
) -> CalendarEventsReaderAdapter:
    """Wire the daily-driver CalendarEventsReader consumer adapter (D159, D17)."""
    return CalendarEventsReaderAdapter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        ),
        domain_tag=domain_tag,
    )


def build_goal_graph() -> GoalGraphAdapter:
    """Wire the daily-driver GoalGraphPort over the shared graph (D163, D17).

    The ``Neo4jGraphRepository`` is process-shared (the calendar precedent) and
    imported lazily so this module stays importable without a live Neo4j; tenant
    scoping flows through the ``tenant_context`` on each call.
    """
    from contexts.ingestion.adapters.outbound.neo4j import Neo4jGraphRepository
    from padhanam.config import Neo4jSettings

    return GoalGraphAdapter(
        outcome_graph=Neo4jGraphRepository.from_settings(Neo4jSettings())
    )


__all__ = [
    "CalendarEventsReaderAdapter",
    "CommitmentRepositoryRouter",
    "DayRepositoryRouter",
    "FacetSourceAdapter",
    "GoalGraphAdapter",
    "OpenCasesReaderAdapter",
    "TasksReaderAdapter",
    "UnitGraphAdapter",
    "build_calendar_events_reader",
    "build_commitment_repository",
    "build_day_repository",
    "build_facet_source",
    "build_goal_graph",
    "build_open_cases_reader",
    "build_tasks_reader",
    "build_unit_graph",
]
