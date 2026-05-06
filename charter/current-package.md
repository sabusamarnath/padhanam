# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P5: Evaluation harness

Opened: 2026-05-06 (P5-open strategic block; framing under D53).
Epic note: [charter/packages/p5-epic.md](packages/p5-epic.md).

P5 ships the evaluation harness as a bounded context at `contexts/evaluation/`,
with the scoring sheet primitive (versioned, immutable per version, role-gated
authorship), per-tenant storage, deterministic and LLM-as-judge appliers,
replay engine against the inference adapter, cost-per-successful-task metric,
and a CLI-driven regression report. Reading-C posture per D53: data model
absorbs human review (`reviewed_by_user_id` and `confirmed_at` on
rubric-application records); UI surfacing the human-review path defers to
P10 or P11 territory.

Three sessions framed (v1 intent; revisable at build-session framing per D43):

- **S16: Foundations.** Bounded context creation, scoring sheet domain model
  (sheet, revision, criterion, applier, rubric-application), per-tenant
  migration, first deterministic applier, end-to-end test through the new
  context. Charter touch-points: `charter/schema.md`, possibly a D-entry on
  scoring-extensibility shape if a structural decision surfaces.
- **S17: Replay engine and appliers.** Replay against the inference adapter
  (replay-seam decision committed at this session), additional deterministic
  appliers, LLM-as-judge applier, cost-per-successful-task computation locus
  committed.
- **S18: Regression report, CLI runner, P5 close.** Regression-report shape,
  CLI entry point, archive at `docs/archive/packages/p5.md`, measured-outcomes
  paragraph in `log/packages.md`, current-package transition to between-
  packages.

## Carryovers active across the P4→P5 boundary

- **Classification field on TenantContext.** Deferred per S15 framing decision
  option C; lands at the package that genuinely consumes it (P7 or P8 per the
  P4 epic note's out-of-scope section). TenantContext at P4 close carries
  three fields, not four; adding the field later is a one-line edit on the
  value object plus a registry-row column.
- **Cost-ceiling forward-affordance columns.** Configuration columns landed at
  S14 alongside the cost-attribution column per D41. Reading and enforcing
  the columns defers to Phase 2 per
  [charter/deferred-decisions.md](deferred-decisions.md). Migration comments
  mark the columns as not-yet-read; tenant-isolation tests confirm absence
  on per-tenant DBs.
- **Pricing-table monthly review.** Cadence in `ops/scheduled_checks.yaml`
  per D41; first run scheduled 2026-06-05.
- **Pricing-table format evolution.** S14 reflection forward-note: the
  format-(b) Pydantic + dict shape will need to evolve to YAML/TOML under
  `ops/` when multi-region rates, time-zoned rates, or rate-card complexity
  arrives. Phase 2 framing.
- **PRFAQ operator-voice rewrite.** Follow-on strategic conversation, queued
  alongside P5 build at operator discretion.
- **Phase 1 PRD operator-review** of the problem-statement and target-user
  sections. Same cadence as the PRFAQ rewrite.

## Deferred items remaining visible

- Production-shaped tenant onboarding workflow (full D13 implementation):
  awaits production deployment context.
- Cross-replica cache invalidation for the routing layer (D36):
  single-replica dev makes this a non-issue.
- Hash chain caching as a performance optimisation (D37): deferred until
  measurement justifies.
- Load testing of the chain-concurrency posture: deferred to whichever
  future session has multi-writer load.
- Methodology mechanical-enforcement upgrades (decision-to-code translation
  gate, per-package reconciliation gate, adaptive reassessment prompt,
  `make doctor`, session-close walkthrough template, edge-case hunter
  procedural shape): tracked in
  [charter/deferred-decisions.md](deferred-decisions.md).
- Platform-baseline scoring sheet library (deferred per D53; activates at
  real onboarding flow or a cross-tenant curated library with a real
  consumer).
- Human-review UI for evaluation (deferred per D53; lands at P10 or P11
  territory).
