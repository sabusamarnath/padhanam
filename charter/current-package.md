# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P4: LLM gateway

Active. Epic note at [charter/packages/p4-epic.md](packages/p4-epic.md). Two-session breakdown.

### Sessions

- **S14: Cost capture and registry migration.** In progress (opened 2026-05-05). Pricing table at `padhanam/config/inference.py`, `gen_ai.cost.*` OTel attributes from the LiteLLMAdapter, control-plane Alembic revision adding the cost-attribution column and the cost-ceiling forward-affordance columns to `tenant_registry`. Monthly pricing-table review entry per D41.
- **S15: Tenant context enrichment and P4 close.** Pending. Tenant context value object propagated through the inference path. Package archive at `docs/archive/packages/p4.md` per D31. First entry in `log/packages.md` with measured-outcomes paragraph per D40.

### Carryovers active in P4

- **Cost-ceiling forward-affordance.** Cost-ceiling configuration columns ship at S14 alongside the cost-attribution column per D41. Reading and enforcing the columns defers to Phase 2 per [charter/deferred-decisions.md](deferred-decisions.md). Migration comments mark the columns as not-yet-read; tenant-isolation tests confirm absence on per-tenant DBs.
- **Pricing table monthly review.** Cadence lands in `ops/scheduled_checks.yaml` per D41.
- **Tenant context value-object placement.** S15 decides where the value object lives (`shared_kernel/` vs context-local) when the build session faces the cross-context import question; the architectural choice carries Kano category at the D-entry per D42.

### Deferred items remaining visible

- Production-shaped tenant onboarding workflow (full D13 implementation): awaits production deployment context.
- Cross-replica cache invalidation for the routing layer (D36): single-replica dev makes this a non-issue.
- Hash chain caching as a performance optimisation (D37): deferred until measurement justifies.
- Load testing of the chain-concurrency posture: deferred to whichever future session has multi-writer load.
- PRFAQ operator-voice rewrite: follow-on strategic session.
- Phase 1 PRD operator-review of the problem-statement and target-user sections: follow-on strategic session on the same cadence.
