"""Pipeline stats — the three-way split, the depth ladder, the engaged Kanban,
and the rules-based next best action (S103q, D217). Pure (D16, stdlib only).

The grain distinction (D171, no invented denominator): the three-way split
categorises *applications by outcome* — ``rejected`` and ``engaged`` are processes
(opportunities), ``no_response`` is the one-touch application volume (a different
grain), so the parts are reported separately, never summed into a faked "applied".

The "engaged set" for the depth ladder and the Kanban is **every tracked
opportunity** (all drew a reply / are multi-touch), rejected ones included and
marked — because the depth question (where does the staircase collapse?) is about
all processes that got into the pipeline, not only the still-alive ones. The
split's ``engaged`` *bucket* is the narrower not-rejected subset.

The next-best-action is a deterministic rules layer (no LLM) — the small cousin of
the win-probability engine, which replaces it later without changing the surface.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

# A process with no activity for at least this many days reads as silent.
SILENT_DAYS = 14
_CLOSED = "closed"
_UNPLACED = "Unplaced"


@dataclass(frozen=True)
class PipelineOpp:
    """One opportunity as the pipeline stats read it (the use case assembles these
    from the CDD view + the bindings' latest activity)."""

    opportunity_id: UUID
    company: str
    role: str
    status: str               # live / closed
    closed_reason: str | None
    stage: str                # the gate name, or "" when unplaced
    gate_order: int | None
    last_activity: datetime | None
    touches: int              # the correspondence thread length


@dataclass(frozen=True)
class SplitBucket:
    key: str
    label: str
    count: int
    opportunity_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class LadderRung:
    stage: str
    gate_order: int | None
    count: int
    opportunity_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class CardStat:
    opportunity_id: UUID
    company: str
    role: str
    stage: str
    gate_order: int | None
    status: str
    closed_reason: str | None
    last_activity: datetime | None
    days_silent: int | None
    touches: int
    next_action: str


@dataclass(frozen=True)
class PipelineStats:
    rejected: SplitBucket
    no_response: SplitBucket
    engaged: SplitBucket
    one_touch_volume: int
    ladder: tuple[LadderRung, ...]
    cards: tuple[CardStat, ...]


def next_best_action(
    *, status: str, closed_reason: str | None, stage: str, days_silent: int | None,
    silent_days: int = SILENT_DAYS,
) -> str:
    """One deterministic next action from the opportunity's stage + thread timing
    (D217). Rules now; the win-probability engine replaces them later."""
    if status == _CLOSED:
        r = closed_reason or "closed"
        return f"Closed ({r.replace('_', ' ')}) — reopen if it is still live."
    silent = days_silent is not None and days_silent >= silent_days
    # past the apply gate (screening or deeper) — Unplaced/Apply/none are still early.
    deep = stage not in ("", "Apply", _UNPLACED)
    if deep:
        if silent:
            return f"Silent {days_silent} days since {stage.lower()} — chase the next round or a decision timeline."
        return f"In {stage.lower()} — prepare the next round."
    # applied / unplaced (no reply progressed yet)
    if days_silent is None:
        return "No dated activity — confirm it is real or let it go."
    if silent:
        return f"Silent {days_silent} days — follow up once, then let it go."
    return "Recently active — await their reply."


def build_pipeline_stats(
    *,
    opportunities: tuple[PipelineOpp, ...],
    one_touch_volume: int,
    now: datetime,
    silent_days: int = SILENT_DAYS,
) -> PipelineStats:
    """Assemble the three-way split, the depth ladder, and the cards (D217)."""
    rejected_ids = tuple(
        o.opportunity_id for o in opportunities
        if o.status == _CLOSED and o.closed_reason == "rejected"
    )
    rejected_set = set(rejected_ids)
    engaged_ids = tuple(
        o.opportunity_id for o in opportunities
        if o.opportunity_id not in rejected_set
    )

    rejected = SplitBucket("rejected", "Rejected", len(rejected_ids), rejected_ids)
    engaged = SplitBucket("engaged", "Engaged", len(engaged_ids), engaged_ids)
    # no_response is the one-touch silence — a different grain (applications, not
    # processes), so it carries the count only, no opportunity constituents (D171).
    no_response = SplitBucket("no_response", "No response", one_touch_volume, ())

    # The depth ladder — every tracked opportunity by furthest gate, deepest rung
    # first, Unplaced last. Rejected ones are included (they reached gates too).
    by_stage: dict[str, list[PipelineOpp]] = {}
    order_of: dict[str, int | None] = {}
    for o in opportunities:
        stage = o.stage or _UNPLACED
        by_stage.setdefault(stage, []).append(o)
        order_of[stage] = o.gate_order
    rungs = [
        LadderRung(
            stage=stage, gate_order=order_of[stage], count=len(opps),
            opportunity_ids=tuple(o.opportunity_id for o in opps),
        )
        for stage, opps in by_stage.items()
    ]
    # deepest first; Unplaced (gate_order None) sinks to the bottom.
    rungs.sort(key=lambda r: (r.gate_order is not None, r.gate_order or 0), reverse=True)
    ladder = tuple(rungs)

    cards = tuple(
        CardStat(
            opportunity_id=o.opportunity_id, company=o.company, role=o.role,
            stage=o.stage or _UNPLACED, gate_order=o.gate_order,
            status=o.status, closed_reason=o.closed_reason,
            last_activity=o.last_activity,
            days_silent=(
                (now - o.last_activity).days if o.last_activity is not None else None
            ),
            touches=o.touches,
            next_action=next_best_action(
                status=o.status, closed_reason=o.closed_reason,
                stage=o.stage or _UNPLACED,
                days_silent=(
                    (now - o.last_activity).days
                    if o.last_activity is not None else None
                ),
                silent_days=silent_days,
            ),
        )
        for o in sorted(
            opportunities,
            key=lambda o: (o.gate_order is not None, o.gate_order or 0),
            reverse=True,
        )
    )
    return PipelineStats(
        rejected=rejected, no_response=no_response, engaged=engaged,
        one_touch_volume=one_touch_volume, ladder=ladder, cards=cards,
    )


__all__ = [
    "CardStat", "LadderRung", "PipelineOpp", "PipelineStats", "SILENT_DAYS",
    "SplitBucket", "build_pipeline_stats", "next_best_action",
]
