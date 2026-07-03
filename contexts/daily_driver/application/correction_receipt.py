"""list_correction_origins — the recorded origins for the corrected-receipt Undo
(S103ae, D237).

The corrected-receipt expander lists every ``user_owned`` binding (from the existing
bindings read) with where it went; the **Undo** needs where it *came from*, which
lives only in the D203 correction audit trail (``cdd.relink`` / ``cdd.unlink``
events, whose ``before_state`` carries the from-target). This reads that trail and
maps each unit to its latest recorded origin. Corrections predating the S103v
audit-port fix have no event here, so they are absent from the map — the surface
lists them but shows no Undo (show-only).
"""

from __future__ import annotations

from contexts.daily_driver.application.audit_events import (
    ACTION_CDD_RELINK,
    ACTION_CDD_UNLINK,
    RESOURCE_TYPE_CDD_EVIDENCE,
)
from shared_kernel import ActorContext
from shared_kernel.authorisation import (
    DAILY_DRIVER_CDD_READ,
    requires_authorisation,
)

# Defensive page cap: 20 pages × 50 = 1000 correction events. Well past any realistic
# correction volume; a hard stop so a runaway trail cannot loop unbounded.
_MAX_PAGES = 20
_PAGE_SIZE = 50


@requires_authorisation(DAILY_DRIVER_CDD_READ)
async def list_correction_origins(
    *, audit_reader: object, actor: ActorContext,
) -> dict[str, dict]:
    """Map ``unit_id -> {verb, from_kind, from_element_id}`` from the D203 correction
    trail (S103ae/D237). Events sort timestamp DESC, so the first seen per unit is its
    latest correction. Returns ``{}`` when the reader is unwired or has no events."""
    if audit_reader is None:
        return {}
    from contexts.audit.domain.query_filters import AuditEventListFilters

    origins: dict[str, dict] = {}
    cursor = None
    for _ in range(_MAX_PAGES):
        page = await audit_reader.list_audit_events_with_filters(
            destination="per_tenant",
            filters=AuditEventListFilters(
                resource_type=RESOURCE_TYPE_CDD_EVIDENCE,
                action_verbs=(ACTION_CDD_RELINK, ACTION_CDD_UNLINK),
            ),
            cursor=cursor,
            page_size=_PAGE_SIZE,
            tenant_context=actor.tenant_context,
        )
        for e in page.events:
            uid = e.resource_id
            if uid in origins:  # newest already kept (timestamp DESC)
                continue
            before = e.before_state or {}
            origins[uid] = {
                "verb": e.action_verb,
                "from_kind": before.get("element_kind"),
                "from_element_id": before.get("element_id"),
            }
        cursor = page.next_cursor
        if cursor is None:
            break
    return origins


__all__ = ["list_correction_origins"]
