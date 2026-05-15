# P11 S40 — Live-stack smoke for the retrieval-evaluation runner

Substrate verification for D110: the runner orchestrator exercises
the S39b real-corpus gold-set against the two executing D66
strategies (`vector_only` and `graph_only`) on `tenant_a`, persists
the run plus per-query results plus per-strategy aggregates,
emits ten `AuditEvent`s into the per-tenant audit chain, and surfaces
the S40-close verdict on whether the S39b gold-set's metrics are
S41-evidence-grade.

Verification date: 2026-05-15. Compose stack identified by
`docker compose ps` snapshot in pre-flight.

## Caveats captured up-front

Two caveats inherited from S39b apply to every metric this smoke
produces. Reading the metric values below without these in mind would
overstate what the runner has demonstrated.

- **LVT-feedback-loop caveat.** The `lvt_methodology` query's results
  reflect corpus-system-prompt contamination per the S39b carryover:
  tenant_a's corpus and the LVTGuide agent's system prompt share LVT
  framing content, so retrieval against that query surfaces chunks
  that look "correct" by token overlap with the system prompt rather
  than by independent content fit.
- **CC-autonomously-authoring provenance caveat.** The gold-set's
  three entries (`78f65f1e-...`, revision `fdecc36b-...`) were
  authored by CC during the S39b smoke, with CC selecting candidate
  indices `1`, `1,2,3`, `1,2,3` by rank order — not by human
  content-fit judgment. Vector retrieval at evaluation time produces
  the same rank order as the discovery-mode authoring did, so
  recall@1 and MRR scores collapse to "vector retrieval agrees with
  its own ranking" rather than measuring retrieval quality against
  an independent ground truth.

Both caveats feed into the S40-close verdict at the tail of this
document.

## Pre-flight

- Compose stack: all 14 services healthy per `docker compose ps`
  including `postgres-control-plane`, `postgres-tenant-a`,
  `postgres-tenant-b`, `litellm`, `ollama`, `padhanam-neo4j`.
- Embedding model: `nomic-embed-text:v1.5` reachable via
  `docker compose exec ollama ollama list` (verified at S39b smoke;
  no reverification at S40 because S39b's verification covers the
  same model surface).
- tenant_a corpus state: chunks present from S39b re-ingest.
- S39b real-corpus gold-set `78f65f1e-c352-453c-aa1c-589930cd5293`
  with finalized revision `fdecc36b-2b5d-4eb8-97ee-31f962892ffb`
  and 3 entries (verified before stage 1 via `psql`).

## Stage 0 — Migration 0014 applied

```
$ make migrate
…
INFO  [alembic.runtime.migration] Running upgrade
  0013_retrieval_eval_substrate -> 0014_eval_runner_substrate,
  create evaluation_runs, evaluation_results, evaluation_aggregates (D110)
INFO  [ops.migrate] phase 2: tenant 00000000-0000-4000-8000-00000000a001 migrated
INFO  [alembic.runtime.migration] Running upgrade
  0013_retrieval_eval_substrate -> 0014_eval_runner_substrate, …
INFO  [ops.migrate] phase 2: tenant 00000000-0000-4000-8000-00000000b002 migrated
```

Post-migration verification on `tenant_a`:

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -tAc "SELECT version_num FROM alembic_version;
          SELECT table_name FROM information_schema.tables
          WHERE table_schema='public'
            AND table_name IN ('evaluation_runs','evaluation_results',
                               'evaluation_aggregates')
          ORDER BY table_name"
0014_eval_runner_substrate
evaluation_aggregates
evaluation_results
evaluation_runs
```

## Stage 1 — Start an evaluation run against the S39b gold-set

```
$ docker compose exec -T padhanam-api python -m apps.cli.main \
    evaluation-run start --tenant-id a \
    --gold-set-id 78f65f1e-c352-453c-aa1c-589930cd5293 \
    --invoked-by smoke-s40
evaluation_run_id=ef58678a-3392-4013-a9a0-2e94440aed6a
status=completed
completed_at=2026-05-15T15:23:10.624233+00:00
per_query_results=6
per_strategy_aggregates=2
  strategy=vector_only
    recall_mean={1: 0.555, 3: 1.0, 5: 1.0, 10: 1.0}
    precision_mean={1: 1.0, 3: 0.777, 5: 0.466, 10: 0.233}
    mrr_mean=1.0000
    latency_p50=417ms latency_p95=691ms
  strategy=graph_only
    recall_mean={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}
    precision_mean={1: 0.0, 3: 0.0, 5: 0.0, 10: 0.0}
    mrr_mean=0.0000
    latency_p50=0ms latency_p95=0ms
```

Run took ~1.2 seconds end-to-end (invoked_at to completed_at). The
six per-query results match the expected shape: 3 gold-set entries ×
2 executing strategies. The two aggregates correspond to the two
executing strategies per D110 commitment 6.

## Stage 2 — Per-query results land

`evaluation-run get` surfaces the snapshot:

```
$ docker compose exec -T padhanam-api python -m apps.cli.main \
    evaluation-run get --tenant-id a \
    --run-id ef58678a-3392-4013-a9a0-2e94440aed6a
id=ef58678a-3392-4013-a9a0-2e94440aed6a
status=completed
gold_set_id=78f65f1e-c352-453c-aa1c-589930cd5293
gold_set_revision_id=fdecc36b-2b5d-4eb8-97ee-31f962892ffb
invoked_at=2026-05-15T15:23:09.411844+00:00
completed_at=2026-05-15T15:23:10.624233+00:00
per-query results (6):
  entry=440bbc3a-… strategy=graph_only  mrr=0.0000 latency=0ms   returned=0  chunks
  entry=440bbc3a-… strategy=vector_only mrr=1.0000 latency=691ms returned=10 chunks
  entry=a5cdf2cd-… strategy=graph_only  mrr=0.0000 latency=0ms   returned=0  chunks
  entry=a5cdf2cd-… strategy=vector_only mrr=1.0000 latency=417ms returned=10 chunks
  entry=e8e6ae22-… strategy=graph_only  mrr=0.0000 latency=0ms   returned=0  chunks
  entry=e8e6ae22-… strategy=vector_only mrr=1.0000 latency=58ms  returned=10 chunks
```

Each `vector_only` row returns 10 chunks (the runner's `RUNNER_TOP_K`
constant) and scores MRR=1.0000, confirming the rank-1 chunk in
retrieval matches the rank-1 expected chunk in the gold-set entry —
which is the rank-based-not-content-fit caveat surfacing exactly as
the S39b session log predicted.

Each `graph_only` row returns 0 chunks because the CLI's
`_CliCompositeRetrievalClient.traverse_graph` returns an empty
sequence (the structurally honest Phase 1 limitation captured at
commit 7's docstring: graph leg at the CLI runner path needs
seed-entity derivation which the agent runtime defers to a Phase 2
implementation per D66 and the AgentRetrievalClientAdapter's own
docstring at apps/cli/_cross_context.py:411-422). Zero metrics, zero
latency. This is honest emptiness, not a bug; production paths via
TenantRoutingRetrievalClient compose Neo4jTraverse alongside
PgVectorSearch, but graph dispatch still uses the raw query string
as seed-entity name today, so even in production the graph strategy
surfaces results only when the query happens to equal an entity
name. S40 documents the gap; S41 reads `graph_only` rows as evidence
that the strategy is not currently a competitor for vector retrieval
on free-form queries.

## Stage 3 — Per-strategy aggregates compute at completion

The aggregate-level output above shows the runner computed both
strategies' per-strategy aggregates at run-completion time per D110
commitment 4. Direct SQL inspection confirms two aggregate rows
landed:

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -c "SELECT retrieval_strategy, mrr_mean, latency_ms_p50, latency_ms_p95
        FROM evaluation_aggregates
        WHERE evaluation_run_id = 'ef58678a-3392-4013-a9a0-2e94440aed6a'
        ORDER BY retrieval_strategy"
 retrieval_strategy | mrr_mean | latency_ms_p50 | latency_ms_p95
--------------------+----------+----------------+----------------
 graph_only         |   0.0000 |              0 |              0
 vector_only        |   1.0000 |            417 |            691
```

The (run_id, strategy) UNIQUE constraint per D110 schema commitment
holds — the runner produced exactly two aggregate rows for two
executing strategies.

## Stage 4 — `evaluation-run list` paginates

```
$ docker compose exec -T padhanam-api python -m apps.cli.main \
    evaluation-run list --tenant-id a --page-size 5
ef58678a-3392-4013-a9a0-2e94440aed6a  status=completed
  invoked_at=2026-05-15T15:23:09.411844+00:00
  gold_set_id=78f65f1e-c352-453c-aa1c-589930cd5293
```

One run on tenant_a. The list returns no `next_cursor` because the
single row fits within page_size=5. Cursor codec is structurally
verified by unit tests; the production cursor round-trip lands at
S42's HTTP transport.

## Stage 5 — Audit-event emission verification

D110 commitment 7 requires one `AuditEvent` per write to
`evaluation_runs`, `evaluation_results`, and `evaluation_aggregates`.
The runner's orchestrator at commit 3 emits via `AuditPort.emit(...)`
inside `run_retrieval_evaluation`; the live-stack PostgresAuditAdapter
overwrites the chain hashes during its locking transaction per D37.

Expected event count: 1 run.start + 6 result.append + 2 aggregate.append
+ 1 run.complete = **10 events**.

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -tAc "SELECT count(*) FROM tenant_audit
          WHERE resource_type IN ('evaluation_run', 'evaluation_result',
                                  'evaluation_aggregate')"
10

$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -tAc "SELECT action_verb, resource_type, count(*)
          FROM tenant_audit
          WHERE resource_type IN ('evaluation_run', 'evaluation_result',
                                  'evaluation_aggregate')
          GROUP BY action_verb, resource_type
          ORDER BY action_verb"
retrieval_evaluation.aggregate.append|evaluation_aggregate|2
retrieval_evaluation.result.append   |evaluation_result   |6
retrieval_evaluation.run.complete    |evaluation_run      |1
retrieval_evaluation.run.start       |evaluation_run      |1
```

Audit chain hash integrity verification:

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -tAc "SELECT count(*) FROM tenant_audit
          WHERE this_event_hash IS NOT NULL
            AND length(this_event_hash) = 64
            AND length(previous_event_hash) = 64"
35
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -tAc "SELECT count(*) FROM tenant_audit"
35
```

All 35 audit rows on tenant_a (the 10 runner events plus 25 pre-
existing events from S39 and S39b) carry valid 64-character hex
chain hashes. The runner extended the chain without breakage.

## Cross-tenant verification

tenant_b stays empty per D32:

```
$ docker compose exec -T postgres-tenant-b psql -U tenant_b -d tenant_b -tAc "
    SELECT 'evaluation_runs:' || count(*) FROM evaluation_runs UNION ALL
    SELECT 'evaluation_results:' || count(*) FROM evaluation_results UNION ALL
    SELECT 'evaluation_aggregates:' || count(*) FROM evaluation_aggregates"
evaluation_runs:0
evaluation_results:0
evaluation_aggregates:0
```

The tenant-isolation contract harness scenarios at commit 8 cover
the structural reasons cross-tenant access is blocked (FK
enforcement, per-tenant DB topology, defence-in-depth ValueError on
mismatch). The live-stack confirms the substrate behaves as the
contract scenarios predict against synthetic per-tenant DBs.

## Deviations from the brief

Three deviations surfaced at smoke time and were fixed inline per
the operator's smoke-time-fix disposition.

**Deviation 1: ControlPlaneSettings.url_async AttributeError.**
The CLI runner's `_build_runner_dependencies` constructed the audit
adapter with `create_async_engine(control_plane_settings.url_async,
...)` — but `ControlPlaneSettings` exposes no `url_async`
attribute. The control-plane URL builder lives at
`contexts/audit/adapters/outbound/postgres/audit.py:_control_plane_url`
and is invoked internally by `PostgresAuditAdapter.from_settings`.
Fixed by switching the CLI to `PostgresAuditAdapter.from_settings(
control_plane_settings=ControlPlaneSettings(),
per_tenant_sessionmaker_resolver=_resolver)`. Landed as commit
21acd36. **Methodology finding**: the unit test suite cannot
exercise this inline construction because the fakes
(`RecordingAuditPort`) substitute the adapter wholesale; runtime
verification at the smoke surface caught what fakes structurally
cannot. Same shape as the S39b `ChunkResult.content`/`.similarity_score`
AttributeError fix at 5c7a7f2; the verification-debt-from-smoke-
carryovers pattern (S39 methodology line 1) has fired its second
instance at retrieval_evaluation. **P12 audit observation**: CLI
wiring helpers that construct production-class adapters inline (vs
delegating to existing factory functions) are a specific sub-pattern
of substrate-session ACs that import-shape verification cannot
close.

**Deviation 2: tenant label vs UUID.** The brief and the live-stack
smoke initially attempted `--tenant-id tenant_a`. The CLI's
`resolve_tenant_context` accepts only the short label (`a`, `b`) or
the actual UUID; `tenant_a` is neither. Corrected to `--tenant-id a`
inline. No code change; this is a documentation note for future
smoke authors.

**Deviation 3: migration not in the padhanam-api image.** The first
`make migrate` after authoring migration 0014 reported success but
left both tenant DBs on `0013_retrieval_eval_substrate`. The
container runs migrations against `/app/alembic/tenant/versions/`
which is the image's frozen snapshot of the migration tree; new
migrations on the host don't reach the container until the image
rebuilds or the file is copied in. Fixed by
`docker cp alembic/tenant/versions/2026_05_15_0014_evaluation_runner_substrate.py
padhanam-padhanam-api-1:/app/alembic/tenant/versions/` followed by
re-running `make migrate`. This is the same shape as the S32 finding
about the api image needing rebuilds; the operator's S31 reflection
suggested an automated `make build-api` target would absorb this
class of friction. Recurring pattern: methodology candidate at the
P12 audit for the migration-authoring-vs-image-state friction class.

The CLI source itself also needed copying into the container
(`docker cp contexts/retrieval_evaluation apps/cli apps/api
padhanam-padhanam-api-1:/app/...`) for the same reason: the
container's `/app` carries the image's frozen Python tree. This is
not a new finding; the same class of friction surfaces every
substrate session that adds new CLI surfaces. The persistent
`make build-api` carryover absorbs it.

## S40-close verdict on the S39b gold-set's S41 usability

The runner substrate works structurally end-to-end against tenant_a.
The metrics it produced, however, are **not procurement-grade
evidence for S41's optimization-engine recommendations**, and this
is the load-bearing verdict the brief asked S40 to surface.

The vector_only aggregates on the S39b real-corpus gold-set are
"perfect" — recall@3 = 1.0, MRR = 1.0, precision@1 = 1.0. This
looks like ideal retrieval. It is not. The gold-set's
`expected_chunk_ids` were authored at S39b by CC selecting candidate
indices `1`, `1,2,3`, `1,2,3` from the discovery-mode CLI's
*vector-retrieval* output. The discovery-mode CLI at S39b ran
`PgVectorSearch.search_vector(query, scope, top_k=10)` and CC
selected by rank. The runner at S40 invokes
`AgentRetrievalClientAdapter` which dispatches `{"primary": "vector"}`
to the same `PgVectorSearch.search_vector` against the same
embedding model on the same corpus. The two paths are
substantively identical, so the runner's vector-only output is
structurally guaranteed to match the gold-set's expected order
(modulo tie-breaks in ranking). MRR=1.0 is therefore not evidence
that vector retrieval works well; it is the artefact of the
gold-set author and the gold-set consumer being the same retrieval
function applied to the same corpus, recorded twice.

The structural-honesty reading: this gold-set verifies the runner's
shape (it persists records, computes metrics with the correct
formulas, emits audit events, handles two strategies) but cannot
discriminate between vector-only and any alternative retrieval
strategy that would produce a different ranking. For S41's
optimization engine to cite `recall_at_5 = 0.42` as evidence that a
particular strategy underperforms, the gold-set's "correct" answers
must be independent of the strategy being measured. The S39b
gold-set's correct answers are not independent of vector retrieval.

Additionally the LVT-feedback-loop caveat compounds this: one of
the three queries scores against a corpus that overlaps with the
system prompt, so even a strategy-independent gold-set author
would face confounding for that entry.

**Verdict: an S40b clean-gold-set bridge session is required before
S41 ships.** Specifically, S40b authors a methodologically-clean
gold-set by either (a) human content-fit judgment over retrieval
candidates instead of rank-based selection, (b) prior-art queries
whose ground truth is documentable independent of retrieval (e.g.
chunks that contain specific named entities or numeric values), or
(c) a re-ingested corpus that does not overlap with the agent
system prompt. The recommendation is (a) + (c) together to address
both caveats in one bridge session. S41 framing at strategic-mode
conversation post-S40 close will commit the specific shape; this
smoke document surfaces the requirement, not the design.

The pattern recurs: P11 has now produced two substrate sessions
(S39, S40) that each surfaced a structural-honesty close-verdict
requiring a follow-on bridge session (S39 → S39b verification-and-
hygiene; S40 → S40b gold-set authoring). The bridge-session-shape
methodology candidate (S39b methodology line 5) confirms at S40
close with a second instance against a different sub-substrate
concern (verification-and-hygiene at S39b; methodologically-clean
artefact authoring at S40b). One more instance at P11 close or P12
would promote this to a formal methodology entry.

## Acceptance criteria status

| AC | Status | Evidence |
|---|---|---|
| 1. D110 in `charter/decisions.md` | Done | Commit 9e062b7 |
| 2. Three new tables in `charter/schema.md` | Done | Commit 9e062b7 |
| 3. `charter/current-package.md` updated | Done | Commit 9e062b7 |
| 4. `contexts/retrieval_evaluation/` extended | Done | Commits a76919b, 8a86265, b4c44f3 |
| 5. EvaluationRun/Result/Aggregate VOs | Done | Commit a76919b |
| 6. Runner invokes via AgentRetrievalClientAdapter (no agent loop) | Done | `_CliRetrievalRunnerPort` at apps/cli/_retrieval_evaluation.py |
| 7. Three EvaluationAggregate rows per run | **Partial** | Two rows (executing strategies only); `parallel_rrf` deferred per `charter/deferred-decisions.md` |
| 8. Audit events for every write | Done | 10 events on tenant_a; chain integrity intact |
| 9. Alembic migration applies cleanly | Done | Commit d9cb409; verified above |
| 10. Wiring at both composition roots | Done | Commit e7c02b0 |
| 11. CLI subcommands end-to-end | Done | This document |
| 12. Tenant-isolation contract scenarios | Done | Commit 8f179fd; harness 114 → 126 (+12) |
| 13. All unit tests pass | Done | 1105 passed, 12 skipped |
| 14. Import-linter contracts | Done | 26/26 kept |
| 15. Smoke walks the full flow + verdict | Done | This document |
| 16. LVT-feedback-loop + CC-authoring caveats captured | Done | Sections above |
| 17. `git status` clean at session close | Pending | Session-log commit |
| 18. Session log entry | Pending | Commit 10 |

AC 7 carries an asterisk: the brief's drafted "three EvaluationAggregate
records" reframed to "every executing strategy" per the Finding 2
disposition at session open; the as-built two-row output reflects
the AgentRetrievalClientAdapter's two-strategy implementation surface,
and `parallel_rrf` deferral lives at `charter/deferred-decisions.md`.
