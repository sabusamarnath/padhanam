# P9 S31 — Live-stack smoke (2026-05-13)

End-to-end exercise of the run-history substrate through the SSE
endpoint against `tenant_a` per D95's write-timing commitment
(shape B). Image `padhanam-api:dev@sha256:838e3ec94e2b0cb9867ec77234d0540d3c4b59c27d0b2c88d068473710d8b46f`
carries S31's full commit set (alembic 0011_create_run_history,
PostgresRunHistoryAdapter, RunHistoryWriterAdapter,
AgentRuntimeComposition.run_history_writer field, invoke_agent
accumulator + post-terminal-yield write seam).

CLI invocation: `docker compose exec -T padhanam-api python -m
apps.cli agent run --tenant a --agent
637602a2-b19e-44c5-8f32-e4228f4692b5 --input "Smoke S31: define
a good problem statement in one sentence."` ran end-to-end against
the live LiteLLM → Ollama Qwen 2.5 7B stack; one iteration, 7.5
seconds, `termination_reason=content`. The Flowstate ProblemFramer
agent on `tenant_a` produced a SMART-shaped problem statement
("To reduce hospital readmission rates by 20% within one year
through ...") — generic LLM filler per the S30b retrieval-not-
exercised carryover, but the substrate exercise is the focus
of this smoke, not the artifact quality.

## Runs row verification

`docker compose exec -T postgres-tenant-a psql -U tenant_a -d
tenant_a -c "SELECT id, agent_template_id, termination_reason,
iteration_count, total_cost_usd, audit_start_hash,
audit_end_hash FROM runs ORDER BY created_at DESC LIMIT 1;"`
output:

```
                  id                  |          agent_template_id           | termination_reason | iteration_count | total_cost_usd |                         audit_start_hash                         |                          audit_end_hash                          
--------------------------------------+--------------------------------------+--------------------+-----------------+----------------+------------------------------------------------------------------+------------------------------------------------------------------
 aedbefba-ea30-49fd-bf2e-435e9a4d2375 | 637602a2-b19e-44c5-8f32-e4228f4692b5 | content            |               1 |       0.000000 | 4d615b63f50017e2d215153974f61edddacf30fbe5ec18f26aa32486f8623abf | 5663b22a14ea8f5c15002b88cad4c27c8d4a9790bf1550210798638ab158e8b2
(1 row)
```

Fifteen-column shape per D95 confirmed (truncated to the
operationally-relevant subset for this query). The runs row's
`id` matches the SSE stream's `invocation_id`. `agent_template_id`
matches the Flowstate ProblemFramer template
(`637602a2-...`). `termination_reason='content'` matches the
SSE terminal event class (`InvocationCompleted` with
`TerminationReason.CONTENT`). `iteration_count=1` matches the
streamed `IterationStarted` cardinality. `total_cost_usd=0.000000`
matches Ollama's zero-cost local inference per D49.

## Audit-chain linkage

Audit rows for this invocation's resource_id, ordered by recent:

```
    action_verb     |                         this_event_hash                          
--------------------+------------------------------------------------------------------
 agent.invoke.end   | 5663b22a14ea8f5c15002b88cad4c27c8d4a9790bf1550210798638ab158e8b2
 agent.invoke.start | 4d615b63f50017e2d215153974f61edddacf30fbe5ec18f26aa32486f8623abf
```

Both hashes match the runs row's `audit_start_hash` and
`audit_end_hash` byte-for-byte. The runs row is the rendering
projection over the canonical audit chain per D94 / D95; the
chain linkage is verified at the persisted layer.

## Citation tables

`docker compose exec -T postgres-tenant-a psql -U tenant_a -d
tenant_a -tAc "SELECT count(*) FROM run_chunk_citations; SELECT
count(*) FROM run_entity_citations;"` returned:

```
0
0
```

Both citation tables empty per S31's skeleton commitment.
Citation population lands at S32 alongside the single-transaction
completion seam per the p9-epic forecast.

## Pre-smoke setup notes

Two pre-existing-substrate gaps surfaced at smoke time, both
absorbed:

1. **Tenant registry empty after recent contract-test fixture
   leak (S30b carryover).** The earlier-this-session
   `tests/contract/tenant_isolation/test_run_history_isolation.py`
   layer-2 behavioural tests provisioned synthetic per-tenant
   databases on the loopback control-plane Postgres and dropped
   them on teardown; the `tenant_registry` table on the
   control-plane was untouched by the test (the test does not
   register tenants), but the dev `tenant_registry` rows from
   `make seed-tenants` had been wiped at some prior point in
   the session — likely the `tests/contract/tenant_isolation/`
   suite as a whole at some earlier moment. Resolution: `make
   seed-tenants` re-registered both test-set tenants
   (`00000000-0000-4000-8000-00000000a001` Tenant A,
   `00000000-0000-4000-8000-00000000b002` Tenant B) in one
   command. The S30b methodology-fixture-leak captures entry
   pattern continues to be the right shape; the dev workflow
   absorbs the operator step of `make seed-tenants` after any
   contract-test run.

2. **Image rebuild required for commits 5 + 6 to land in the
   running container.** Commit 4 rebuilt the image with the
   migration files; commits 5 and 6 added the
   AgentRuntimeComposition.run_history_writer field and the
   invoke_agent writer call, but the running container still
   had the commit-4 image, so the first smoke attempt produced
   a clean SSE response with no runs row written (the runtime
   composition lacked the writer field; the invoke_agent inside
   the container was the pre-commit-6 version). Resolution:
   `docker build -f apps/api/Dockerfile -t padhanam-api:dev .`
   plus `compose.yaml` digest pin advance to
   `sha256:838e3ec9...` plus `docker compose up -d
   --force-recreate --no-deps padhanam-api`. The second smoke
   attempt produced the runs row above. The structural lesson:
   image rebuild is required between any commit that touches
   runtime code (executor, use cases, wiring) and the next
   live-stack smoke. The Phase 2 cleanup carryover for an
   automated rebuild + recreate target (the brief's missing
   `make build-api`) would absorb this.

## Acceptance criteria satisfied

- One new runs row in `tenant_a` per the smoke invocation: ✓.
- `audit_start_hash` and `audit_end_hash` match the SSE
  terminal event's `audit_chain_hashes`: ✓ (byte-for-byte
  match against the audit chain).
- `termination_reason='content'` matches the streamed terminal
  event class: ✓.
- `run_chunk_citations` and `run_entity_citations` empty: ✓
  per S31 skeleton commitment.
- Image rebuilt and pinned: ✓
  (`sha256:838e3ec94e2b0cb9867ec77234d0540d3c4b59c27d0b2c88d068473710d8b46f`).
