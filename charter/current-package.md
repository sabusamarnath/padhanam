# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P6: Source ingestion (active)

Opened: 2026-05-07 (P6-open strategic block).
Sessions forecast: S19 through S21 or S22.
Framing D-entry: D60.
Epic note: `charter/packages/p6-epic.md` v1.

P6 ships the source-ingestion vertical so the agent runtime at P8 has a corpus to retrieve from. Asynchronous pipeline behind a single `contexts/ingestion/` bounded context. Two-track coordination across pgvector (per-tenant) and Neo4j (topology TBD at the implementing session). CLI surface at `apps/cli/`. Tenant isolation discipline holds for both stores.

## Carryovers active across the P5→P6 boundary

- **OTel TracerProvider initialisation helper at `padhanam/observability/init_tracing.py`.** Third-instance promotion candidate from S18 reflection. P6 CLI surface is the natural consumer that justifies the lift; if S19 adds the fourth caller, the helper lands then.
- **Production CLI tenant resolution via the registry.** Phase 2 shape; current `apps/cli/_runtime.py` hardcoded test-set mapping is honest about its dev-only scope.
- **Multi-baseline regression reports.** Deferred per D58; activates at P11 alongside run-history infrastructure from P9.

## Deferred items remaining visible

- **Per-tenant topology for Neo4j.** New entry in `deferred-decisions.md` from P6 framing. Activates at the session that first writes to Neo4j.
- **Classification field on TenantContext.** Lands at the package that consumes it (P7 or P8).
- **Cost-ceiling forward-affordance columns.** Reading and enforcing defers to Phase 2.
- **Pricing-table monthly review.** First run scheduled 2026-06-05.
- **Pricing-table format evolution.** Phase 2 framing.
- **PRFAQ operator-voice rewrite.** Operator discretion.
- **Phase 1 PRD operator-review.** Operator discretion.
- **Production-shaped tenant onboarding workflow.** Awaits production deployment context.
- **Cross-replica cache invalidation for the routing layer.** Single-replica dev makes this a non-issue.
- **Hash chain caching.** Deferred until measurement justifies.
- **Methodology mechanical-enforcement upgrades.** Tracked in `deferred-decisions.md`.
- **Platform-baseline scoring sheet library.** Activates at real onboarding flow.
- **Human-review UI for evaluation.** Lands at P10 or P11 territory.
- **Multi-currency cost reporting.** Activates at multi-region deployment context.
- **Per-criterion cost breakdowns in evaluation results.** P11 territory.
- **Calibration learning loops over `automated_score` vs `human_score`.** P11 territory.
- **Trace_id-based recommendation queries beyond cost-per-successful-task.** P11 territory.
- **HTTP API for evaluation management.** Activates when UI consumer arrives at P10 or P11.
- **Sheet/interaction-set management commands in the CLI.** Activates when CRUD UI is needed.
