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
    # D193/S98: the row's representative time, so the unlinked coverage view can
    # list items with a date (not just a count). None when the unit has none.
    occurred_at: datetime | None = None


class GoalLeverStatusDTO(BaseModel):
    """One lever commitment's name and status within a cadence goal (D191)."""

    name: str
    status: str


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
    # D187/S92: the goal's one status (on_track / behind / stalled / done /
    # active / asleep), or None when the status read is unavailable.
    status: str | None = None
    # D189/S93: the one-phrase why for the folded verdict line.
    status_why: str | None = None
    # D190/S94: distinct-vs-repeated — units is the head; units_more is the
    # counted tail. The in-goal suggestions: a head of prose + the full total
    # (the render collapses a flood to one "N suggested" line).
    units_more: int = 0
    suggestion_head: list[str] = []
    suggestion_total: int = 0
    # D191/S96: per-lever status for a cadence goal — which levers have no
    # completion data ("not_tracked") even when the goal reads a verdict.
    levers: list[GoalLeverStatusDTO] = []
    # D199/S101: the goal's measurable-outcome fields (D163), for the Map to
    # render the outcome distinct from the goal (the aim). ``mode`` discriminates
    # the shape; ``ladder``/``current_target_level`` are the progressive level
    # against the target; ``terminal_target``/``terminal_state`` are the sequence
    # terminal and its state; a homeostatic goal's measure is the rhythm held
    # (read from the verdict, no field). Propagated from the :Outcome node.
    mode: str | None = None
    ladder: list[str] = []
    current_target_level: str | None = None
    terminal_target: str | None = None
    terminal_state: str | None = None


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
        occurred_at=u.occurred_at,
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
                status=g.status.value if g.status is not None else None,
                status_why=g.status_why,
                units_more=g.units_more,
                suggestion_head=list(g.suggestion_head),
                suggestion_total=g.suggestion_total,
                levers=[
                    GoalLeverStatusDTO(name=lv.name, status=lv.status.value)
                    for lv in g.levers
                ],
                mode=g.mode,
                ladder=list(g.ladder),
                current_target_level=g.current_target_level,
                terminal_target=g.terminal_target,
                terminal_state=g.terminal_state,
            )
            for g in grouped.groups
        ],
        unlinked=[_grouped_unit_dto(u) for u in grouped.unlinked],
    )


class CddDraftResultDTO(BaseModel):
    """The outcome of drafting one goal's CDD (S102, D200)."""

    outcome_id: UUID
    name: str
    drafted: bool
    skipped_existing: bool
    levers: int
    intermediaries: int
    externals: int


class CddDraftSummaryDTO(BaseModel):
    """The result of drafting every goal's CDD (S102, D200)."""

    results: list[CddDraftResultDTO]


class AuthoredElementDTO(BaseModel):
    """One authored CDD element for proof (S102, D200)."""

    kind: str
    element_id: UUID
    label: str
    provenance_origin: str
    proof_state: str
    # The gate whose local CDD this element belongs to (S103g, D207), or None for
    # a goal-level (portfolio) element — the surface groups by it.
    gate_id: UUID | None = None


class GateDTO(BaseModel):
    """One process-flow gate for the CDD surface (S103g, D207). A gate is a portal
    into its local CDD; its elements are the ``AuthoredElementDTO``s carrying its
    ``gate_id``."""

    gate_id: UUID
    name: str
    gate_order: int
    local_outcome: str
    local_goal: str
    provenance_origin: str
    proof_state: str
    step_commitment_id: UUID | None = None


class OpportunityDTO(BaseModel):
    """One opportunity (process instance, S103h, D208) for the surface — positioned
    at ``current_gate_id``, grouping ``unit_count`` units."""

    opportunity_id: UUID
    name: str
    current_gate_id: UUID | None = None
    unit_count: int
    provenance_origin: str
    proof_state: str
    source: str | None = None
    # The closed state (S103n, D214): status live/closed, the outcome reason + when.
    status: str = "live"
    closed_reason: str | None = None
    closed_at: datetime | None = None


# D214: the five outcome reasons a close must carry (a well-declined process is
# value, not loss). Validated at the router so the model never holds a free-text
# reason. With the furthest gate, the reason gives the real-outcome-vs-non-start read.
CLOSE_REASONS: frozenset[str] = frozenset(
    {"won", "declined", "withdrawn_or_killed", "rejected", "went_cold"}
)


class CloseOpportunityRequest(BaseModel):
    """Close an opportunity with a required outcome reason (S103n, D214)."""

    reason: str


class RestageOpportunityRequest(BaseModel):
    """Re-stage an opportunity to a gate (S103q, D217); ``gate_id`` null clears it
    to Unplaced. The operator proofing the gate position."""

    gate_id: UUID | None = None


class PipelineAssessmentDTO(BaseModel):
    """The "how am I doing" assessment for a goal (S103p, D216): a
    recommendation-shaped verdict whose headline is label-independent, plus the
    funnel counts and the proof-dependent close-reason split."""

    verdict_label: str
    verdict_text: str
    because: str
    move: str
    confirmed_live: int
    suggested_live: int
    closed: int
    engaged: int
    interviewed: int
    offers: int
    one_touch_volume: int
    activity: int
    closed_reasons: dict[str, int]
    suggested_closed: int
    split_proof_dependent: bool


def pipeline_assessment_to_dto(a) -> "PipelineAssessmentDTO":
    return PipelineAssessmentDTO(
        verdict_label=a.verdict_label, verdict_text=a.verdict_text,
        because=a.because, move=a.move,
        confirmed_live=a.confirmed_live, suggested_live=a.suggested_live,
        closed=a.closed, engaged=a.engaged, interviewed=a.interviewed,
        offers=a.offers, one_touch_volume=a.one_touch_volume, activity=a.activity,
        closed_reasons=a.closed_reasons, suggested_closed=a.suggested_closed,
        split_proof_dependent=a.split_proof_dependent,
    )


class AuthoredEdgeDTO(BaseModel):
    """One authored causal edge for proof (S102, D200).

    ``needs_review`` flags an edge a reclassify left ungrammatical (D201, S103a) —
    surfaced for the user to resolve, never silently dropped.
    """

    edge_type: str
    source_kind: str
    source_id: UUID
    target_kind: str
    target_id: UUID
    needs_review: bool = False


class GoalCddDTO(BaseModel):
    """A goal's authored CDD for proof (S102, D200).

    ``expected_outcome_origin`` / ``expected_outcome_proof_state`` carry the
    outcome's authored signal so the surface renders it as a proofable terminal
    element (S103a); both ``None`` when the goal has no authored outcome.
    """

    outcome_id: UUID
    expected_outcome: str
    elements: list[AuthoredElementDTO]
    edges: list[AuthoredEdgeDTO]
    expected_outcome_origin: str | None = None
    expected_outcome_proof_state: str | None = None
    # The process-flow gates (S103g, D207), ordered by gate_order; each a portal
    # into its local CDD (the elements carrying its gate_id).
    gates: list[GateDTO] = []
    # The opportunities (process instances, S103h, D208) moving through the gates.
    opportunities: list[OpportunityDTO] = []
    # The precision pass's disposition summary (S103i/D210) for the Map.
    disposition: "DispositionDTO | None" = None


class DispositionDTO(BaseModel):
    """The Map's disposition summary (S103i/D210): the confirmed-email moat, the
    pipeline + market routed counts, and the parked residual."""

    moat: int
    pipeline: int
    market: int
    parked: int


class CorrectCddElementRequest(BaseModel):
    """Edit an authored element's label (the proof correct path, S102)."""

    label: str


class AddCddElementRequest(BaseModel):
    """Add a user-authored element of any of the four types (S103a).

    ``kind`` is ``lever`` / ``intermediary`` / ``external`` / ``outcome``; the
    outcome routes to the authored outcome stance (the goal's single terminal),
    the others create a new element node with a default edge to the outcome.
    """

    kind: str
    label: str = Field(min_length=1)


class AddedCddElementDTO(BaseModel):
    """The id of the newly added element (``None`` for an authored outcome, which
    has no element node of its own, S103a)."""

    element_id: UUID | None = None


class ElementEvidenceSummaryDTO(BaseModel):
    """Read-only element-evidence summary for the CDD lens (D202, S103b).

    ``counts`` maps each authored element's id (string) to the number of distinct
    units that evidence it; ``unbound_units`` is the bucket of units matching no
    element (the emergent loop's queue, S104)."""

    counts: dict[str, int] = {}
    bound_units: int = 0
    unbound_units: int = 0
    total_units: int = 0


def element_evidence_summary_to_dto(summary) -> "ElementEvidenceSummaryDTO":
    return ElementEvidenceSummaryDTO(
        counts={str(eid): n for eid, n in summary.counts},
        bound_units=summary.bound_units,
        unbound_units=summary.unbound_units,
        total_units=summary.total_units,
    )


class ElementBindingDTO(BaseModel):
    """One unit→element binding for the interactive lens (D203, S103c).

    ``matched_term`` (the why) and ``strength`` (a lexical match-strength band —
    string-match strength, not correctness) are recomputed on read (S103c-fix)."""

    unit_id: UUID
    title: str
    element_kind: str
    element_id: UUID
    outcome_id: UUID
    tier: str
    user_owned: bool
    matched_term: str = ""
    strength: str = ""
    # D212: the unit's primary facet, so the drawer can open its read-only source.
    source_facet_type: str = ""
    source_facet_id: UUID | None = None
    # D213: the opportunity the unit belongs to + its representative time, so the
    # opportunity lens scopes the binds and time-orders the correspondence thread.
    opportunity_id: UUID | None = None
    occurred_at: datetime | None = None


def element_binding_to_dto(b) -> "ElementBindingDTO":
    return ElementBindingDTO(
        unit_id=b.unit_id, title=b.title, element_kind=b.element_kind,
        element_id=b.element_id, outcome_id=b.outcome_id, tier=b.tier,
        user_owned=b.user_owned, matched_term=b.matched_term, strength=b.strength,
        source_facet_type=getattr(b, "source_facet_type", ""),
        source_facet_id=getattr(b, "source_facet_id", None),
        opportunity_id=getattr(b, "opportunity_id", None),
        occurred_at=getattr(b, "occurred_at", None),
    )


class EmailSourceDTO(BaseModel):
    """The read-only ingested source of one email facet, for the verification
    drawer's openable-source leg (D212): sender, date, subject, body."""

    facet_id: UUID
    sender: str | None = None
    received_at: datetime | None = None
    subject: str | None = None
    body: str | None = None


class RematchResultDTO(BaseModel):
    """The on-demand re-match result (D203, S103c): the element-evidence edge
    count after re-running (user-owned units skipped)."""

    evidence_edges: int


class UnlinkCddEvidenceRequest(BaseModel):
    """Remove one of a unit's element bindings (D203, S103c)."""

    unit_id: UUID
    kind: str
    element_id: UUID


class RelinkCddEvidenceRequest(BaseModel):
    """Retarget one of a unit's element bindings to a different element (D203)."""

    unit_id: UUID
    from_kind: str
    from_element_id: UUID
    to_kind: str
    to_element_id: UUID


class ReclassifyCddElementRequest(BaseModel):
    """Reclassify an authored element to a new type (D201, S103a). ``to_kind`` is
    ``lever`` / ``intermediary`` / ``external`` (the outcome is not a reclassify
    target — it is the goal's single terminal, D199)."""

    to_kind: str


def goal_cdd_to_dto(view) -> "GoalCddDTO":
    return GoalCddDTO(
        outcome_id=view.outcome_id,
        expected_outcome=view.expected_outcome,
        expected_outcome_origin=(
            view.expected_outcome_origin.value
            if view.expected_outcome_origin is not None
            else None
        ),
        expected_outcome_proof_state=(
            view.expected_outcome_proof_state.value
            if view.expected_outcome_proof_state is not None
            else None
        ),
        elements=[
            AuthoredElementDTO(
                kind=e.kind.value,
                element_id=e.element_id,
                label=e.label,
                provenance_origin=e.provenance_origin.value,
                proof_state=e.proof_state.value,
                gate_id=e.gate_id,
            )
            for e in view.elements
        ],
        edges=[
            AuthoredEdgeDTO(
                edge_type=edge.edge_type,
                source_kind=edge.source_kind,
                source_id=edge.source_id,
                target_kind=edge.target_kind,
                target_id=edge.target_id,
                needs_review=edge.needs_review,
            )
            for edge in view.edges
        ],
        gates=[
            GateDTO(
                gate_id=g.gate_id,
                name=g.name,
                gate_order=g.gate_order,
                local_outcome=g.local_outcome,
                local_goal=g.local_goal,
                provenance_origin=g.provenance_origin.value,
                proof_state=g.proof_state.value,
                step_commitment_id=g.step_commitment_id,
            )
            for g in getattr(view, "gates", ())
        ],
        opportunities=[
            OpportunityDTO(
                opportunity_id=o.opportunity_id,
                name=o.name,
                current_gate_id=o.current_gate_id,
                unit_count=o.unit_count,
                provenance_origin=o.provenance_origin.value,
                proof_state=o.proof_state.value,
                source=o.source,
                status=getattr(o, "status", "live"),
                closed_reason=getattr(o, "closed_reason", None),
                closed_at=getattr(o, "closed_at", None),
            )
            for o in getattr(view, "opportunities", ())
        ],
        disposition=(
            DispositionDTO(
                moat=view.disposition.moat,
                pipeline=view.disposition.pipeline,
                market=view.disposition.market,
                parked=view.disposition.parked,
            )
            if getattr(view, "disposition", None) is not None
            else None
        ),
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
