# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## Between packages — P6 closed, P7 not yet open

P6 closed at S22 close on 2026-05-07. The P6 retrospective lives at
[docs/archive/packages/p6.md](../docs/archive/packages/p6.md);
the P6 measured-outcomes paragraph at
[log/packages.md](../log/packages.md) covers S19 through S22 plus
the two mid-package strategic commits (Ask David external-reference
absorption; product reframe with the four-domain demonstration
scope).

The next strategic-mode conversation frames P7 (Agent CRUD per
[charter/roadmap.md](roadmap.md) and [charter/packages.md](packages.md)).
The data-retrieval design session held 2026-05-07 between P6 close and
P7 framing produced D66 (hybrid composition architecture) and D67
(filter expression architecture); both inherit into P7's agent config
schema (default strategy field, filter tree field) and P8's agent
runtime (composition orchestrator, strategy registry, three-strategy
starter catalogue, filter tree translator). No package elevation
needed; no roadmap v5. P7 (Agent CRUD) inherits the
agent-with-embedded-methodology pattern from the product reframe and
the agent-config schema commitments from D66 and D67; the
methodology-embedding shape established in
[charter/product-methodology.md](product-methodology.md) plus the
retrieval-config shape established in D66 and D67 are P7 framing
inputs. The retrieval-evaluation design session is queued as a
separate strategic-mode commitment ahead of P11; see the carryovers
section.

## Carryovers active across the P6→P7 boundary

- **Retrieval-evaluation design session.** Queued strategic-mode
  conversation ahead of P11 (recommendation engine). The audience
  is the existing eval harness from P5 and the optimisation layer
  at P11; the design space (gold-set construction, offline versus
  online relevance signals, recall@k versus precision@k tradeoffs,
  test corpus shape) warrants its own focused session at the
  audience-relevant moment. Must-have for the bet's optimisation
  claim because the optimisation layer has to distinguish retrieval
  failures from reasoning failures; deferred at the data-retrieval
  design session on Kano-versus-RICE asymmetry grounds (must-have
  on Kano, high effort on RICE relative to its on-runtime impact).
- **Product methodology selection-space.** P7 (Agent CRUD)
  inherits the methodology-embedded-not-gated principle from the
  product reframe absorption; per-domain methodology selection
  per [charter/product-methodology.md](product-methodology.md)
  surfaces at the framing of each domain-bearing package.
- **Production CLI tenant resolution via the registry.** Phase 2
  shape; `apps/cli/_runtime.py`'s hardcoded test-set mapping is
  honest about its dev-only scope. Activates when production
  deployment context arrives.
- **Multi-baseline regression reports.** Deferred per D58;
  single-baseline at S18. Activates at P11's recommendation
  engine when run-history infrastructure exists from P9.
- **PRFAQ phase-audit refresh.** Cadence per D45 (every phase
  audit). The v2 PRFAQ from the P4-post carryover-cleanup
  strategic session stands until the Phase 1 close audit.

## Deferred items remaining visible

- **Per-tenant Neo4j topology.** Activated at S21 per D63 with
  Phase 1 shared-instance + property-based scoping; the
  deferred-decisions entry remains as the production-deployment
  revisit marker with three named triggers (residency, blast
  radius, security-review).
- **Within-tenant segmentation primitive.** Held in the P6-open
  strategic-block conversation; activates at the consumer-driven
  session that demands it (likely P8 agent runtime). No schema
  commitment at P6 beyond tenant.
- **Classification field on TenantContext.** Deferred per S15
  framing decision option C; lands at the package that genuinely
  consumes it (P7 or P8 per the P4 epic note's out-of-scope
  section). TenantContext at P6 close still carries three fields,
  not four; adding the field later is a one-line edit on the
  value object plus a registry-row column.
- **Cost-ceiling forward-affordance columns.** Configuration
  columns landed at S14 alongside the cost-attribution column per
  D41. Reading and enforcing the columns defers to Phase 2 per
  [charter/deferred-decisions.md](deferred-decisions.md).
- **Pricing-table monthly review.** Cadence in
  `ops/scheduled_checks.yaml` per D41; first run scheduled
  2026-06-05.
- **Pricing-table format evolution.** S14 reflection forward-note;
  the format-(b) Pydantic + dict shape evolves to YAML/TOML under
  `ops/` when multi-region rates, time-zoned rates, or rate-card
  complexity arrives. Phase 2 framing.
- **PRFAQ operator-voice rewrite.** Follow-on strategic
  conversation, queued at operator discretion.
- **Phase 1 PRD operator-review** of the problem-statement and
  target-user sections. Operator discretion.
- **Production-shaped tenant onboarding workflow** (full D13
  implementation): awaits production deployment context.
- **Cross-replica cache invalidation for the routing layer**
  (D36): single-replica dev makes this a non-issue.
- **Hash chain caching as a performance optimisation** (D37):
  deferred until measurement justifies.
- **Methodology mechanical-enforcement upgrades.** Tracked in
  [charter/deferred-decisions.md](deferred-decisions.md). The
  framing-prompt-as-recommendation and pre-write reconciliation
  promotions at this commit move two items off the
  Patterns-observed candidate list onto the prescriptive
  principle surface; the user-driven course-correction Patterns-
  observed entry lands at the same commit.
- **Platform-baseline scoring sheet library** (deferred per D53;
  activates at real onboarding flow or a cross-tenant curated
  library with a real consumer).
- **Human-review UI for evaluation** (deferred per D53; lands at
  P10 or P11 territory).
- **Multi-currency cost reporting** (deferred per the strategic
  commit `24561c9` deferred-decisions entry; activates at the
  Phase 2 multi-region deployment context).
- **Per-criterion cost breakdowns in
  `CostPerSuccessfulTaskResult`** (P11 territory).
- **Calibration learning loops over `automated_score` vs
  `human_score`** (P11 territory; data substrate lives at
  rubric_applications per D55).
- **Trace_id-based recommendation queries beyond
  cost-per-successful-task** (P11 territory).
- **HTTP API for ingestion management** (deferred per the P6
  out-of-scope; CLI is the user surface at P6; HTTP API ships
  when a UI consumer arrives at P9 or P10).
- **HTTP API for evaluation management** (deferred; activates
  when a UI consumer arrives at P10 or P11).
- **Sheet/interaction-set management commands in the CLI**
  (deferred; activates when CRUD UI is needed).
- **Personalization as a runtime concern.** Deferred-decisions
  entry from P6 mid-package absorption (Ask David external
  reference); activates at P8 agent runtime or whichever
  predecessor orchestration session demands it.
