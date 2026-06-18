"""The authored CDD domain + draft use case + the migration-shape guard (S102, D200)."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from uuid import UUID, uuid4

from contexts.daily_driver.application.draft_goal_cdd import draft_goal_cdds
from contexts.daily_driver.domain.cdd import (
    DRAFT_SCHEMA,
    DraftedCdd,
    DraftedElement,
    ElementKind,
    GoalCddView,
    ProofState,
    ProvenanceOrigin,
    build_draft_prompt,
    parse_cdd_draft,
)
from contexts.daily_driver.domain.goal import (
    ControlAxis,
    Goal,
    GoalMode,
    LeverStep,
    StepState,
    Subject,
    Terminal,
    TerminalState,
)
from shared_kernel import ActorContext, TenantContext
from shared_kernel.authorisation import authorisations_for_roles

_T = "00000000-0000-4000-8000-00000000d001"


def _actor() -> ActorContext:
    return ActorContext(
        tenant_context=TenantContext(
            tenant_id=_T, jurisdiction="eu-west", cost_attribution_id=_T
        ),
        actor_id="op",
        role_list=frozenset({"operator"}),
        authorisation_set=authorisations_for_roles(frozenset({"operator"})),
    )


# --- provenance + proof enums (D200) ---------------------------------------

def test_provenance_origin_has_exactly_three_values():
    assert {o.value for o in ProvenanceOrigin} == {
        "llm_drafted", "user_authored", "system_suggested"
    }


def test_proof_state_values():
    assert {s.value for s in ProofState} == {"pending", "accepted"}


# --- the pure parse (defensive) --------------------------------------------

def test_parse_dedupes_and_drops_blanks_and_strips_expected():
    d = parse_cdd_draft({
        "levers": [{"label": "Apply"}, {"label": "apply"}, {"label": "  "}],
        "intermediaries": [{"label": "Response rate"}],
        "externals": [],
        "expected_outcome": "  Offer accepted  ",
    })
    assert [e.label for e in d.levers] == ["Apply"]  # case-insensitive dedupe + blank drop
    assert d.intermediaries[0].kind is ElementKind.INTERMEDIARY
    assert d.externals == ()
    assert d.expected_outcome == "Offer accepted"


def test_parse_caps_per_kind():
    many = [{"label": f"lever {i}"} for i in range(20)]
    d = parse_cdd_draft({"levers": many, "intermediaries": [], "externals": [],
                         "expected_outcome": "x"})
    assert len(d.levers) == 6  # the per-kind head cap


def test_parse_degrades_on_malformed_shapes():
    d = parse_cdd_draft({"levers": "nope", "expected_outcome": 5})
    assert d.levers == () and d.intermediaries == () and d.externals == ()
    assert d.expected_outcome == ""


def test_draft_schema_is_a_well_formed_json_schema():
    assert DRAFT_SCHEMA["type"] == "object"
    for key in ("levers", "intermediaries", "externals", "expected_outcome"):
        assert key in DRAFT_SCHEMA["properties"]
    assert DRAFT_SCHEMA["additionalProperties"] is False


def test_prompt_carries_goal_and_known_levers():
    p = build_draft_prompt(
        goal_name="Get a job", mode="sequence",
        lever_names=("Apply to roles", "Prep interviews"),
    )
    assert "Get a job" in p and "sequence" in p
    assert "Apply to roles" in p and "Prep interviews" in p
    assert "intermediaries" in p and "externals" in p


# --- the draft use case (fakes) --------------------------------------------

class _FakeGraph:
    def __init__(self, *, existing=False):
        self.elements = []
        self.edges = []
        self.outcome = None
        self._existing = existing

    async def list_goals(self, *, tenant_context):
        return (self._goal,)

    async def read_goal_cdd(self, *, tenant_context, outcome_id):
        els = (
            (object(),) if self._existing else ()
        )  # non-empty -> skip
        return GoalCddView(
            outcome_id=outcome_id, expected_outcome="", elements=els, edges=()
        )

    async def set_authored_outcome(self, *, tenant_context, outcome_id, expected_outcome):
        self.outcome = expected_outcome

    async def write_authored_element(self, *, tenant_context, outcome_id, kind,
                                     element_id, label, origin, proof_state):
        self.elements.append((kind, label, origin, proof_state))

    async def write_authored_edge(self, *, tenant_context, edge_type, source_kind,
                                  source_id, target_kind, target_id):
        self.edges.append((edge_type, source_kind, target_kind))


class _FakeDrafter:
    def __init__(self, drafted):
        self._drafted = drafted

    async def draft(self, *, goal_name, mode, lever_names):
        return self._drafted


_SEQ_GOAL = Goal(
    id=uuid4(), tenant_id=UUID(_T), jurisdiction="eu-west", name="Get a job",
    mode=GoalMode.SEQUENCE, control=ControlAxis.SELF, subject=Subject.SELF,
    terminal=Terminal(target="Offer", state=TerminalState.PENDING),
    steps=(LeverStep(commitment_id=uuid4(), order=1, state=StepState.READY),),
)

_FULL_DRAFT = DraftedCdd(
    levers=(DraftedElement(ElementKind.LEVER, "Apply to roles"),),
    intermediaries=(DraftedElement(ElementKind.INTERMEDIARY, "Response rate"),),
    externals=(DraftedElement(ElementKind.EXTERNAL, "Hiring freeze"),),
    expected_outcome="Offer accepted",
)


def test_draft_persists_elements_with_llm_drafted_pending_and_the_edge_chain():
    g = _FakeGraph()
    g._goal = _SEQ_GOAL
    res = asyncio.run(draft_goal_cdds(goal_graph=g, drafter=_FakeDrafter(_FULL_DRAFT), actor=_actor()))
    assert res[0].drafted and res[0].levers == 1
    # Every persisted element is llm_drafted / pending (D200, AC3).
    assert all(
        o is ProvenanceOrigin.LLM_DRAFTED and p is ProofState.PENDING
        for (_k, _l, o, p) in g.elements
    )
    assert g.outcome == "Offer accepted"
    # The default chain: lever -> intermediary -> outcome; external -> outcome.
    assert ("FEEDS", "intermediary", "outcome") in g.edges
    assert ("FEEDS", "lever", "intermediary") in g.edges
    assert ("INFLUENCES", "external", "outcome") in g.edges


def test_draft_skips_a_goal_that_already_has_a_cdd():
    g = _FakeGraph(existing=True)
    g._goal = _SEQ_GOAL
    res = asyncio.run(draft_goal_cdds(goal_graph=g, drafter=_FakeDrafter(_FULL_DRAFT), actor=_actor()))
    assert res[0].skipped_existing and not res[0].drafted
    assert g.elements == []  # nothing re-persisted


def test_draft_persists_nothing_when_the_model_gives_no_levers():
    g = _FakeGraph()
    g._goal = _SEQ_GOAL
    empty = DraftedCdd(levers=(), intermediaries=(), externals=(), expected_outcome="")
    res = asyncio.run(draft_goal_cdds(goal_graph=g, drafter=_FakeDrafter(empty), actor=_actor()))
    assert not res[0].drafted and g.elements == []


def test_draft_persists_nothing_on_parse_failure_none():
    g = _FakeGraph()
    g._goal = _SEQ_GOAL
    res = asyncio.run(draft_goal_cdds(goal_graph=g, drafter=_FakeDrafter(None), actor=_actor()))
    assert not res[0].drafted and g.elements == []


# --- migration-shape guard (the live-surface law's minimum standing guard) --

_MIGRATION = Path("migrations/neo4j/0005_authored_cdd.cypher")


def test_migration_declares_the_authored_constraints():
    """The migration must declare a constraint for each authored node kind the
    code writes, so drift between the code's whitelist and the schema fails here
    rather than in production (the live-surface verification law)."""
    text = _MIGRATION.read_text()
    assert "intermediary_unique_per_tenant" in text
    assert "external_unique_per_tenant" in text
    assert "lever_id_unique_per_tenant" in text
    # Each authored node kind the wrapper composes labels for has a constraint.
    from contexts.ingestion.adapters.outbound.neo4j.session import _AUTHORED_NODE
    for kind, (label, _id) in _AUTHORED_NODE.items():
        # the label appears in a constraint declaration (FOR (n:Label))
        assert re.search(rf"FOR \(\w+:{label}\)", text), (kind, label)
