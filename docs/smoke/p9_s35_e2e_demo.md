# P9 S35 — End-to-end demo against tenant_a closing P9

**Date:** 2026-05-14
**Mode:** smoke (live stack, real LLM via Ollama qwen2.5:7b)

This document records the end-to-end demonstration of the full P9
path closing the run-history substrate. The demo exercises agent
invocation through the SSE endpoint at `apps/api/routers/agent.py`;
run completion writing a record plus citation tables to the per-
tenant Postgres tables via the S31/S32 substrate; HTTP routes from
S34 retrieving the rendered surface; audit chain hashes on the run
record matching the audit chain entries byte-for-byte. The bet-proof
artefact for Phase 1 substrate-completeness per D92 is the
verification recorded below: the substrate executes end-to-end with
no manual intervention beyond the trigger command.

## Pre-demo state recovery

Two recurring pre-session surface-ups absorbed before the trigger
fired.

**Tenant registry recovery.** The control-plane `tenant_registry`
was empty at session open. Same wipe class S30b and S31 surfaced.
Recovered via `make seed-tenants`:

```
$ make seed-tenants
docker compose --env-file .env --env-file .env.derived exec padhanam-api python -m ops.seed_tenants
2026-05-14 08:58:38,665 ops.seed_tenants INFO registered 00000000-0000-4000-8000-00000000a001 (Tenant A)
2026-05-14 08:58:38,669 ops.seed_tenants INFO registered 00000000-0000-4000-8000-00000000b002 (Tenant B)
```

**Agent seeding for retrieval-enabled invocation.** The two existing
agents on tenant_a (`Flowstate ProblemFramer S30b demo` v1/v2) ship
with empty `tool_allowlist=[]` per the P8→P9 carryover on migration-
seeded roles. A fresh agent template was authored via
`agent create-from-role` against the `ProblemFramer` role
(`60976ffc-7f03-4a34-8e78-0f37222f7490` v1), then revision 2 added
via `agent update` with `tool_allowlist: [retrieval]`:

```
$ docker compose exec padhanam-api python -m apps.cli.main \
    agent create-from-role --tenant a --config /tmp/p9_s35_demo_create_from_role.yaml
created agent_template_id=5a6b54b5-476a-4ca1-b333-e4e8462e7382 ...

$ docker compose exec padhanam-api python -m apps.cli.main \
    agent update 5a6b54b5-476a-4ca1-b333-e4e8462e7382 --tenant a --config /tmp/p9_s35_demo_revision.yaml
created revision_id=6b436b5f-e354-49f0-baa9-ba9194e2af43 version=2
```

The `create-from-role` path avoids methodology lineage on the new
agent, sidestepping the S30b methodology-row wipe class that
otherwise causes the methodology_overrides_lookup to fail at
invocation time (an existing agent with methodology lineage whose
methodology row has been wiped cannot be invoked). The fresh agent
has only role lineage; the methodology_overrides_lookup skips
cleanly per the use case's branching at
`contexts/agent/application/use_cases.py:819`.

## Demo trigger

```
$ docker compose exec padhanam-api python -m apps.cli.main \
    agent run --tenant a \
    --agent 5a6b54b5-476a-4ca1-b333-e4e8462e7382 \
    --input "Frame the problem of high customer churn for our SaaS product."
```

Single command, no manual intervention beyond the trigger. The CLI
constructs a dev token carrying the resolved tenant UUID and the
`agent.invoke` role, opens an SSE stream against
`POST /agents/{agent_id}/invoke`, parses the D90 event vocabulary,
renders each event to stdout, and exits with the code mapped from
the terminal event.

## Captured SSE event stream

```
[invocation] agent=5a6b54b5-476a-4ca1-b333-e4e8462e7382 tenant=00000000-0000-4000-8000-00000000a001 model=qwen2.5:7b
[input] Frame the problem of high customer churn for our SaaS product.

[iteration 1]
  generating... (message_count=2)
**Sharpened Problem Statement:**

- **Scope:** The issue is centered around reducing customer churn rates for our SaaS product. This includes both identifying why customers are leaving and implementing strategies to retain them.

- **Context:** Our SaaS product is a project management tool designed for teams in various industries, ranging from small startups to large enterprises. Over the past quarter, we have observed an increase in customer churn, which impacts our revenue growth and company reputation.

- **Complication:** The high churn rate stems from multiple factors such as difficulty in onboarding new users, insufficient support responsiveness, lack of clear value proposition, competing product offerings with better features or pricing, and inconsistent user experience.

- **Success Criteria:** Success will be measured by a reduction in customer churn rate over the next six months. Key performance indicators include:
  - A 15% decrease in monthly cancellations.
  - An increase in positive customer feedback on support responsiveness and product features.
  - Improved user satisfaction scores based on surveys and direct feedback from current users.

This sharpened problem statement can now be broken down into more specific issues for further analysis.
[iteration 1 done] signal=content duration_ms=57826 cost_usd=0.000000

[invocation done] termination_reason=content iterations=1 total_cost_usd=0.000000 duration_ms=57861
```

Event vocabulary observed across the trigger: `InvocationStarted`,
`IterationStarted`, `ContentDelta` (streamed), `IterationCompleted`,
`InvocationCompleted`. Five of the eleven D90 event types fired on
this code path; the remaining six (`ToolCallProposed`,
`ToolCallStarted`, `ToolCallCompleted`, `ToolCallSkipped`,
`InvariantBlocked`, `InvocationFailed`) are not exercised on this
trigger because the model chose not to invoke the retrieval tool
(see "Phase 1 retrieval-not-exercised" note at the end). Total
demo duration: ~58 seconds.

## Postgres verification on tenant_a

### runs row

```
$ docker compose exec postgres-tenant-a psql -U tenant_a -d tenant_a -c \
    "SELECT id, started_at, termination_reason, agent_template_version, total_cost_usd, trace_id, audit_start_hash, audit_end_hash FROM runs WHERE agent_template_id = '5a6b54b5-476a-4ca1-b333-e4e8462e7382';"

                  id                  |          started_at           | termination_reason | agent_template_version | total_cost_usd | trace_id |                         audit_start_hash                         |                          audit_end_hash
--------------------------------------+-------------------------------+--------------------+------------------------+----------------+----------+------------------------------------------------------------------+------------------------------------------------------------------
 5226925f-bd76-47c2-8c9b-fdb4b370e3ab | 2026-05-14 09:02:56.182889+00 | content            |                      2 |       0.000000 |          | f0b4fb23af7e54735729fdbf8d0a8bb2cfd997d6bcf518e981fa3d21d141c63e | e11e82a419d0704b8fb139987e5f6d74c8798857544439d6462a157e354c1672
(1 row)
```

The runs row landed with:

- `termination_reason='content'` matching the SSE stream's terminal event.
- `agent_template_version=2` matching the seeded retrieval-enabled revision.
- `total_cost_usd=0` — Ollama is free at the API boundary; the cost-capture path's zero behaviour holds.
- `audit_start_hash` and `audit_end_hash` populated and 64 chars each.
- `trace_id=NULL` — see "Trace correlation gap" note at the end.

### Citation tables

```
$ docker compose exec postgres-tenant-a psql -U tenant_a -d tenant_a -c \
    "SELECT count(*) AS chunk_citations FROM run_chunk_citations WHERE run_id = '5226925f-bd76-47c2-8c9b-fdb4b370e3ab';"
 chunk_citations
-----------------
               0

$ docker compose exec postgres-tenant-a psql -U tenant_a -d tenant_a -c \
    "SELECT count(*) AS entity_citations FROM run_entity_citations WHERE run_id = '5226925f-bd76-47c2-8c9b-fdb4b370e3ab';"
 entity_citations
------------------
                0
```

Zero citation rows for the demo run. This is consistent with the
SSE stream observation: the model did not invoke the retrieval tool
during the iteration despite having `retrieval` in the
`tool_allowlist`. The citation surface was already verified end-to-
end at S32 commit 11 when a model-invoked retrieval call wrote
citations to both tables; S35's demo verifies the same substrate
path executes when no retrieval invocations occur (zero-citation
case). Both branches of the citation surface (zero and non-zero) are
substrate-verified.

## Audit chain integrity verification

The runs row's `audit_start_hash` and `audit_end_hash` are the join
keys to `tenant_audit`. Byte-for-byte equality:

```
$ docker compose exec postgres-tenant-a psql -U tenant_a -d tenant_a -c \
    "SELECT timestamp, action_verb, resource_type, previous_event_hash, this_event_hash FROM tenant_audit WHERE this_event_hash IN ('f0b4fb23af7e54735729fdbf8d0a8bb2cfd997d6bcf518e981fa3d21d141c63e', 'e11e82a419d0704b8fb139987e5f6d74c8798857544439d6462a157e354c1672') ORDER BY timestamp;"

           timestamp           |    action_verb     | resource_type  |                       previous_event_hash                        |                         this_event_hash
-------------------------------+--------------------+----------------+------------------------------------------------------------------+------------------------------------------------------------------
 2026-05-14 09:02:56.184699+00 | agent.invoke.start | agent_template | 5663b22a14ea8f5c15002b88cad4c27c8d4a9790bf1550210798638ab158e8b2 | f0b4fb23af7e54735729fdbf8d0a8bb2cfd997d6bcf518e981fa3d21d141c63e
 2026-05-14 09:03:54.034263+00 | agent.invoke.end   | agent_template | f0b4fb23af7e54735729fdbf8d0a8bb2cfd997d6bcf518e981fa3d21d141c63e | e11e82a419d0704b8fb139987e5f6d74c8798857544439d6462a157e354c1672
(2 rows)
```

Verification claims, all holding byte-for-byte:

1. `runs.audit_start_hash = tenant_audit.this_event_hash[where action_verb='agent.invoke.start']`
   → `f0b4fb23af7e54735729fdbf8d0a8bb2cfd997d6bcf518e981fa3d21d141c63e`
2. `runs.audit_end_hash = tenant_audit.this_event_hash[where action_verb='agent.invoke.end']`
   → `e11e82a419d0704b8fb139987e5f6d74c8798857544439d6462a157e354c1672`
3. `tenant_audit.previous_event_hash[end] = tenant_audit.this_event_hash[start]`
   → both rows agree on `f0b4fb23af7e54735729fdbf8d0a8bb2cfd997d6bcf518e981fa3d21d141c63e`

This is D95's audit-chain-partial-state shape executing end-to-end
across a real invocation for the first time. The audit chain is
tamper-evident: any modification of the start or end audit event
would break the hash chain; any modification of the runs row's
audit_*_hash columns would break the join to the chain. Both
properties hold under the verification above.

## HTTP read surface verification

### GET /runs/{run_id}

```
$ TOKEN=$(docker compose exec padhanam-api python -c "from padhanam.security.auth import issue_dev_token; print(issue_dev_token(subject='cli-operator', tenant_id='00000000-0000-4000-8000-00000000a001', roles=['agent.invoke']))")

$ docker compose exec padhanam-api python -c "
import httpx, json
r = httpx.get('http://localhost:8000/runs/5226925f-bd76-47c2-8c9b-fdb4b370e3ab',
              headers={'Authorization': f'Bearer {TOKEN}'}, timeout=10)
print('status:', r.status_code)
print('x-correlation-id:', r.headers.get('x-correlation-id'))
print(json.dumps(r.json(), indent=2)[:1500])
"

status: 200
x-correlation-id: ef991eb0-62b9-4ef6-98c8-1f5006bd270d
{
  "id": "5226925f-bd76-47c2-8c9b-fdb4b370e3ab",
  "tenant_id": "00000000-0000-4000-8000-00000000a001",
  "jurisdiction": "eu-west",
  "agent_template_id": "5a6b54b5-476a-4ca1-b333-e4e8462e7382",
  "agent_template_version": 2,
  "input_message": "Frame the problem of high customer churn for our SaaS product.",
  "output_content": "**Sharpened Problem Statement:**\n\n- **Scope:** The issue is centered around reducing customer churn rates for our SaaS product. This includes both identifying why customers are leaving and implementing strategies to retain them.\n  \n- **Context:** Our SaaS product is a project management tool designed for teams in various industries, ranging from small startups to large enterprises. Over the past quarter, we have observed an increase in customer churn, which impacts our revenue growth and company reputation.\n
  ...
}
```

The HTTP layer renders the same run + citations the Postgres query
produces. The Pydantic DTO's 1:1 mirror of the `RunRecord` domain
type (per D98) absorbs every field cleanly: UUID, datetime in ISO
8601, Decimal as string, nullable trace_id, citations as JSON arrays
(empty in this demo per the model-behavior observation above). The
`X-Correlation-Id` header is populated by the
`CorrelationIdMiddleware` per S34 commit 5.

### GET /runs?termination_reasons=content&page_size=10

```
$ docker compose exec padhanam-api python -c "
import httpx, json
r = httpx.get('http://localhost:8000/runs?termination_reasons=content&page_size=10',
              headers={'Authorization': f'Bearer {TOKEN}'}, timeout=10)
print('status:', r.status_code)
print('x-correlation-id:', r.headers.get('x-correlation-id'))
body = r.json()
print('runs returned:', len(body['runs']))
for run in body['runs']:
    print(f\"  - id={run['id']} agent_template_version={run['agent_template_version']} started_at={run['started_at']}\")
print('next_cursor:', body.get('next_cursor'))
"

status: 200
x-correlation-id: d0b4368e-ee77-4568-9ab9-ee14757d7e82
runs returned: 4
  - id=86f1f247-3e9c-4e97-9b97-7edcd252fd78 agent_template_version=2 started_at=2026-05-14T09:04:53.499454Z
  - id=5226925f-bd76-47c2-8c9b-fdb4b370e3ab agent_template_version=2 started_at=2026-05-14T09:02:56.182889Z
  - id=2e86d393-96b8-4aca-a12f-ac09d7e35355 agent_template_version=1 started_at=2026-05-13T23:00:00Z
  - id=aedbefba-ea30-49fd-bf2e-435e9a4d2375 agent_template_version=1 started_at=2026-05-13T19:42:18.793247Z
```

Four runs returned (two from the S35 demo agent + two from earlier
S31/S33 smokes), sorted DESC on `started_at` per D97. The four-
filter vocabulary (`termination_reasons=content`) parses through
`apps/api/routers/_run_history_query.py` per S34 commit 3 and
filters at the reader layer. `next_cursor=None` because all four
runs fit on a single page at `page_size=10`. The cursor codec's
opacity from S33 is preserved at the HTTP boundary; the sentinel-
cursor mechanism for the initial page from S34 fires cleanly when
no `cursor=` query param is supplied.

## Phase 1 limitations recorded (consistent with prior smokes)

**Retrieval-not-exercised, model-behavior.** The seeded agent has
`tool_allowlist=[retrieval]` and an explicit prompt to use
retrieval (system prompt), but qwen2.5:7b chose not to invoke the
retrieval tool on either of the two demo invocations attempted. A
second invocation with the user input "Use the retrieval tool to
find context about customer churn from our indexed sources, then
frame the problem of high customer churn." also produced
`termination_reason='content'` with zero retrieval invocations. This
is consistent with the S30b session log's documented Phase 1
retrieval-not-exercised limitation; the substrate path through
citation linking was already verified at S32 commit 11 when the
model did invoke retrieval, so both branches (zero and non-zero
citations) are substrate-verified across the cumulative P9 smokes.
The limitation is model-behaviour at the runtime-tooling boundary,
not substrate gap; it is the same kind of carryover that motivates
the per-invocation retrieval-constraint threading deferred entry
from the P8→P9 carryover list at `charter/current-package.md`.

**Trace-id propagation gap.** The runs row's `trace_id` column is
NULL on both demo invocations despite Langfuse-web returning 200 OK
on the public health endpoint
(`http://langfuse-web:3000/api/public/health` reports
`{"status":"OK","version":"3.172.0"}`). The optional cross-store
correlation step from the brief's reconciliation surface 5 cannot
be exercised because there is no join key on the runs row. The
trace-id capture path on the agent runtime goes through OTel; the
gap is likely that the trace context is not threaded through to the
run-record accumulator when the SSE handler initialises the
runtime. This is structural — different from the retrieval gap
above — and worth surfacing as a Phase 1 substrate-completeness
finding for the Phase 1 close audit. Activation trigger for repair:
when Phase 2 UX surfaces an operational requirement for trace-deep-
dive linkage from the run record. Substrate complete at column +
read-port level; capture path needs revisit.

## Outcome

The P9 substrate executed end-to-end. Run record written through
the S31 path; citation tables exercised structurally with zero rows
matching the observed event stream; audit chain hashes link
byte-for-byte between the runs row and `tenant_audit`; HTTP routes
from S34 surface the rendered shape with correlation-id and JWT
auth; the four-filter vocabulary + cursor pagination from S33+S34
materialise correctly at the HTTP boundary.

The bet's substrate-completeness claim per D92 is exercised in
product form: every consumer surface Phase 2 UX needs for run-
history is in place and verifiable end-to-end through a single
trigger command against tenant_a's data plane.
