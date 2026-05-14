# P9 S35a — trace_id propagation smoke

Live-stack verification that S35's trace_id propagation gap is closed.
Captured at S35a commit 4 (`fix(p9/s35a): trace_id propagation from
active OTel span to runs row`).

## Setup

Compose stack up; tenant_a registry seeded; `make migrate` applied
control-plane `0011_tenant_actor_provenance` and per-tenant migrations
through `0012_revise_citation_snapshots`. The fresh agent authored
at S35 (`5a6b54b5-476a-4ca1-b333-e4e8462e7382` — ProblemFramer with
retrieval allowlist) re-used as the demo subject.

## Trigger

```
docker compose exec -T padhanam-api python -m apps.cli agent run \
  --tenant a \
  --agent 5a6b54b5-476a-4ca1-b333-e4e8462e7382 \
  --input "What is two plus two? Reply briefly."
```

Termination: `content`. 1 iteration. Duration ~33s.

## Verification

```
docker compose exec -T postgres-tenant-a psql ... -c \
  "SELECT id, started_at, termination_reason, trace_id
   FROM runs ORDER BY started_at DESC LIMIT 3;"
```

| id                                   | started_at                    | termination_reason | trace_id                         |
|--------------------------------------|-------------------------------|--------------------|----------------------------------|
| 486af46b-37b5-429f-a0bf-9b2699335a95 | 2026-05-14 12:05:29.308661+00 | content            | b7e677a03e28afd51c5f691055545022 |
| 86f1f247-3e9c-4e97-9b97-7edcd252fd78 | 2026-05-14 09:04:53.499454+00 | content            | (NULL)                           |
| 5226925f-bd76-47c2-8c9b-fdb4b370e3ab | 2026-05-14 09:02:56.182889+00 | content            | (NULL)                           |

The new run (`486af46b-...`) at S35a carries `trace_id =
b7e677a03e28afd51c5f691055545022` — 32 lowercase hex chars per D95's
column-type commitment and the OTel `format(span_context.trace_id,
'032x')` convention. The two prior runs from S35 close pre-date the
S35a fix and remain NULL.

## What this confirms

D27's join-key claim (Postgres runs row ↔ Langfuse trace lookup) is
exercised end-to-end for the first time. `AgentLoopExecutor` opens
the `agent.invocation` OTel span; the span context propagates via
OTel contextvars through `invoke_agent`'s `async for event in stream`
loop; the `_assemble_agent_run_record` helper lifts
`trace.get_current_span().get_span_context().trace_id` after the
terminal yield and formats it to the conventional 32-character
lowercase hex string; `PostgresRunHistoryAdapter` persists the value
to the runs row's `trace_id` column.

D101's tenant_registry `created_by_user_id` migration also exercised
end-to-end: the existing seed tenants (Tenant A and Tenant B) carry
`created_by_user_id = 'migration:0001'` after the `0011_tenant_actor_
provenance` Alembic backfill. Future `make seed-tenants` runs would
carry `migration:ops/seed_tenants` per the updated seed-script
principal subject.
