# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P4: LLM gateway

Active. Epic note at [charter/packages/p4-epic.md](packages/p4-epic.md). Two-session breakdown.

### Sessions

- **S14: Cost capture and registry migration.** Closed 2026-05-05. Pricing table at `padhanam/config/inference.py` (`PRICING_TABLE` dict with `qwen2.5:7b` at zero rates and `gpt-4o-mini` at 0.150 / 0.600 USD per 1M tokens). LiteLLMAdapter emits four attributes per completion (`gen_ai.cost.input_usd`, `output_usd`, `total_usd`, `pricing_status`); browser-verified on trace `9677d5252e095b8d8a2158e11d17a4c6`. Control-plane Alembic revision `0003_add_cost_columns` added `cost_attribution_id` (NOT NULL, populated from `tenant_id::text` for both seeded tenants), `cost_ceiling_usd_monthly` and `cost_ceiling_action` (forward-affordance, CHECK on action enum). Monthly pricing-table review added to `ops/scheduled_checks.yaml` (first run 2026-06-05). D49 records the wiring shape (Kano: must-have).
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
