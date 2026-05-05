# Package 4: LLM gateway

First instance of the D43 package-epic-note convention. Written at package open. Archive at `docs/archive/packages/p4.md` reconciles against this v1 draft per D43, with the delta as the audit deliverable.

## Goal

End-to-end cost dimension wired through the inference path. Per-tenant cost-attribution column on the control-plane registry, with cost-ceiling configuration columns landing alongside as forward-affordance. Inference path resolves a tenant context object from registry at request time, carrying jurisdiction, classification, and cost-attribution identifier through to the adapter. Two sessions; closes when tenant A and tenant B both produce traces in Langfuse with cost attributes populated and tenant context flowing end-to-end with no cross-tenant leakage.

## Strategic placement

Per `charter/roadmap.md` v2:

- **Bet:** Padhanam.
- **Initiative:** Phase 1.
- **Epic:** P4 — LLM gateway.
- **Stories:** S14 (cost capture and registry migration), S15 (tenant context enrichment and P4 close).

P4 is RICE-scored 5 / 5 / 3 / 0.8 = 93.75, the highest-impact unit of work in Phase 1 by raw score. Sequence position is dependency-driven: P3 (tenancy primitives) precedes P4 because the per-tenant cost-attribution column needs the tenant registry surface, and tenant context must flow through the inference path. Dependency overrode RICE; the score is honest about how strongly P4 contributes evidence, not about whether it could run in isolation.

## Why this package matters

Most of what `charter/packages.md` attributes to P4 (LiteLLM in Compose, Langfuse wired up, OTel GenAI conventions, FastAPI endpoint, tenant routing) shipped across S6 through S12. What remains is the cost dimension committed in D41, the per-tenant cost-attribution column that D41 retrofits onto the tenant registry, and a small reconciliation of how rich the tenant context flowing into the inference path needs to be.

P4 closes the optimization-recommendation triangle. P11 already has token, latency, and quality data via the existing GenAI attributes; without cost attributes attached at the trace level, recommendations can produce "this is faster" or "this is higher-quality" but never "this costs N% more for M% quality at the same task type." The third recommendation shape is what makes the optimization layer enterprise-defensible, per the cost commitment section of `charter/methodology.md` and D9's recommendation-shape commitment.

The tenant context refactor is the option that S15 buys: every later session that needs jurisdiction at inference time, classification gating, or routing decisions based on tenant attributes pays a smaller refactor cost because the value-object boundary is already in place. The alternative of skipping S15 and adding the layer when production routing forces it would compound — a bounded refactor against one consumer (cost-attribution) is structurally cleaner than a refactor against three consumers (cost, jurisdiction, classification) at once.

## User stories

As the operator directing the case study, I want every model completion to carry per-tenant cost attribution at the trace level, so that the optimization layer at P11 can produce cost-aware recommendations without downstream aggregation across stores.

As an enterprise procurement reader of the case study, I want the cost dimension structurally captured at the trace level rather than computed downstream, so that the architecture survives reconciliation against actual billing without a separate accounting layer.

As a future Phase 2 routing-decisions designer, I want the inference adapter to receive a full tenant context object at request time, so that production routing decisions (jurisdiction-aware model selection, classification-aware tool gating, tier-aware cost ceiling enforcement) can be added without refactoring the inference path's boundary.

## Sessions

### S14: Cost capture and registry migration

Goal at session close: a real Ollama completion through the inference path emits `gen_ai.cost.input_usd`, `gen_ai.cost.output_usd`, and `gen_ai.cost.total_usd` attributes verified in Langfuse on both the FastAPI request span and the LiteLLM gateway span. The control-plane tenant registry has the per-tenant cost-attribution column applied via Alembic migration, alongside cost-ceiling configuration columns landed as forward-affordance. Both seeded tenants populated.

Substantive work:

- Pricing table at `padhanam/config/inference.py` covering Qwen 2.5 7B (zero, exercising the table shape) plus at least one stand-in commercial model so the structure is honest rather than stubbed.
- LiteLLMAdapter cost extension reading the pricing table, computing USD per call from token counts, emitting `gen_ai.cost.*` OTel attributes on the adapter span.
- Alembic migration on the control-plane tenant registry: per-tenant cost-attribution column, plus cost-ceiling configuration columns with a migration comment marking them forward-affordance and not yet read by the codebase.
- `ops/scheduled_checks.yaml` extension: monthly pricing-table review cadence per D41.
- Browser interactive verification of the cost attributes rendering in Langfuse, per the convention from S4.
- Charter touch-points: `charter/schema.md` updated in the same commit as the migration; D-entry for the cost-capture wiring shape if the alternatives are non-trivial; `charter/current-package.md` status update.

### S15: Tenant context enrichment and P4 close

Goal at session close: the inference path resolves a tenant context object from the registry at request time. The object carries `tenant_id`, `jurisdiction`, `classification`, and `cost_attribution_id`. End-to-end integration tests across tenant A and tenant B confirm isolation holds against the enriched payload (already verified structurally at S12; re-verified here against the new shape). P4 archived at `docs/archive/packages/p4.md` per D31; the archive at `docs/archive/packages/p4.md` reconciles against this v1 draft per D43, with the delta as the audit deliverable. First entry in `log/packages.md` lands with a measured-outcomes paragraph per D40.

Substantive work:

- Tenant context value object defined where it best fits (likely `shared_kernel/` since multiple contexts will read it; the placement decision is a build-session call).
- Inference path moves from accepting a `tenant_id` to resolving the full tenant context from the registry at request time, with the resolution path placed where it does not create new cross-context dependencies.
- Tenant context propagated to `LiteLLMAdapter` and surfaced in trace attributes (jurisdiction and classification at minimum, in addition to the existing tenant_id).
- End-to-end integration tests across two tenants with the enriched payload, asserting cost attributes, tenant context attributes, and audit-row isolation all hold simultaneously.
- Package retrospective at `docs/archive/packages/p4.md` following the P3 archive shape; first measured-outcomes paragraph per D40 lands in `log/packages.md` (created at P4 close as the first instance).
- Archive at `docs/archive/packages/p4.md` reconciles against this v1 draft per D43, with the delta as the audit deliverable.
- Charter touch-points: D-entries for any structural decisions in the tenant context refactor; `charter/current-package.md` transitions to the between-packages state pointing at the P4 archive.

## Architectural commitments expected

P4 expects to ship at minimum two D-entries:

- **Cost capture wiring shape.** Pricing table as configuration source, OTel attribute extension as the integration point, `gen_ai.cost.*` attributes as the trace surface. Kano: must-have (D41 enforcement).
- **Tenant context value object shape.** Where the value object lives, what fields it carries, how it propagates from the FastAPI middleware through the use case to the adapter. Kano: performance (the option preserved is what S15 buys; the alternative of skipping was considered and rejected at framing).

Additional D-entries are possible if structural decisions surface during build. The session-close discipline catches them; the build session does not pre-commit to D-entry counts.

## Out of scope

- Cost ceiling enforcement. Configuration columns land at S14; reading and enforcing them defers to Phase 2 per `charter/deferred-decisions.md`.
- Multi-tier model routing. Single-model dev environment; deferred to Phase 2.
- Progressive throttling. Same context; deferred to Phase 2.
- Optimization recommendations. P11 territory.
- Cost-per-successful-task evaluation metric. P5 territory per D8 and D41.
- Jurisdiction-aware inference routing. Single-region in dev; the abstraction earns its place when production deployment context arrives.
- Classification-aware tool gating. P7 or P8 territory; the value object carries the field but no consumer reads it in P4.
- Production-shaped tenant onboarding. Full D13 implementation deferred until infrastructure-as-code is real.
- Cross-replica cache invalidation for the routing layer. D36 deferred; single-replica dev makes this a non-issue at P4.

## Acceptance criteria for package close

1. Pricing table at `padhanam/config/inference.py` exists, covers at least the dev model and one stand-in commercial model, and is read by the LiteLLMAdapter at request time.
2. Every completion through the inference path emits `gen_ai.cost.input_usd`, `gen_ai.cost.output_usd`, and `gen_ai.cost.total_usd` OTel attributes.
3. Browser interactive verification confirms the cost attributes render correctly in Langfuse on both the FastAPI request span and the LiteLLM gateway span.
4. Alembic migration applied to the control-plane registry adds the per-tenant cost-attribution column and the cost-ceiling configuration columns; both seeded tenants are populated.
5. The inference path resolves a tenant context object from the registry at request time.
6. The tenant context object carries `tenant_id`, `jurisdiction`, `classification`, and `cost_attribution_id`. The object propagates through the inference adapter and is visible in trace attributes for at least `tenant_id` and `jurisdiction`.
7. End-to-end integration tests pass across tenant A and tenant B against the enriched payload with no cross-tenant leakage; per-tenant audit chains remain independent per D35.
8. `make lint` keeps all import-linter contracts; AST tests pass; `make scan` clean against the documented exceptions list.
9. `charter/schema.md` updated in the same commits as the migrations.
10. `docs/archive/packages/p4.md` exists with retrospective following the P3 archive shape per D31.
11. `log/packages.md` exists with a P4 entry containing a measured-outcomes paragraph per D40 (first instance of the post-D40 retrospective shape).
12. Archive at `docs/archive/packages/p4.md` reconciles against this v1 draft per D43, with the delta as the audit deliverable.
13. `charter/current-package.md` transitions to the between-packages state pointing at the P4 archive.

## RICE

| Reach | Impact | Confidence | Effort | RICE |
|---|---|---|---|---|
| 5 | 5 | 3 | 0.8 | 93.75 |

- **Reach 5.** Exercises four of the bet's evidence-needs: architectural decisions (tenant context value-object placement, cost-capture wiring), observability differentiator (cost dimension at trace level), tenant isolation maintained under enrichment, optimization-recommendation foundation (cost data attached for P11).
- **Impact 5.** Highest demonstration of the proposition for any single Phase 1 package; closes the cost dimension that completes the optimization-recommendation triangle, which is the platform's enterprise-defensible moment.
- **Confidence 3.** Substrate is in (LiteLLM, Langfuse, FastAPI, tenant routing, audit context). P4 is the lightest-effort high-impact package because the heavy infrastructure shipped earlier; cost wiring is well-understood and the tenant context refactor is small surface area.
- **Effort 0.8.** Two sessions, both bounded.

## Kano

Package-level: must-have. The cost dimension is constitutive to the optimization-recommendation differentiator per D9; D41 commits the wiring; without P4 the optimization recommendations cannot produce the third recommendation shape that distinguishes Padhanam from observability tools that report data without recommending action.

Decision-level commitments set in framing:

- **Cost-ceiling configuration columns at S14:** must-have. Same logic D41 used for the cost-attribution column; avoidable retrofit is a learning failure given the case study's audit posture, and the columns are cheap to add at S14 versus expensive to migrate later.
- **S15 tenant context refactor (vs skip and close P4 at S14):** performance. The refactor is not strictly required for D41's cost commitment, but the option preserved (jurisdiction, classification, and routing extensions without subsequent refactor against three consumers at once) is worth one session of effort.
