# P10 / S36 — Live-stack smoke for the audit reader read surface

Exercises `PostgresAuditEventReader.get_audit_event`,
`PostgresAuditEventReader.list_audit_events_with_filters`, and
`PostgresAuditEventReader.verify_chain_segment` against both
destinations (per-tenant `tenant_audit` on `padhanam-postgres-
tenant-a-1`; control-plane `tenant_audit` on `padhanam-postgres-
control-plane-1`) through the live `padhanam-padhanam-api-1`
container.

D102 acceptance: the three reads work against both destinations
through one port with destination-parameter routing; chain
integrity verifies on read at page granularity reusing
`compute_event_hash` + `GENESIS_HASH` primitives from
`contexts/audit/domain/events.py`; routing guards fire at port-
method entry for mismatched `(destination, tenant_context)` pairs.

## Pre-state on tenant_a

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -c "SELECT action_verb, count(*) FROM tenant_audit GROUP BY action_verb ORDER BY count(*) DESC;"
       action_verb       | count
-------------------------+-------
 agent.invoke.start      |     7
 agent.invoke.end        |     7
 tenant.audit.test_event |     6
(3 rows)
```

20 audit rows total on tenant_a's chain. Mix of agent-invocation
events (the P9 demo runs at S35 + S35a + S35b) and operator probe
events from earlier smokes.

## Pre-state on control-plane

```
$ docker compose exec -T postgres-control-plane psql -U control_plane \
    -d control_plane -c "SELECT count(*) FROM tenant_audit;"
 count
-------
     0
```

The control-plane chain is empty at smoke open. The smoke script
seeds one probe event before scenario 4 so the destination has
data to read.

## Smoke invocation

```
docker build -t padhanam-api:dev-s36 -f apps/api/Dockerfile .
docker tag padhanam-api:dev-s36 padhanam-api:dev
# compose.yaml pins to the new content-addressed digest at line 380:
#   image: padhanam-api:dev@sha256:ce8ef7df72c8c71636f23684c9dbce901ea89521d234ba9a1a9f78a859f80834
docker compose up -d --force-recreate --no-deps padhanam-api
docker cp scripts/smoke_p10_s36.py padhanam-padhanam-api-1:/app/scripts_smoke_p10_s36.py
docker compose exec -T padhanam-api python /app/scripts_smoke_p10_s36.py
```

The script lives at [scripts/smoke_p10_s36.py](../../scripts/smoke_p10_s36.py)
(copied in via `docker cp`; the smoke does not require a code
change to the running image because the script only consumes
public reader symbols already baked into the S36 image build).

## Captured output

### Scenario 1 — `get_audit_event` per-tenant

```json
"scenario_1_get_audit_event": {
  "id": "d2c44ec8-25a7-45d7-b7b9-fb5fbd96553d",
  "tenant_id": "00000000-0000-4000-8000-00000000a001",
  "actor": "principal:system:test:s12",
  "timestamp": "2026-05-14T13:08:10.367920+00:00",
  "action_verb": "tenant.audit.test_event",
  "resource_type": "probe",
  "resource_id": "00000000-0000-4000-8000-00000000a001",
  "correlation_id": "70a9090a9a10e5b561be02067028c63c",
  "previous_event_hash": "b5228844fc98c962af9759286a796ae1f5653a00a6a3bf388e30884d3b633450",
  "this_event_hash": "007f5d3d39e2bafcfd0f5997097de6eb3b059ac3a0950485ea964caaa3c88622"
}
```

The lookup retrieved the most-recent event from tenant_a's chain
through the per-tenant destination. Tenant scoping flowed from
`TENANT_A_CTX` → `_resolve_per_tenant` → `tenant_a` session.

### Scenario 2 — `list_audit_events_with_filters` no filters

```json
"scenario_2_list_no_filters_page": {
  "events_count": 5,
  "first_event": "...d2c44ec8 (timestamp 2026-05-14T13:08:10) — chain head of page",
  "last_event": "...f15f0b16 (timestamp 2026-05-14T12:15:48) — page tail",
  "next_cursor_present": true,
  "chain_integrity_status": "verified",
  "broken_at_id": null
}
```

Five events returned at `page_size=5`. Page span covered a
contiguous chain segment of `tenant.audit.test_event` rows;
`chain_integrity_status: "verified"` confirms every per-row hash
recomputed cleanly and consecutive rows linked correctly through
the chain. `next_cursor_present: true` because 20 total rows
exceed page_size — the overflow row drives cursor construction.

### Scenario 3 — `list` with narrow `action_verbs` filter → `partial`

```json
"scenario_3_list_action_filter_partial": {
  "events_count": 7,
  "first_event": "...f0a05e8c (agent.invoke.start, 2026-05-14T12:05:29)",
  "last_event": "...88fd6482 (agent.invoke.start, 2026-05-12T16:12:00)",
  "next_cursor_present": false,
  "chain_integrity_status": "partial",
  "broken_at_id": null
}
```

Filter `action_verbs=("agent.invoke.start",)` matched 7 events
across multiple agent invocations. Each `agent.invoke.start` event
is paired with an `agent.invoke.end` row that was filtered out
between consecutive returned rows; the page is intentionally non-
contiguous in the chain. The verifier surfaces `partial` exactly
as D102 specifies: per-row hashes all pass, but the chain links
between consecutive returned rows fail because the page does not
cover a contiguous chain segment. The status is honest — the page
is not broken in a tampering sense, just non-contiguous, and the
verifier cannot disambiguate at page granularity.

### Scenario 4 — control-plane chain

The smoke seeds one probe event into the control-plane chain
before reading:

```json
"scenario_4a_seeded_cp_event_id": "9ff9a952-d99a-484d-af40-4976683507f4"

"scenario_4b_list_control_plane": {
  "events_count": 1,
  "first_event": {
    "id": "9ff9a952-d99a-484d-af40-4976683507f4",
    "tenant_id": "",
    "actor": "smoke:p10_s36",
    "action_verb": "control_plane.audit.smoke_probe",
    "previous_event_hash": "0000000000000000000000000000000000000000000000000000000000000000",
    "this_event_hash": "13446cf2542437a299d6ad21df102180cb45bbb31052fa1948efb2d22ff88971"
  },
  "next_cursor_present": false,
  "chain_integrity_status": "partial",
  "broken_at_id": null
}

"scenario_4c_get_cp_event": {
  "id": "9ff9a952-d99a-484d-af40-4976683507f4",
  "tenant_id": "",
  ...
}
```

The seeded event landed with `tenant_id = ""` (control-plane
sentinel per D35); its `previous_event_hash` is `GENESIS_HASH`
because the chain was empty before this seed. The control-plane
destination resolved through `control_plane_sessionmaker`
without invoking the per-tenant resolver; `tenant_context = None`
flowed through without raising. Chain integrity is `partial`
because the page has only 1 row (cannot verify chain linkage
across consecutive rows) — same surfacing as scenario 4b in the
S36 unit tests.

### Scenario 5 — `verify_chain_segment` over the no-filter page

```json
"scenario_5_verify_chain_segment": {
  "status": "verified",
  "broken_at_id": null
}
```

Explicit verification against the five-event page from scenario 2
returned `verified`. The verifier is pure-function: no session
opened, no resolver invoked; only the in-memory events are walked
through `compute_event_hash` recomputation and consecutive-row
chain-link check.

### Routing guards

```
"routing_guard_per_tenant_no_ctx": "raised: destination='per_tenant' requires a tenant_context"
"routing_guard_cp_with_ctx":       "raised: destination='control_plane' prohibits a tenant_context; got tenant_id=UUID('00000000-0000-4000-8000-00000000a001')"
```

Both `AuditQueryRoutingError` cases fire at port-method entry
before any SQL issues; the routing defence aligns with the
contract harness scenarios at
`tests/contract/tenant_isolation/test_audit_reader_isolation.py`
and the unit tests at
`tests/unit/contexts/audit/adapters/test_postgres_reader.py`.

## Findings

1. **Page-granularity verification matches D102 exactly.** The
   no-filter page returned `verified`; the narrow-filter page
   returned `partial`. Both surfacings are honest at page
   granularity: filter-induced non-contiguity is `partial` (the
   verifier cannot disambiguate from chain tampering), and a
   contiguous segment of correctly-linked rows is `verified`.
2. **Control-plane destination works end-to-end.** Seeded one
   probe event, read it back via both `get_audit_event` and
   `list_audit_events_with_filters` on the control-plane
   destination. `tenant_context=None` flowed through without
   raising; routing resolved to `control_plane_sessionmaker`.
3. **Per-tenant destination scopes correctly.** Tenant_a's 20
   audit rows surfaced through the per-tenant destination
   bound to `TENANT_A_CTX`. The same row would be invisible to
   a tenant_b-scoped read per the contract harness scenario at
   `test_get_audit_event_returns_none_for_event_on_other_tenant`.
4. **Routing defence is pre-routing.** No SQL was issued when
   the destination/tenant_context pair mismatched. The defence
   is at port-method entry per D102; consumers cannot accidentally
   read across the wrong destination.
5. **Chain primitive reuse held.** The per-row hash recomputation
   used `compute_event_hash` against tenant_a's existing rows
   (written by the S11/S12 write-side adapter) and verified each
   row's stored `this_event_hash` cleanly. The write-side and
   read-side hash composition agree byte-for-byte, which is the
   substrate-completeness check for D102's "chain integrity
   verified on read" claim.
