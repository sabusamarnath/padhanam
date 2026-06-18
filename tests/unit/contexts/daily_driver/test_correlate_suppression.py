"""Single-signal suppression at the correlate hook (D186/S91b).

When the active policy's flag is on, ``correlate_goal_facets`` drops the weak
goal-name keyword-on-name candidate edges before measuring + replacing, and
touches no confirmed edge. Flag off reproduces the unsuppressed edge set exactly.
Synthetic fixtures — no PII.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import UUID, uuid4

from contexts.daily_driver.application import correlate_goal_facets
from contexts.daily_driver.domain.cdd import (
    AuthoredElement,
    ElementKind,
    GoalCddView,
    ProofState,
    ProvenanceOrigin,
)
from contexts.daily_driver.domain.goal import (
    ControlAxis,
    Goal,
    GoalMode,
    LevelLadder,
    Subject,
)
from contexts.daily_driver.domain.goal_assessment import WEAK_KEYWORD_BASIS
from contexts.daily_driver.domain.work_unit import (
    FacetType,
    LinkStatus,
    UnitFacetRef,
    UnitRecord,
    WorkFacet,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import ROLE_OPERATOR, authorisations_for_roles

_TENANT = "00000000-0000-4000-8000-00000000d001"
_LEVER = uuid4()


def _actor() -> ActorContext:
    roles = frozenset({ROLE_OPERATOR})
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_TENANT, jurisdiction="eu-west", cost_attribution_id=_TENANT
        ),
        actor_id="operator-001",
        role_list=roles,
        authorisation_set=authorisations_for_roles(roles),
    )


def _goal() -> Goal:
    return Goal(
        id=uuid4(),
        tenant_id=UUID(_TENANT),
        jurisdiction="eu-west",
        name="Marathon",
        mode=GoalMode.PROGRESSIVE,
        control=ControlAxis.SELF,
        subject=Subject.SELF,
        lever_commitment_id=_LEVER,
        ladder=LevelLadder(levels=("A1", "A2", "B1"), current_target_level="A2"),
    )


def _unit(title: str):
    fid = uuid4()
    record = UnitRecord(
        unit_id=uuid4(),
        facets=(
            UnitFacetRef(
                facet_type=FacetType.TASK,
                facet_id=fid,
                confidence=1.0,
                status=LinkStatus.CONFIRMED,
                basis="anchor",
            ),
        ),
    )
    facet = WorkFacet(
        facet_type=FacetType.TASK, facet_id=fid, title=title, occurred_at=None
    )
    return record, facet


class _FakeUnitGraph:
    def __init__(self, records):
        self._records = records
        self.replaced = None

    async def list_units(self, *, tenant_context):
        return self._records

    async def list_user_owned_unit_ids(self, *, tenant_context):
        return set()

    async def replace_element_evidence(self, *, tenant_context, evidence):
        self.replaced = tuple(evidence)


class _FakeFacetSource:
    def __init__(self, facets):
        self._facets = facets

    async def list_facets(self, *, actor):
        return self._facets


class _FakeGoalGraph:
    """One goal carrying an authored lever labelled 'Long run' (S103b): a unit
    titled the same forms an element-exact (confirmed) binding that suppression
    must not touch; a unit keyword-matching only the goal name forms an alias
    (single-signal) binding that suppression drops."""

    def __init__(self, goals):
        self._goals = goals

    async def list_goals(self, *, tenant_context):
        return self._goals

    async def read_goal_cdd(self, *, tenant_context, outcome_id):
        return GoalCddView(
            outcome_id=outcome_id,
            expected_outcome="",
            elements=(
                AuthoredElement(
                    kind=ElementKind.LEVER,
                    element_id=_LEVER,
                    label="Long run",
                    provenance_origin=ProvenanceOrigin.USER_AUTHORED,
                    proof_state=ProofState.ACCEPTED,
                ),
            ),
            edges=(),
        )


class _FakeCommitmentRepo:
    """Returns one lever commitment named 'Long run' so a unit titled the same
    forms a CONFIRMED commitment edge (the edge suppression must not touch)."""

    async def list_with_activity(self, *, tenant_context):
        return (
            SimpleNamespace(
                commitment=SimpleNamespace(id=_LEVER, name="Long run")
            ),
        )


class _Policy:
    def __init__(self, on: bool) -> None:
        self._on = on

    async def suppress_single_signal(self, *, actor) -> bool:
        return self._on


class _RecordingRecorder:
    """Captures what the S90 matcher-quality recorder would measure."""

    def __init__(self) -> None:
        self.edges = None

    async def record(self, *, actor, edges, units) -> None:
        self.edges = edges


def _fixture():
    # Unit A: keyword 'marathon' -> goal-name candidate edge (single-signal).
    # Unit B: exact 'Long run' -> element-exact CONFIRMED binding.
    a_rec, a_facet = _unit("Marathon training plan")
    b_rec, b_facet = _unit("Long run")
    return (a_rec, b_rec), (a_facet, b_facet), (_goal(),)


def _run(fixture, *, policy=None, recorder=None):
    records, facets, goals = fixture
    ug = _FakeUnitGraph(records)
    n = asyncio.run(
        correlate_goal_facets(
            unit_graph=ug,
            facet_source=_FakeFacetSource(facets),
            goal_graph=_FakeGoalGraph(goals),
            commitment_repository=_FakeCommitmentRepo(),
            suppression_policy=policy,
            matcher_quality_recorder=recorder,
            actor=_actor(),
        )
    )
    return n, ug


def test_flag_off_leaves_the_edge_set_unchanged() -> None:
    fixture = _fixture()
    _, ug_none = _run(fixture)  # no policy wired
    _, ug_off = _run(fixture, policy=_Policy(False))  # policy present, flag off
    assert ug_none.replaced == ug_off.replaced
    bases = {e.basis for e in ug_off.replaced}
    # both tiers present unsuppressed
    assert WEAK_KEYWORD_BASIS in bases and "element-exact" in bases


def test_flag_on_suppresses_single_signal_only() -> None:
    fixture = _fixture()
    _, ug_off = _run(fixture, policy=_Policy(False))
    _, ug_on = _run(fixture, policy=_Policy(True))
    off_bases = sorted(e.basis for e in ug_off.replaced)
    on_bases = sorted(e.basis for e in ug_on.replaced)
    # the single-signal (goal-name) edge is gone; the confirmed (commitment) stays
    assert WEAK_KEYWORD_BASIS in off_bases
    assert WEAK_KEYWORD_BASIS not in on_bases
    assert "element-exact" in on_bases
    # exactly the single-signal edges were removed, nothing else
    assert [b for b in off_bases if b != WEAK_KEYWORD_BASIS] == on_bases


def test_recorder_measures_zero_single_signal_after_suppression() -> None:
    # The loop's re-measure: with the flag on, the recorder (S90's measurement,
    # placed after suppression at the hook) sees no single-signal edges — so the
    # next matcher-quality run reads single-signal share 0.
    fixture = _fixture()
    rec_off = _RecordingRecorder()
    _run(fixture, policy=_Policy(False), recorder=rec_off)
    rec_on = _RecordingRecorder()
    _run(fixture, policy=_Policy(True), recorder=rec_on)
    assert any(e.basis == WEAK_KEYWORD_BASIS for e in rec_off.edges)  # before
    assert all(e.basis != WEAK_KEYWORD_BASIS for e in rec_on.edges)  # after: 0


def test_matcher_does_not_import_optimization_or_policy_writer() -> None:
    # The seam: the matcher reads policy via its own port; it must not reach the
    # optimization context or the policy WRITER (that is optimization's side).
    # (import-linter's matcher-apply-seam contract is the durable enforcement;
    # this is a fast local check.)
    import os

    import contexts.daily_driver.application as app_pkg

    path = os.path.join(
        os.path.dirname(app_pkg.__file__), "correlate_goal_facets.py"
    )
    src = open(path).read()
    assert "contexts.optimization" not in src
    assert "MatcherPolicyRepository" not in src  # the write side is not the matcher's
