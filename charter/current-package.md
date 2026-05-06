# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## Between packages — P5 closed, P6 not yet open

P5 closed at S18 close on 2026-05-06. The P5 retrospective lives at
[docs/archive/packages/p5.md](../docs/archive/packages/p5.md);
the P5 measured-outcomes paragraph at
[log/packages.md](../log/packages.md) covers S16 through S18.

The next strategic-mode conversation frames P6 (source ingestion per
[charter/roadmap.md](roadmap.md) and [charter/packages.md](packages.md)).
The framing produces a P6 epic note at `charter/packages/p6-epic.md`
per D43, the S19 (and beyond) session prompts, and any P6 D-entries
that follow from framing decisions. This file transitions to the
active-P6 state at the strategic boundary.

## Carryovers active across the P5→P6 boundary

- **Source ingestion** (P6 territory) — the agent runtime's data
  substrate; upload + two-track pipeline to pgvector + Neo4j +
  retrieval interfaces. The eval harness scores outputs; it does
  not ingest sources. Activates at P6 framing.
- **Production CLI tenant resolution via the registry.** Phase 2
  shape; `apps/cli/_runtime.py`'s hardcoded test-set mapping is
  honest about its dev-only scope. Activates when production
  deployment context arrives.
- **OTel TracerProvider initialisation helper at
  `padhanam/observability/init_tracing.py`.** Third-instance
  promotion candidate (the pattern lives in `apps/api/main.py`,
  the e2e test scripts, and `apps/cli/_runtime.py`); promotion
  to a shared helper at the next consumer (P6 CLI surface or P11
  recommendation engine background workers).
- **Multi-baseline regression reports.** Deferred per D58;
  single-baseline at S18. Activates at P11's recommendation
  engine when run-history infrastructure exists from P9.

## Deferred items remaining visible

- **Classification field on TenantContext.** Deferred per S15
  framing decision option C; lands at the package that genuinely
  consumes it (P7 or P8 per the P4 epic note's out-of-scope
  section). TenantContext at P5 close still carries three fields,
  not four; adding the field later is a one-line edit on the value
  object plus a registry-row column.
- **Cost-ceiling forward-affordance columns.** Configuration
  columns landed at S14 alongside the cost-attribution column per
  D41. Reading and enforcing the columns defers to Phase 2 per
  [charter/deferred-decisions.md](deferred-decisions.md). Migration
  comments mark the columns as not-yet-read; tenant-isolation tests
  confirm absence on per-tenant DBs.
- **Pricing-table monthly review.** Cadence in
  `ops/scheduled_checks.yaml` per D41; first run scheduled
  2026-06-05.
- **Pricing-table format evolution.** S14 reflection forward-note:
  the format-(b) Pydantic + dict shape will need to evolve to
  YAML/TOML under `ops/` when multi-region rates, time-zoned rates,
  or rate-card complexity arrives. Phase 2 framing.
- **PRFAQ operator-voice rewrite.** Follow-on strategic
  conversation, queued alongside future package builds at
  operator discretion.
- **Phase 1 PRD operator-review** of the problem-statement and
  target-user sections. Same cadence as the PRFAQ rewrite.
- **Production-shaped tenant onboarding workflow** (full D13
  implementation): awaits production deployment context.
- **Cross-replica cache invalidation for the routing layer**
  (D36): single-replica dev makes this a non-issue.
- **Hash chain caching as a performance optimisation** (D37):
  deferred until measurement justifies.
- **Load testing of the chain-concurrency posture:** deferred to
  whichever future session has multi-writer load.
- **Methodology mechanical-enforcement upgrades** (decision-to-code
  translation gate, per-package reconciliation gate, adaptive
  reassessment prompt, `make doctor`, session-close walkthrough
  template, edge-case hunter procedural shape, currency-suffix-
  field AST enforcement): tracked in
  [charter/deferred-decisions.md](deferred-decisions.md).
- **Platform-baseline scoring sheet library** (deferred per D53;
  activates at real onboarding flow or a cross-tenant curated
  library with a real consumer).
- **Human-review UI for evaluation** (deferred per D53; lands at
  P10 or P11 territory).
- **Multi-currency cost reporting** (deferred per the strategic
  commit `24561c9` deferred-decisions entry; activates at the
  Phase 2 multi-region deployment context).
- **CTI promotion for appliers** (watch-item per S16 reflection
  2(a); not triggered at P5 close because the prompt applier
  branch landed cleanly without straining the type-tag-plus-
  nullable-columns shape).
- **Per-criterion cost breakdowns in
  `CostPerSuccessfulTaskResult`** (P11 territory; the
  recommendation engine's per-criterion consumption justifies
  the extra query work).
- **Calibration learning loops over `automated_score` vs
  `human_score`** (P11 territory; data substrate lives at
  rubric_applications per D55).
- **Trace_id-based recommendation queries beyond
  cost-per-successful-task** (P11 territory).
- **HTTP API for evaluation management** (deferred; activates
  when a UI consumer arrives at P10 or P11).
- **Sheet/interaction-set management commands in the CLI**
  (deferred; activates when CRUD UI is needed).
