"""Postgres adapter for the audit read port (D102, S36).

Implements ``AuditEventReader`` against both destinations per
D102: per-tenant ``tenant_audit`` on the routed tenant's data
plane, and control-plane ``tenant_audit`` on the dedicated
control-plane Postgres instance. Schema is column-for-column
identical between the two per D35; the single SQLAlchemy
``tenant_audit`` Table object from
``contexts/audit/adapters/outbound/postgres/audit.py`` is reused
against either destination.

Constructor mirrors the write-side ``PostgresAuditAdapter``: a
control-plane sessionmaker held as instance state plus a
callback that resolves per-tenant sessionmakers via the tenancy
routing layer (D36). Destination routing happens per-method based
on the ``destination`` parameter; ``tenant_context``
correctness is enforced at port entry via
``AuditQueryRoutingError`` per D102.

Chain integrity verification reuses ``compute_event_hash`` and
``GENESIS_HASH`` from ``contexts/audit/domain/events.py`` as
primitives; the existing ``verify_chain`` walker is NOT reused
because it walks from genesis and a page may begin mid-chain
(D102 alternative (h)). The page-granularity verifier is new
logic on top of the reusable primitives.

Tuple-comparison cursor pagination uses
``sa.cast(..., pg.UUID)`` per S33's defence-in-depth finding
so the Postgres operator resolver does not see ``uuid <
varchar`` in mixed-shape comparisons.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, Sequence
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql as pg
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from contexts.audit.adapters.outbound.postgres.audit import tenant_audit
from contexts.audit.domain.audit_event_record import AuditEventRecord
from contexts.audit.domain.chain_integrity import ChainIntegrityVerification
from contexts.audit.domain.destination import AuditDestination
from contexts.audit.domain.events import GENESIS_HASH, compute_event_hash
from contexts.audit.domain.query_filters import (
    PAGE_SIZE_CEILING,
    AuditEventListCursor,
    AuditEventListFilters,
    AuditEventListPage,
)
from contexts.audit.ports.reader import AuditQueryRoutingError
from shared_kernel import TenantContext, TenantId


class _SessionFactoryResolver(Protocol):
    """Same shape as the write-side adapter's resolver — given a
    ``TenantId``, return the per-tenant ``async_sessionmaker``."""

    async def __call__(
        self, tenant_id: TenantId
    ) -> async_sessionmaker[AsyncSession]: ...


class PostgresAuditEventReader:
    """Adapter implementation of ``AuditEventReader`` (D102).

    Holds the control-plane sessionmaker plus a callback that
    resolves per-tenant sessionmakers. Destination parameter
    selects the routing per call.

    No tenant credentials, plaintext or otherwise, are kept on
    the instance — per-tenant routing is opaque via the
    resolver callback (mirrors the write-side adapter's
    plaintext-credentials-free posture).
    """

    def __init__(
        self,
        *,
        per_tenant_sessionmaker_resolver: _SessionFactoryResolver,
        control_plane_sessionmaker: async_sessionmaker[AsyncSession],
    ) -> None:
        self._resolve_per_tenant = per_tenant_sessionmaker_resolver
        self._control_plane_sessionmaker = control_plane_sessionmaker

    # ------------------------------------------------------------------
    # AuditEventReader implementation
    # ------------------------------------------------------------------

    async def get_audit_event(
        self,
        *,
        destination: AuditDestination,
        event_id: UUID,
        tenant_context: TenantContext | None,
    ) -> AuditEventRecord | None:
        self._assert_routing(destination, tenant_context)
        sessionmaker = await self._resolve_sessionmaker(destination, tenant_context)
        scope_tenant_id = (
            str(tenant_context.tenant_id) if tenant_context is not None else ""
        )
        async with sessionmaker() as session:
            row = (
                await session.execute(
                    sa.select(tenant_audit).where(
                        sa.and_(
                            tenant_audit.c.id == str(event_id),
                            tenant_audit.c.tenant_id == scope_tenant_id,
                        )
                    )
                )
            ).mappings().first()
        if row is None:
            return None
        return _row_to_record(row)

    async def list_audit_events_with_filters(
        self,
        *,
        destination: AuditDestination,
        filters: AuditEventListFilters,
        cursor: AuditEventListCursor | None,
        page_size: int,
        tenant_context: TenantContext | None,
    ) -> AuditEventListPage:
        self._assert_routing(destination, tenant_context)
        if cursor is not None and cursor.page_size != page_size:
            page_size = cursor.page_size
        if not (1 <= page_size <= PAGE_SIZE_CEILING):
            raise ValueError(
                f"page_size must be in [1, {PAGE_SIZE_CEILING}]; got {page_size}"
            )
        scope_tenant_id = (
            str(tenant_context.tenant_id) if tenant_context is not None else ""
        )
        sessionmaker = await self._resolve_sessionmaker(destination, tenant_context)

        clauses = [tenant_audit.c.tenant_id == scope_tenant_id]
        if filters.timestamp_range is not None:
            lower, upper = filters.timestamp_range
            clauses.append(tenant_audit.c.timestamp >= lower)
            clauses.append(tenant_audit.c.timestamp < upper)
        if filters.actor is not None:
            clauses.append(tenant_audit.c.actor == filters.actor)
        if filters.action_verbs is not None:
            clauses.append(tenant_audit.c.action_verb.in_(filters.action_verbs))
        if filters.resource_type is not None:
            clauses.append(tenant_audit.c.resource_type == filters.resource_type)
        if filters.resource_id is not None:
            clauses.append(tenant_audit.c.resource_id == filters.resource_id)
        if filters.correlation_id is not None:
            clauses.append(tenant_audit.c.correlation_id == filters.correlation_id)
        if filters.jurisdiction is not None:
            clauses.append(tenant_audit.c.jurisdiction.in_(filters.jurisdiction))
        if cursor is not None:
            # Row-value tuple comparison: (timestamp, id) < (cursor_timestamp, cursor_id)
            # paginates stably under the (timestamp DESC, id DESC) sort. The id
            # column is pg.UUID; cast the parameter so the Postgres operator
            # resolver does not see uuid < varchar (S33 defence-in-depth).
            clauses.append(
                sa.tuple_(tenant_audit.c.timestamp, tenant_audit.c.id)
                < sa.tuple_(
                    cursor.timestamp,
                    sa.cast(str(cursor.id), pg.UUID(as_uuid=False)),
                )
            )

        query = (
            sa.select(tenant_audit)
            .where(sa.and_(*clauses))
            .order_by(tenant_audit.c.timestamp.desc(), tenant_audit.c.id.desc())
            .limit(page_size + 1)
        )

        async with sessionmaker() as session:
            rows = (await session.execute(query)).mappings().all()

        has_next = len(rows) > page_size
        page_rows = rows[:page_size]
        records = tuple(_row_to_record(r) for r in page_rows)

        if has_next and page_rows:
            last = page_rows[-1]
            next_cursor: AuditEventListCursor | None = AuditEventListCursor(
                timestamp=last["timestamp"],
                id=_coerce_uuid(last["id"]),
                page_size=page_size,
            )
        else:
            next_cursor = None

        chain_integrity = _verify_page(records)

        return AuditEventListPage(
            events=records,
            next_cursor=next_cursor,
            chain_integrity=chain_integrity,
        )

    async def verify_chain_segment(
        self,
        *,
        destination: AuditDestination,  # accepted for symmetry, not used in pure verification
        events: Sequence[AuditEventRecord],
    ) -> ChainIntegrityVerification:
        # destination parameter is accepted at the port level for symmetry
        # but the verifier is pure-function over the provided events.
        _ = destination
        return _verify_segment(tuple(events))

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _assert_routing(
        destination: AuditDestination,
        tenant_context: TenantContext | None,
    ) -> None:
        if destination == "per_tenant" and tenant_context is None:
            raise AuditQueryRoutingError(
                "destination='per_tenant' requires a tenant_context"
            )
        if destination == "control_plane" and tenant_context is not None:
            raise AuditQueryRoutingError(
                "destination='control_plane' prohibits a tenant_context; "
                f"got tenant_id={tenant_context.tenant_id!r}"
            )

    async def _resolve_sessionmaker(
        self,
        destination: AuditDestination,
        tenant_context: TenantContext | None,
    ) -> async_sessionmaker[AsyncSession]:
        if destination == "per_tenant":
            assert tenant_context is not None  # gated by _assert_routing
            return await self._resolve_per_tenant(
                TenantId(str(tenant_context.tenant_id))
            )
        return self._control_plane_sessionmaker


# ---------------------------------------------------------------------------
# Row → record + chain verification
# ---------------------------------------------------------------------------


def _coerce_uuid(value: object) -> UUID:
    if isinstance(value, UUID):
        return value
    return UUID(str(value))


def _row_to_record(row) -> AuditEventRecord:
    """Map a tenant_audit row mapping to an AuditEventRecord."""
    return AuditEventRecord(
        id=_coerce_uuid(row["id"]),
        tenant_id=row["tenant_id"],
        actor=row["actor"],
        jurisdiction=row["jurisdiction"],
        timestamp=row["timestamp"],
        action_verb=row["action_verb"],
        resource_type=row["resource_type"],
        resource_id=row["resource_id"],
        before_state=row["before_state"] or {},
        after_state=row["after_state"] or {},
        correlation_id=row["correlation_id"],
        previous_event_hash=row["previous_event_hash"],
        this_event_hash=row["this_event_hash"],
    )


def _per_row_hash_ok(record: AuditEventRecord) -> bool:
    """Recompute this_event_hash from payload + stored previous_event_hash.

    Reuses ``compute_event_hash`` from ``contexts/audit/domain/events.py``
    as the per-row primitive. The hash payload mirrors the write-side
    composition exactly so a row written by ``PostgresAuditAdapter.emit``
    verifies cleanly here.

    The hash payload uses ``timestamp`` as ISO string (the write side
    uses ``datetime.now(timezone.utc).isoformat()``); the read-side
    timestamp comes back as a ``datetime`` from Postgres ``timestamptz``.
    Round-trip via ``isoformat()`` to match the write-side format.
    """
    expected = compute_event_hash(
        actor=record.actor,
        tenant_id=record.tenant_id,
        jurisdiction=record.jurisdiction,
        timestamp=record.timestamp.isoformat()
        if isinstance(record.timestamp, datetime)
        else str(record.timestamp),
        action_verb=record.action_verb,
        resource_type=record.resource_type,
        resource_id=record.resource_id,
        before_state=record.before_state,
        after_state=record.after_state,
        correlation_id=record.correlation_id,
        previous_event_hash=record.previous_event_hash,
    )
    return expected == record.this_event_hash


def _verify_segment(
    events: tuple[AuditEventRecord, ...],
) -> ChainIntegrityVerification:
    """Verify integrity over an explicit segment of events.

    Per-row recomputation first (any failure → ``broken_at_row``),
    then chain-link verification across consecutive rows in chain
    order (any link mismatch → ``partial``; the link could be
    broken or simply non-contiguous due to filter selectivity).
    Segments of fewer than two rows surface as ``partial``
    because they cannot verify chain linkage; the single-row case
    still verifies the per-row hash though, so a per-row failure
    still surfaces as ``broken_at_row``.
    """
    if not events:
        return ChainIntegrityVerification(status="partial")

    # Per-row hash check — order-independent because each row's
    # hash is a pure function of its own payload + stored prev hash.
    for record in events:
        if not _per_row_hash_ok(record):
            return ChainIntegrityVerification(
                status="broken_at_row", broken_at_id=record.id
            )

    if len(events) < 2:
        # Single-row segment: per-row hash check passed, but no
        # chain-link to verify. Conservative reading per D102 —
        # surface as partial so consumers know the segment was
        # too small to verify chain linkage.
        return ChainIntegrityVerification(status="partial")

    # Sort by (timestamp, id) ASC so consecutive pairs are in
    # chain order regardless of the caller's input order. The
    # list-page caller passes events in DESC display order; the
    # verifier consumes chain order internally.
    chain_ordered = sorted(events, key=lambda r: (r.timestamp, r.id))
    for prev, curr in zip(chain_ordered, chain_ordered[1:]):
        if curr.previous_event_hash != prev.this_event_hash:
            return ChainIntegrityVerification(status="partial")

    return ChainIntegrityVerification(status="verified")


def _verify_page(
    events: tuple[AuditEventRecord, ...],
) -> ChainIntegrityVerification:
    """Page-level wrapper around ``_verify_segment``.

    Centralises the call site so the page-builder in
    ``list_audit_events_with_filters`` stays readable. The empty
    page returns ``partial`` per ``_verify_segment``; the consumer
    can act on that or call ``verify_chain_segment`` separately
    over a different set of events.
    """
    return _verify_segment(events)


__all__ = ["PostgresAuditEventReader"]
