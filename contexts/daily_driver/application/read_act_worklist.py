"""read_act_worklist — the act substrate (D232).

A read-and-render projection (S83) that unions six actionable sources into one
worklist: the pipeline next-best-action (S103q), warming steps due (D224),
stage-relative stale qualification (D229), and the three existing Today
sources — commitments (D157/D162), calendar events (S60), and open cases. Each
maps onto an ``ActItem`` tagged source / subject / action / due-horizon; the
pure ``build_act_worklist`` dedupes per subject and sorts by urgency.

Projection only — no graph write, no model change. Each source is guarded so a
missing seam (no calendar connected, pipeline seams unconfigured) degrades the
worklist cleanly rather than failing it, mirroring ``list_today`` (D159).
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from contexts.daily_driver.application.qualification import (
    QUALIFICATION_STALE_DAYS,
    read_opportunity_qualification,
)
from contexts.daily_driver.application.read_pipeline_stats import (
    read_pipeline_stats,
)
from contexts.daily_driver.domain.act_worklist import (
    SOURCE_CALENDAR,
    SOURCE_CASE,
    SOURCE_COMMITMENT,
    SOURCE_PIPELINE,
    SOURCE_QUALIFICATION,
    SOURCE_WARMING,
    ActItem,
    build_act_worklist,
)
from contexts.daily_driver.domain.commitment import OutcomeStatus
from contexts.daily_driver.domain.pipeline_stats import SILENT_DAYS, _CLOSED
from contexts.daily_driver.domain.staleness import days_elapsed
from contexts.daily_driver.ports.calendar_events_reader import (
    CalendarEventsReader,
)
from contexts.daily_driver.ports.commitment_repository import (
    CommitmentRepository,
)
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from contexts.daily_driver.ports.open_cases_reader import OpenCasesReader
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_TODAY_READ,
    requires_authorisation,
)


def _label(company: str, role: str) -> str:
    company = (company or "").strip()
    role = (role or "").strip()
    return f"{company} — {role}" if role else company


@requires_authorisation(DAILY_DRIVER_TODAY_READ)
async def read_act_worklist(
    *,
    goal_graph: GoalGraphPort,
    commitment_repository: CommitmentRepository,
    open_cases_reader: OpenCasesReader,
    actor: ActorContext,
    unit_graph: object | None = None,
    facet_source: object | None = None,
    audit_reader: object | None = None,
    calendar_events_reader: CalendarEventsReader | None = None,
    now: datetime | None = None,
) -> tuple[ActItem, ...]:
    """Assemble the act worklist for the actor across every goal (D232)."""
    now = now or datetime.now(timezone.utc)
    items: list[ActItem] = []
    items.extend(
        await _pipeline_items(
            goal_graph=goal_graph, unit_graph=unit_graph,
            facet_source=facet_source, audit_reader=audit_reader,
            actor=actor, now=now,
        )
    )
    items.extend(
        await _commitment_items(
            commitment_repository=commitment_repository, actor=actor, now=now,
        )
    )
    items.extend(
        await _calendar_items(
            calendar_events_reader=calendar_events_reader, actor=actor, now=now,
        )
    )
    items.extend(await _case_items(open_cases_reader=open_cases_reader, actor=actor))
    return build_act_worklist(items)


async def _pipeline_items(
    *, goal_graph, unit_graph, facet_source, audit_reader, actor, now,
) -> list[ActItem]:
    """Pipeline next-best-actions, warming steps, and stale qualification across
    every goal. Requires the assessment seams; degrades to empty without them."""
    if unit_graph is None or facet_source is None:
        return []
    out: list[ActItem] = []
    try:
        goals = await goal_graph.list_goals(tenant_context=actor.tenant_context)
    except Exception:
        return []
    for goal in goals:
        try:
            stats = await read_pipeline_stats(
                goal_graph=goal_graph, unit_graph=unit_graph,
                facet_source=facet_source, outcome_id=goal.id, actor=actor,
                now=now, audit_reader=audit_reader,
            )
        except Exception:
            continue
        oid = str(goal.id)
        # A live opportunity's next-best-action (S103q). Undated → due today
        # (confirm it); silent → overdue; recently active → upcoming.
        for c in stats.cards:
            if c.status == _CLOSED:
                continue
            due = 0 if c.days_silent is None else SILENT_DAYS - c.days_silent
            out.append(ActItem(
                source=SOURCE_PIPELINE, subject_kind="opportunity",
                subject_id=str(c.opportunity_id), subject=_label(c.company, c.role),
                action=c.next_action, due_in_days=due, is_opportunity=True,
                ref={"outcome_id": oid, "opportunity_id": str(c.opportunity_id)},
            ))
        # A lead's warming next-best-action (D224) — origination work, due now.
        for lead in stats.leads:
            out.append(ActItem(
                source=SOURCE_WARMING, subject_kind="opportunity",
                subject_id=str(lead.opportunity_id),
                subject=_label(lead.company, lead.role),
                action=lead.warming_action, due_in_days=0, is_opportunity=True,
                ref={"outcome_id": oid, "opportunity_id": str(lead.opportunity_id)},
            ))
        # Stage-relative stale qualification (D229) — one item per opportunity,
        # the most overdue stale field; dedupes against the pipeline card.
        for c in stats.cards:
            if c.status == _CLOSED:
                continue
            item = await _qualification_item(
                goal_graph=goal_graph, actor=actor, outcome_id=goal.id,
                opportunity_id=c.opportunity_id, label=_label(c.company, c.role),
                stage=c.stage, oid=oid, now=now,
            )
            if item is not None:
                out.append(item)
    return out


async def _qualification_item(
    *, goal_graph, actor, outcome_id: UUID, opportunity_id: UUID,
    label: str, stage: str, oid: str, now: datetime,
) -> ActItem | None:
    try:
        fields = await read_opportunity_qualification(
            goal_graph=goal_graph, actor=actor, outcome_id=outcome_id,
            opportunity_id=opportunity_id, now=now,
        )
    except Exception:
        return None
    worst: tuple[int, str] | None = None  # (due_in_days, action)
    for f in fields:
        if f.risk != "stale" or not f.last_touched:
            continue
        try:
            last = datetime.fromisoformat(f.last_touched)
        except (ValueError, TypeError):
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        silent = days_elapsed(since=last, now=now)
        due = QUALIFICATION_STALE_DAYS - silent  # < 0 (stale ⇒ overdue)
        action = f"{f.label} silent {silent} days at {stage.lower()} — refresh it."
        if worst is None or due < worst[0]:
            worst = (due, action)
    if worst is None:
        return None
    return ActItem(
        source=SOURCE_QUALIFICATION, subject_kind="opportunity",
        subject_id=str(opportunity_id), subject=label, action=worst[1],
        due_in_days=worst[0], is_opportunity=True,
        ref={"outcome_id": oid, "opportunity_id": str(opportunity_id)},
    )


async def _commitment_items(
    *, commitment_repository, actor, now,
) -> list[ActItem]:
    """Commitments (D157/D162): due_in_days from the interval + last completion.
    A completion resets the due date, so no per-day done overlay is needed."""
    try:
        activities = await commitment_repository.list_with_activity(
            tenant_context=actor.tenant_context
        )
    except Exception:
        return []
    out: list[ActItem] = []
    for a in activities:
        c = a.commitment
        if c.outcome_status is OutcomeStatus.DROPPED:
            continue
        last = a.last_completed_at or c.created_at
        elapsed = days_elapsed(since=last, now=now)
        due = c.expected_interval_days - elapsed
        if due < 0:
            action = f"Overdue by {abs(due)} days — log it or record the outcome."
            status = "BEHIND"
        elif due == 0:
            action = "Due today — log it or record the outcome."
            status = "BEHIND"
        else:
            action = f"On cadence — due in {due} days."
            status = "ON_TRACK"
        out.append(ActItem(
            source=SOURCE_COMMITMENT, subject_kind="commitment",
            subject_id=str(c.id), subject=c.name, action=action,
            due_in_days=due, is_opportunity=False,
            ref={
                "kind": "COMMITMENT", "item_id": str(c.id), "status": status,
                "detail": f"every {c.expected_interval_days} days",
                "expected_outcome": c.expected_outcome,
                "observed_outcome": c.observed_outcome,
                "outcome_status": (
                    c.outcome_status.value if c.outcome_status is not None else None
                ),
                "drop_candidate": False,
            },
        ))
    return out


async def _calendar_items(
    *, calendar_events_reader, actor, now,
) -> list[ActItem]:
    """Today's calendar events (S60) — due today by definition."""
    if calendar_events_reader is None:
        return []
    try:
        events = await calendar_events_reader.list_today_events(
            actor=actor, day_date=now.date()
        )
    except Exception:
        return []
    out: list[ActItem] = []
    for e in events:
        when = e.start_at.isoformat() if e.start_at is not None else None
        out.append(ActItem(
            source=SOURCE_CALENDAR, subject_kind="calendar",
            subject_id=str(e.meeting_id), subject=e.title,
            action="On your calendar today.", due_in_days=0, is_opportunity=False,
            ref={
                "kind": "CALENDAR", "item_id": str(e.meeting_id),
                "start_at": when, "detail": "today", "status": "NEEDS_YOU",
            },
        ))
    return out


async def _case_items(*, open_cases_reader, actor) -> list[ActItem]:
    """Open correspondence cases — awaiting you, due now."""
    try:
        cases = await open_cases_reader.list_open_cases(actor=actor)
    except Exception:
        return []
    return [
        ActItem(
            source=SOURCE_CASE, subject_kind="case", subject_id=str(k.case_id),
            subject=k.title, action="Open — awaiting you.", due_in_days=0,
            is_opportunity=False,
            ref={"kind": "CASE", "item_id": str(k.case_id), "status": "NEEDS_YOU"},
        )
        for k in cases
    ]


__all__ = ["read_act_worklist"]
