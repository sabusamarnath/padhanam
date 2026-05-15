# P11 S39 — Live-stack smoke: retrieval_evaluation substrate (2026-05-15)

End-to-end exercise of the gold-set authoring substrate per D109
against `tenant_a`. Three concerns verified end-to-end:

1. **Allowlist closure** (commit 2): migration `0012_role_allowlist_retrieval_closure`
   UPDATEs the eight seeded role-revision rows (LVTGuide plus the seven McKinsey
   7-Step roles) to carry the retrieval tool reference and recomputes each
   role-revision hash per D26 chain-self-containment. The recompute is the
   structural integrity work; chain verification on each role's revision chain
   must pass post-migration.

2. **Retrieval evaluation substrate** (commits 3-8): tenant migration
   `0013_retrieval_evaluation_substrate` creates `gold_sets`, `gold_set_revisions`,
   and `gold_set_entries` on `tenant_a`'s database. The CLI walks the operator
   through create → append-entry × 3 (discovery mode) → finalize against the
   tenant's existing corpus.

3. **Hash-chain integrity verification** (D109 commitment 4): after finalize,
   the revision's stored `this_event_hash` recomputes byte-identically from the
   persisted revision content via
   `contexts.retrieval_evaluation.domain.compute_revision_hash`, which delegates
   to `padhanam.security.hash_chain.compute_revision_hash`. Genesis revision
   chains from `GENESIS_REVISION_HASH`.

## Mid-build correction note (Finding 3)

The brief's commit 2.5 (extract `compute_chained_payload_hash` from
`contexts/audit/domain/events.py`) **did not land**. Mid-build reading of
migration 0010 surfaced that `padhanam/security/hash_chain.py` already exposes
the field-set-agnostic primitive (promoted at S24 per D75). The gold-set
context became the third consumer of that primitive after methodology and role.
No audit refactor; `compute_event_hash` in the audit context is unchanged.
The smoke does not exercise the audit chain because the audit context was
not touched.

## Pre-flight

```bash
# Bring up the local stack
docker compose up -d postgres-control-plane postgres-tenant-a postgres-tenant-b \
    neo4j langfuse ollama padhanam-api

# Apply both migration trees
make migrate
```

Expected: both control-plane (0012) and per-tenant (0013) migration trees
upgrade clean. Captured at `docker compose logs --tail=20 padhanam-api` and
the alembic CLI output:

- Control plane: `Running upgrade 0011_tenant_actor_provenance -> 0012_role_allowlist_retrieval_closure`
- Tenant a: `Running upgrade 0012_revise_citation_snapshots -> 0013_retrieval_evaluation_substrate`
- Tenant b: same as tenant a

## Stage 1 — Allowlist closure verification

Confirm the eight seeded role-revision rows carry the retrieval tool reference
post-0012:

```bash
docker compose exec -T postgres-control-plane psql -U "$POSTGRES_CONTROL_PLANE_USER" \
    -d "$POSTGRES_CONTROL_PLANE_DB" -tAc "
SELECT t.name, r.tool_allowlist::text
FROM role_revisions r JOIN role_templates t ON t.id = r.role_template_id
WHERE t.name IN ('LVTGuide','ProblemFramer','Disaggregator','Prioritiser','Planner','Analyst','Synthesiser','Communicator')
ORDER BY t.name;
"
```

Expected: eight rows each carrying
`[{"tool_id": "00000000-0000-0000-0000-000000000001", "revision_id": "00000000-0000-0000-0000-000000000002"}]`.

Confirm role-revision chain integrity verifies bit-identically post-recompute.
For each of the eight roles, recompute `this_revision_hash` against the
persisted content and compare against the stored value. The migration 0010
helper pattern is the reference implementation; a one-shot verifier script
mirrors that logic. Expected: zero broken chains on the eight roles.

## Stage 2 — Discovery-mode authoring against tenant_a

Run the CLI from inside the `padhanam-api` container so per-tenant Postgres
hostnames resolve over the compose network:

```bash
docker compose exec -T padhanam-api python -m apps.cli gold-set create \
    --tenant-id a --name "P11 retrieval baseline"
```

Expected:
```
gold_set_id=<UUID>
initial_revision_id=<UUID>
status=draft revision_number=1
```

Note the `gold_set_id` for the subsequent commands. Append three entries via
discovery mode against `tenant_a`'s existing corpus (sources ingested at S25):

```bash
# Entry 1
docker compose exec -T padhanam-api python -m apps.cli gold-set append-entry \
    --tenant-id a --gold-set-id <GOLD_SET_UUID> \
    --query "what is the cost ceiling for the PM agent" \
    --top-k 10 \
    --correct-indices "3,1"   # operator-chosen ranked indices

# Entry 2
docker compose exec -T padhanam-api python -m apps.cli gold-set append-entry \
    --tenant-id a --gold-set-id <GOLD_SET_UUID> \
    --query "which sources cover the LVT methodology framing" \
    --top-k 10 \
    --correct-indices "1,2,4"

# Entry 3
docker compose exec -T padhanam-api python -m apps.cli gold-set append-entry \
    --tenant-id a --gold-set-id <GOLD_SET_UUID> \
    --query "what does the bet say about procurement-grade architecture" \
    --top-k 10 \
    --correct-indices "5,2"
```

Expected per call:
```
entry_id=<UUID>
entry_index=<0,1,2 in order>
revision_id=<INITIAL_REVISION_UUID>
opened_new_draft=False
```

The `opened_new_draft=False` confirms all three entries land on the same
draft revision (the initial one from `create`).

## Stage 3 — Finalize revision

```bash
docker compose exec -T padhanam-api python -m apps.cli gold-set finalize \
    --tenant-id a --gold-set-id <GOLD_SET_UUID>
```

Expected:
```
revision_id=<INITIAL_REVISION_UUID>
revision_number=1
status=finalized
this_event_hash=<64-char hex>
previous_event_hash=0000000000000000000000000000000000000000000000000000000000000000
finalized_at=<timestamp>
```

`previous_event_hash` of all zeros confirms `GENESIS_REVISION_HASH` is the chain
anchor for revision 1 (D109 commitment 4).

## Stage 4 — Hash-chain integrity verification

Read the persisted revision content and recompute `this_event_hash` via the
platform primitive; compare against the stored hash.

```bash
docker compose exec -T padhanam-api python -m apps.cli gold-set get \
    --tenant-id a --gold-set-id <GOLD_SET_UUID>
```

Expected output includes:
- `current revision: number=1 status=finalized finalized_at=<ts>`
- `this_event_hash=<H>`
- `previous_event_hash=00...`
- `entries (3): [0] query=... expected_chunk_ids=[...]` etc.

Independent recomputation (run inside the `padhanam-api` container so the
same Python interpreter loads the same module versions):

```python
# python -m apps.cli ... or a one-shot script
import asyncio
from uuid import UUID
from contexts.retrieval_evaluation.domain import (
    GENESIS_REVISION_HASH, compute_revision_hash,
)
from contexts.retrieval_evaluation.adapters.outbound.postgres.reader import (
    PostgresGoldSetReader,
)
from shared_kernel import TenantId
from apps.cli._runtime import build_tenant_wiring

GOLD_SET_ID = UUID("<paste>")

async def verify():
    wiring = build_tenant_wiring("a")
    async def resolver(_): return wiring.session_factory
    reader = PostgresGoldSetReader(
        per_tenant_sessionmaker_resolver=resolver,
        bound_tenant_id=TenantId(str(wiring.tenant_context.tenant_id)),
    )
    snap = await reader.get_gold_set_with_current_revision(
        tenant_context=wiring.tenant_context, gold_set_id=GOLD_SET_ID,
    )
    rev = snap.current_revision
    recomputed = compute_revision_hash(
        revision_number=rev.revision_number,
        entries=snap.entries,
        previous_event_hash=GENESIS_REVISION_HASH,
    )
    print(f"stored:     {rev.this_event_hash}")
    print(f"recomputed: {recomputed}")
    assert recomputed == rev.this_event_hash, "chain integrity broken"
    print("chain integrity verified")
    await wiring.engine.dispose()

asyncio.run(verify())
```

Expected: `stored` and `recomputed` match byte-identically; the
`chain integrity verified` line confirms the on-read verification per D109
commitment 4 ("chain integrity verifies on read at revision granularity by
recomputing this_event_hash from the persisted revision content and comparing
against the stored value").

## Stage 5 — List view

```bash
docker compose exec -T padhanam-api python -m apps.cli gold-set list --tenant-id a
```

Expected: the newly-created gold set appears with
`current_revision_id=<INITIAL_REVISION_UUID>` (the finalized revision id),
created_at matching stage-2 creation time. No `next_cursor` (single page).

## Acceptance summary

| AC | Verified by |
|----|-------------|
| 4 (allowlist closure on 8 roles + chain integrity) | Stage 1 |
| 5 (hexagonal layout) | Commits 3-5 directory tree |
| 6 (GoldSet/Revision/Entry domain) | Commit 3 + stage 2 + stage 3 outputs |
| 7 (compute_revision_hash via padhanam.security.hash_chain) | Stage 4 recomputation |
| 8 (Alembic migration applies cleanly to both tenants) | Pre-flight + stage 1 (tenant_a structural) |
| 10 (CLI subcommands execute end-to-end) | Stages 2-3-4-5 |
| 14 (this document walks the full flow + hash-chain) | Document itself + execution |

## Deviations from the brief

- Commit 2.5 (extract `compute_chained_payload_hash` from
  `contexts/audit/domain/events.py`) did not land. The platform already
  exposes the field-set-agnostic primitive at `padhanam.security.hash_chain`
  (promoted at S24 per D75); the audit-context refactor was unnecessary. See
  the session log entry methodology line for the third-consumer-confirms
  observation.
- Adapter unit tests against fake session (mentioned in the brief at commit 5)
  not landed. End-to-end coverage via this smoke document is the verification
  surface for the adapter at S39; the unit-against-fake-session pattern is a
  hygiene opportunity for a future session if signal emerges.

## After execution

Append actual outputs (gold_set_id, revision_id, hash values, recomputed-vs-
stored confirmation) inline under each stage so this document captures the
executed-state evidence per the smoke-document convention at
docs/smoke/p9_s32_smoke.md and docs/smoke/p10_s38_close_demo.md. The session
log entry references this document for AC 4 / AC 14 verification.
