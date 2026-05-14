"""AuditEventReader query port for the read surface (D17, D102, S36).

The producer-side query port shaped to the eventual HTTP API at
S37. Three methods per D102:

- ``get_audit_event(destination, event_id, tenant_context) ->
  AuditEventRecord | None`` returns a single event from the
  selected destination or ``None`` if not present. The HTTP
  layer at S37 translates ``None`` to 404.

- ``list_audit_events_with_filters(destination, filters, cursor,
  page_size, tenant_context) -> AuditEventListPage`` returns a
  paginated, filtered list with the page-level chain integrity
  verification attached. Sort order is fixed at ``timestamp DESC,
  id DESC``; tuple-comparison cursor pagination on ``(timestamp,
  id)`` mirrors the run_history reader pattern.

- ``verify_chain_segment(destination, events) ->
  ChainIntegrityVerification`` returns the page-level integrity
  status for an explicit sequence of events. Exposed separately
  from ``list_audit_events_with_filters`` so consumers that
  obtained events through ``get_audit_event`` calls or other
  paths can verify a constructed segment.

Destination-parameter routing per D102 alternative (b) compresses
the per-tenant and control-plane surfaces into one port: schema
is column-for-column identical per D35, primitives are identical,
so the destination is a parameter rather than a separate port.

``tenant_context`` is required when ``destination == "per_tenant"``
and prohibited when ``destination == "control_plane"``. A mismatch
raises ``AuditQueryRoutingError`` at port-method entry. The
constraint exists at the port surface (not just the adapter)
because callers should not be able to supply a tenant context to
a control-plane read and get a silent ignored parameter.

Port location at the producer context under ``ports/`` per the
P9-era convention established at run_history. Intra-context
asymmetry with the write-side ``AuditPort`` at
``contexts/audit/domain/ports.py`` is recorded as a carryover at
``charter/current-package.md`` per S36 pre-write reconciliation
finding 1; the symmetrize-or-accept decision lands at the next
port-addition moment in the audit context.
"""

from __future__ import annotations

from typing import Protocol, Sequence
from uuid import UUID

from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.chain_integrity import ChainIntegrityVerification
from contexts.audit.domain.destination import AuditDestination
from contexts.audit.domain.query_filters import (
    AuditEventListCursor,
    AuditEventListFilters,
    AuditEventListPage,
)
from shared_kernel import TenantContext


class AuditQueryRoutingError(Exception):
    """Raised when destination and tenant_context disagree.

    Two surface mismatches both raise:

    - ``destination == "per_tenant"`` with ``tenant_context is
      None`` — the per-tenant destination requires a routed
      session; a missing tenant context cannot be coerced.
    - ``destination == "control_plane"`` with ``tenant_context``
      set — the control-plane destination ignores tenant context
      by construction; surfacing the mismatch protects against
      caller bugs where the wrong destination is selected.

    The HTTP layer at S37 catches this error and translates to
    400 (invalid request) rather than 500.
    """


class AuditEventReader(Protocol):
    """Read-side query port for the audit context (D102).

    Tenant scoping flows through the ``TenantContext`` parameter
    when ``destination == "per_tenant"``. Control-plane reads
    take no tenant context; the destination parameter is the
    routing dimension.

    Auth is not enforced at the port surface: the HTTP layer at
    S37 performs authentication and authorisation before the
    dependency-injected reader is invoked. The platform-operator
    claim extension to D23 (also S37 territory) is what gates
    control-plane reads.
    """

    async def get_audit_event(
        self,
        *,
        destination: AuditDestination,
        event_id: UUID,
        tenant_context: TenantContext | None,
    ) -> AuditEventRecord | None:
        """Return the audit event or ``None`` if not found.

        Raises ``AuditQueryRoutingError`` when destination and
        tenant_context disagree per the port-surface invariant.
        """
        ...

    async def list_audit_events_with_filters(
        self,
        *,
        destination: AuditDestination,
        filters: AuditEventListFilters,
        cursor: AuditEventListCursor | None,
        page_size: int,
        tenant_context: TenantContext | None,
    ) -> AuditEventListPage:
        """Return a page of events plus optional next-page cursor.

        Initial-page invocations pass ``cursor=None``; the adapter
        treats this as "newest event, page-size-many results."
        Subsequent-page invocations pass the previous page's
        ``next_cursor``; the adapter uses tuple comparison on
        ``(timestamp, id)`` so equal-timestamp events paginate
        stably under concurrent insert pressure (mirrors S33's
        ``sa.cast(..., pg.UUID)`` defence-in-depth).

        Sort order is fixed at ``timestamp DESC, id DESC`` per
        D102. Each returned page carries a
        ``ChainIntegrityVerification`` computed across the page
        events; the consumer can act on the status without
        re-reading the chain.

        Raises ``AuditQueryRoutingError`` when destination and
        tenant_context disagree.
        """
        ...

    async def verify_chain_segment(
        self,
        *,
        destination: AuditDestination,
        events: Sequence[AuditEventRecord],
    ) -> ChainIntegrityVerification:
        """Verify chain integrity over an explicit segment.

        Page-granularity verification per D102:

        - Recompute each row's ``this_event_hash`` from payload
          plus stored ``previous_event_hash`` via
          ``compute_event_hash`` and check equality.
        - Verify consecutive rows in the segment link correctly
          (row N's ``this_event_hash`` equals row N+1's
          ``previous_event_hash``).

        Returns ``ChainIntegrityVerification`` with one of:
        ``verified`` (all checks pass), ``broken_at_row``
        (specific row failed), ``partial`` (segment too short
        to verify, or contains non-contiguous rows whose
        ordering does not match chain order).

        Destination is accepted for symmetry with the other
        methods; verification itself is pure-function and does
        not query the destination at this entry point (the
        events come from the caller). Future implementations
        may use destination to fetch the prior row for head
        verification.
        """
        ...


__all__ = ["AuditEventReader", "AuditQueryRoutingError"]
