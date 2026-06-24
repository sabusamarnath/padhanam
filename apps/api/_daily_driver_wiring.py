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
from contexts.daily_driver.domain.cdd import (
    DRAFT_SCHEMA,
    AuthoredEdgeView,
    AuthoredElement,
    DraftedCdd,
    ElementKind,
    GoalCddView,
    ProofState,
    ProvenanceOrigin,
    build_draft_prompt,
    parse_cdd_draft,
)
from contexts.daily_driver.ports.cdd_drafter import CddDrafterPort
from shared_kernel.structured_output import (
    StructuredOutputParseFailure,
    StructuredOutputPort,
    StructuredOutputRequest,
)
from contexts.daily_driver.domain.commitment import (
    CheckinResponse,
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
from contexts.daily_driver.domain.goal_assessment import (
    WEAK_KEYWORD_BASIS,
    ElementEvidence,
    GoalEdge,
    derive_goal_edges,
)
from contexts.daily_driver.domain.unit_view import UnitView
from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
    WorkFacet,
    WorkUnit,
)
from contexts.matcher_evaluation.adapters.outbound.postgres import (
    PostgresMatcherQualityRunRepository,
)
from contexts.matcher_evaluation.application import record_matcher_quality_run
from contexts.matcher_evaluation.domain import EdgeSample, MatcherQualitySample
from contexts.matcher_policy.adapters.outbound.postgres import (
    PostgresMatcherPolicyReader,
)
from contexts.daily_driver.ports.email_job_search_source import (
    EmailJobSearchClassification,
)
from contexts.daily_driver.ports.unit_graph import UnitFacetRef, UnitRecord
from contexts.email.adapters.outbound.postgres.email_store import (
    PostgresEmailStore,
)
from contexts.portfolio.adapters.outbound.postgres.portfolio_reader import (
    PostgresPortfolioReader,
)
from contexts.ingestion.ports.unit_graph_port import (
    ElementEvidenceWrite,
    FacetLinkWrite,
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

    async def add_checkin_response(
        self,
        *,
        tenant_context: TenantContext,
        response: CheckinResponse,
    ) -> None:
        repo = await self._build(tenant_context)
        await repo.add_checkin_response(
            tenant_context=tenant_context, response=response
        )

    async def completion_exists_on_day(
        self,
        *,
        tenant_context: TenantContext,
        commitment_id: UUID,
        day: date,
    ) -> bool:
        repo = await self._build(tenant_context)
        return await repo.completion_exists_on_day(
            tenant_context=tenant_context,
            commitment_id=commitment_id,
            day=day,
        )

    async def checkin_response_exists_on_day(
        self,
        *,
        tenant_context: TenantContext,
        commitment_id: UUID,
        beat_date: date,
    ) -> bool:
        repo = await self._build(tenant_context)
        return await repo.checkin_response_exists_on_day(
            tenant_context=tenant_context,
            commitment_id=commitment_id,
            beat_date=beat_date,
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

    # --- Authored CDD layer (S102, D200): bridge to OutcomeGraphPort -------

    async def write_authored_element(
        self, *, tenant_context, outcome_id, kind, element_id, label, origin,
        proof_state,
    ) -> None:
        await self._outcome_graph.merge_authored_element(
            tenant_context=tenant_context, outcome_id=outcome_id,
            element_kind=kind.value, element_id=element_id, label=label,
            provenance_origin=origin.value, proof_state=proof_state.value,
        )

    async def write_authored_edge(
        self, *, tenant_context, edge_type, source_kind, source_id, target_kind,
        target_id,
    ) -> None:
        await self._outcome_graph.merge_authored_edge(
            tenant_context=tenant_context, edge_type=edge_type,
            source_kind=source_kind, source_id=source_id,
            target_kind=target_kind, target_id=target_id,
        )

    async def set_authored_outcome(
        self, *, tenant_context, outcome_id, expected_outcome, origin, proof_state,
    ) -> None:
        await self._outcome_graph.set_authored_outcome(
            tenant_context=tenant_context, outcome_id=outcome_id,
            expected_outcome=expected_outcome,
            provenance_origin=origin.value, proof_state=proof_state.value,
        )

    async def accept_authored_outcome(self, *, tenant_context, outcome_id) -> bool:
        return await self._outcome_graph.accept_authored_outcome(
            tenant_context=tenant_context, outcome_id=outcome_id
        )

    async def reject_authored_outcome(self, *, tenant_context, outcome_id) -> bool:
        return await self._outcome_graph.clear_authored_outcome(
            tenant_context=tenant_context, outcome_id=outcome_id
        )

    async def read_goal_cdd(self, *, tenant_context, outcome_id) -> GoalCddView:
        record = await self._outcome_graph.read_authored_cdd(
            tenant_context=tenant_context, outcome_id=outcome_id
        )
        elements = tuple(
            AuthoredElement(
                kind=ElementKind(e.element_kind),
                element_id=e.element_id,
                label=e.label,
                provenance_origin=ProvenanceOrigin(e.provenance_origin),
                proof_state=ProofState(e.proof_state),
                gate_id=e.gate_id,
            )
            for e in record.elements
        )
        edges = tuple(
            AuthoredEdgeView(
                edge_type=edge.edge_type,
                source_kind=edge.source_kind,
                source_id=edge.source_id,
                target_kind=edge.target_kind,
                target_id=edge.target_id,
                needs_review=edge.needs_review,
            )
            for edge in record.edges
        )
        outcome_origin = (
            ProvenanceOrigin(record.expected_outcome_origin)
            if record.expected_outcome_origin is not None
            else None
        )
        outcome_proof = (
            ProofState(record.expected_outcome_proof_state)
            if record.expected_outcome_proof_state is not None
            else None
        )
        return GoalCddView(
            outcome_id=outcome_id,
            expected_outcome=record.expected_outcome or "",
            elements=elements,
            edges=edges,
            expected_outcome_origin=outcome_origin,
            expected_outcome_proof_state=outcome_proof,
        )

    async def accept_authored_element(
        self, *, tenant_context, kind, element_id,
    ) -> bool:
        return await self._outcome_graph.set_authored_proof_state(
            tenant_context=tenant_context, element_kind=kind.value,
            element_id=element_id, proof_state=ProofState.ACCEPTED.value,
        )

    async def correct_authored_element(
        self, *, tenant_context, kind, element_id, label,
    ) -> bool:
        return await self._outcome_graph.set_authored_label(
            tenant_context=tenant_context, element_kind=kind.value,
            element_id=element_id, label=label,
        )

    async def reject_authored_element(
        self, *, tenant_context, kind, element_id,
    ) -> bool:
        return await self._outcome_graph.delete_authored_element(
            tenant_context=tenant_context, element_kind=kind.value,
            element_id=element_id,
        )

    async def reclassify_authored_element(
        self, *, tenant_context, from_kind, to_kind, element_id,
    ) -> bool:
        return await self._outcome_graph.reclassify_authored_element(
            tenant_context=tenant_context, from_kind=from_kind.value,
            to_kind=to_kind.value, element_id=element_id,
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

    async def replace_element_evidence(
        self, *, tenant_context: TenantContext, evidence: Any
    ) -> None:
        writes = [
            ElementEvidenceWrite(
                unit_id=ev.unit_id,
                element_kind=ev.element_kind,
                element_id=ev.element_id,
                tier=ev.tier,
                status=ev.status.value,
                basis=ev.basis,
            )
            for ev in evidence
        ]
        await self._unit_graph.replace_element_evidence(
            tenant_context=tenant_context, evidence=writes
        )

    async def list_element_evidence(
        self, *, tenant_context: TenantContext
    ) -> tuple[ElementEvidence, ...]:
        records = await self._unit_graph.list_element_evidence(
            tenant_context=tenant_context
        )
        return tuple(
            ElementEvidence(
                unit_id=record.unit_id,
                element_kind=record.element_kind,
                element_id=record.element_id,
                outcome_id=record.outcome_id,
                tier=record.tier,
                status=LinkStatus(record.status),
                basis=record.basis,
            )
            for record in records
        )

    async def list_goal_edges(
        self, *, tenant_context: TenantContext
    ) -> tuple[GoalEdge, ...]:
        # Derive the goal level on read from element evidence (D202, S103b): the
        # written SERVES edge is retired, so the goal rollup comes from the units'
        # element bindings, leaving the coverage/grouping readers untouched.
        evidence = await self.list_element_evidence(tenant_context=tenant_context)
        return derive_goal_edges(evidence)

    async def list_user_owned_unit_ids(
        self, *, tenant_context: TenantContext
    ) -> set:
        return await self._unit_graph.list_user_owned_unit_ids(
            tenant_context=tenant_context
        )

    async def unlink_element_evidence(
        self, *, tenant_context: TenantContext, unit_id, element_kind, element_id
    ) -> bool:
        # element_kind is an EVIDENCES endpoint kind string (incl. "outcome",
        # S103c-fix-3); the graph composes the label from its whitelist.
        return await self._unit_graph.unlink_element_evidence(
            tenant_context=tenant_context, unit_id=unit_id,
            element_kind=element_kind, element_id=element_id,
        )

    async def relink_element_evidence(
        self, *, tenant_context: TenantContext, unit_id, from_kind,
        from_element_id, to_kind, to_element_id,
    ) -> bool:
        return await self._unit_graph.relink_element_evidence(
            tenant_context=tenant_context, unit_id=unit_id,
            from_kind=from_kind, from_element_id=from_element_id,
            to_kind=to_kind, to_element_id=to_element_id,
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


class EmailJobSearchSourceAdapter:
    """apps/ adapter implementing daily-driver's ``EmailJobSearchSource`` over the
    email store's persisted classifier verdict (D183/S89, D17). Reads which email
    facets the rules confirmed as job-search — durable state, re-read each
    correlate run — without the daily-driver context importing the email store.
    """

    def __init__(self, *, session_factory_for_tenant: _SessionFactoryForTenant) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def list_confirmed(
        self, *, actor: ActorContext
    ) -> tuple[EmailJobSearchClassification, ...]:
        sessionmaker = await self._session_factory_for_tenant(actor.tenant_context)
        bound = TenantId(str(actor.tenant_context.tenant_id))
        emails = PostgresEmailStore(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=bound,
        )
        rows = await emails.list_job_search_classifications(
            tenant_context=actor.tenant_context
        )
        return tuple(
            EmailJobSearchClassification(facet_id=fid, kind=kind, occurred_at=rec)
            for fid, kind, rec in rows
        )


def build_email_job_search_source(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> EmailJobSearchSourceAdapter:
    """Wire the daily-driver EmailJobSearchSource over the email store (D183)."""
    return EmailJobSearchSourceAdapter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


def _edge_to_sample(edge: GoalEdge) -> EdgeSample:
    """Project one matcher SERVES edge to the producer's neutral sample.

    The matcher's vocabulary (the weak ``goal-name`` basis, the CANDIDATE /
    CONFIRMED status) is single-sourced from ``daily_driver`` here at the
    composition root, so the producer (``matcher_evaluation``) stays independent
    of it (D17). Status maps the confidence tiers: CANDIDATE is the 0.5 guess,
    CONFIRMED the 0.9 / 0.95 settle.
    """
    return EdgeSample(
        unit_id=edge.unit_id,
        is_single_signal=edge.basis == WEAK_KEYWORD_BASIS,
        is_candidate=edge.status is LinkStatus.CANDIDATE,
        is_confirmed=edge.status is LinkStatus.CONFIRMED,
    )


class MatcherQualityRecorderAdapter:
    """apps/ bridge implementing daily-driver's ``MatcherQualityRecorder`` over the
    ``matcher_evaluation`` producer (D185/S90, D17). The observe-only correlate
    hook calls ``record`` with the final SERVES edges + units; this projects them
    to the producer's neutral, label-free sample and persists a quality run —
    without the daily-driver context importing the producer. Counts and rates
    only; nothing content-bearing crosses the seam.
    """

    def __init__(self, *, session_factory_for_tenant: _SessionFactoryForTenant) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def record(
        self,
        *,
        actor: ActorContext,
        edges: tuple[GoalEdge, ...],
        units: tuple[UnitView, ...],
    ) -> None:
        sample = MatcherQualitySample(
            edges=tuple(_edge_to_sample(e) for e in edges),
            unit_ids=frozenset(u.unit_id for u in units),
        )
        sessionmaker = await self._session_factory_for_tenant(actor.tenant_context)
        repository = PostgresMatcherQualityRunRepository(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(actor.tenant_context.tenant_id)),
        )
        await record_matcher_quality_run(
            tenant_context=actor.tenant_context,
            sample=sample,
            repository=repository,
        )


def build_matcher_quality_recorder(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> MatcherQualityRecorderAdapter:
    """Wire the matcher-quality recorder over the producer's store (D185)."""
    return MatcherQualityRecorderAdapter(
        session_factory_for_tenant=_session_factory_builder(
            tenant_registry=tenant_registry,
            session_factory_cache=session_factory_cache,
            operator_principal=operator_principal,
            security_events=security_events,
        )
    )


class SuppressionPolicyAdapter:
    """apps/ bridge implementing daily-driver's ``SuppressionPolicy`` over the
    neutral ``matcher_policy`` reader (D186/S91b, D17). The matcher reads the
    active policy at the correlate hook through this bridge — without the
    daily-driver context importing the policy surface or optimization. Reads the
    read half of the seam only; the write half is optimization's, on apply.
    """

    def __init__(self, *, session_factory_for_tenant: _SessionFactoryForTenant) -> None:
        self._session_factory_for_tenant = session_factory_for_tenant

    async def suppress_single_signal(self, *, actor: ActorContext) -> bool:
        sessionmaker = await self._session_factory_for_tenant(actor.tenant_context)
        reader = PostgresMatcherPolicyReader(
            per_tenant_sessionmaker_resolver=_resolver_for(sessionmaker),
            bound_tenant_id=TenantId(str(actor.tenant_context.tenant_id)),
        )
        policy = await reader.get_policy(tenant_context=actor.tenant_context)
        return policy.suppress_single_signal


def build_suppression_policy(
    *,
    tenant_registry: PostgresTenantRegistry,
    session_factory_cache: TenantSessionFactoryCache,
    operator_principal: Principal,
    security_events: SecurityEventLogger,
) -> SuppressionPolicyAdapter:
    """Wire the matcher suppression-policy read over the neutral surface (D186)."""
    return SuppressionPolicyAdapter(
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


class CddDrafterAdapter:
    """apps/ adapter implementing daily-driver's ``CddDrafterPort`` over the
    provider-agnostic ``StructuredOutputPort`` (S102, D200 — the checkin
    reply-parse precedent).

    The pure domain helpers (``contexts.daily_driver.domain.cdd``) build the
    prompt + schema and parse the response; the litellm SDK stays confined to the
    inference adapter, never here or in the daily-driver context.
    """

    def __init__(self, *, structured_output_port: StructuredOutputPort) -> None:
        self._structured_output = structured_output_port

    async def draft(
        self, *, goal_name: str, mode: str, lever_names: tuple[str, ...]
    ) -> DraftedCdd | None:
        request = StructuredOutputRequest(
            prompt=build_draft_prompt(
                goal_name=goal_name, mode=mode, lever_names=lever_names
            ),
            schema=DRAFT_SCHEMA,
        )
        try:
            response = await self._structured_output.generate_structured(request)
        except StructuredOutputParseFailure:
            # No schema-conforming draft — the use case persists nothing.
            return None
        return parse_cdd_draft(response.value)


def build_cdd_drafter(
    *, structured_output_port: StructuredOutputPort
) -> CddDrafterAdapter:
    """Wire daily-driver's ``CddDrafterPort`` over the structured-output seam."""
    return CddDrafterAdapter(structured_output_port=structured_output_port)


__all__ = [
    "CalendarEventsReaderAdapter",
    "CddDrafterAdapter",
    "CommitmentRepositoryRouter",
    "DayRepositoryRouter",
    "FacetSourceAdapter",
    "GoalGraphAdapter",
    "OpenCasesReaderAdapter",
    "TasksReaderAdapter",
    "UnitGraphAdapter",
    "build_calendar_events_reader",
    "build_cdd_drafter",
    "build_commitment_repository",
    "build_day_repository",
    "build_facet_source",
    "build_goal_graph",
    "build_open_cases_reader",
    "build_tasks_reader",
    "build_unit_graph",
]
