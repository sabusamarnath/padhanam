"""Warming-step tracking use cases (S103v, D224).

The operator logs a warming action (intro requested, follow-up sent, referral asked,
message sent) against a :Contact or an :Opportunity; it is stored append-only via the
audit context (`warming.step` verb, the subject as `resource_type`/`resource_id`) and
read back per subject through the faceted reader — the D203 correction precedent, no
new node type. The compliance record and the future warming-learning signal are the
same hash-chained artefact.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from contexts.audit.domain.ports import AuditPort
from contexts.audit.domain.query_filters import AuditEventListFilters
from contexts.audit.ports.reader import AuditEventReader
from contexts.daily_driver.application.audit_events import (
    ACTION_WARMING_STEP,
    RESOURCE_TYPE_CONTACT,
    RESOURCE_TYPE_OPPORTUNITY,
    WARMING_STEP_KINDS,
    warming_step_event,
)
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)

_SUBJECT_TYPES = (RESOURCE_TYPE_CONTACT, RESOURCE_TYPE_OPPORTUNITY)
_PER_TENANT = "per_tenant"
_PAGE_SIZE = 50  # the audit reader caps page_size at [1, 50]


class WarmingStepError(ValueError):
    """A warming-step field is outside its vocabulary, or the audit port is absent."""


@dataclass(frozen=True)
class WarmingStep:
    """One logged warming step read back for a subject (D224)."""

    kind: str
    note: str
    occurred_at: datetime
    actor: str


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def log_warming_step(
    *,
    actor: ActorContext,
    subject_type: str,
    subject_id: UUID,
    kind: str,
    note: str = "",
    audit_port: AuditPort | None,
) -> None:
    """Log a warming step against a contact/lead as an append-only audit event."""
    if subject_type not in _SUBJECT_TYPES:
        raise WarmingStepError(f"subject_type must be one of {list(_SUBJECT_TYPES)}")
    if kind not in WARMING_STEP_KINDS:
        raise WarmingStepError(f"kind must be one of {list(WARMING_STEP_KINDS)}")
    if audit_port is None:
        raise WarmingStepError("the audit port is not configured")
    await audit_port.emit(
        warming_step_event(
            tenant_context=actor.tenant_context, actor=actor.actor_id,
            subject_type=subject_type, subject_id=subject_id, kind=kind,
            note=note.strip(),
        )
    )


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def list_warming_steps(
    *,
    actor: ActorContext,
    subject_type: str,
    subject_id: UUID,
    audit_reader: AuditEventReader | None,
) -> tuple[WarmingStep, ...]:
    """The warming steps logged against a subject, newest first (D224). The faceted
    reader filters on resource_type + resource_id + the warming.step verb."""
    if subject_type not in _SUBJECT_TYPES or audit_reader is None:
        return ()
    page = await audit_reader.list_audit_events_with_filters(
        destination=_PER_TENANT,
        filters=AuditEventListFilters(
            resource_type=subject_type,
            resource_id=str(subject_id),
            action_verbs=(ACTION_WARMING_STEP,),
        ),
        cursor=None,
        page_size=_PAGE_SIZE,
        tenant_context=actor.tenant_context,
    )
    return tuple(
        WarmingStep(
            kind=str(e.after_state.get("kind", "")),
            note=str(e.after_state.get("note", "")),
            occurred_at=e.timestamp,
            actor=e.actor,
        )
        for e in page.events
    )


__all__ = [
    "WarmingStep", "WarmingStepError", "list_warming_steps", "log_warming_step",
]
