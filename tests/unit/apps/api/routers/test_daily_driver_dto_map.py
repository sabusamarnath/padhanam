"""The Map's read-shape contract (D199/S101).

The Map renders from the units-by-goal grouped read; these tests bind that
render to the read by asserting the domain ``GoalGroupedUnits`` encodes through
``grouped_units_to_dto`` carrying exactly what the Map draws: the per-goal
verdict (read from ``goal_status``, recomputed nowhere — the encoder copies it),
the measurable-outcome fields per mode (D163), and the levers as their own list.

The decisive invariant (Step-0): no field on the wire links a unit to a
*specific* lever. The graph links work to the outcome via ``SERVES`` and levers
to the outcome via ``LEVER_FOR``; the two are never joined, so the DTO carries
``units`` and ``levers`` as siblings and nothing nests a unit under a lever.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from apps.api.routers._daily_driver_dto import grouped_units_to_dto
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
from contexts.daily_driver.domain.goal_assessment import (
    GoalEdge,
    group_units_by_goal,
)
from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
)
from contexts.daily_driver.domain.unit_view import UnitFacetView, UnitView

_TENANT = uuid4()
_NOW = datetime(2026, 6, 18, 9, 0, tzinfo=timezone.utc)


def _unit(title: str) -> UnitView:
    return UnitView(
        unit_id=uuid4(),
        title=title,
        facets=(
            UnitFacetView(
                facet_type=FacetType.MEETING, facet_id=uuid4(), title=title,
                occurred_at=_NOW, status=LinkStatus.CONFIRMED, confidence=1.0,
                basis="anchor", present=True, series_id=None,
            ),
        ),
    )


def _edge(unit: UnitView, goal: Goal) -> GoalEdge:
    return GoalEdge(
        unit_id=unit.unit_id, outcome_id=goal.id, confidence=0.9,
        status=LinkStatus.CONFIRMED, basis="commitment",
    )


def _goal(**kw) -> Goal:
    base = dict(
        id=uuid4(), tenant_id=_TENANT, jurisdiction="eu-west",
        control=ControlAxis.SELF, subject=Subject.SELF,
    )
    base.update(kw)
    return Goal(**base)


def _encode_one(goal: Goal):
    unit = _unit("Some serving work")
    grouped = group_units_by_goal((unit,), (goal,), (_edge(unit, goal),), now=_NOW)
    dto = grouped_units_to_dto(grouped)
    assert len(dto.groups) == 1
    return dto.groups[0]


def test_progressive_measurable_outcome_reaches_the_wire():
    goal = _goal(
        name="German",
        mode=GoalMode.PROGRESSIVE,
        lever_commitment_id=uuid4(),
        ladder=LevelLadder(levels=("A1", "A2", "B1"), current_target_level="A2"),
    )
    g = _encode_one(goal)
    assert g.mode == "progressive"
    assert g.ladder == ["A1", "A2", "B1"]
    assert g.current_target_level == "A2"
    assert g.terminal_target is None and g.terminal_state is None


def test_sequence_measurable_outcome_reaches_the_wire():
    goal = _goal(
        name="Get a job",
        mode=GoalMode.SEQUENCE,
        terminal=Terminal(target="Offer accepted", state=TerminalState.PENDING),
        steps=(LeverStep(commitment_id=uuid4(), order=1, state=StepState.READY),),
    )
    g = _encode_one(goal)
    assert g.mode == "sequence"
    assert g.terminal_target == "Offer accepted"
    assert g.terminal_state == "pending"
    assert g.ladder == [] and g.current_target_level is None


def test_homeostatic_carries_mode_but_no_target_fields():
    goal = _goal(
        name="Litany", mode=GoalMode.HOMEOSTATIC, lever_commitment_id=uuid4(),
    )
    g = _encode_one(goal)
    assert g.mode == "homeostatic"
    assert g.ladder == [] and g.current_target_level is None
    assert g.terminal_target is None and g.terminal_state is None


def test_verdict_is_copied_from_status_not_recomputed():
    # The encoder copies the domain verdict's status onto the DTO verbatim; the
    # Map reads goal_status and recomputes nothing.
    goal = _goal(
        name="German",
        mode=GoalMode.PROGRESSIVE,
        lever_commitment_id=uuid4(),
        ladder=LevelLadder(levels=("A1", "A2"), current_target_level="A2"),
    )
    unit = _unit("Practice")
    grouped = group_units_by_goal((unit,), (goal,), (_edge(unit, goal),), now=_NOW)
    domain_status = grouped.groups[0].status
    dto = grouped_units_to_dto(grouped)
    expected = domain_status.value if domain_status is not None else None
    assert dto.groups[0].status == expected


def test_no_field_links_a_unit_to_a_specific_lever():
    # The decisive Step-0 invariant rendered honest on the wire: a group carries
    # units and levers as separate lists; no unit field names a lever.
    goal = _goal(
        name="Litany", mode=GoalMode.HOMEOSTATIC, lever_commitment_id=uuid4(),
    )
    g = _encode_one(goal)
    for u in g.units:
        fields = set(type(u).model_fields)
        assert not any("lever" in f for f in fields), fields


def test_goal_cdd_to_dto_carries_gates_and_gate_id():
    # S103g (D207): gates + element gate_id reach the wire so the surface groups.
    from uuid import uuid4 as _uuid4

    from apps.api.routers._daily_driver_dto import goal_cdd_to_dto
    from contexts.daily_driver.domain.cdd import (
        AuthoredElement,
        ElementKind,
        GateView,
        GoalCddView,
        ProofState,
        ProvenanceOrigin,
    )

    gate_id = _uuid4()
    outcome_id = _uuid4()
    view = GoalCddView(
        outcome_id=outcome_id,
        expected_outcome="Role secured",
        elements=(
            AuthoredElement(
                kind=ElementKind.LEVER, element_id=_uuid4(), label="Origination",
                provenance_origin=ProvenanceOrigin.LLM_DRAFTED,
                proof_state=ProofState.PENDING,
            ),
            AuthoredElement(
                kind=ElementKind.LEVER, element_id=_uuid4(),
                label="Tailoring effort",
                provenance_origin=ProvenanceOrigin.LLM_DRAFTED,
                proof_state=ProofState.PENDING, gate_id=gate_id,
            ),
        ),
        edges=(),
        gates=(
            GateView(
                gate_id=gate_id, name="Apply", gate_order=3,
                local_outcome="Expected interviews generated",
                local_goal="highest return on marginal effort",
                provenance_origin=ProvenanceOrigin.LLM_DRAFTED,
                proof_state=ProofState.PENDING,
            ),
        ),
    )
    dto = goal_cdd_to_dto(view)
    assert len(dto.gates) == 1 and dto.gates[0].name == "Apply"
    by_label = {e.label: e for e in dto.elements}
    assert by_label["Tailoring effort"].gate_id == gate_id
    assert by_label["Origination"].gate_id is None


def test_goal_cdd_to_dto_carries_opportunities():
    # S103h (D208): opportunities reach the wire with position + unit count.
    from uuid import uuid4 as _uuid4

    from apps.api.routers._daily_driver_dto import goal_cdd_to_dto
    from contexts.daily_driver.domain.cdd import (
        GoalCddView, OpportunityView, ProofState, ProvenanceOrigin,
    )

    gate_id = _uuid4()
    view = GoalCddView(
        outcome_id=_uuid4(), expected_outcome="Role secured",
        elements=(), edges=(),
        opportunities=(
            OpportunityView(
                opportunity_id=_uuid4(), name="Acme", current_gate_id=gate_id,
                unit_count=5, provenance_origin=ProvenanceOrigin.USER_AUTHORED,
                proof_state=ProofState.PENDING, source="acme.example",
            ),
        ),
    )
    dto = goal_cdd_to_dto(view)
    assert len(dto.opportunities) == 1
    assert dto.opportunities[0].name == "Acme"
    assert dto.opportunities[0].unit_count == 5
    assert dto.opportunities[0].current_gate_id == gate_id


def test_goal_cdd_to_dto_carries_disposition():
    # S103j (D210): the precision disposition counts reach the wire for the Map.
    from uuid import uuid4 as _uuid4
    from apps.api.routers._daily_driver_dto import goal_cdd_to_dto
    from contexts.daily_driver.domain.cdd import DispositionCounts, GoalCddView

    view = GoalCddView(
        outcome_id=_uuid4(), expected_outcome="Role secured", elements=(), edges=(),
        disposition=DispositionCounts(moat=166, pipeline=108, market=74, parked=249),
    )
    dto = goal_cdd_to_dto(view)
    assert dto.disposition.moat == 166 and dto.disposition.parked == 249
