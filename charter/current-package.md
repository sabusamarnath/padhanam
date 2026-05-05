# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## Between packages — P4 closed, P5 not yet open

P4 closed at S15 close on 2026-05-05. The P4 retrospective lives at
[docs/archive/packages/p4.md](../docs/archive/packages/p4.md);
the first measured-outcomes paragraph in
[log/packages.md](../log/packages.md) covers S14 and S15.

The next strategic-mode conversation frames P5 (eval-harness scaffold
per `charter/roadmap.md` and `charter/packages.md`). The framing
produces a P5 epic note at `charter/packages/p5-epic.md` per D43, the
S16 (and beyond) session prompts, and any P5 D-entries that follow
from framing decisions. This file transitions to the active-P5 state
at the strategic boundary.

## Carryovers active across the P4→P5 boundary

- **Classification field on TenantContext.** Deferred per S15 framing
  decision option C; lands at the package that genuinely consumes it
  (P7 or P8 per the P4 epic note's out-of-scope section).
  TenantContext at P4 close carries three fields, not four; adding
  the field later is a one-line edit on the value object plus a
  registry-row column.
- **Cost-ceiling forward-affordance columns.** Configuration columns
  landed at S14 alongside the cost-attribution column per D41.
  Reading and enforcing the columns defers to Phase 2 per
  [charter/deferred-decisions.md](deferred-decisions.md). Migration
  comments mark the columns as not-yet-read; tenant-isolation tests
  confirm absence on per-tenant DBs.
- **Pricing-table monthly review.** Cadence in
  `ops/scheduled_checks.yaml` per D41; first run scheduled
  2026-06-05.
- **Pricing-table format evolution.** S14 reflection forward-note: the
  format-(b) Pydantic + dict shape will need to evolve to
  YAML/TOML under `ops/` when multi-region rates, time-zoned rates,
  or rate-card complexity arrives. Phase 2 framing.
- **PRFAQ operator-voice rewrite.** Follow-on strategic conversation;
  carried forward from the P3 post-close strategic session.
- **Phase 1 PRD operator-review of the problem-statement and
  target-user sections.** Follow-on strategic conversation on the
  same cadence as the PRFAQ rewrite.

## Deferred items remaining visible

- Production-shaped tenant onboarding workflow (full D13
  implementation): awaits production deployment context.
- Cross-replica cache invalidation for the routing layer (D36):
  single-replica dev makes this a non-issue.
- Hash chain caching as a performance optimisation (D37): deferred
  until measurement justifies.
- Load testing of the chain-concurrency posture: deferred to whichever
  future session has multi-writer load.
- Methodology mechanical-enforcement upgrades (decision-to-code
  translation gate, per-package reconciliation gate, adaptive
  reassessment prompt, `make doctor`, session-close walkthrough
  template, edge-case hunter procedural shape): tracked in
  [charter/deferred-decisions.md](deferred-decisions.md). Earliest
  meaningful activations are at the P4→P5 boundary or the Phase 1
  close audit.
