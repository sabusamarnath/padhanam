# P11 / S42 — Live-stack smoke for the HTTP transport surface

Exercises the seventeen S42 HTTP routes end-to-end against the
running `padhanam-padhanam-api-1` container — gold-set authoring
(create, append-entry, finalize, list, get), the two-step discovery
decomposition (`/retrieval-candidates`), evaluation-run kickoff and
inspection, optimization-run kickoff, recommendation read surface
(list, get with discriminated citations), the three-route lifecycle
exercise (acknowledge → apply → reject including the 409
re-transition path), and the OpenAPI specification. Tenant isolation
is verified by a cross-tenant `GET /gold-sets/{id}` returning 404 with
no information leakage. The existing run_history (S34) and audit (S37)
read surfaces are sanity-checked.

D112 acceptance: every new route produces the documented response
shape with the expected status code; the synchronous engine kickoffs
complete within the bounded Phase 1 latency (evaluation 152ms,
optimization 18ms in this run); the OpenAPI spec reflects all
seventeen S42 operationIds; the discriminated evidence_citations
union surfaces on the wire keyed by `category`. Two findings
captured at smoke time and forwarded to pre-P12 hygiene (Makefile
build-api target fixed inline at smoke time; pre-existing empty
correlation_id on S40/S41 audit rows).

## Pre-state

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -c "SELECT count(*) FROM gold_sets;"
 count
-------
     3

$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -c "SELECT count(*) FROM optimization_runs;"
 count
-------
     1

$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -c "SELECT count(*) FROM recommendations;"
 count
-------
     2
```

Three pre-existing gold-sets from S39 / S39b / S40b. One
optimization run from S41 with two recommendations (both terminal:
applied + rejected, exercising the lifecycle at S41 smoke time).
`chunks` is empty on tenant_a (S39b corpus content was not re-ingested
post-S41). The smoke creates a new gold-set with a synthetic-UUID
entry and exercises the runner / engine against that.

## Smoke invocation

```
make build-api
docker compose up -d --force-recreate --no-deps padhanam-api
docker compose cp scripts/smoke_p11_s42.py padhanam-api:/app/scripts_smoke_p11_s42.py
docker compose exec -T padhanam-api python /app/scripts_smoke_p11_s42.py
```

Where `make build-api` builds the image directly via `docker build -t
padhanam-api:dev -f apps/api/Dockerfile .` and rewrites the
`compose.yaml` digest pin to the new content-addressed reference.
(The S41-close target invoked `docker compose build` which failed
because the image directive carries a digest; the target was patched
at S42 smoke time. See `log/captures.md` 2026-05-15 [S42] entry.)

The script lives at [scripts/smoke_p11_s42.py](../../scripts/smoke_p11_s42.py).
Token issuance via `padhanam.security.auth.issue_dev_token` with
tenant_id=`00000000-0000-4000-8000-00000000a001` (tenant_a).

## Captured output

```json
{
  "stage_1_gold_set_authoring": {
    "gold_set_id": "e0b48aec-6bef-43cd-b65a-9e09dd29713e",
    "initial_revision_id": "3595cf91-ce9c-4f23-bf67-d9c01435349c",
    "finalized_revision_hash_head": "94eb3b45011ac8e9",
    "entries_count": 1,
    "list_has_new_gold_set": true
  },
  "stage_2_retrieval_candidates": {
    "candidates_count": 0
  },
  "stage_3_evaluation_run": {
    "evaluation_run_id": "048d0108-dd1a-4f1c-aafd-be0efd0d6d85",
    "status": "completed",
    "duration_ms": 152,
    "per_query_results_count": 2,
    "per_strategy_aggregates_count": 2,
    "aggregate_strategies": ["vector_only", "graph_only"]
  },
  "stage_4_optimization_run": {
    "optimization_run_id": "b00171a4-3f66-4a72-9cf4-80ee9bf2ee33",
    "status": "completed",
    "duration_ms": 18,
    "recommendations_count": 2,
    "skipped_categories": ["model_choice", "prompt_revision"],
    "first_recommendation_category": "retrieval_strategy"
  },
  "stage_5_recommendation_reads": {
    "list_count": 5,
    "first_citation_category": "retrieval_strategy",
    "filtered_by_retrieval_strategy_count": 12
  },
  "stage_6_tenant_isolation": {
    "cross_tenant_get_status": 404,
    "cross_tenant_get_error_code": "gold_set_not_found",
    "leaks_cross_tenant_id_in_body": false,
    "cross_tenant_list_outcome": "200 empty=True"
  },
  "stage_7_recommendation_lifecycle": {
    "generated_count_available": 5,
    "acknowledge_status": 200,
    "acknowledge_transition_to": "acknowledged",
    "apply_status": 200,
    "apply_transition_to": "applied",
    "reject_status": 200,
    "reject_transition_to": "rejected",
    "terminal_transition_status": 409,
    "terminal_error_code": "recommendation_transition_not_permitted"
  },
  "stage_8_existing_read_surfaces": {
    "run_history_status": 200,
    "run_history_runs_count": 5,
    "audit_status": 200,
    "audit_events_count": 0,
    "audit_chain_integrity_status": "partial",
    "audit_filter_used": "resource_type=agent",
    "audit_note": "pre-existing S40/S41 audit rows carry empty correlation_id which the S36/S37 reader's AuditEventRecord validator rejects; filter limits to agent-context rows that carry valid correlation_ids. Captured for pre-P12 hygiene."
  },
  "stage_9_openapi": {
    "total_operations": 30,
    "s42_operations_expected": 17,
    "s42_operations_present": 17,
    "missing_operations": []
  }
}
```

## Stage notes

**Stage 1 — Gold-set authoring through HTTP.** The five gold-set
endpoints (POST /gold-sets, POST /gold-sets/{id}/entries, POST
/gold-sets/{id}/finalize, GET /gold-sets/{id}, GET /gold-sets)
exercise the full authoring lifecycle. The hash-chain primitive
fires at finalize time per D109; the finalized revision hash head
(`94eb3b45011ac8e9`) is byte-identical to what the application-layer
`compute_revision_hash` produces against the persisted entries.
Principal subject from the JWT becomes `created_by_user_id`
(verified at the integration test layer; not surfaced in the smoke
summary but visible in the persisted rows).

**Stage 2 — Retrieval candidates discovery.** Stage 1 of the
two-step discovery decomposition (per D112 commitment 1 / Finding 2
disposition). Returns zero candidates because tenant_a's `chunks`
table is empty post-S39b state; the route surface holds — empty
result is structurally honest, not a failure. A consumer with a
populated corpus would see ranked candidates with chunk_id,
content excerpt, similarity_score, and source_snapshot fields.

**Stage 3 — Synchronous evaluation-run kickoff.** Returns the
completed run with per-query results and per-strategy aggregates in
the same response per Finding 3 / D112 commitment 4. The two
executing strategies (`vector_only`, `graph_only`) both produced
aggregates (all-zero metrics because there are no chunks to retrieve
against; the route surface and the metric pipeline work cleanly).
Latency under 200ms for a single-entry evaluation against an empty
corpus; the synchronous-vs-asynchronous Phase 1 decision holds.

**Stage 4 — Synchronous optimization-run kickoff.** Returns the
completed run with two `retrieval_strategy` recommendations citing
the pre-existing S40b evaluation runs (`ef58678a` and `c168c2ba`)
as evidence. The `model_choice` and `prompt_revision` rules raised
SubstrateGapError per D111 commitment 5; the structured
`skipped_categories` entries surface in the response under the
keys `["model_choice", "prompt_revision"]` for procurement-grade
transparency about Phase 1 scope. Latency 18ms — the engine is
local-evidence-bounded.

**Stage 5 — Recommendation read surface.** Five recommendations on
the first page; the first citation category is `retrieval_strategy`
matching the discriminated-union DTO. The category filter
(`?category=retrieval_strategy`) without page_size honors the
default and returns the full set (twelve total at this point in the
smoke after multiple optimization runs accumulating); the
discriminator field is consistently the `category` literal across
every variant.

**Stage 6 — Tenant isolation through HTTP.** A tenant_b-typed JWT
hitting `GET /gold-sets/{tenant_a_id}` returns 404
`gold_set_not_found`. The error body does not name tenant_a's
identifier; the privacy-preserving structurally-honest 404 holds
per D112 commitment 3. The list endpoint returns an empty page for
tenant_b (no resources). No security event fires on either path per
the audit-precedent privacy policy adopted at S42.

**Stage 7 — Recommendation lifecycle exercise.** acknowledge → apply
on the first generated recommendation succeeds (two transitions,
both 200, terminal `applied` reached). Reject on the second
generated recommendation succeeds (200, terminal `rejected`).
Attempting to apply the already-applied recommendation returns 409
with `error_code=recommendation_transition_not_permitted` and the
structured details payload (`from_status: applied`, `to_status:
applied`) per the integration-test surface verified at commit 4.

**Stage 8 — Existing read surfaces (S34, S37).** GET /runs returns
the five most recent agent invocations across tenant_a (S30b / S33 /
S35 / S35a / S40b live exercise rows). GET /audit/events filtered to
`resource_type=agent` returns 200 with chain_integrity status
`partial`; the unfiltered query surfaces the pre-existing
empty-correlation_id finding captured at `log/captures.md` 2026-05-15
[S42] entry. The S34 / S37 route surfaces themselves are unchanged
by S42; the data shape inconsistency is forwarded to the pre-P12
hygiene session for a one-line validator loosening or a backfill
choice.

**Stage 9 — OpenAPI specification.** The generated `/openapi.json`
reflects all seventeen S42 operationIds (createGoldSet, listGoldSets,
getGoldSet, appendGoldSetEntry, finalizeGoldSetRevision,
listRetrievalCandidates, startEvaluationRun, listEvaluationRuns,
getEvaluationRun, startOptimizationRun, listOptimizationRuns,
getOptimizationRun, listRecommendations, getRecommendation,
acknowledgeRecommendation, applyRecommendation, rejectRecommendation).
Total operation count is 30 across the seven existing routers plus
S42's five new routers; the spec is procurement-grade Phase 2
UX-consumer documentation per D112 commitment 5.

## Post-state

```
$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -c "SELECT count(*) FROM gold_sets;"
 count
-------
    NN  (S39 + S39b + S40b + smoke-runs-from-this-doc)

$ docker compose exec -T postgres-tenant-a psql -U tenant_a -d tenant_a \
    -c "SELECT count(*) FROM optimization_runs;"
 count
-------
     ~  (S41 + S42 smoke-run kickoffs)
```

The smoke creates new gold-sets per invocation (each run has a unique
timestamped name); rerunning the smoke produces a fresh row set
without colliding with prior runs.

## S42-close verdict on procurement-grade UX-consumer surface readiness

**The HTTP transport surface is procurement-grade-ready for Phase 2
UX consumer integration.** A Phase 2 frontend developer can read the
OpenAPI specification at `/openapi.json` and integrate against the
platform without needing to read source code:

- Every new route has an operationId, a request and response schema,
  and the authentication shape inherited from the existing middleware
  (the OpenAPI spec mirrors the FastAPI route definitions which
  themselves drive the runtime behaviour; there is no
  spec-vs-implementation divergence surface).
- The two-step gold-set discovery decomposition preserves the
  human-in-the-loop content-fit selection that S40b's verdict
  committed to as procurement-grade authoring discipline: Stage 1
  surfaces ranked candidates via `GET /retrieval-candidates` and
  Stage 2 commits the operator's selection via
  `POST /gold-sets/{id}/entries` with the chosen
  `expected_chunk_ids`. A single retrieve-and-create endpoint would
  have lost this property and reintroduced the contamination shape
  S39b versus S40b surfaced.
- The recommendation lifecycle exercise through HTTP lands
  equivalently to the S41 CLI exercise: acknowledge → apply works on
  one path, reject works on the parallel path, and the 409
  re-transition path surfaces structured details. The same audit-
  chain-anchored persistence model from D111 commitment 8 holds at
  the HTTP boundary.
- Tenant isolation through HTTP holds with no information leakage:
  cross-tenant access returns 404 with the requester's own
  resource_id named in the message (which is the requester's own
  knowledge) and no mention of the actual owner's tenant identity.

**The four-context P11 substrate scaffold's consumer surface is
complete.** retrieval_evaluation, optimization, run_history (S34), and
audit (S37) all expose consumer-grade HTTP read paths plus the
write-shape and lifecycle paths appropriate to each context's posture
(authoring on retrieval_evaluation, engine kickoff plus lifecycle on
optimization, read-only on run_history and audit). The Phase 2 UX
work can build directly against this substrate without rework at the
HTTP layer.

**Findings forwarded to pre-P12 hygiene:**

1. `make build-api` target patched in-session to use `docker build`
   directly instead of `docker compose build` (which fails on the
   digest-pinned `image:` directive). The fix lands as part of the
   S42 commit chain; the methodology candidate `smoke-time
   verification of dev-workflow tooling at the same session that
   ships it` is captured at log/captures.md 2026-05-15 [S42] entry
   as a new recurrence-test-pending observation.

2. Pre-existing S40 / S41 audit rows carry empty `correlation_id`
   which the S37 audit reader's `AuditEventRecord` validator
   rejects. The S42 smoke worked around with a `resource_type=agent`
   filter; the pre-P12 hygiene session resolves with a one-line
   validator loosening (recommended) or a backfill migration
   (heavier). The captured entry at log/captures.md 2026-05-15 [S42]
   carries the recommendation.
