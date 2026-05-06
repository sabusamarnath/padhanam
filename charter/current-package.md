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

Four sessions actual (v2 shape; revised from the v1 three-session forecast at
S17 framing per D43, with the original draft preserved alongside per the
append-only-at-version-level discipline):

- **S16: Foundations.** *Closed 2026-05-06.* Bounded context creation, scoring
  sheet domain model (sheet, revision, criterion, applier, rubric-application),
  per-tenant migration, first deterministic applier (`exact_match`), polymorphic
  ApplierPort, apply_scoring_sheet use case, end-to-end test through the new
  context. Charter touches: `charter/schema.md` updated alongside the
  migration; D54 (Applier port shape — single polymorphic async port) and D55
  (Score representation on rubric_applications — text with criterion-level
  interpretation) committed.
- **S17a: Replay engine, prompt applier, trace_id.** *Closing 2026-05-06.*
  trace_id column on rubric_applications; InferencePort + ModelConfig +
  ReplayResult value objects in evaluation's domain, with adapter calling
  `contexts.inference.api.request_completion` per D17; ExactMatchApplier
  renamed to PolymorphicApplier; prompt-applier branch lands; replay_and_score
  orchestrator composes the existing apply_scoring_sheet (which gains an
  optional `trace_id` parameter); end-to-end integration test exercises the
  full flow against tenant_a's DB through the live inference path. Charter
  touches: `charter/schema.md` updated alongside the trace_id migration; this
  current-package.md shifted to the four-session shape.
- **S17b: Cost-per-successful-task path and observability surface.** *Queued.*
  Cost-query path joining rubric_applications by trace_id to the trace store's
  gen_ai.cost.* attributes per D8/D41; cost-per-successful-task computation
  use case in `contexts/evaluation/application/`; `contexts/observability/`
  application surface establishment for the cost-query read (the bounded
  context exists but its api.py surface for evaluation's consumption needs
  to be named — the S17a reflection answers prompt 3 with "no inference
  surface needed" because contexts.inference.api was already shaped at S6;
  S17b confirms whether contexts.observability follows the same pattern or
  whether the surface is established in this session).
- **S18: Regression report, CLI runner, P5 close.** *Queued.* Regression-
  report shape comparing two runs of a scoring sheet against an interaction
  set; CLI entry point (`make eval-run` or equivalent); archive at
  `docs/archive/packages/p5.md`; measured-outcomes paragraph in
  `log/packages.md`; current-package transition to between-packages state.

The three-session forecast at framing (v1) anticipated replay-engine and
appliers at one session ("S17"); the build-session framing surface that
the work split cleanly into a substrate session (S17a — replay engine + prompt
applier + trace_id) and a consumer session (S17b — cost-per-successful-task
+ observability application surface). The split is recorded here at S17a
close; the v1 draft above is preserved per D43's append-only-at-version-level
discipline; the eventual P5 archive at S18 close reconciles the four-session
actual against the three-session forecast as the audit deliverable.

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
