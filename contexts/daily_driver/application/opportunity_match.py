"""The match — run, read, and accept (S103ag, D239). Matching-engine leg 3.

Reads the opportunity's ``selection_criteria`` (leg 1, D236) and the operator's
**confirmed** skills profile (leg 2, D238, ``confirmed_only``), calls the
``MatchPort`` (the LiteLLM seam) for the per-criterion coverage, computes the
fit-tier suggestion from the coverage mix (pure domain), and stores the result with
an input fingerprint. The read reassembles the stored result and **recomputes
staleness** on read from the current inputs' fingerprint (D155, no silent stale
verdict). Accept promotes the suggestion to the operator's ``fit_tier`` — the only
path from suggestion to the authoritative tier, and it never happens automatically
(operator as ground truth, D200/D221).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from uuid import UUID

from contexts.daily_driver.domain.matching import (
    BANDS,
    FIT_BULLSEYE,
    FIT_OPPORTUNISTIC,
    FIT_STRONG,
    CriterionCoverage,
    match_inputs_fingerprint,
    split_criteria,
    suggest_fit_tier,
)
from contexts.daily_driver.domain.skills import SkillItemView, confirmed_only
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from contexts.daily_driver.ports.match import MatchPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)

_VALID_FIT_TIERS = frozenset({FIT_BULLSEYE, FIT_STRONG, FIT_OPPORTUNISTIC})


@dataclass(frozen=True)
class MatchView:
    """The match as read for the surface (S103ag, D239). ``has_result`` is False
    before the first run; ``has_criteria`` is False when there is no
    ``selection_criteria`` to match on; ``stale`` is recomputed on read from the
    input fingerprint; ``accepted`` is True once the operator's ``fit_tier`` equals
    the suggestion. ``coverages`` is structured for leg 4 (tailoring)."""

    has_result: bool
    has_criteria: bool
    coverages: tuple[CriterionCoverage, ...]
    band_counts: dict[str, int]
    suggested_fit_tier: str | None
    current_fit_tier: str | None
    accepted: bool
    stale: bool
    ran_at: str | None


def _profile_pairs(
    items: tuple[SkillItemView, ...]
) -> tuple[tuple[UUID, str], ...]:
    return tuple((i.item_id, i.text) for i in items)


def _assemble_view(
    *, data: dict, items: tuple[SkillItemView, ...]
) -> MatchView:
    """Build the view from the stored match record + the current confirmed profile,
    recomputing staleness. Single-sourced so run (post-store) and read agree."""
    criteria_text = data.get("selection_criteria")
    has_criteria = bool(split_criteria(criteria_text))
    result_json = data.get("match_result")
    suggested = data.get("fit_tier_suggested")
    current = data.get("fit_tier")
    ran_at = data.get("match_ran_at")

    coverages: tuple[CriterionCoverage, ...] = ()
    stale = False
    has_result = bool(result_json)
    if has_result:
        coverages = _deserialize_coverages(result_json)
        current_hash = match_inputs_fingerprint(
            criteria_text=criteria_text, confirmed_items=_profile_pairs(items),
        )
        stale = current_hash != (data.get("match_inputs_hash") or "")

    counts = {b: 0 for b in BANDS}
    for c in coverages:
        counts[c.band] = counts.get(c.band, 0) + 1

    accepted = bool(suggested and current == suggested)
    return MatchView(
        has_result=has_result, has_criteria=has_criteria, coverages=coverages,
        band_counts=counts, suggested_fit_tier=suggested,
        current_fit_tier=current, accepted=accepted, stale=stale, ran_at=ran_at,
    )


def _serialize_coverages(coverages: tuple[CriterionCoverage, ...]) -> str:
    return json.dumps([
        {"criterion": c.criterion, "band": c.band, "evidence": c.evidence}
        for c in coverages
    ])


def _deserialize_coverages(result_json: str) -> tuple[CriterionCoverage, ...]:
    try:
        raw = json.loads(result_json)
    except (ValueError, TypeError):
        return ()
    out: list[CriterionCoverage] = []
    if isinstance(raw, list):
        for c in raw:
            if isinstance(c, dict) and isinstance(c.get("criterion"), str):
                out.append(CriterionCoverage(
                    criterion=c["criterion"],
                    band=c.get("band") if isinstance(c.get("band"), str) else "gap",
                    evidence=c.get("evidence") if isinstance(c.get("evidence"), str) else "",
                ))
    return tuple(out)


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def read_opportunity_match(
    *, goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
) -> MatchView | None:
    """The stored match for an opportunity, staleness recomputed on read (D239).
    ``None`` when the opportunity is absent or cross-tenant."""
    data = await goal_graph.read_opportunity_match(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
    )
    if data is None:
        return None
    items = confirmed_only(
        await goal_graph.list_skill_items(tenant_context=actor.tenant_context)
    )
    return _assemble_view(data=data, items=items)


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def run_opportunity_match(
    *, goal_graph: GoalGraphPort, match_port: MatchPort,
    actor: ActorContext, opportunity_id: UUID,
) -> MatchView | None:
    """Run (or re-run) the match and store the result (D239). Reads the opportunity's
    selection criteria + the confirmed profile, calls the ``MatchPort``, computes the
    tier suggestion from the coverage mix, and stores the coverage + suggestion +
    input fingerprint. Returns the fresh view. ``None`` when the opportunity is
    absent. When there are no criteria, or the model returns nothing conforming,
    nothing is stored and the current view is returned."""
    data = await goal_graph.read_opportunity_match(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
    )
    if data is None:
        return None
    items = confirmed_only(
        await goal_graph.list_skill_items(tenant_context=actor.tenant_context)
    )
    criteria = split_criteria(data.get("selection_criteria"))
    if not criteria:
        return _assemble_view(data=data, items=items)

    skills = tuple(i.text for i in items if i.kind == "skill")
    experiences = tuple(i.text for i in items if i.kind == "experience")
    coverages = await match_port.match(
        criteria=criteria, skills=skills, experiences=experiences,
    )
    if coverages is None:
        # No schema-conforming match — persist nothing, return the prior state.
        return _assemble_view(data=data, items=items)

    inputs_hash = match_inputs_fingerprint(
        criteria_text=data.get("selection_criteria"),
        confirmed_items=_profile_pairs(items),
    )
    await goal_graph.set_opportunity_match(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        result_json=_serialize_coverages(coverages),
        fit_tier_suggested=suggest_fit_tier(coverages),
        inputs_hash=inputs_hash,
    )
    fresh = await goal_graph.read_opportunity_match(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
    )
    return _assemble_view(data=fresh or data, items=items)


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def accept_fit_tier_suggestion(
    *, goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
) -> bool:
    """Promote the match's fit-tier suggestion to the operator's ``fit_tier`` (D239).
    Returns True when a valid suggestion was promoted, False when there is nothing to
    accept (no run yet, or a malformed suggestion) or the opportunity is absent."""
    data = await goal_graph.read_opportunity_match(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
    )
    if data is None:
        return False
    suggested = data.get("fit_tier_suggested")
    if suggested not in _VALID_FIT_TIERS:
        return False
    return await goal_graph.set_opportunity_fit_tier(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        fit_tier=suggested,
    )


__all__ = [
    "MatchView",
    "accept_fit_tier_suggestion",
    "read_opportunity_match",
    "run_opportunity_match",
]
