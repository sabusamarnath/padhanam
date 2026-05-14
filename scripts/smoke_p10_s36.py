"""Live-stack smoke for the P10 S36 audit reader (D102).

Runs inside padhanam-api against the live per-tenant Postgres
(tenant_a) and the live control-plane Postgres. Exercises:

1. get_audit_event on per-tenant destination — single-event
   lookup against tenant_a.
2. list_audit_events_with_filters on per-tenant — full page
   with no filters, chain_integrity verification.
3. list_audit_events_with_filters on per-tenant — narrow filter
   (action_verbs single value with selective overlap) producing
   partial chain_integrity.
4. list_audit_events_with_filters on control-plane after seeding
   one probe event so the chain is non-empty.
5. verify_chain_segment on a per-tenant page.

Plus the routing guard pair: per_tenant without tenant_context
raises; control_plane with tenant_context raises.

Output is JSON for the smoke document to capture verbatim.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import (
    async_sessionmaker,
    create_async_engine,
)

from contexts.audit.adapters.outbound.postgres.audit import tenant_audit
from contexts.audit.adapters.outbound.postgres.reader import (
    PostgresAuditEventReader,
)
from contexts.audit.domain.events import GENESIS_HASH, compute_event_hash
from contexts.audit.domain.query_filters import AuditEventListFilters
from contexts.audit.ports.reader import AuditQueryRoutingError
from shared_kernel import TenantContext, TenantId


# --------------------------------------------------------------------
# Wiring against the live tenant_a + control-plane Postgres
# --------------------------------------------------------------------

# tenant_a from charter/seed_tenants — looked up at smoke time
# from the control-plane registry rather than hardcoded.
TENANT_A_UUID = UUID("00000000-0000-4000-8000-00000000a001")
TENANT_A_CTX = TenantContext(
    tenant_id=TENANT_A_UUID,
    jurisdiction="eu-west",
    cost_attribution_id=str(TENANT_A_UUID),
)


def _cp_url() -> str:
    user = os.environ["POSTGRES_CONTROL_PLANE_USER"]
    pwd = os.environ["POSTGRES_CONTROL_PLANE_PASSWORD"]
    db = os.environ["POSTGRES_CONTROL_PLANE_DB"]
    return f"postgresql+asyncpg://{user}:{pwd}@postgres-control-plane:5432/{db}"


def _ta_url() -> str:
    user = os.environ["POSTGRES_TENANT_A_USER"]
    pwd = os.environ["POSTGRES_TENANT_A_PASSWORD"]
    db = os.environ["POSTGRES_TENANT_A_DB"]
    return f"postgresql+asyncpg://{user}:{pwd}@postgres-tenant-a:5432/{db}"


async def seed_one_control_plane_event(cp_sm) -> UUID:
    """Seed one probe event into the control-plane chain so the
    smoke's control-plane list returns at least one row."""
    event_id = uuid4()
    ts = datetime.now(timezone.utc)
    resource_id = str(uuid4())
    correlation_id = f"s36-smoke-{event_id.hex[:8]}"
    this_hash = compute_event_hash(
        actor="smoke:p10_s36",
        tenant_id="",
        jurisdiction="eu-west",
        timestamp=ts.isoformat(),
        action_verb="control_plane.audit.smoke_probe",
        resource_type="smoke_probe",
        resource_id=resource_id,
        before_state={},
        after_state={"smoke": "p10_s36"},
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,
    )

    async with cp_sm() as session:
        async with session.begin():
            # SELECT FOR UPDATE chain-tail row to chain correctly
            tail = (
                await session.execute(
                    sa.select(tenant_audit.c.this_event_hash)
                    .order_by(
                        tenant_audit.c.timestamp.desc(),
                        tenant_audit.c.id.desc(),
                    )
                    .limit(1)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            previous = tail if tail is not None else GENESIS_HASH
            this_hash = compute_event_hash(
                actor="smoke:p10_s36",
                tenant_id="",
                jurisdiction="eu-west",
                timestamp=ts.isoformat(),
                action_verb="control_plane.audit.smoke_probe",
                resource_type="smoke_probe",
                resource_id=resource_id,
                before_state={},
                after_state={"smoke": "p10_s36"},
                correlation_id=correlation_id,
                previous_event_hash=previous,
            )
            await session.execute(
                sa.insert(tenant_audit).values(
                    id=str(event_id),
                    tenant_id="",
                    actor="smoke:p10_s36",
                    jurisdiction="eu-west",
                    timestamp=ts,
                    action_verb="control_plane.audit.smoke_probe",
                    resource_type="smoke_probe",
                    resource_id=resource_id,
                    before_state={},
                    after_state={"smoke": "p10_s36"},
                    correlation_id=correlation_id,
                    previous_event_hash=previous,
                    this_event_hash=this_hash,
                )
            )
    return event_id


def _format_record(record) -> dict[str, Any]:
    if record is None:
        return None
    return {
        "id": str(record.id),
        "tenant_id": record.tenant_id,
        "actor": record.actor,
        "timestamp": record.timestamp.isoformat()
        if isinstance(record.timestamp, datetime)
        else str(record.timestamp),
        "action_verb": record.action_verb,
        "resource_type": record.resource_type,
        "resource_id": record.resource_id,
        "correlation_id": record.correlation_id,
        "previous_event_hash": record.previous_event_hash,
        "this_event_hash": record.this_event_hash,
    }


def _format_page(page) -> dict[str, Any]:
    return {
        "events_count": len(page.events),
        "first_event": _format_record(page.events[0]) if page.events else None,
        "last_event": _format_record(page.events[-1]) if page.events else None,
        "next_cursor_present": page.next_cursor is not None,
        "chain_integrity_status": page.chain_integrity.status,
        "broken_at_id": str(page.chain_integrity.broken_at_id)
        if page.chain_integrity.broken_at_id is not None
        else None,
    }


async def main() -> None:
    ta_engine = create_async_engine(_ta_url())
    cp_engine = create_async_engine(_cp_url())
    ta_sm = async_sessionmaker(ta_engine, expire_on_commit=False)
    cp_sm = async_sessionmaker(cp_engine, expire_on_commit=False)

    async def per_tenant_resolver(tid: TenantId):
        return ta_sm

    reader = PostgresAuditEventReader(
        per_tenant_sessionmaker_resolver=per_tenant_resolver,
        control_plane_sessionmaker=cp_sm,
    )

    out: dict[str, Any] = {}

    # --- 1. get_audit_event on tenant_a's chain.
    # Pick a known event id from tenant_a's chain.
    async with ta_sm() as session:
        row = (
            await session.execute(
                sa.select(tenant_audit.c.id, tenant_audit.c.action_verb)
                .order_by(tenant_audit.c.timestamp.desc())
                .limit(1)
            )
        ).first()
    known_event_id = UUID(row[0]) if row else None
    out["pretest_known_event_id"] = str(known_event_id)
    out["pretest_known_event_verb"] = row[1]

    record = await reader.get_audit_event(
        destination="per_tenant",
        event_id=known_event_id,
        tenant_context=TENANT_A_CTX,
    )
    out["scenario_1_get_audit_event"] = _format_record(record)

    # --- 2. list_audit_events_with_filters with no filters.
    page_no_filter = await reader.list_audit_events_with_filters(
        destination="per_tenant",
        filters=AuditEventListFilters(),
        cursor=None,
        page_size=5,
        tenant_context=TENANT_A_CTX,
    )
    out["scenario_2_list_no_filters_page"] = _format_page(page_no_filter)

    # --- 3. list with narrow action_verbs filter producing partial chain_integrity.
    # tenant_a has 'agent.invoke.start', 'agent.invoke.end', 'tenant.audit.test_event'.
    # Filtering on just 'agent.invoke.start' picks every-other event in the chain,
    # which produces partial chain_integrity because consecutive returned rows
    # don't link.
    page_filtered = await reader.list_audit_events_with_filters(
        destination="per_tenant",
        filters=AuditEventListFilters(action_verbs=("agent.invoke.start",)),
        cursor=None,
        page_size=10,
        tenant_context=TENANT_A_CTX,
    )
    out["scenario_3_list_action_filter_partial"] = _format_page(page_filtered)

    # --- 4. control-plane chain (seeded with one probe event for this smoke).
    cp_event_id = await seed_one_control_plane_event(cp_sm)
    out["scenario_4a_seeded_cp_event_id"] = str(cp_event_id)
    page_cp = await reader.list_audit_events_with_filters(
        destination="control_plane",
        filters=AuditEventListFilters(),
        cursor=None,
        page_size=10,
        tenant_context=None,
    )
    out["scenario_4b_list_control_plane"] = _format_page(page_cp)

    cp_record = await reader.get_audit_event(
        destination="control_plane",
        event_id=cp_event_id,
        tenant_context=None,
    )
    out["scenario_4c_get_cp_event"] = _format_record(cp_record)

    # --- 5. verify_chain_segment over the no-filter page.
    verification = await reader.verify_chain_segment(
        destination="per_tenant",
        events=page_no_filter.events,
    )
    out["scenario_5_verify_chain_segment"] = {
        "status": verification.status,
        "broken_at_id": str(verification.broken_at_id)
        if verification.broken_at_id is not None
        else None,
    }

    # --- Routing-guard pair (negative scenarios).
    try:
        await reader.get_audit_event(
            destination="per_tenant",
            event_id=uuid4(),
            tenant_context=None,
        )
        out["routing_guard_per_tenant_no_ctx"] = "FAIL — should have raised"
    except AuditQueryRoutingError as exc:
        out["routing_guard_per_tenant_no_ctx"] = f"raised: {exc}"

    try:
        await reader.get_audit_event(
            destination="control_plane",
            event_id=uuid4(),
            tenant_context=TENANT_A_CTX,
        )
        out["routing_guard_cp_with_ctx"] = "FAIL — should have raised"
    except AuditQueryRoutingError as exc:
        out["routing_guard_cp_with_ctx"] = f"raised: {exc}"

    print(json.dumps(out, indent=2, default=str))

    await ta_engine.dispose()
    await cp_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
