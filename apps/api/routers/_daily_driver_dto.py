"""HTTP DTOs for the daily-driver routes (D157, S58).

Response models mirror the domain value objects 1:1; request models
carry the minimal user-authored inputs. Pydantic v2 BaseModel, the
portfolio-DTO precedent.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from contexts.daily_driver.domain.commitment import OutcomeStatus
from contexts.daily_driver.domain.goal_view import ChainReading, GoalReading
from contexts.daily_driver.domain.today_item import (
    ItemKind,
    TodayItem,
    TodayView,
)
from contexts.daily_driver.domain.facet_suggestion import FacetSuggestion
from contexts.daily_driver.domain.goal_assessment import (
    GoalAssessment,
    GoalGroupedUnits,
)
from contexts.daily_driver.domain.unit_view import UnitView
from contexts.tasks.domain.task import Task


class TodayItemDTO(BaseModel):
    """One rendered row on the prioritised-today surface."""

    kind: str
    item_id: UUID
    title: str
    status: str
    target_cell: str
    artefact_type: str
    detail: str
    position: int | None
    done: bool
    overdue_by_days: int | None
    domain: str
    start_at: datetime | None
    # S61 (D162) — the expected-versus-observed loop on the row.
    expected_outcome: str | None
    observed_outcome: str | None
    outcome_status: str | None
    drop_candidate: bool


class TodayDTO(BaseModel):
    """The ordered prioritised-today list.

    ``items`` is the live today-forward plan; ``history`` is the observed
    stream of completed/ended items today (D175 time-scoping, feeding D162).
    """

    day_date: date
    items: list[TodayItemDTO]
    history: list[TodayItemDTO] = []


class CommitmentDTO(BaseModel):
    """A user-authored Commitment."""

    id: UUID
    name: str
    expected_interval_days: int
    created_at: datetime
    expected_outcome: str | None = None
    observed_outcome: str | None = None
    outcome_status: str | None = None
    observed_at: datetime | None = None


class CompletionDTO(BaseModel):
    """One completion-log entry."""

    id: UUID
    commitment_id: UUID
    completed_at: datetime


class CreateCommitmentRequest(BaseModel):
    """Create a user-authored Commitment."""

    name: str = Field(min_length=1)
    expected_interval_days: int = Field(gt=0)
    # S61 (D162): the free-text expectation captured forward at creation.
    expected_outcome: str | None = None


class RecordObservedOutcomeRequest(BaseModel):
    """Record what transpired for a Commitment (D162).

    ``observed_outcome`` is free text (optional — a drop can carry no
    note); ``outcome_status`` is the coarse human-set status. Setting
    ``dropped`` is how the operator acts on a drop-candidate nudge.
    """

    observed_outcome: str | None = None
    outcome_status: OutcomeStatus


class ItemRef(BaseModel):
    """A (kind, id) reference to a today-item."""

    kind: ItemKind
    item_id: UUID


class SetOrderRequest(BaseModel):
    """The user's explicit ordering of today-items."""

    ordered: list[ItemRef]


class MarkDoneRequest(BaseModel):
    """Set or clear an item's done-for-today mark."""

    kind: ItemKind
    item_id: UUID
    done: bool


class GoalStepDTO(BaseModel):
    """One lever step in a sequence goal's chain view (D163, S63)."""

    name: str
    order: int
    state: str
    is_active: bool


class GoalReadingDTO(BaseModel):
    """A goal read against its lever(s) (D163).

    ``remedy_kind`` discriminates the shape: ``raise_or_hold`` (progressive) or
    ``unblock_or_drop`` (sequence). Progressive fields (``ladder``,
    ``current_target``, ``next_target``) are ``None`` for a sequence goal;
    sequence fields (``terminal_target``, ``terminal_state``, ``steps``,
    ``active_step``) are absent/empty for a progressive goal.
    """

    outcome_id: UUID
    name: str
    mode: str
    control: str
    subject: str
    remedy_kind: str
    # progressive (raise-or-hold)
    lever_commitment_id: UUID | None = None
    ladder: list[str] | None = None
    current_target: str | None = None
    next_target: str | None = None
    # sequence (unblock-or-drop)
    terminal_target: str | None = None
    terminal_state: str | None = None
    steps: list[GoalStepDTO] = []
    active_step: str | None = None
    # common
    progress_summary: str
    gap_summary: str
    recommendation: str
    reason: str


def goal_reading_to_dto(reading: GoalReading | ChainReading) -> GoalReadingDTO:
    """Encode a domain reading into the HTTP DTO, dispatching on shape (D163)."""
    if isinstance(reading, ChainReading):
        return _chain_reading_to_dto(reading)
    return _goal_reading_to_dto(reading)


def _goal_reading_to_dto(reading: GoalReading) -> GoalReadingDTO:
    goal = reading.goal
    return GoalReadingDTO(
        outcome_id=goal.id,
        name=goal.name,
        mode=goal.mode.value,
        control=goal.control.value,
        subject=goal.subject.value,
        remedy_kind="raise_or_hold",
        lever_commitment_id=goal.lever_commitment_id,
        ladder=list(goal.ladder.levels) if goal.ladder is not None else None,
        current_target=reading.current_target,
        next_target=reading.next_target,
        progress_summary=reading.progress_summary,
        gap_summary=reading.gap_summary,
        recommendation=reading.recommendation.value,
        reason=reading.reason,
    )


def _chain_reading_to_dto(reading: ChainReading) -> GoalReadingDTO:
    goal = reading.goal
    return GoalReadingDTO(
        outcome_id=goal.id,
        name=goal.name,
        mode=goal.mode.value,
        control=goal.control.value,
        subject=goal.subject.value,
        remedy_kind="unblock_or_drop",
        terminal_target=reading.terminal_target,
        terminal_state=reading.terminal_state,
        steps=[
            GoalStepDTO(
                name=s.name,
                order=s.order,
                state=s.state.value,
                is_active=s.is_active,
            )
            for s in reading.steps
        ],
        active_step=reading.active_step_name,
        progress_summary=reading.chain_summary,
        gap_summary=reading.chain_summary,
        recommendation=reading.recommendation.value,
        reason=reading.reason,
    )


class TaskDTO(BaseModel):
    """One ingested Google task in the daily-driver Tasks view (D167).

    Its own view — not correlated to calendar or goals (correlation is P18).
    """

    google_task_id: str
    tasklist_id: str
    tasklist_title: str | None
    status: str
    title: str | None
    notes: str | None
    due_at: datetime | None
    completed_at: datetime | None


def task_to_dto(task: Task) -> TaskDTO:
    """Encode an ingested Task into the HTTP DTO (D167)."""
    return TaskDTO(
        google_task_id=task.google_task_id,
        tasklist_id=task.tasklist_id,
        tasklist_title=task.tasklist_title,
        status=task.status.value,
        title=task.title,
        notes=task.notes,
        due_at=task.due_at,
        completed_at=task.completed_at,
    )


class UnitFacetDTO(BaseModel):
    """One facet of a correlated unit (D168)."""

    facet_type: str
    facet_id: UUID
    title: str
    occurred_at: datetime | None
    status: str
    confidence: float
    basis: str
    present: bool


class UnitDTO(BaseModel):
    """One correlated unit of work in the daily-driver Units view (D168, D166).

    Shown as a unit — its facets (task, calendar block, email-origin) grouped —
    rather than as separate rows. ``has_candidate`` flags a below-floor facet
    surfaced as a suggestion-to-confirm, not an asserted link.
    """

    unit_id: UUID
    title: str
    is_correlated: bool
    has_candidate: bool
    facets: list[UnitFacetDTO]


def unit_view_to_dto(view: UnitView) -> UnitDTO:
    """Encode a domain UnitView into the HTTP DTO (D168)."""
    return UnitDTO(
        unit_id=view.unit_id,
        title=view.title,
        is_correlated=view.is_correlated,
        has_candidate=view.has_candidate,
        facets=[
            UnitFacetDTO(
                facet_type=f.facet_type.value,
                facet_id=f.facet_id,
                title=f.title,
                occurred_at=f.occurred_at,
                status=f.status.value,
                confidence=f.confidence,
                basis=f.basis,
                present=f.present,
            )
            for f in view.facets
        ],
    )


class CoverageDTO(BaseModel):
    """The assessment's coverage boundary (D171)."""

    goals_total: int
    goals_covered: int
    units_total: int
    units_linked: int
    has_coverage: bool


class UncoveredGoalDTO(BaseModel):
    """A goal with no linked evidence — uncovered, not neglected (D171)."""

    outcome_id: UUID
    name: str
    reason: str


class OrphanUnitDTO(BaseModel):
    """A unit Padhanam couldn't link to a goal (D169) — coverage-gated (D171)."""

    unit_id: UUID
    title: str
    facet_count: int
    is_correlated: bool
    reason: str
    # Recurrence fold (D175): one row per source series, carrying its instance
    # count; ``instance_count`` is 1 for a one-off, N for a recurring series.
    instance_count: int = 1
    series_id: str | None = None


class GoalAssessmentDTO(BaseModel):
    """The coverage-honest moat reads (D169, D171, D166)."""

    coverage: CoverageDTO
    uncovered_goals: list[UncoveredGoalDTO]
    orphan_work: list[OrphanUnitDTO]


def _empty_assessment_dto() -> "GoalAssessmentDTO":
    """The zero-coverage assessment for an unwired/empty instance (D171)."""
    return GoalAssessmentDTO(
        coverage=CoverageDTO(
            goals_total=0, goals_covered=0, units_total=0,
            units_linked=0, has_coverage=False,
        ),
        uncovered_goals=[],
        orphan_work=[],
    )


def goal_assessment_to_dto(assessment: GoalAssessment) -> GoalAssessmentDTO:
    """Encode the domain GoalAssessment into the HTTP DTO (D169, D171)."""
    c = assessment.coverage
    return GoalAssessmentDTO(
        coverage=CoverageDTO(
            goals_total=c.goals_total,
            goals_covered=c.goals_covered,
            units_total=c.units_total,
            units_linked=c.units_linked,
            has_coverage=c.has_coverage,
        ),
        uncovered_goals=[
            UncoveredGoalDTO(
                outcome_id=g.outcome_id, name=g.name, reason=g.reason
            )
            for g in assessment.uncovered_goals
        ],
        orphan_work=[
            OrphanUnitDTO(
                unit_id=o.unit_id,
                title=o.title,
                facet_count=o.facet_count,
                is_correlated=o.is_correlated,
                reason=o.reason,
                instance_count=o.instance_count,
                series_id=o.series_id,
            )
            for o in assessment.orphan_work
        ],
    )


# --- D180: the moat view anchored on the goal served --------------------------


class GroupedUnitDTO(BaseModel):
    """One folded unit row inside a group (D180; the D175 fold applied)."""

    unit_id: UUID
    title: str
    facet_count: int
    is_correlated: bool
    confirmed: bool
    facet_types: list[str] = []
    instance_count: int = 1
    series_id: str | None = None


class GoalGroupDTO(BaseModel):
    """A goal gathering the units that serve it (D180)."""

    outcome_id: UUID
    name: str
    domain: str | None
    units: list[GroupedUnitDTO]
    # D183/S89: job-search email activity folded to a count by kind (emails are
    # seriesless), and whether that activity is recent (the active reading).
    email_activity: dict[str, int] = {}
    active: bool = False


class GoalGroupedUnitsDTO(BaseModel):
    """The moat view anchored on the goal served (D180): groups + unlinked."""

    coverage: CoverageDTO
    groups: list[GoalGroupDTO]
    unlinked: list[GroupedUnitDTO]


def _grouped_unit_dto(u) -> "GroupedUnitDTO":
    return GroupedUnitDTO(
        unit_id=u.unit_id,
        title=u.title,
        facet_count=u.facet_count,
        is_correlated=u.is_correlated,
        confirmed=u.confirmed,
        facet_types=list(u.facet_types),
        instance_count=u.instance_count,
        series_id=u.series_id,
    )


def _empty_grouped_units_dto() -> "GoalGroupedUnitsDTO":
    """The zero-coverage grouped view for an unwired/empty instance (D171)."""
    return GoalGroupedUnitsDTO(
        coverage=CoverageDTO(
            goals_total=0, goals_covered=0, units_total=0,
            units_linked=0, has_coverage=False,
        ),
        groups=[],
        unlinked=[],
    )


def grouped_units_to_dto(grouped: GoalGroupedUnits) -> GoalGroupedUnitsDTO:
    """Encode the domain GoalGroupedUnits into the HTTP DTO (D180)."""
    c = grouped.coverage
    return GoalGroupedUnitsDTO(
        coverage=CoverageDTO(
            goals_total=c.goals_total,
            goals_covered=c.goals_covered,
            units_total=c.units_total,
            units_linked=c.units_linked,
            has_coverage=c.has_coverage,
        ),
        groups=[
            GoalGroupDTO(
                outcome_id=g.outcome_id,
                name=g.name,
                domain=g.domain,
                units=[_grouped_unit_dto(u) for u in g.units],
                email_activity=dict(g.email_activity),
                active=g.active,
            )
            for g in grouped.groups
        ],
        unlinked=[_grouped_unit_dto(u) for u in grouped.unlinked],
    )


class FacetSuggestionDTO(BaseModel):
    """One missing-facet suggestion (D170) — recommendation-shaped."""

    unit_id: UUID
    kind: str
    subject: str
    suggestion: str


def facet_suggestion_to_dto(s: FacetSuggestion) -> FacetSuggestionDTO:
    """Encode a domain FacetSuggestion into the HTTP DTO (D170)."""
    return FacetSuggestionDTO(
        unit_id=s.unit_id,
        kind=s.kind.value,
        subject=s.subject,
        suggestion=s.suggestion,
    )


def today_view_to_dto(view: TodayView) -> TodayDTO:
    """Encode a domain TodayView into the HTTP DTO."""
    return TodayDTO(
        day_date=view.day_date,
        items=[_item_to_dto(item) for item in view.items],
        history=[_item_to_dto(item) for item in view.history],
    )


def _item_to_dto(item: TodayItem) -> TodayItemDTO:
    return TodayItemDTO(
        kind=item.kind.value,
        item_id=item.item_id,
        title=item.title,
        status=item.status.value,
        target_cell=item.target_cell,
        artefact_type=item.artefact_type,
        detail=item.detail,
        position=item.position,
        done=item.done,
        overdue_by_days=item.overdue_by_days,
        domain=item.domain,
        start_at=item.start_at,
        expected_outcome=item.expected_outcome,
        observed_outcome=item.observed_outcome,
        outcome_status=item.outcome_status,
        drop_candidate=item.drop_candidate,
    )


__all__ = [
    "CommitmentDTO",
    "CompletionDTO",
    "CreateCommitmentRequest",
    "GoalReadingDTO",
    "GoalStepDTO",
    "ItemRef",
    "TaskDTO",
    "MarkDoneRequest",
    "RecordObservedOutcomeRequest",
    "SetOrderRequest",
    "TodayDTO",
    "TodayItemDTO",
    "goal_reading_to_dto",
    "task_to_dto",
    "today_view_to_dto",
]
