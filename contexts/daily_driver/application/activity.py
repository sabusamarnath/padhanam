"""Per-opportunity activity history (S103w, D229).

An opportunity's history is append-only audit events: the union of the D224
``warming.step`` events (retained) and a general ``opportunity.activity`` verb, read
back per opportunity by the faceted reader (`resource_type=opportunity` +
`resource_id` + both verbs). An entry may name a qualification field it touched,
which bumps that field's ``last_touched`` (a `touch_only` write) so freshness (D229)
reflects the real activity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.audit.domain.ports import AuditPort
from contexts.audit.domain.query_filters import AuditEventListFilters
from contexts.audit.ports.reader import AuditEventReader
from contexts.daily_driver.application.audit_events import (
    ACTION_OPPORTUNITY_ACTIVITY,
    ACTION_WARMING_STEP,
    RESOURCE_TYPE_OPPORTUNITY,
    opportunity_activity_event,
)
from contexts.daily_driver.domain.qualification import QUAL_FIELD_KEYS
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)

_PER_TENANT = "per_tenant"
_PAGE_SIZE = 50  # the audit reader caps page_size at [1, 50]


class ActivityError(ValueError):
    """A bad activity field, or the audit trail is unwired."""


@dataclass(frozen=True)
class ActivityEntry:
    """One activity in an opportunity's history (D229)."""

    kind: str
    note: str
    touches_field: str | None
    occurred_at: datetime
    actor: str


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def log_opportunity_activity(
    *,
    goal_graph: GoalGraphPort,
    actor: ActorContext,
    opportunity_id: UUID,
    kind: str,
    note: str = "",
    touches_field: str | None = None,
    audit_port: AuditPort | None,
) -> None:
    """Log an activity against an opportunity (append-only). When ``touches_field``
    names a qualification field, bump that field's last_touched (D229)."""
    kind = kind.strip()
    if not kind:
        raise ActivityError("kind is required")
    if touches_field and touches_field not in QUAL_FIELD_KEYS:
        raise ActivityError(f"unknown qualification field: {touches_field}")
    if audit_port is None:
        raise ActivityError("the audit port is not configured")
    await audit_port.emit(
        opportunity_activity_event(
            tenant_context=actor.tenant_context, actor=actor.actor_id,
            opportunity_id=opportunity_id, kind=kind, note=note.strip(),
            touches_field=touches_field,
        )
    )
    if touches_field:
        await goal_graph.set_qualification_field(
            tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
            field_key=touches_field, value=None, touch_only=True,
        )


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def list_opportunity_activity(
    *, actor: ActorContext, opportunity_id: UUID,
    audit_reader: AuditEventReader | None,
) -> tuple[ActivityEntry, ...]:
    """The opportunity's activity history, newest first (D229) — the union of
    warming steps and general activities via one faceted query."""
    if audit_reader is None:
        return ()
    page = await audit_reader.list_audit_events_with_filters(
        destination=_PER_TENANT,
        filters=AuditEventListFilters(
            resource_type=RESOURCE_TYPE_OPPORTUNITY,
            resource_id=str(opportunity_id),
            action_verbs=(ACTION_OPPORTUNITY_ACTIVITY, ACTION_WARMING_STEP),
        ),
        cursor=None,
        page_size=_PAGE_SIZE,
        tenant_context=actor.tenant_context,
    )
    return tuple(
        ActivityEntry(
            kind=str(e.after_state.get("kind", "")),
            note=str(e.after_state.get("note", "")),
            touches_field=(e.after_state.get("touches_field") or None),
            occurred_at=e.timestamp,
            actor=e.actor,
        )
        for e in page.events
    )


__all__ = [
    "ActivityEntry", "ActivityError", "list_opportunity_activity",
    "log_opportunity_activity",
]
