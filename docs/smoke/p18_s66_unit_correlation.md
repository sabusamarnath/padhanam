# S66 smoke — unit-of-work correlation

Live verification of the P18 correlation build against the running stack (Docker
reachable). The api image was rebuilt and recreated before migrate/correlate
(the S41/S56a baked-image discipline; the S62 stale-image lesson).

## Procedure (run, this session)

1. `docker compose build padhanam-api` — rebuilt the image (new digest pinned in
   `compose.yaml`).
2. `docker compose up -d padhanam-api` — recreated on the new image.
3. `python -m ops.migrate_neo4j` — applied `0004_work_unit` (the `:Unit` +
   `:Facet` uniqueness constraints + tenant indexes) to the shared Neo4j.
4. `python -m ops.correlate_units` — ran the full read-match-write path for the
   personal tenant.

## Results (live, 2026-06-08)

- **Graph schema applied (D168).** `0004_work_unit` applied; `SHOW CONSTRAINTS`
  confirms `unit_unique_per_tenant` and `facet_unique_per_tenant` exist.
- **`GET /units` reads the live graph (AC: unit view).** Personal-tenant token →
  `[]` before correlation, then 979 units after — the route, `UnitGraphAdapter`,
  `Neo4jGraphRepository`, and the `list_units` Cypher all execute against the
  live graph (an absent graph/constraint would error, not return `[]`).
- **The correlate path runs end-to-end (AC: correlated units in the graph).**
  `ops.correlate_units` read the personal tenant's caches (calendar populated;
  tasks/email operator-gated and currently empty), ran the matcher, and replaced
  the tenant's `:Unit`/`:Facet`/`SAME_WORK` subgraph: `correlation complete: 979
  units written`. Re-running is idempotent (derived state; deterministic ids).
- **High-precision: no same-type mega-unit (the live-caught fix).** The first
  correlate run collapsed ~84 recurring calendar instances of one title into a
  single 84-facet unit. The matcher was corrected so a unit binds **at most one
  facet per type**; the re-run shows **max facets per unit = 1**, **0 units with
  a duplicated facet-type**, and **0 cross-tool units** (only calendar is
  ingested for this tenant, so there is nothing of another type to correlate
  against — the cross-tool path is unit-tested and gated on the task/email
  pulls).
- **Tenant isolation (D24/D63).** tenant_b token → `GET /units` returns `[]`
  while the personal tenant returns 979 — the wrapper binds `tenant_id` into
  every predicate.
- **The Units panel serves.** `GET /app` returns 200 and carries the
  "Units of work" panel (`loadUnits`, `id="units"`, the cross-tool copy).

## Operator-gated: the cross-tool correlation against real task/email data

The build env has no Nango `google-tasks`/`google-mail` integration for the
personal tenant, so only the calendar cache is populated — a cross-tool unit
(task ⊕ meeting ⊕ email) cannot form from one source alone. The matcher's
cross-tool inference (a task pairs with its nearest-in-time same-title meeting;
a below-floor match is a candidate) is covered by the unit tests
(`tests/unit/contexts/daily_driver/test_work_unit.py`). The live cross-tool
proof is the operator's step, after the other pulls run:

```
make pull-tasks         # provision google-tasks first (docs/smoke/p17_s65)
# (calendar/email refresh as needed)
make correlate-units    # recompute the unit graph from all caches
# open /app → Units of work → a task and its meeting drawn into one unit
```

Re-running `make correlate-units` after any pull is safe and idempotent: the
graph is derived state, replaced each run, with deterministic unit ids so P19's
goal facet (next package) attaches to a unit that survives a re-run.
