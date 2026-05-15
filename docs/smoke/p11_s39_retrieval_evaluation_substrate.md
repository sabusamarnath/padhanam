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

## Executed-state evidence (2026-05-15 12:45 UTC)

Image: `padhanam-api:dev@sha256:fcb4b71942999ab159523771281a3ebd10e7612cac960575b313ec31d3792d1a`.
Rebuilt at smoke time to bake in the S39 commits (the pre-S39 image at
`6479c9d0` predated all S39 work). Compose digest pin updated in
`compose.yaml`.

### Migration name length correction at smoke time

Initial `make migrate` failed with
`StringDataRightTruncation: value too long for type character varying(32)`
on the `alembic_version` UPDATE. Both new migrations carried revision
strings longer than the 32-char column ceiling:

- `0012_role_allowlist_retrieval_closure` (37 chars)
- `0013_retrieval_evaluation_substrate` (35 chars)

Shortened to `0012_role_allowlist_retrieval` (29 chars) and
`0013_retrieval_eval_substrate` (29 chars) in-place at the migration
files. The transactional DDL rolled back the failed upgrade cleanly,
so no partial state. Image rebuilt; re-run succeeded.

### Stage 1 — Allowlist closure (executed)

`make migrate` post-fix:
```
INFO  [alembic.runtime.migration] Running upgrade 0011_tenant_actor_provenance -> 0012_role_allowlist_retrieval
INFO  [alembic.runtime.migration] Running upgrade 0012_revise_citation_snapshots -> 0013_retrieval_eval_substrate
INFO  [ops.migrate] phase 2: tenant 00000000-0000-4000-8000-00000000a001 migrated
INFO  [ops.migrate] phase 2: tenant 00000000-0000-4000-8000-00000000b002 migrated
```

Allowlist verification post-migration — **seven McKinsey roles carry the
retrieval reference; LVTGuide is absent from the DB**:

```
Analyst       | [{"tool_id": "00000000-0000-0000-0000-000000000001", "revision_id": "00000000-0000-0000-0000-000000000002"}]
Communicator  | [{"tool_id": "00000000-0000-0000-0000-000000000001", "revision_id": "00000000-0000-0000-0000-000000000002"}]
Disaggregator | [{"tool_id": "00000000-0000-0000-0000-000000000001", "revision_id": "00000000-0000-0000-0000-000000000002"}]
Planner       | [{"tool_id": "00000000-0000-0000-0000-000000000001", "revision_id": "00000000-0000-0000-0000-000000000002"}]
Prioritiser   | [{"tool_id": "00000000-0000-0000-0000-000000000001", "revision_id": "00000000-0000-0000-0000-000000000002"}]
ProblemFramer | [{"tool_id": "00000000-0000-0000-0000-000000000001", "revision_id": "00000000-0000-0000-0000-000000000002"}]
Synthesiser  | [{"tool_id": "00000000-0000-0000-0000-000000000001", "revision_id": "00000000-0000-0000-0000-000000000002"}]
```

LVTGuide absence is the S30b carryover state: the role was wiped by the
test-fixture leak named in `log/captures.md` (2026-05-13 entry) and was
re-seeded via CLI authoring at S30b close on a different DB instance or
was wiped again later. Migration 0012's `WHERE t.name = ANY(:names)`
filter handles the absence gracefully (the SELECT just returns no row
for LVTGuide; idempotent). When LVTGuide is re-seeded into this DB,
re-running migration 0012 idempotently picks it up. Operator note for
the P12 audit: LVTGuide re-seed flow should run migration 0012 or the
CLI authoring should set `tool_allowlist` to the retrieval pin at
authoring time.

Chain integrity verification on the seven updated roles:

```
Planner              stored=22eec192a66c recomputed=22eec192a66c OK
Synthesiser          stored=04f54e975cd4 recomputed=04f54e975cd4 OK
ProblemFramer        stored=a98915cb8bc0 recomputed=a98915cb8bc0 OK
Prioritiser          stored=a7fd0da3b0f6 recomputed=a7fd0da3b0f6 OK
Analyst              stored=e2235a8213cf recomputed=e2235a8213cf OK
Disaggregator        stored=8ff135007d2d recomputed=8ff135007d2d OK
Communicator         stored=046529d3afe7 recomputed=046529d3afe7 OK
broken=0/7
```

D26 chain-self-containment honoured on every updated row.

### Stage 2 — Authoring against tenant_a (executed; discovery-mode synthesised)

**Tenant_a has zero chunks at smoke time** (`SELECT COUNT(*) FROM chunks` →
0). The S25 sources were ingested at the time of S25's smoke but data did
not survive subsequent DB volume rebuilds or test-fixture cycles; this is
the same kind of decay that hit LVTGuide on the control plane. The discovery-
mode CLI path (`gold-set append-entry --query ... --top-k ...`) requires
retrieval candidates and was therefore not exercised end-to-end.

Substrate path (create / append / finalize / hash-chain) exercised via a
direct use-case call with synthetic chunk_ids in lieu of retrieval-surfaced
candidates. This satisfies AC 6, 7, 10 (substrate side), 14 (hash-chain
integrity) and leaves the discovery-mode CLI path verified at the
unit-test level only (the `gold-set append-entry` typer command imports
and constructs cleanly; the retrieval call wasn't fired).

Create:
```
$ docker compose exec -T padhanam-api python -m apps.cli gold-set create \
    --tenant-id a --name "P11 retrieval baseline"
gold_set_id=dd4ec3ee-b65d-4426-b6f1-df8a715a1062
initial_revision_id=eebd5df0-9681-4d21-9bbf-3f9534e49a75
status=draft revision_number=1
```

Three direct-use-case appends with synthetic chunk_ids (`11...1`, `22...2`,
`33...3`, `44...4`):
```
appended entry_index=0 opened_new_draft=False
appended entry_index=1 opened_new_draft=False
appended entry_index=2 opened_new_draft=False
```

### Stage 3 — Finalize (executed)

```
finalized: revision_number=1 this_event_hash=ad94611492299f23b76d7c3eb4602206e88a20223e9ea5983bb0568c43f465a4
           previous_event_hash=0000000000000000000000000000000000000000000000000000000000000000
```

`previous_event_hash` of all zeros confirms `GENESIS_REVISION_HASH` chains
the genesis revision per D109 commitment 4.

### Stage 4 — Hash-chain integrity verification (executed)

Independent recomputation via `compute_revision_hash` from
`contexts/retrieval_evaluation/domain/hash_chain.py` (which delegates to
`padhanam.security.hash_chain.compute_revision_hash` — the D75-promoted
primitive):

```
stored:     ad94611492299f23b76d7c3eb4602206e88a20223e9ea5983bb0568c43f465a4
recomputed: ad94611492299f23b76d7c3eb4602206e88a20223e9ea5983bb0568c43f465a4
match=True
```

D109 commitment 4 verified at revision granularity: stored
`this_event_hash` matches the recomputed value byte-identically.

### Stage 5 — List and get (executed)

```
$ docker compose exec -T padhanam-api python -m apps.cli gold-set list --tenant-id a
dd4ec3ee-b65d-4426-b6f1-df8a715a1062  name='P11 retrieval baseline'  created_at=2026-05-15T11:45:24.462274+00:00  current_revision_id=eebd5df0-9681-4d21-9bbf-3f9534e49a75

$ docker compose exec -T padhanam-api python -m apps.cli gold-set get \
    --tenant-id a --gold-set-id dd4ec3ee-b65d-4426-b6f1-df8a715a1062
id=dd4ec3ee-b65d-4426-b6f1-df8a715a1062
name='P11 retrieval baseline'
jurisdiction=eu-west
created_at=2026-05-15T11:45:24.462274+00:00
current_revision_id=eebd5df0-9681-4d21-9bbf-3f9534e49a75
current revision: number=1 status=finalized finalized_at=2026-05-15T11:48:07.352389+00:00
this_event_hash=ad94611492299f23b76d7c3eb4602206e88a20223e9ea5983bb0568c43f465a4
previous_event_hash=0000000000000000000000000000000000000000000000000000000000000000
entries (3):
  [0] query='what is the cost ceiling for the PM agent'
      expected_chunk_ids=[11111111-1111-1111-1111-111111111111]
  [1] query='which sources cover the LVT methodology framing'
      expected_chunk_ids=[22222222-2222-2222-2222-222222222222, 33333333-3333-3333-3333-333333333333]
  [2] query='what does the bet say about procurement-grade architecture'
      expected_chunk_ids=[44444444-4444-4444-4444-444444444444]
```

### Smoke-evidence carryovers for the P12 audit

1. **LVTGuide re-seed** plus retrieval-allowlist application against this
   DB instance. Migration 0012 picks it up idempotently when the row exists.
2. **Tenant_a corpus re-ingestion**, so the discovery-mode CLI path
   (`gold-set append-entry --query`) can be exercised end-to-end against
   real retrieval candidates rather than synthesised chunk_ids. The CLI
   command itself works (imports + typer wiring verified at unit-test
   level); only the `PgVectorSearch` leg is unrun.
3. **Image digest pin** at `compose.yaml` updated to
   `fcb4b71942999ab159523771281a3ebd10e7612cac960575b313ec31d3792d1a`
   at smoke time. Commit alongside this evidence.
4. **Migration name length convention**: revision strings must stay ≤32
   chars to fit the `alembic_version.version_num` column. The existing
   migrations all comply; future migrations should keep this in mind.
   Worth a one-line note in `charter/principles.md` Token discipline
   section or as a project-convention capture in `log/captures.md`.
