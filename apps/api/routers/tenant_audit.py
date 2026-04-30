"""POST /tenant/{tenant_id}/audit/test-event — tenant-scoped endpoint
that exercises the full P3 slice (S12).

The handler validates an authenticated operator-context request,
resolves the tenant against the registry to confirm it exists and to
read its jurisdiction, decorates the active OTel span with
``tenant.id`` and ``tenant.jurisdiction`` (D37 names), then writes one
audit event through the Postgres audit adapter — which routes via
``get_tenant_session_factory`` to the tenant's data-plane database
and chains the event under SELECT FOR UPDATE per D37.

This is a session-scoped utility endpoint: the production audit
emission paths are the registry mutations from S10 (already wired)
plus future tenant-data-touching endpoints in P4+. The endpoint exists
so the S12 integration test can drive an end-to-end run and so the
Langfuse trace UI verification has a deterministic surface to look at.

OTel attribute namespace: ``tenant.id`` and ``tenant.jurisdiction`` are
Vadakkan-domain names per D37 — the OTel semantic-conventions group
has not stabilised multi-tenant attribute naming, so the names live
in the domain. If the OTel group converges on a different namespace,
the migration is a one-line rename here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from opentelemetry import trace
from pydantic import BaseModel

from apps.api.middleware import get_principal
from contexts.audit.adapters.outbound.postgres.audit import PostgresAuditAdapter
from contexts.audit.domain.events import AuditEvent, GENESIS_HASH
from contexts.tenancy.adapters.outbound.postgres.registry import (
    PostgresTenantRegistry,
)
from contexts.tenancy.application.use_cases import OPERATOR_ROLE
from contexts.tenancy.domain.tenant_id import TenantId
from vadakkan.security import Principal

router = APIRouter(prefix="/tenant", tags=["tenant"])

_tracer = trace.get_tracer("vadakkan.tenant_audit")


class TestEventResponse(BaseModel):
    tenant_id: str
    jurisdiction: str
    action_verb: str
    correlation_id: str


def _audit_port(request: Request) -> PostgresAuditAdapter:
    port = getattr(request.app.state, "audit_port", None)
    if port is None:
        raise HTTPException(
            status_code=503, detail="audit adapter not configured"
        )
    return port


def _registry(request: Request) -> PostgresTenantRegistry:
    reg = getattr(request.app.state, "tenant_registry", None)
    if reg is None:
        raise HTTPException(
            status_code=503, detail="tenant registry not configured"
        )
    return reg


@router.post(
    "/{tenant_id}/audit/test-event",
    response_model=TestEventResponse,
)
async def write_test_audit_event(
    tenant_id: str,
    principal: Annotated[Principal, Depends(get_principal)],
    audit: Annotated[PostgresAuditAdapter, Depends(_audit_port)],
    registry: Annotated[PostgresTenantRegistry, Depends(_registry)],
) -> TestEventResponse:
    """Emit one audit event to the routed tenant's tenant_audit table.

    Operator-context required at the handler boundary; the tenancy
    routing layer enforces the same invariant on its own
    ``reveal_connection_config`` path. The handler is async because
    the registry adapter and audit adapter are both async.
    """
    if OPERATOR_ROLE not in principal.roles:
        # Convert the policy-layer denial into an HTTP 403 at the
        # endpoint boundary so callers get a typed response rather
        # than a 500 from an unhandled exception.
        raise HTTPException(
            status_code=403,
            detail=(
                f"tenant.audit.test_event requires operator context; "
                f"principal {principal.subject!r} denied"
            ),
        )

    tenant = await registry.get_tenant(TenantId(tenant_id))
    if tenant is None:
        raise HTTPException(status_code=404, detail=f"tenant {tenant_id} not found")

    span = trace.get_current_span()
    span.set_attribute("tenant.id", str(tenant.id))
    span.set_attribute("tenant.jurisdiction", str(tenant.jurisdiction))

    correlation_id = (
        span.get_span_context().trace_id and f"{span.get_span_context().trace_id:032x}"
    ) or ""

    event = AuditEvent(
        actor=f"principal:{principal.subject}",
        tenant_id=str(tenant.id),
        jurisdiction=str(tenant.jurisdiction),
        action_verb="tenant.audit.test_event",
        resource_type="probe",
        resource_id=str(tenant.id),
        before_state={},
        after_state={"endpoint": "POST /tenant/{tenant_id}/audit/test-event"},
        correlation_id=correlation_id,
        previous_event_hash=GENESIS_HASH,  # adapter recomputes
        this_event_hash="",                 # adapter recomputes
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    await audit.emit(event)

    return TestEventResponse(
        tenant_id=str(tenant.id),
        jurisdiction=str(tenant.jurisdiction),
        action_verb=event.action_verb,
        correlation_id=correlation_id,
    )
