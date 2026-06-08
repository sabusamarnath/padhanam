# S63 smoke — schema corrections + get-a-job as the second goal (a sequence)

Live verification of the S63 build against the running personal-tenant stack
(Docker reachable this session — the S62 forward-correction lesson rewards live
verification over operator-gating). The api image was rebuilt and the container
recreated before any seed or smoke (the S41/S56a baked-image discipline).

## Procedure (run, this session)

1. `make build-api` — rebuilt the image (new digest pinned in `compose.yaml`).
2. `docker compose up -d --force-recreate padhanam-api` — recreated on the new image.
3. `make migrate` — applied `migrations/neo4j/0003_outcome_props_to_node.cypher`
   (phase 3; 0001/0002 already applied, skipped).
4. `make seed-german` — idempotent re-seed; cleared the synthetic observation.
5. `make seed-get-a-job` — seeded the sequence goal + its lever chain.

## Results (live, 2026-06-08)

**Migration moved German edge→node, in place (AC2, AC3).** Before any re-seed,
querying the graph after `make migrate`:

    German → node mode=progressive, current_target=B1, ladder=[A1..C2];
             edge mode=NULL, current_target=NULL

The edge no longer holds mode/target; the node does; German's target reads B1
identically — no data loss.

**Migration idempotent across two runs (AC11).** A second `make migrate` logged
`0003_outcome_props_to_node already applied, skipping`; German still reads B1 on
the node (the `:_Migration` gate plus the guarded `coalesce` in the cypher).

**get-a-job exists as one sequence Outcome with a lever chain (AC4).** Graph
query:

    mode=sequence, control=other, subject=self,
    terminal="Offer accepted" (pending);
    step 1 "Refresh CV and portfolio" [done]
    step 2 "Apply to target roles"   [blocked]
    step 3 "Interview preparation"    [blocked]

**Tenancy holds on every node and edge (AC8).** Graph audit returned
`bad_nodes=0`, `bad_edges=0` (no Outcome/Lever/LEVER_FOR missing tenant_id or
jurisdiction).

**`GET /goals` reads the shape (AC5, AC6, AC7, AC10).** Personal-tenant token:

    German   | mode=progressive control=self  remedy_kind=raise_or_hold  rec=hold
             | current_target=B1 next=B2; reason: "hold the target — the last
             |   observation hasn't met the current target"  (clean slate — the
             |   synthetic 'met' was cleared, so it correctly holds, AC10)
    Get a job| mode=sequence    control=other remedy_kind=unblock_or_drop rec=unblock
             | terminal "Offer accepted" (pending); active="Apply to target roles"
             | chain: 1.done  2.blocked<ACTIVE>  3.blocked
             | reason: "'Apply to target roles' is blocked — unblock it (clear
             |   what is stalling it), or drop the step if it is no longer needed"

German exposes raise-or-hold and never unblock-or-drop; get-a-job exposes
unblock-or-drop and never raise-or-hold (AC6). control influence is recorded as
`other` with no influence-specific logic (AC7).

**Tenant isolation (AC8).** `GET /goals` with a tenant_b token returned 0 goals.

## Operator-gated: the browser click-through

This build environment has no browser binary (no chromium/playwright), so the
literal interactive click-through is the operator's final confirmation. The data
path is fully live-verified above; `GET /app` serves 200 and the page carries
the chain-rendering code (`chainCard`, `stepGlyph`, the `remedy_kind` branch).

Operator step: open `http://localhost:8000/app`, sign in, and confirm in the
Goals panel that **German** shows a target + raise-or-hold (no chain), and
**Get a job** shows the three-step chain (✓ done, ⚠ active-blocked, ⋯ blocked),
the "Offer accepted (pending)" terminal, and an "⚠ Unblock or drop" recommendation
with **no Raise button**.
