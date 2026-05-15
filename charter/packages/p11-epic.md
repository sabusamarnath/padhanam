# P11 Epic — Optimization dashboard (backend-only)

## Goal

P11 ships the optimization-engine substrate that closes Phase 1's recommendation-engine claim per the bet's success criterion 4 and that Phase 2 procurement-facing UX consumes directly per D93. At P11 close, the optimization context produces `Recommendation` aggregates with category, subject, text, evidence citations, and append-only status; the recommendation generation reads from four producer contexts through consumer-defined ports plus wiring adapters; the four committed recommendation categories (retrieval strategy, model choice, prompt revision, cost optimization) cover the dimensions the bet's criterion 4 needs to demonstrate defensibly; the HTTP transports for the optimization context, retrieval evaluation context, and evaluation context (absorbing the P5-deferred carryover) complete the Phase 2 UX consumer surface; and the P11 close demonstration produces a working recommendation output against tenant_a that a procurement reader can verify is grounded in producer-context evidence.

## Scope at P11 close

Two new bounded contexts. The `contexts/retrieval_evaluation/` context per D105 carries tenant-authored gold sets (named container plus immutable revisions plus entries referencing revisions), hash-chain audit per D26, recall@k / precision@k / MRR computation at k of 1/3/5/10 plus latency-per-retrieval-call recording on result records, mean-aggregation across queries per strategy, comparison of vector_only / graph_only / parallel_rrf strategies on the same gold set per D66's strategy registry, and offline-only evaluation posture at Phase 1. The `contexts/optimization/` context per D108 carries the `Recommendation` aggregate with five fields (category, subject, text, evidence_citations, status), four consumer-defined reader ports for the four producer contexts (evaluation, retrieval evaluation, run history with the S33 reader reused, observability), four wiring adapters at the composition roots, recommendation generation paths for the four committed categories (retrieval_strategy, model_choice, prompt_revision, cost_optimization), and append-only status revisions covering generated/acknowledged/applied/rejected.

The allowlist closure folds into S39's front half: role-allowlist seed migrations gain the retrieval tool reference so role-bound agents invoke retrieval against the per-tenant corpus. Per-invocation retrieval-constraint threading at ToolInvoker remains Phase 2 territory unchanged.

The HTTP transports at S42 expose three FastAPI router trees: optimization reads (recommendation queries, recommendation status updates), retrieval evaluation reads (gold-set queries, evaluation result queries), evaluation reads (the P5-deferred carryover). All three follow the principal-derived tenant context convention from S29b and S34 with the cursor codec and DTO patterns S33 and S34 established.

Tenant-isolation contract tests extend the existing `tests/contract/tenant_isolation/` harness across the new context boundaries and the new HTTP surfaces. Cross-tenant read attempts through all surfaces must fail. The harness count extension is forecast at +15 to +25 scenarios across the four sessions.

## Sessions forecast

Four sessions firm, plus S43 reserved.

- **S39: Allowlist closure plus `contexts/retrieval_evaluation/` substrate.** Allowlist closure as commit 1 (Alembic migration adding retrieval tool reference to seeded role allowlists, smoke verification). Retrieval evaluation context substrate as commits 2 through N: domain (gold-set aggregate root, gold-set-revision immutability, gold-set-entry with ranked chunk ID list), consumer-defined reader port for the optimization context's future read at S41, Postgres adapter with hash-chain audit on revisions, Alembic migration, CLI surface walking the operator through authoring a gold set against tenant_a's corpus, tenant-isolation contract scenarios. D-entry forecast: gold-set domain shape and hash-chain reuse.

- **S40: Retrieval evaluation runner plus metric computation.** The runner exercises the agent loop against gold sets across the three retrieval strategies registered at D66, accumulates retrieved chunks, computes recall@k / precision@k / MRR at the four k values plus latency, records results behind the reader port from S39, and produces strategy-comparison output on tenant_a. D-entry forecast: runner integration shape with the agent loop, evaluation result record schema, strategy comparison aggregation.

- **S41: `contexts/optimization/` substrate.** Four consumer-defined reader ports (`EvaluationResultReader`, `RetrievalEvaluationResultReader`, observability reader, plus the S33 `RunHistoryReader` reused), four wiring adapters at the composition roots, `Recommendation` aggregate, recommendation generation paths for the four categories, CLI surface for triggering recommendation runs, tenant-isolation contract scenarios. D-entry forecast: recommendation aggregate concrete shape, recommendation generation logic per category, port-placement decisions for the three new ports.

- **S42: HTTP transports plus P11 close demo.** Three FastAPI router trees (optimization, retrieval_evaluation, evaluation), query-string parsers and DTO shapes per the S34 precedent, error response extensions to the S34 eleven-path map, tenant-isolation contract scenarios across the HTTP layer. End-to-end demonstration against tenant_a producing a `Recommendation` aggregate with citations procurement readers can verify. P11 retrospective addendum appended to this epic note. P11 archive of the live `current-package.md` content to `docs/archive/packages/p11.md` per the established pattern. Session-log archival to `docs/archive/sessions/p11.md` per D107. D-entry forecast: HTTP transport shapes across the three router trees, possibly a Kano-recorded decision on HTTP-layer surface scope if it surfaces structurally.

- **S43 reserved.** Fires only if S42 close surfaces a structurally honest carryover requiring resolution before P12 framing. Default unused.

## D-entries forecast

Five to seven D-entries across the package. Forecast at framing:

- Gold-set domain shape and hash-chain reuse at S39.
- Retrieval evaluation runner integration with the agent loop, evaluation result record schema, strategy comparison aggregation at S40.
- Recommendation aggregate concrete shape, recommendation generation logic per category at S41.
- HTTP transport shapes across the three router trees at S42.
- Possibly: a Kano-recorded decision at any session where alternatives produce real choice (port placement, runner integration patterns, recommendation generation specifics).

## Out of scope

- **Active testing scheduler integration.** P12 territory per packages.md. The active_testing context becomes a fifth producer the optimization context consumes when P12 lands; P11 ships against four producers.
- **LLM-generated recommendation text.** Phase 2 refinement under D93. Templated prose against the evidence ships at P11 close.
- **Numeric confidence scores on recommendations.** Out per D108 alternative (d) on D9 grounds.
- **Recommendation aggregation across multiple insights.** Phase 2 UX concern. P11 ships one recommendation per insight.
- **Recommendation workflow UX beyond status field.** Phase 2 surface under D93.
- **Online retrieval evaluation.** Phase 2 territory per D105 alternative (g).
- **nDCG and graded relevance.** Phase 2 territory per D105 alternative (d) and (e).
- **Per-invocation retrieval-constraint threading at ToolInvoker.** Phase 2 substrate refinement per the existing carryover at `current-package.md`.
- **Audit-driven recommendations.** Forward-compatible via observability reader; not a P11 committed category.
- **Browser-based authentication.** Phase 1 close substrate-completion territory.
- **Replay UI.** Phase 2 per D92.

## Open questions surfaced at framing

- Producer-side versus consumer-side placement for the three new reader ports at S41 settles per-port at build time depending on each producer's existing reader surface.
- The observability reader's read surface (Langfuse via D7's interface versus direct trace store access) settles at S41 against the existing trace adapter shape.
- Recommendation generation specifics per category (templated prose templates, evidence-citation density rules) settle at S41 against the four categories' producer shapes.
- HTTP query-string vocabulary for recommendation reads settles at S42 against the recommendation aggregate's field shape.
