# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P7 — Agent CRUD (active)

Opened 2026-05-08 at the P7 framing strategic block. P7 ships the agent authoring substrate; by P7 close, the platform stores agent specifications, supports CRUD on agents and methodology templates through the CLI, and exposes the abstractions P8's runtime will consume and the P5 eval harness will score against. Methodology embedding lands as platform-managed templates on the control plane that tenants clone into independent agent instances on per-tenant Postgres. See [packages/p7-epic.md](packages/p7-epic.md) for goal, scope, and session forecast; the v1 epic note will be reconciled against `docs/archive/packages/p7.md` at P7 close per D43.

## Sessions

- **S23: Methodology bounded context skeleton, methodology aggregate, methodology CRUD.** Methodology context with full hexagonal layout; methodology aggregate (revision-shaped per D31, hash-chain audit per D26); control-plane Postgres migration; methodology repository; CRUD use cases; CLI commands at `padhanam methodology ...`.
- **S24: Agent bounded context skeleton, agent aggregate, agent CRUD.** Agent context with full hexagonal layout; agent aggregate (revision-shaped, hash-chain audit, methodology lineage fields, retrieval-config fields per D66 and D67); per-tenant Postgres migration; agent repository; CRUD use cases (excluding cross-context create-from-methodology); CLI commands at `padhanam agent ...`.
- **S25: Cross-context create-from-methodology flow plus LVT template plus first agent.** `create_agent_from_methodology` use case reading the methodology context's API; LVT methodology template authored on control plane; one agent cloned from LVT in operator's tenant with operator-uploaded sources attached; e2e test covering the full clone-and-edit flow with revision and hash-chain verification.
- **S26 (if needed): P7 close.** Archive at `docs/archive/packages/p7.md`, `log/packages.md` measured-outcomes paragraph, `current-package.md` transition to between-packages state.

## Carryovers active across the P6→P7 boundary

- **Hierarchical multi-agent topology design session.** Queued
  strategic-mode conversation paired with P8 framing or as
  pre-P8 strategic block per the Ask David capture. P8 (Agent
  runtime) inherits the composition orchestrator (D66), filter
  tree translator (D67), and tool registry surface (deferred
  from P7 per D68); the hierarchical-topology design adds the
  multi-agent shape on top of the runtime substrate.
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
- **Product methodology selection-space.** P7 commits to LVT as
  the first methodology per D68; the LVT methodology template
  lands at S25. Other methodologies in
  [charter/product-methodology.md](product-methodology.md)
  activate as evidence pulls them in (operator authors as needed);
  per-domain methodology selection surfaces at the framing of each
  domain-bearing package.
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
