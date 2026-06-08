"""Pull Google Tasks for the personal dogfood tenant (S65, D167).

The operator-gated live trigger for task ingestion: ensures the personal
tenant's ``task_connections`` row points at the operator-provisioned Nango
``google-tasks`` connection, then runs ``sync_tasks`` (a full re-pull into the
re-pullable cache). Idempotent — re-running refreshes the cache. Ops-only,
composing the tasks adapters at the boundary (the ``apps/cli/_calendar`` and
``ops/seed_*`` precedent). Must run where the personal-tenant Postgres host
resolves and Nango is reachable (inside ``padhanam-api``, via ``make pull-tasks``).

Operator pre-flight (the S56a operator-gated provisioning precedent): provision a
Nango ``google-tasks`` integration with the ``tasks.readonly`` scope on the
connected Google account, obtain the connection reference, and set
``TASKS_CONNECTION_REF`` (plus ``NANGO_SECRET_KEY``) in the gitignored ``.env``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone
from uuid import UUID, uuid4

log = logging.getLogger("ops.pull_tasks")

# Personal dogfood tenant (ops/dogfood_provision.py).
PERSONAL_TENANT_UUID = "00000000-0000-4000-8000-00000000d001"

# Deterministic id for the personal tenant's single google-tasks connection.
TASKS_CONNECTION_ID = UUID("00000000-0000-4000-8000-0000006500a1")


async def _pull() -> None:
    from apps.cli._runtime import build_tenant_wiring
    from contexts.tasks.adapters.outbound.nango.nango_proxy_task_adapter import (
        NangoProxyTaskAdapter,
    )
    from contexts.tasks.adapters.outbound.postgres.connection_repository import (
        PostgresConnectionRepository,
    )
    from contexts.tasks.adapters.outbound.postgres.task_store import (
        PostgresTaskStore,
    )
    from contexts.tasks.application.sync_tasks import sync_tasks
    from contexts.tasks.domain.connection import Connection
    from contexts.tasks.domain.sync_trigger import TaskSyncTrigger
    from padhanam.config.tasks import TasksSettings
    from shared_kernel import TenantId

    settings = TasksSettings()
    if not settings.tasks_connection_ref:
        raise SystemExit(
            "TASKS_CONNECTION_REF is empty — provision the Nango google-tasks "
            "connection (tasks.readonly) and set it in .env before pulling."
        )

    wiring = build_tenant_wiring(PERSONAL_TENANT_UUID)
    tenant_context = wiring.tenant_context
    session_factory = wiring.session_factory

    async def _resolver(_tid: TenantId):
        return session_factory

    bound = TenantId(str(tenant_context.tenant_id))
    connections = PostgresConnectionRepository(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )
    store = PostgresTaskStore(
        per_tenant_sessionmaker_resolver=_resolver, bound_tenant_id=bound
    )

    now = datetime.now(timezone.utc)
    await connections.save_connection(
        tenant_context=tenant_context,
        connection=Connection(
            id=TASKS_CONNECTION_ID,
            tenant_id=UUID(str(tenant_context.tenant_id)),
            jurisdiction=tenant_context.jurisdiction,
            provider="google_tasks",
            provider_config_key=settings.tasks_provider_config_key,
            provider_connection_ref=settings.tasks_connection_ref,
            created_at=now,
            updated_at=now,
        ),
    )
    log.info("ensured google-tasks connection %s", TASKS_CONNECTION_ID)

    source = NangoProxyTaskAdapter(
        base_url=settings.nango_base_url, secret_key=settings.nango_secret_key
    )
    result = await sync_tasks(
        tenant_context=tenant_context,
        connection_id=TASKS_CONNECTION_ID,
        trigger=TaskSyncTrigger.POLL,
        task_source=source,
        connections=connections,
        tasks=store,
        task_reader=store,
    )
    log.info(
        "pull complete: fetched=%d upserted=%d tombstoned=%d changed=%d",
        result.fetched,
        result.upserted,
        result.tombstoned,
        len(result.changed_task_ids),
    )


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
        stream=sys.stdout,
    )
    log.setLevel(logging.INFO)
    log.info("pulling Google Tasks for the personal dogfood tenant (S65)")
    asyncio.run(_pull())
    log.info("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
