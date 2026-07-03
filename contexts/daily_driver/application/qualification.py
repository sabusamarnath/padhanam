"""Qualification read + write use cases (S103w, D228; freshness layered at D229).

The operator sets a qualification field's value (proof-and-author, D200); the read
assembles the eight fields for an opportunity — value (champion / decision-maker
falling back to the role-typed contact at the company, D227), stage activation
(D228), and (D229, layered in ``read_opportunity_qualification``) the stage-relative
freshness risk.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from contexts.daily_driver.domain.contacts import (
    ContactView,
    normalize_company,
)
from contexts.daily_driver.domain.qualification import (
    QUAL_FIELD_KEYS,
    QualificationField,
    build_qualification_base,
)
from contexts.daily_driver.domain.staleness import is_overdue
from contexts.daily_driver.ports.goal_graph import GoalGraphPort
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    DAILY_DRIVER_CDD_WRITE,
    requires_authorisation,
)

# A field active at the current stage that has been silent this long reads stale.
QUALIFICATION_STALE_DAYS = 14


class QualificationError(ValueError):
    """An unknown qualification field key."""


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def set_qualification_field(
    *, goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
    field_key: str, value: str,
) -> bool:
    """Author a qualification field's value + bump its last_touched (D228). A saved
    value also clears any JD-extracted draft for the field (S103ad/D236 — Save
    supersedes the suggestion)."""
    if field_key not in QUAL_FIELD_KEYS:
        raise QualificationError(f"unknown qualification field: {field_key}")
    return await goal_graph.set_qualification_field(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        field_key=field_key, value=value.strip(), touch_only=False,
    )


@requires_authorisation(DAILY_DRIVER_CDD_WRITE)
async def dismiss_qualification_draft(
    *, goal_graph: GoalGraphPort, actor: ActorContext, opportunity_id: UUID,
    field_key: str,
) -> bool:
    """Dismiss a JD-extracted draft suggestion (S103ad/D236) — clears ``q_<key>_draft``
    without writing a value."""
    if field_key not in QUAL_FIELD_KEYS:
        raise QualificationError(f"unknown qualification field: {field_key}")
    return await goal_graph.set_qualification_draft(
        tenant_context=actor.tenant_context, opportunity_id=opportunity_id,
        field_key=field_key, value=None,
    )


def _role_by_field(
    company: str, contacts: tuple[ContactView, ...]
) -> dict[str, str]:
    """Map champion / decision_maker to a role-typed contact's name at the company
    (D227)."""
    nc = normalize_company(company)
    out: dict[str, str] = {}
    for c in contacts:
        if normalize_company(c.company) != nc or not c.process_role:
            continue
        if c.process_role == "champion" and "champion" not in out:
            out["champion"] = c.name
        elif c.process_role == "decision_maker" and "decision_maker" not in out:
            out["decision_maker"] = c.name
    return out


def _stale(field: QualificationField, now: datetime, stale_days: int) -> str | None:
    """The stage-relative freshness risk (D229): a field reads ``stale`` only when it
    is active at the current stage AND has a value that has gone quiet past the
    threshold. Computed always; surfaced only for active fields."""
    if not field.active or not field.value or not field.last_touched:
        return None
    try:
        last = datetime.fromisoformat(field.last_touched)
    except (ValueError, TypeError):
        return None
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return "stale" if is_overdue(
        last_activity_at=last, expected_interval_days=stale_days, now=now
    ) else None


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def read_opportunity_qualification(
    *, goal_graph: GoalGraphPort, actor: ActorContext, outcome_id: UUID,
    opportunity_id: UUID, now: datetime | None = None,
    stale_days: int = QUALIFICATION_STALE_DAYS,
) -> tuple[QualificationField, ...]:
    """The eight qualification fields for one opportunity (D228) with stage-relative
    freshness (D229). Returns () when the opportunity is absent."""
    now = now or datetime.now(timezone.utc)
    cdd = await goal_graph.read_goal_cdd(
        tenant_context=actor.tenant_context, outcome_id=outcome_id
    )
    opp = next(
        (o for o in cdd.opportunities if o.opportunity_id == opportunity_id), None
    )
    if opp is None:
        return ()
    gate = next((g for g in cdd.gates if g.gate_id == opp.current_gate_id), None)
    stage = gate.name if gate is not None else ""
    company = opp.name.split(" — ", 1)[0].strip()
    contacts = await goal_graph.list_contacts(tenant_context=actor.tenant_context)
    base = build_qualification_base(
        qual_props=getattr(opp, "qualification", None) or {}, stage=stage,
        role_by_field=_role_by_field(company, contacts),
    )
    return tuple(
        QualificationField(
            key=f.key, label=f.label, value=f.value, last_touched=f.last_touched,
            active=f.active, from_contact=f.from_contact,
            risk=_stale(f, now, stale_days), draft=f.draft,
        )
        for f in base
    )


__all__ = [
    "QUALIFICATION_STALE_DAYS", "QualificationError",
    "dismiss_qualification_draft", "read_opportunity_qualification",
    "set_qualification_field",
]
