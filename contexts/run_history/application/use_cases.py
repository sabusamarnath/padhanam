"""record_run use case for the run-history context (D17, D75, D95, S31).

The producer-side write-path entry point. Called from the wiring
adapter at ``apps/cli/_cross_context.py`` (``RunHistoryWriterAdapter``,
lands at S31 commit 5) after the adapter has translated the
agent-context-shaped ``AgentRunRecord`` DTO into the run-history
domain ``RunRecord``.

Auth posture matches D75: operator-context-or-tenant-context.
Unauthenticated callers (empty role set) raise
``AuthorizationError`` at the use case boundary. The runtime
caller is tenant-context (the invocation's tenant principal
threaded through ``invoke_agent``); the future operator-facing
HTTP API at S34 will use operator-context.

Hash chain: the runs row's ``audit_start_hash`` and
``audit_end_hash`` link the projection to the canonical audit
chain per D95. This use case persists the link but does not
verify it; chain integrity is the audit context's responsibility
at audit emission time.
"""

from __future__ import annotations

from contexts.run_history.domain.run_record import RunRecord
from contexts.run_history.ports.repository import RunHistoryRepositoryPort
from padhanam.observability.security_events import (
    SecurityEvent,
    SecurityEventCategory,
    SecurityEventLogger,
)
from padhanam.security import (
    AuthorizationError,
    Principal,
    is_operator,
)


def _is_authenticated(principal: Principal) -> bool:
    """Operator-context-or-tenant-context auth posture (D75).

    Mirrors the agent context's ``_is_authenticated`` helper.
    Authentication is satisfied by any role on the principal;
    unauthenticated callers (empty role set) are denied at the
    use case boundary.
    """
    return is_operator(principal) or len(principal.roles) > 0


def _deny(
    *,
    principal: Principal,
    action: str,
    resource_ref: str,
    security_events: SecurityEventLogger,
) -> AuthorizationError:
    security_events.emit(
        SecurityEvent(
            category=SecurityEventCategory.AUTHZ_DENIAL,
            principal_ref=principal.subject,
            tenant_id=str(principal.tenant_id),
            action=action,
            resource_ref=resource_ref,
            outcome="deny",
        )
    )
    return AuthorizationError(
        f"{action} requires an authenticated principal "
        f"(tenant-context or operator-context); "
        f"principal {principal.subject!r} has no roles"
    )


async def record_run(
    *,
    principal: Principal,
    repository: RunHistoryRepositoryPort,
    security_events: SecurityEventLogger,
    run_record: RunRecord,
) -> None:
    """Persist a single ``RunRecord`` to the per-tenant ``runs`` table.

    The repository's tenant scoping is the session factory bound
    at composition time per D36. The use case does not re-scope
    the tenant — the routing happened upstream at the wiring
    adapter when it resolved the per-tenant session factory from
    the agent's ``tenant_context``.

    Returns ``None``; raises on persistence failure (typically
    asyncpg integrity errors surfaced through SQLAlchemy).
    Failure propagates to the ``invoke_agent`` generator per
    D95's write-timing commitment.
    """
    if not _is_authenticated(principal):
        raise _deny(
            principal=principal,
            action="run_history.record_run",
            resource_ref=f"runs:{run_record.id}",
            security_events=security_events,
        )
    await repository.persist(run_record)
