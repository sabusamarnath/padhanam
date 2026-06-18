"""draft_goal_cdds — draft each goal's CDD through the inference seam (S102, D200).

For each live goal the use case asks the LLM (behind ``CddDrafterPort``) to draft
the goal's levers, intermediaries, externals, and expected outcome, then persists
each element with ``provenance_origin = llm_drafted`` / ``proof_state = pending``
and a default causal structure (lever → intermediary → outcome; external →
outcome). It is **safely re-runnable**: a goal that already carries authored
elements is skipped, so a second draft does not duplicate (re-authoring is the
S103 edit loop, not a re-draft). Read-and-draft; the matcher's SERVES/LEVER_FOR
layer is untouched.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4

from contexts.daily_driver.domain.cdd import (
    ElementKind,
    ProofState,
    ProvenanceOrigin,
)
from contexts.daily_driver.domain.goal import Goal
from contexts.daily_driver.ports.cdd_drafter import CddDrafterPort
from contexts.daily_driver.ports.commitment_repository import CommitmentRepository
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)


@dataclass(frozen=True)
class GoalDraftResult:
    """The outcome of drafting one goal's CDD."""

    outcome_id: UUID
    name: str
    drafted: bool
    skipped_existing: bool
    levers: int
    intermediaries: int
    externals: int


def _goal_commitment_ids(goal: Goal) -> tuple[UUID, ...]:
    ids: list[UUID] = []
    seen: set[UUID] = set()
    for cid in (
        goal.lever_commitment_id,
        *goal.lever_commitment_ids,
        *(step.commitment_id for step in goal.steps),
    ):
        if cid is not None and cid not in seen:
            seen.add(cid)
            ids.append(cid)
    return tuple(ids)


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def draft_goal_cdds(
    *,
    goal_graph: GoalGraphPort,
    drafter: CddDrafterPort,
    actor: ActorContext,
    commitment_repository: CommitmentRepository | None = None,
) -> tuple[GoalDraftResult, ...]:
    """Draft every goal's CDD that does not already have one (S102, D200)."""
    goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
    names_by_commitment: dict[UUID, str] = {}
    if commitment_repository is not None:
        for a in await commitment_repository.list_with_activity(
            tenant_context=actor.tenant_context
        ):
            names_by_commitment[a.commitment.id] = a.commitment.name

    results: list[GoalDraftResult] = []
    for goal in goals:
        existing = await goal_graph.read_goal_cdd(
            tenant_context=actor.tenant_context, outcome_id=goal.id
        )
        if existing.elements:
            results.append(
                GoalDraftResult(
                    outcome_id=goal.id, name=goal.name, drafted=False,
                    skipped_existing=True, levers=0, intermediaries=0, externals=0,
                )
            )
            continue
        lever_names = tuple(
            names_by_commitment[cid]
            for cid in _goal_commitment_ids(goal)
            if cid in names_by_commitment
        )
        drafted = await drafter.draft(
            goal_name=goal.name, mode=goal.mode.value, lever_names=lever_names
        )
        if drafted is None or not drafted.levers:
            results.append(
                GoalDraftResult(
                    outcome_id=goal.id, name=goal.name, drafted=False,
                    skipped_existing=False, levers=0, intermediaries=0, externals=0,
                )
            )
            continue

        if drafted.expected_outcome:
            await goal_graph.set_authored_outcome(
                tenant_context=actor.tenant_context,
                outcome_id=goal.id,
                expected_outcome=drafted.expected_outcome,
                origin=ProvenanceOrigin.LLM_DRAFTED,
                proof_state=ProofState.PENDING,
            )

        async def _persist(kind: ElementKind, label: str) -> UUID:
            element_id = uuid4()
            await goal_graph.write_authored_element(
                tenant_context=actor.tenant_context,
                outcome_id=goal.id,
                kind=kind,
                element_id=element_id,
                label=label,
                origin=ProvenanceOrigin.LLM_DRAFTED,
                proof_state=ProofState.PENDING,
            )
            return element_id

        # Intermediaries feed the outcome; the first one is the levers' default
        # target so the chain reads lever -> intermediary -> outcome.
        intermediary_ids: list[UUID] = []
        for el in drafted.intermediaries:
            eid = await _persist(ElementKind.INTERMEDIARY, el.label)
            intermediary_ids.append(eid)
            await goal_graph.write_authored_edge(
                tenant_context=actor.tenant_context, edge_type="FEEDS",
                source_kind="intermediary", source_id=eid,
                target_kind="outcome", target_id=goal.id,
            )
        for el in drafted.levers:
            eid = await _persist(ElementKind.LEVER, el.label)
            if intermediary_ids:
                await goal_graph.write_authored_edge(
                    tenant_context=actor.tenant_context, edge_type="FEEDS",
                    source_kind="lever", source_id=eid,
                    target_kind="intermediary", target_id=intermediary_ids[0],
                )
            else:
                await goal_graph.write_authored_edge(
                    tenant_context=actor.tenant_context, edge_type="FEEDS",
                    source_kind="lever", source_id=eid,
                    target_kind="outcome", target_id=goal.id,
                )
        for el in drafted.externals:
            eid = await _persist(ElementKind.EXTERNAL, el.label)
            await goal_graph.write_authored_edge(
                tenant_context=actor.tenant_context, edge_type="INFLUENCES",
                source_kind="external", source_id=eid,
                target_kind="outcome", target_id=goal.id,
            )

        results.append(
            GoalDraftResult(
                outcome_id=goal.id, name=goal.name, drafted=True,
                skipped_existing=False,
                levers=len(drafted.levers),
                intermediaries=len(drafted.intermediaries),
                externals=len(drafted.externals),
            )
        )
    return tuple(results)


__all__ = ["GoalDraftResult", "draft_goal_cdds"]
