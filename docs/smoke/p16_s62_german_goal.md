# S62 smoke — German as the first progressive-cadence goal (D163)

Operator-gated live verification. The build environment cannot reach Docker,
Postgres, or Neo4j (the procedural-then-executed precedent, S45/S55a/S58/S60).
Stages 1–2 are operator setup; stage 3 is the browser verification that is the
success criterion for the UI surface (CLAUDE.md: browser interactive
verification, not CLI smoke).

## Stage 0 — preconditions

- `make up` with the personal-tenant Postgres + Neo4j healthy.
- `make dogfood-provision` has run (personal tenant registered + migrated).
- A dev token for the personal tenant: `make dogfood-token`.

## Stage 1 — apply the graph migration + seed German

```
make migrate           # applies migrations/neo4j/0002_outcome_goal.cypher (phase 3)
make seed-german       # ops.seed_german_goal inside the api container
```

Expected log lines from `seed-german`:

- `seeded German-practice commitment 00000000-0000-4000-8000-000000620c01`
  (or `... already present, reusing as lever` on a re-run — idempotent).
- `seeded Outcome 00000000-0000-4000-8000-0000006200a1 (German, progressive)
  with lever edge ... current target B1 on ladder A1/A2/B1/B2/C1/C2`.

Re-run `make seed-german` once — it must be a no-op on the commitment and a MERGE
in place on the graph (idempotency).

## Stage 2 — confirm the graph shape (optional, via `make neo4j-shell`)

```cypher
MATCH (l:Lever)-[r:LEVER_FOR]->(o:Outcome {name:'German'})
RETURN o.tenant_id, o.control, o.subject, r.mode, r.ladder, r.current_target_level;
```

Expect: `tenant_id` = the personal tenant, `control='self'`, `subject='self'`,
`mode='progressive'`, `ladder=['A1','A2','B1','B2','C1','C2']`,
`current_target_level='B1'`. Every node + edge carries `tenant_id` +
`jurisdiction` (D12/D63).

## Stage 3 — browser verification (the success criterion)

1. Open `/app`, paste the dev token, land on Today.
2. Under **Goals**, the German card shows:
   - **target: B1** (the current target);
   - **Progress —** the lever line drawn from the German-practice commitment
     (cadence on/behind + last observation);
   - **Gap —** the qualitative gap between target and progress;
   - **Recommendation:** `↑ Raise` or `→ Hold` with a reason.
3. Drive the loop:
   - Mark the German-practice commitment done (Today list), then record an
     observed outcome of **met** on it. Reload Goals — the recommendation should
     become **↑ Raise** with a "Raise target to B2" button.
   - Click **Raise target to B2**. The card's target becomes **B2** and the
     button updates. Confirm the target did **not** change without the click
     (no auto-raise) — this is the D9 recommendation-shaped / no-auto-modify
     invariant.
   - Let the lever go quiet (no completion) or record a **partial** observation —
     the recommendation returns to **→ Hold**.
4. Tenant isolation: a token for tenant_b shows **no** German goal.

## Notes

- The goal is a graph node; the lever reuses the Postgres `commitments` row —
  no Alembic migration this slice (D163 Step 0 F5).
- Only the progressive shape is read/wired. Homeostatic, sequence, influence,
  avoidance, balance, and the exploratory phase are schema-present and
  uninstanced (AC9).
