"""The S103c correction loop: relink, unlink, capture, and a correction-respecting
re-match (D203). Synthetic fixtures — no PII.

- relink/unlink use cases: the right graph mutation + an append-only correction
  audit event with the prior→new provenance.
- the re-runnable re-match (``correlate_goal_facets``): idempotent (no duplicate
  edges, no change to correct bindings), it skips user-owned units (a correction
  survives a re-match), and it recovers coverage (a newly-authored element binds a
  previously-unbound unit) while leaving user-owned units alone.
"""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from contexts.daily_driver.application.correct_cdd_evidence import (
    relink_cdd_evidence,
    unlink_cdd_evidence,
)
from contexts.daily_driver.application.correlate_goal_facets import (
    correlate_goal_facets,
)
from contexts.daily_driver.application.audit_events import (
    ACTION_CDD_RELINK,
    ACTION_CDD_UNLINK,
)
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
from contexts.daily_driver.domain.goal_assessment import (
    ElementEvidence,
    binding_rationale,
    element_token_counts,
)
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


# --- relink / unlink use cases + capture ------------------------------------

class _RecordingUnitGraph:
    def __init__(self, ok=True):
        self.ok = ok
        self.calls = []

    async def relink_element_evidence(self, *, tenant_context, unit_id,
                                      from_kind, from_element_id, to_kind,
                                      to_element_id):
        self.calls.append(("relink", unit_id, from_kind, from_element_id,
                           to_kind, to_element_id))
        return self.ok

    async def unlink_element_evidence(self, *, tenant_context, unit_id,
                                      element_kind, element_id):
        self.calls.append(("unlink", unit_id, element_kind, element_id))
        return self.ok


class _RecordingAudit:
    def __init__(self):
        self.events = []

    async def emit(self, event):
        self.events.append(event)
        return event


def test_relink_mutates_and_captures_the_prior_to_new_pair():
    ug = _RecordingUnitGraph()
    audit = _RecordingAudit()
    uid, lev, inter = uuid4(), uuid4(), uuid4()
    ok = asyncio.run(relink_cdd_evidence(
        unit_graph=ug, actor=_actor(), unit_id=uid,
        from_kind=ElementKind.LEVER, from_element_id=lev,
        to_kind=ElementKind.INTERMEDIARY, to_element_id=inter,
        audit_port=audit,
    ))
    assert ok and ug.calls[0][0] == "relink"
    assert len(audit.events) == 1
    ev = audit.events[0]
    assert ev.action_verb == ACTION_CDD_RELINK
    assert ev.before_state["element_id"] == str(lev)  # prior binding
    assert ev.after_state["element_id"] == str(inter)  # new binding
    assert ev.resource_id == str(uid)


def test_unlink_mutates_and_captures_the_removed_binding():
    ug = _RecordingUnitGraph()
    audit = _RecordingAudit()
    uid, lev = uuid4(), uuid4()
    ok = asyncio.run(unlink_cdd_evidence(
        unit_graph=ug, actor=_actor(), unit_id=uid,
        kind=ElementKind.LEVER, element_id=lev, audit_port=audit,
    ))
    assert ok and ug.calls[0][0] == "unlink"
    ev = audit.events[0]
    assert ev.action_verb == ACTION_CDD_UNLINK
    assert ev.before_state["element_id"] == str(lev)
    assert ev.after_state == {}  # removed


def test_no_capture_when_the_binding_is_absent():
    ug = _RecordingUnitGraph(ok=False)
    audit = _RecordingAudit()
    ok = asyncio.run(unlink_cdd_evidence(
        unit_graph=ug, actor=_actor(), unit_id=uuid4(),
        kind=ElementKind.LEVER, element_id=uuid4(), audit_port=audit,
    ))
    assert ok is False and audit.events == []  # no record for a no-op


def test_bulk_unlink_emits_one_correction_record_per_binding():
    # S103c-fix: bulk unlink is batching — N bindings unlinked is N use-case calls,
    # each emitting its own correction record (signal unchanged in kind, larger).
    ug = _RecordingUnitGraph()
    audit = _RecordingAudit()
    units = [uuid4(), uuid4(), uuid4()]
    for u in units:  # the front-end loops the single-unlink path per selected binding
        asyncio.run(unlink_cdd_evidence(
            unit_graph=ug, actor=_actor(), unit_id=u,
            kind=ElementKind.LEVER, element_id=uuid4(), audit_port=audit,
        ))
    assert len(audit.events) == len(units)  # one record each
    assert {e.resource_id for e in audit.events} == {str(u) for u in units}


# --- S103c-fix: binding rationale + match strength (recompute on read) -------

def test_binding_rationale_exact_is_strong():
    term, strength = binding_rationale(
        unit_title="Apply to roles", element_label="Apply to roles",
        tier="lexical_exact", token_element_counts={},
    )
    assert strength == "strong" and term == "Apply to roles"


def test_binding_rationale_distinctive_keyword_is_medium():
    counts = element_token_counts(("Network", "Apply to roles"))  # 'network' unique
    term, strength = binding_rationale(
        unit_title="Network with Sam", element_label="Network",
        tier="lexical_keyword", token_element_counts=counts,
    )
    assert term == "network" and strength == "medium"


def test_binding_rationale_incidental_shared_token_is_weak():
    # 'review' appears across multiple element labels -> incidental. The only token
    # this unit shares with the element is the incidental one -> weak (the trap).
    counts = element_token_counts(("Review applications", "Review interviews"))
    term, strength = binding_rationale(
        unit_title="Review notes", element_label="Review interviews",
        tier="lexical_keyword", token_element_counts=counts,
    )
    assert term == "review" and strength == "weak"  # high string match, incidental


def test_binding_rationale_alias_is_weak():
    _, strength = binding_rationale(
        unit_title="x", element_label="y", tier="alias", token_element_counts={},
    )
    assert strength == "weak"


# --- re-match: idempotence, ownership, coverage recovery --------------------

def _unit(title: str):
    fid = uuid4()
    rec = UnitRecord(
        unit_id=uuid4(),
        facets=(UnitFacetRef(facet_type=FacetType.TASK, facet_id=fid,
                             confidence=1.0, status=LinkStatus.CONFIRMED,
                             basis="anchor"),),
    )
    facet = WorkFacet(facet_type=FacetType.TASK, facet_id=fid, title=title,
                      occurred_at=None)
    return rec, facet


class _ModelGraph:
    """A model unit-graph honouring user-ownership: replace skips owned units,
    relink/unlink mark a unit owned (the live Cypher's reference behaviour)."""

    def __init__(self, records):
        self._records = records
        self.evidence: list[dict] = []
        self.owned: set[UUID] = set()

    async def list_units(self, *, tenant_context):
        return self._records

    async def list_user_owned_unit_ids(self, *, tenant_context):
        return set(self.owned)

    async def list_element_evidence(self, *, tenant_context):
        return tuple(
            ElementEvidence(
                unit_id=e["unit_id"], element_kind=e["element_kind"],
                element_id=e["element_id"], outcome_id=e["outcome_id"],
                tier=e["tier"], status=LinkStatus(e["status"]), basis=e["basis"],
            )
            for e in self.evidence
        )

    async def replace_element_evidence(self, *, tenant_context, evidence):
        # Derived state: keep owned units' edges, replace the rest (D203).
        self.evidence = [e for e in self.evidence if e["unit_id"] in self.owned]
        for ev in evidence:
            self.evidence.append({
                "unit_id": ev.unit_id, "element_kind": ev.element_kind,
                "element_id": ev.element_id, "outcome_id": ev.outcome_id,
                "tier": ev.tier, "status": ev.status.value, "basis": ev.basis,
            })

    async def relink_element_evidence(self, *, tenant_context, unit_id,
                                      from_kind, from_element_id, to_kind,
                                      to_element_id):
        for e in self.evidence:
            if e["unit_id"] == unit_id and e["element_id"] == from_element_id:
                e["element_kind"] = to_kind.value
                e["element_id"] = to_element_id
                e["tier"] = "user"
                e["basis"] = "user-corrected"
        self.owned.add(unit_id)
        return True


class _FakeFacetSource:
    def __init__(self, facets):
        self._facets = facets

    async def list_facets(self, *, actor):
        return self._facets


class _FakeGoalGraph:
    def __init__(self, goal, elements, expected_outcome=""):
        self._goal = goal
        self._elements = elements  # tuple[AuthoredElement]
        self._expected = expected_outcome

    async def list_goals(self, *, tenant_context):
        return (self._goal,)

    async def read_goal_cdd(self, *, tenant_context, outcome_id):
        return GoalCddView(
            outcome_id=outcome_id, expected_outcome=self._expected,
            elements=self._elements, edges=(),
        )


class _FakeCommitmentRepo:
    async def list_with_activity(self, *, tenant_context):
        return ()


def _goal() -> Goal:
    return Goal(
        id=uuid4(), tenant_id=UUID(_TENANT), jurisdiction="eu-west",
        name="Marathon", mode=GoalMode.PROGRESSIVE, control=ControlAxis.SELF,
        subject=Subject.SELF, lever_commitment_id=uuid4(),
        ladder=LevelLadder(levels=("A1", "A2"), current_target_level="A2"),
    )


def _elem(kind, label):
    return AuthoredElement(
        kind=kind, element_id=uuid4(), label=label,
        provenance_origin=ProvenanceOrigin.USER_AUTHORED,
        proof_state=ProofState.ACCEPTED,
    )


def _correlate(ug, facets, goal_graph):
    return asyncio.run(correlate_goal_facets(
        unit_graph=ug, facet_source=_FakeFacetSource(facets),
        goal_graph=goal_graph, commitment_repository=_FakeCommitmentRepo(),
        actor=_actor(),
    ))


def test_rematch_is_idempotent():
    rec, facet = _unit("Long run")
    ug = _ModelGraph((rec,))
    goal = _goal()
    gg = _FakeGoalGraph(goal, (_elem(ElementKind.LEVER, "Long run"),))
    n1 = _correlate(ug, (facet,), gg)
    after_first = [dict(e) for e in ug.evidence]
    n2 = _correlate(ug, (facet,), gg)
    assert n1 == n2  # same count
    assert [dict(e) for e in ug.evidence] == after_first  # no dup, no change


def test_rematch_skips_user_owned_units():
    rec, facet = _unit("Long run")
    ug = _ModelGraph((rec,))
    goal = _goal()
    lever = _elem(ElementKind.LEVER, "Long run")
    inter = _elem(ElementKind.INTERMEDIARY, "Pace")
    gg = _FakeGoalGraph(goal, (lever, inter))
    _correlate(ug, (facet,), gg)  # binds the unit to the lever (exact)
    # The user relinks the unit to the intermediary — now user-owned.
    asyncio.run(relink_cdd_evidence(
        unit_graph=ug, actor=_actor(), unit_id=rec.unit_id,
        from_kind=ElementKind.LEVER, from_element_id=lever.element_id,
        to_kind=ElementKind.INTERMEDIARY, to_element_id=inter.element_id,
    ))
    _correlate(ug, (facet,), gg)  # re-match must NOT overwrite the correction
    bound = [e for e in ug.evidence if e["unit_id"] == rec.unit_id]
    assert len(bound) == 1
    assert bound[0]["element_id"] == inter.element_id  # correction survived
    assert bound[0]["basis"] == "user-corrected"


def test_rematch_recovers_coverage_for_a_newly_authored_element():
    # A unit unbound under the current CDD; author a new element that matches it;
    # re-match binds it — while a separately user-owned unit is left alone.
    rec_new, facet_new = _unit("Tempo intervals")
    rec_owned, facet_owned = _unit("Long run")
    ug = _ModelGraph((rec_new, rec_owned))
    goal = _goal()
    lever = _elem(ElementKind.LEVER, "Long run")
    gg = _FakeGoalGraph(goal, (lever,))
    _correlate(ug, (facet_new, facet_owned), gg)
    # "Long run" binds the lever; "Tempo intervals" matches nothing -> unbound.
    assert not [e for e in ug.evidence if e["unit_id"] == rec_new.unit_id]
    # The user corrects the Long-run unit (owns it).
    asyncio.run(relink_cdd_evidence(
        unit_graph=ug, actor=_actor(), unit_id=rec_owned.unit_id,
        from_kind=ElementKind.LEVER, from_element_id=lever.element_id,
        to_kind=ElementKind.LEVER, to_element_id=lever.element_id,
    ))
    # Author a new lever that matches the previously-unbound unit; re-match.
    tempo = _elem(ElementKind.LEVER, "Tempo intervals")
    gg2 = _FakeGoalGraph(goal, (lever, tempo))
    _correlate(ug, (facet_new, facet_owned), gg2)
    new_bound = [e for e in ug.evidence if e["unit_id"] == rec_new.unit_id]
    assert new_bound and new_bound[0]["element_id"] == tempo.element_id  # recovered
    owned_bound = [e for e in ug.evidence if e["unit_id"] == rec_owned.unit_id]
    assert owned_bound[0]["basis"] == "user-corrected"  # untouched
