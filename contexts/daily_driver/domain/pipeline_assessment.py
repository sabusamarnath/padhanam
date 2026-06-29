"""The get-a-job "how am I doing" assessment — a pure, recommendation-shaped verdict
over the opportunity set (S103p, D216).

The load-bearing rule (from the v2-mock review): the **headline rests only on
label-independent evidence** — the count of confirmed-live opportunities, the
applied→engaged→interview→offer collapse, and the offer (won) count — and is
**invariant to the rejected/declined/went-cold/withdrawn mix**, which is unproofed
and ambiguous. The close-reason split is returned as a *proof-dependent sharpener*
of the move's emphasis (response-vs-conversion), never as the thing the headline
rests on. Deterministic and traceable (the goal_assessment pure-verdict precedent,
D16 — no LLM). The use case reads the ``GoalCddView`` and feeds the primitives in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from contexts.daily_driver.domain.cdd import OpportunityView, ProvenanceOrigin

# The closed reasons whose mix is unproofed + ambiguous (rejection vs silence) — the
# headline must NOT read these. ``won`` is a distinct, unambiguous outcome (you
# either got an offer or you did not), so the headline may read it.
_AMBIGUOUS_REASONS = ("rejected", "declined", "withdrawn_or_killed", "went_cold")

_CLOSED = "closed"


@dataclass(frozen=True)
class PipelineAssessment:
    """The assessment a get-a-job read renders (D216). The headline fields
    (``verdict_label`` / ``verdict_text`` / ``because`` / ``move``) are computed
    without reading the ambiguous close-reason mix; the ``closed_reasons`` split is
    the proof-dependent sharpener the render shows as two interpretations."""

    verdict_label: str
    verdict_text: str
    because: str
    move: str
    # funnel (label-independent)
    confirmed_live: int
    suggested_live: int
    closed: int
    engaged: int
    interviewed: int
    offers: int
    one_touch_volume: int
    activity: int
    # the proof-dependent split
    closed_reasons: dict[str, int] = field(default_factory=dict)
    suggested_closed: int = 0  # closed opportunities still system_suggested (unproofed)

    @property
    def split_proof_dependent(self) -> bool:
        """The response-vs-conversion reading depends on proof while any closed
        opportunity is still system-suggested (its reason unconfirmed)."""
        return self.suggested_closed > 0


def assess_pipeline(
    *,
    opportunities: tuple[OpportunityView, ...],
    interview_gate_ids: frozenset[UUID],
    one_touch_volume: int,
    activity: int,
) -> PipelineAssessment:
    """Assess the opportunity set into a recommendation-shaped verdict (D216).

    ``interview_gate_ids`` are the gates that count as "reached interview" (beyond
    the earliest/apply gate); ``one_touch_volume`` is the S103i pipeline count (the
    applications that drew only an automated acknowledgement); ``activity`` is the
    classifier-moat count (the job-search emails). The headline reads none of the
    ambiguous close reasons.
    """
    def _live(o: OpportunityView) -> bool:
        return o.status != _CLOSED

    confirmed_live = sum(
        1 for o in opportunities
        if o.provenance_origin is ProvenanceOrigin.USER_AUTHORED and _live(o)
    )
    suggested_live = sum(
        1 for o in opportunities
        if o.provenance_origin is ProvenanceOrigin.SYSTEM_SUGGESTED and _live(o)
    )
    closed = sum(1 for o in opportunities if o.status == _CLOSED)
    engaged = len(opportunities)
    interviewed = sum(
        1 for o in opportunities if o.current_gate_id in interview_gate_ids
    )
    # ``won`` is unambiguous — the headline may read it; the ambiguous mix it may not.
    offers = sum(1 for o in opportunities if o.closed_reason == "won")
    suggested_closed = sum(
        1 for o in opportunities
        if o.status == _CLOSED
        and o.provenance_origin is ProvenanceOrigin.SYSTEM_SUGGESTED
    )
    closed_reasons: dict[str, int] = {}
    for o in opportunities:
        if o.status == _CLOSED and o.closed_reason:
            closed_reasons[o.closed_reason] = closed_reasons.get(o.closed_reason, 0) + 1

    # --- the headline (label-independent: confirmed_live, offers, interviewed,
    # engaged, one_touch — never the ambiguous reason mix) ---------------------
    if confirmed_live > 0 or offers > 0:
        verdict_label = "live processes" if offers == 0 else "offer in hand"
        verdict_text = (
            f"{confirmed_live} live process{'es' if confirmed_live != 1 else ''} "
            f"and {offers} offer{'s' if offers != 1 else ''} — there is something to "
            "tend. Keep the live processes moving and the pipeline filled behind them."
        )
        because = (
            f"{confirmed_live} confirmed-live, {interviewed} at interview, "
            f"{offers} offer{'s' if offers != 1 else ''} across {engaged} engaged "
            "processes."
        )
        move = (
            "Tend the live processes to the next gate while keeping origination "
            "going behind them, so a single loss does not empty the pipeline."
        )
    else:
        verdict_label = "pipeline empty"
        upstream = interviewed <= 1
        verdict_text = (
            "Nothing is live, and almost nothing reached a real evaluation — the "
            "constraint is upstream of interviews, not at them. You are not being read."
            if upstream else
            "Nothing is live. Processes reached interview but none converted — keep "
            "originating while you tighten the late stages."
        )
        because = (
            f"{engaged} process{'es' if engaged != 1 else ''} drew a reply, "
            f"{interviewed} reached interview, {offers} offers; behind them ~"
            f"{one_touch_volume} applications drew only an automated acknowledgement "
            f"(of ~{activity} job-search emails). The collapse is at getting a reply, "
            "not at converting interviews."
            if upstream else
            f"{interviewed} of {engaged} engaged processes reached interview, "
            f"{offers} offers — the late stages, not getting read, are the gap."
        )
        move = (
            "Fix getting read, not interviewing — sharper targeting and warm "
            "introductions change the response rate that volume cannot. Originate "
            "again, differently; do not spend effort on interview prep for a problem "
            "upstream of interviews."
            if upstream else
            "Keep originating to refill the pipeline while you tighten interview "
            "conversion; do not let it run dry."
        )

    return PipelineAssessment(
        verdict_label=verdict_label,
        verdict_text=verdict_text,
        because=because,
        move=move,
        confirmed_live=confirmed_live,
        suggested_live=suggested_live,
        closed=closed,
        engaged=engaged,
        interviewed=interviewed,
        offers=offers,
        one_touch_volume=one_touch_volume,
        activity=activity,
        closed_reasons=closed_reasons,
        suggested_closed=suggested_closed,
    )


__all__ = ["PipelineAssessment", "assess_pipeline"]
