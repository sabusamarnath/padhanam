# P12 Phase 2 inputs

This file consolidates the P12 audit's strategic input set for the subsequent Phase 2 packaging conversation. The granularity is high-level per the P12 brief's Finding 3 disposition: deferred-item-to-package-candidate mapping, architectural rework observations, and strategic-tree input observations. Granular package framing (LVT placement, RICE scoring, dependency structure) belongs at Phase 2's strategic-mode opening session — this file surfaces inputs and observations, not pre-emptive Phase 2 packaging.

The audit's verdict per `charter/p12-audit-findings.md` is that the bet's load-bearing claims hold at Phase 1 close; Phase 2 inherits a complete substrate to build against per D93's methodology-as-product positioning. This file is the audit-output bridge between Phase 1's substrate-completion and Phase 2's strategic-mode opening.

## Phase 2 package candidates from deferred-decisions

Deferred-decisions entries that mature into Phase 2 package candidates at the strategic-mode opening conversation. Each candidate is one paragraph; Phase 2 framing decides which become packages, which absorb into other packages, and which defer further.

### Browser-based authentication

Cookies, CSRF, session management. D23's signed-token backend is operator-only; consumer UX needs proper session handling. Listed as "Phase 1 close substrate-completion session" carryover in `charter/current-package.md`. Phase 2 candidate: substrate-completion session at Phase 2 open, before the first consumer-UX package; small scope (one substrate session); enables the methodology-as-product audience to authenticate without operator-shaped flow. Strong candidate for the first Phase 2 package alongside the frontend stack confirmation.

### Frontend stack confirmation or commitment

React 19 / Vite 6 / React Router 7 are pinned at D10 as pre-S1 baseline; Phase 2 open confirms or revisits, plus chooses a UI library or commits to an in-house design system grounded in `charter/brand-guidelines.md` and `charter/brand/tokens.css`. Listed as "Phase 1 close substrate-completion session" carryover. Phase 2 candidate: strategic-mode decision block at Phase 2 open (not a build session); the decision input feeds every subsequent consumer-UX package. Coupled with browser-authentication above.

### HTTP API for ingestion management

The P6-deferred-then-P10-absorbed HTTP API for ingestion management landed at S38 commit chain per D104. Listed in `charter/deferred-decisions.md` as Phase 2 substrate-completion fallback if structural drift surfaces at S38. The audit verifies S38 closed the surface; the entry can be retired at Phase 2 framing. Note for the strategic-mode block: no Phase 2 packaging implication.

### HTTP API for evaluation management

Mentioned in `charter/current-package.md` "Carryovers active across the P8→P9 boundary" as "HTTP API for evaluation management" deferred to "when a UI consumer arrives at P10 or P11; under D93 lands as Phase 1 substrate completion at P10 or P11." S42 absorbed the evaluation HTTP carryover per D112's coupling-commitment 1. The audit verifies S42 closed the surface; the entry can be retired at Phase 2 framing. Note for the strategic-mode block: no Phase 2 packaging implication.

### Calendar tool service plus email tool service plus scheduled-runs primitive

Three deferred-decisions entries with same activation shape: public Padhanam needs the integration for any package work, OR the operator's personal-use deployment Phase C activates per D78. Phase 2 candidate: bundle into a single "external tool services" Phase 2 package alongside the personal-use deployment Phase C activation. Operator-discretion timing on Phase C activation (post-P8 close per D78) shapes whether this lands at Phase 2 open or later. The platform-primitive-vs-external-trigger choice for scheduled-runs settles at this package's framing.

### Gold-set aggregate-level audit-emission back-fill

Per `charter/p12-audit-findings.md` Section 3 entry 10's disposition: extend `contexts/retrieval_evaluation/application/` use cases (create_gold_set, append_entry_to_revision, finalize_revision, plus a new `rename_gold_set` use case which today does not exist) to emit audit events on aggregate-level mutations. The rename surface is part of the gap surfacing — S39b's rename was a direct SQL UPDATE. Operational specificity: estimated half-session of substrate work; lands at Phase 2-entry hygiene window before consumer-UX work begins. Procurement-grade-readiness consequence: closes the audit-evidence-claim gap that the audit identifies as known carryover.

### Graph-extract pipeline reliability — reclaim-after-timeout policy

Per `charter/deferred-decisions.md` graph-extract entry. Three structural pieces (reclaim policy, worker-side asyncio timeout, optimistic-concurrency-control on reclaim) needed. Estimated substrate work: one full session. Phase 2 candidate: lands at Phase 2-entry hygiene window alongside the gold-set audit-emission back-fill above; both are pre-consumer-UX Phase 2-substrate-completion work. Activation trigger if pulled forward: the first Phase 2 package framing that depends on graph retrieval producing entities reliably (workflow agents per D83 with graph-evidence-bearing roles).

### Workflow context implementation alongside the LangGraph adapter

D83 commits the workflow context as a new bounded context at `contexts/workflow/` with charter-only commitment at Phase 1; Phase 2 implements alongside consumer-grade UX and the LangGraph adapter per D84. Phase 2 candidate: substantive package alongside consumer-UX surface work. The workflow-as-architectural-primitive substrate (Phase 2's largest single architectural surface) carries: WorkflowTemplate + WorkflowRevision aggregates; topology JSONB shape; WorkflowExecutor port; LangGraph adapter; cross-context lookup ports for methodology and agent; tenant-isolation contract tests; CLI surface. Operator-judgement at framing: package or multi-package scope.

### Gate-as-workflow-step topology category

D83's topology categories (sequential, conditional, reflective) extend with a fourth category (gate) at Phase 2 workflow context implementation. Per the deferred-decisions entry, the gate-type vocabulary commits at the topology amendment. Bundled with the workflow context implementation above; not a standalone Phase 2 package.

### User-authored taps as workflow-attached checkpoints

Per the deferred-decisions entry "User-authored taps as workflow-attached checkpoints." Activates at Phase 2 workflow context implementation. Bundled with the workflow context implementation above; possibly its own Phase 2 sub-package if scope warrants.

### Learning store + revision mode + output aggregates for framework outputs

Three coupled deferred-decisions entries activating at Phase 2 alongside the workflow context implementation per D83. Phase 2 candidate: bundled package alongside workflow context, since revision mode operates over methodology aggregates and the learning store is the substrate that makes revision mode meaningful. Operator-judgement at framing on bundle-vs-split.

### Skills aggregate

Per D86's sub-commitment (d), skills defer to Phase 2 as a separate bounded context (`contexts/skills/`) or as `contexts/methodology/`-internal capability. Bounded-context-shape choice settles at Phase 2 evidence on cross-methodology reuse patterns and gallery surfaces. Phase 2 candidate: sized as one substrate package alongside the consumer-UX gallery work.

### Methodology mechanical-enforcement upgrades

Six items in the methodology mechanical-enforcement upgrades section at `charter/deferred-decisions.md` (decision-to-code translation gate, per-package reconciliation gate mechanical, adaptive per-package reassessment as explicit prompt, `make doctor` for operational drift, session-close walkthrough template, edge-case hunter procedural shape, proper-noun-attribution check). Each is performance-category per the principles' Kano framing; none is must-have for Phase 2. Phase 2 framing pulls items into specific packages where conditions warrant; the audit observes the backlog is healthy and can absorb most items as embedded hygiene rather than dedicated sessions.

### Personalization as a runtime concern

Per the deferred-decisions entry, activates at P8 agent runtime or whichever predecessor orchestration session demands it. Phase 1 did not surface the consumer that demands it; Phase 2 consumer-UX surfaces may. Note for Phase 2 framing: not standalone package candidate; bundled into the agent-runtime evolution or workflow context work when the consumer materialises.

### Per-tenant Neo4j topology

Activated at S21 per D63 with Phase 1 shared-instance + property-based scoping. The deferred-decisions entry remains as production-deployment revisit marker. Phase 2 candidate: not standalone; revisits at production-deployment context with three named triggers (residency, blast radius, security-review). Operator-judgement at production-deployment time on which trigger fires.

### Per-tenant tool authoring + per-tenant supply-chain surveillance for tenant-supplied tools

D89's per-tenant tool authoring lift defers to Phase 2 when consumer evidence (a tenant-supplied tool, a compliance-driven per-tenant tool diversity requirement, or D78's personal-use deployment) materialises. The supply-chain-surveillance deferred-decisions entry activates at the same trigger. Phase 2 candidate: bundled package alongside the personal-use deployment Phase C work; activation timing follows operator-discretion on Phase C.

### Layer A policy authoring (compliance documentation scaffolds)

Carryover from P7 close: ten policy scaffolds at `charter/compliance/` per the compliance-as-shared-responsibility principle. Estimated one strategic-block session. Phase 2 candidate: lands at the Phase 2 SOC 2 / ISO 27001 audit-preparation block alongside per-tenant compliance evidence aggregation (Layer B) and workflow compliance frames (Layer C). Three-layer compliance work bundles into a Phase 2 strategic-mode block; specific packaging settles at that block.

### Per-tenant compliance evidence aggregation (Layer B) + Workflow compliance frames (Layer C)

Per the deferred-decisions entries. Phase 2 candidates: same shape as Layer A — bundled into compliance work at Phase 2. Layer B activation: real tenant compliance use case demand or Phase 2 framing as candidate package. Layer C activation: requires the three prerequisites in the deferred-decisions entry (Padhanam's own SOC 2 / ISO 27001 audit completed, workflow taxonomy stabilised, tenant demand). Operator-judgement at Phase 2 framing on which Layers activate.

### Forkable-vs-non-forkable architecture for commercial deployment

Per the deferred-decisions entry. Activates only if Phase 2 takes commercial direction. D93 commits Phase 2 to methodology-as-product positioning (L&D, advisory, content, senior-role positioning per `bet.md` line 67), which sits outside platform-commercialisation territory. The deferred-decisions entry's framing holds: this entry closes without a numbered D-entry landing unless Phase 2 strategic-mode block surfaces a commercial direction change.

### Multi-currency cost reporting

Activates when first non-USD-jurisdiction tenant arrives. Phase 2 framing decides whether to lift the deferral proactively (as part of D12's "by construction" posture extension) or to wait for actual tenant trigger. Operator-judgement at framing.

### Cost ceilings, multi-tier model routing, progressive throttling

Activates at Phase 2 framing. Phase 2 candidate: the cost ceilings configuration columns landed at P4 alongside cost-attribution per D41; the enforcement architecture (multi-tier routing, throttling, operator-facing controls) is Phase 2 work. Estimated substrate work: one substrate package alongside or coupled to the production-deployment infrastructure work.

### Full DORA and CORE4 instrumentation

Activates at Phase 2 framing when production deployment exists. Phase 1 partial coverage is in place via reflection density and operational-friction signals; Phase 2 full instrumentation requires deployment frequency, MTTR, change failure rate measured against production. Bundled with the production-deployment infrastructure work.

### Optimization-engine cost-per-successful-task threshold tuning

Per the new deferred-decisions entry added at P12 audit's commit 7. Activates when a tenant operates against vendor APIs at non-trivial cost rates with at least one full month of run history, or when Phase 2 UX surfaces a tenant-operator-configurable threshold surface. Phase 2 candidate: not standalone; bundled with the optimization-UX consumer surface work or the production-deployment-infrastructure work.

## Architectural rework observations

Areas where Phase 1's architecture surfaced finding-shape concerns that may need attention before Phase 2 scales the substrate or the consumer surface.

### Graph-extract pipeline reliability (the primary example per the P12 brief)

Per `charter/deferred-decisions.md` graph-extract entry plus `charter/p12-audit-inputs.md` entry 13 plus `charter/p12-audit-findings.md` Section 3 entry 13. Production-deployment context with multiple worker processes amplifies the failure mode; the reclaim policy is non-negotiable at production. Phase 2-entry hygiene window absorbs the work or first Phase 2 production-deployment work absorbs it; operator-judgement on which.

### Gold-set aggregate-level audit emission

Per `charter/deferred-decisions.md` gold-set entry plus the same audit-inputs / audit-findings cross-reference. Phase 2-entry hygiene window absorbs; the rename surface needs a new use case which today does not exist (audit-emission gap and missing-use-case gap are the same gap).

### Schema.md formalisation of cross-cutting shapes

Per `charter/p12-audit-findings.md` Section 4 audit-surfaced entry 17. `TenantContext`, `ErrorResponse`, and the canonical cursor codec shape are well-defined in code but not in the binding-specification surface. Phase 2-entry hygiene window absorbs as schema-supplement workitem; small scope (one half-session of doc work). Not architectural rework strictly speaking — hygiene work — but worth listing here for completeness of the Phase 2-entry workitem set.

### Doc-content rebrand from "(pending operator authorship per D39)"

Per `charter/p12-audit-findings.md` Section 1 Finding T2 and D113's note on doc-content refresh. CLAUDE.md "Methodology capture" section and `charter/deferred-decisions.md` "Methodology metrics" entry plus "Methodology mechanical-enforcement upgrades" preamble still carry the stale framing. Hygiene work, not architectural rework. Phase 2-entry hygiene window absorbs.

## Strategic-tree input observations

Observations relevant to the Phase 2 strategic-mode opening conversation's LVT placement and roadmap version update.

### Methodology-as-product is the load-bearing direction commitment per D93

D93 commits Phase 2 direction; the strategic-tree v6 entry at `charter/roadmap.md` lands at Phase 2 packaging's opening conversation per the P12 brief's "Out of scope" framing. The Phase 2 LVT placement work organises around the three-wave sequencing in D93's body: (a) consumer-facing UX first (gallery, methodology adoption flow, agent-authoring surface, run-history-as-learning surface, methodology library UI); (b) trust-and-evidence layer second (audit-and-trust surface for tenant operators, active-testing reports); (c) optimisation UX third (procurement-grade recommendation surface that closes the bet's success criterion 4).

### Phase 1's role-function distribution audit at audit close

The P12 audit observes (per the methodology document's roles-tag discipline per D46) that P11 sessions exercised a healthy distribution across analyst, PM, architect, engineer, and technical writer functions. Phase 2 framing inherits this surface; the role-function audit at Phase 2 close compares Phase 2's distribution against Phase 1's. Operator-relevance: the bet's "all five product-leader functions can be sustained through AI-assisted implementation" claim depends on the distribution holding across phases.

### Phase 1's session-shape distribution as Phase 2 framing input

P11 alone produced six sessions across five shapes (S39 substrate, S39b bridge, S40 substrate, S40b bridge, S41 substrate, S42 transport, pre-P12 hygiene). The shape distribution suggests Phase 2 substrate work may produce a similar mix; framing the Phase 2 strategic-mode opening with explicit shape-vocabulary lets the operator anticipate session sequence rather than discover it reactively. The "Session shapes" sub-section in the methodology document v2 update is the vocabulary surface.

### Phase 2's bet-criterion-4 close: optimisation UX as the load-bearing deliverable

D92 names success criterion 4 as closing fully at Phase 2 when the optimisation UX ships. The substrate at Phase 1 close (procurement-grade defensibility per S41's verdict, OpenAPI specification at S42 as Phase 2 UX-consumer interface contract) is what Phase 2 UX consumes; the deliverable is the rendering surface that surfaces recommendations to the procurement-grade audience. The optimisation UX wave is third in D93's three-wave sequencing because consumer-grade UX foundations need to land first and the audience for optimisation UX (procurement readers) is distinct from the audience for consumer-UX foundations (methodology adopters).

### Phase 2 framing decision: bundle Phase 2-entry hygiene work or distribute

Phase 2 inherits a set of hygiene workitems (gold-set audit-emission back-fill; graph-extract reclaim policy; schema.md formalisation; doc-content rebrand). Bundling into a single Phase 2-entry hygiene-shaped session (one or two sessions) mirrors the pre-P12 hygiene precedent; distributing across the first three or four Phase 2 packages absorbs the work incrementally. Operator-judgement at Phase 2 framing; the audit observes both shapes are valid and the trade-off is between concentrated-hygiene-overhead (the bundled shape) vs distributed-context-switching (the absorbed shape).

### Roadmap version update at Phase 2 opening

D44 commits the living-roadmap pattern with reasoning categories on every change. Phase 2 packaging's opening conversation lands a v6 entry at `charter/roadmap.md` reflecting the Phase 2 package commitments. Reasoning categories per D44 (discovery, capacity, signal, hedge). The v6 entry framing is Phase 2 strategic-mode opening's deliverable, not P12 audit-output.

## Phase 2 entry handoff

The audit's output for the Phase 2 packaging conversation:

1. `charter/p12-audit-findings.md` — the audit's consolidated deliverable (three findings sections plus dispositions plus cross-reference index plus audit-verdict summary).
2. `charter/p12-audit-inputs.md` — the input set the audit acted on (fourteen P11-session methodology candidates plus the audit's per-entry disposition annotations once propagated by the Phase 2 framing block; the file remains for Phase 2 audit-trail reference).
3. `charter/methodology.md` — v2 update with discipline-pattern-taxonomy Patterns-observed entries and the Session shapes sub-section; the methodology document is the proprietary insight the platform demonstrates and Phase 2 consumers (a senior product leader adopting the discipline) read this document.
4. `charter/decisions.md` — D113 supersession of D39's pending-authorship framing; principles.md line 45 amended in place at the same commit.
5. `charter/deferred-decisions.md` — three refreshed entries (gold-set audit emission, graph-extract reliability, plus new optimization-engine cost-threshold tuning entry).
6. This file (`charter/p12-phase-2-inputs.md`) — the bridge between Phase 1's close and Phase 2's opening.

The Phase 2 strategic-mode opening conversation reads these six artefacts plus the bet (`charter/bet.md`), the PRFAQ at the candidate Phase 2-direction articulation (`charter/prfaq.md`), the principles file (`charter/principles.md`), and the roadmap (`charter/roadmap.md`) at v5. Phase 2 framing produces a v6 roadmap entry plus a Phase 2 PRD (or extends the Phase 1 PRD with the Phase 2 living-document section per D43) plus the first Phase 2 package's epic note.
