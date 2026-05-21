# PRFAQ

Living storytelling artefact per D45's living-artefact commitment, refreshed at every phase audit. Versioned at every phase boundary per the standing rule. Press-release and FAQ sections in vendor product-launch voice for AI Labs teams and procurement audience per D51, in supersession of D45's case-study-voice-and-audience framing.

The active version is v2 (carryover-cleanup strategic session, 2026-05-06) onward. v1 is preserved below verbatim with its `[OPERATOR REWRITE — ...]` markers intact per D43's append-only-at-version-level discipline; the markers themselves are signal of the structural-form mismatch that prompted D51.

---

## Version 1 (P3 post-close strategic session) — initial draft

*[v1 framing note: This version was drafted in case-study voice per D45 and marked scaffolding pending operator rewrite. D51 superseded D45 on voice and audience; v2 below replaces both sections in vendor voice. The `[OPERATOR REWRITE — ...]` markers were canary signals of the structural-form mismatch that prompted D51.]*

### Press release [OPERATOR REWRITE — case-study positioning, external voice]

**A senior product leader publishes a year-long case study of directing enterprise-grade software implementation through AI-assisted development.**

The question for product organisations is no longer whether AI agents can write code. The question is what changes when they do, and specifically what changes for the people directing the work. Anecdotes about AI-assisted development are everywhere. Sustained, public, measurable evidence about whether the discipline scales to the level of complexity that real enterprise software requires is rare.

This case study generates that evidence. A senior product leader directs the implementation of an enterprise-grade agentic platform through Claude Code over the course of twelve packages of work. The platform is built to procurement-realistic standards: multi-tenant with database-per-tenant isolation, identity-federated, hash-chained audit, jurisdiction-aware from inception, OTel-instrumented for vendor portability, supply-chain-pinned. SOC 2 Type II and ISO 27001 are the architectural floor.

Every architectural decision is recorded with alternatives. Every methodology observation is captured. The decision log is append-only. The PRDs, roadmap, and PRFAQ are living documents with delta capture. The methodology is measured against DORA Four Keys and CORE4 dimensions, and the metrics are reported publicly including when they do not flatter the proposition.

The deliverables: the platform; the public commit history and decision log; the methodology document that captures the architect-implementer pattern with enough specificity that another senior product leader could read it and adopt the discipline. The platform proves the proposition holds at the level of complexity that real enterprise software requires. The methodology is the insight that travels.

[OPERATOR: this section needs your voice. The structure is functional; the prose is generic. The case study earns the artefact when the press release reads in the voice the target audience would believe.]

### FAQ [OPERATOR REWRITE — stakeholder voice]

**Why does this matter to senior product leaders right now?**

The L&D market for product leaders learning to direct AI-assisted development is expected to grow significantly through 2026 and 2027 as AI coding tools mature and the question of what they enable becomes more pressing for product organisations. Most public evidence is at the toy-prototype scale. Sustained evidence at enterprise architectural complexity, with measured methodology and an honest record of what worked and what didn't, is what the market is short on.

**Why this operator?**

Four years selling enterprise software into named accounts (Graphic Design Institute, VanArsdel, Coho Winery, Wide World Importers, Alpine Ski House, Woodgrove Bank, Southridge Video, and similar) means the operator already knows what enterprises require from the systems they buy and build. The case study tests whether that knowledge, plus AI-assisted development, plus the methodology emerging from the work, is sufficient to direct an enterprise-grade implementation end to end. The architectural decision log to date — D1 through D48 with non-trivial alternatives, 15+ import-linter contracts, multiple AST enforcement tests, append-only audit-trail discipline, hash-chained audit context, envelope encryption, supply-chain hardening with scheduled cadence — is evidence that the discipline is real. The Phase 1 close audit measures whether the methodology document derived from it is also real.

**What's the methodology?**

The architect-implementer pattern: a senior product leader directs Claude Code through structured session prompts, working modes are declared explicitly (strategic versus build), decisions are recorded in an append-only log with alternatives and Kano category, prioritisation is RICE-scored, PRDs and roadmap and PRFAQ are living documents with delta capture, and role-function audit (analyst, PM, architect, engineer, technical writer) at every phase boundary tests whether each function was exercised at quality. The methodology is descriptive at this stage; the methodology document matures across Phase 1 and is the deliverable that travels.

**What's the moat?**

Public, sustained, measured execution under enterprise-realistic constraints, with an append-only record that prevents the post-hoc framing common in AI-assisted-development case studies. The methodology document, derived from running the experiment in the open rather than constructed afterward, is what a different operator could read and adopt. Anyone with access to AI coding tools can build a prototype; the case study's evidence is that a senior product leader's discipline scales the work to enterprise complexity.

**What happens when the AI providers themselves ship platforms like this?**

The case study is investigating product leadership under AI assistance, not commercialising the platform. The platform is a demonstration. If frontier providers ship comparable platforms, the case study's evidence about how to direct end-to-end implementation through AI-assisted development remains the deliverable; the platform's commercial fortune is irrelevant to the proposition.

**Solo operator — why?**

The proposition is specifically about what one senior product leader can direct through AI-assisted development. A team would change the proposition into a different question (about team coordination under AI assistance) that's worth investigating but is not this case study's question. Phase 2 may take a different shape based on what Phase 1 surfaces.

**What about Phase 2?**

Decided at the Phase 1 close audit. Candidate shapes recorded as alternative version-1 stories: continued solo execution with productisation of the methodology as advisory and L&D content; productisation of the platform itself with enterprise tenants; or a different domain pivot if Phase 1 surfaces a stronger investigation. The audit picks one or surfaces a fourth, and v2 of this PRFAQ narrows accordingly.

[OPERATOR: each FAQ answer needs the stakeholder voice rewrite. The structure surfaces the questions; the answers are placeholder until they read in your voice.]

---

## Version 2 (P4-post carryover-cleanup strategic session) — vendor-voice rewrite per D51

### Press release

**Padhanam launches enterprise-grade agentic platform with observability that closes the cost-quality-latency loop**

Padhanam today announced the general availability of its enterprise-grade platform for building, running, auditing, and optimising agentic systems. Padhanam is multi-tenant from inception with database-per-tenant isolation, jurisdiction-aware architecture, hash-chained append-only audit, and OpenTelemetry as the observability portability boundary. The platform is built to SOC 2 Type II and ISO 27001 architectural floors, with supply-chain hardening — digest-pinned container images, SBOM generation, vulnerability scanning in CI — from the first deployment.

The platform's distinguishing feature is the optimisation recommendation surface. Every model completion is observed with token counts, latency components, and per-tenant cost in USD attached at the trace level. The recommendation engine consumes trace data, evaluation results, and active-test reports to produce three classes of recommendation: latency-shaped ("this is faster"), quality-shaped ("this is higher-quality"), and cost-quality-shaped ("this costs N% more for M% quality at the same task type"). The third class is what AI Labs teams have been asking for: optimisation advice that lands in the form procurement and finance partners can audit against actual billing.

"We've been waiting for an observability platform that produces decisions, not dashboards," said the Head of Platform Engineering at a frontier AI Labs customer. "Padhanam's per-tenant cost attribution at the trace level closes the loop between our model selection and our budget reporting. The recommendations our engineers receive are audit-ready by the time they reach our procurement team."

"Padhanam exists because the AI Labs teams we work with kept telling us their observability tools were collecting the right data and producing the wrong artefacts," said Padhanam's founder. "We built the platform around the recommendation shape procurement teams actually consume, with the architectural floor enterprise deployments require from day one. Phase 2 takes Padhanam to production deployment with federated identity, multi-region operation, and the SLA commitments enterprise customers rely on."

Padhanam is available now for evaluation deployments with AI Labs teams. Tenant onboarding is configuration rather than deployment; adding a tenant to an existing regional stack is an idempotent provisioning workflow. Pricing is consumption-based against per-tenant cost attribution. Production-grade federated identity (Keycloak, OIDC, SAML SP, SCIM 2.0) activates with Phase 2 deployment readiness per `charter/roadmap.md`.

### FAQ

**How does Padhanam differ from existing observability tools like Datadog, Honeycomb, or Grafana with OpenTelemetry collectors?**

Padhanam is OpenTelemetry-instrumented per D27, so existing OTel-compatible observability tools can consume the same traces Padhanam emits. The differentiator is at the recommendation layer rather than the trace store. Datadog, Honeycomb, and Grafana give engineering teams interactive dashboards over OTel data; Padhanam consumes the same trace data plus per-tenant cost attribution and produces recommendation-shaped output. The platform is a complement to general-purpose observability rather than a replacement: AI Labs teams already running Datadog or Honeycomb can keep them and use Padhanam for the agentic-systems recommendation layer.

**What's the deployment story?**

Phase 1 ships as a single-region local deployment (Docker Compose, mkcert TLS, fourteen services) for evaluation. Phase 2 adds production deployment to cloud regions with infrastructure-as-code provisioning, multi-region operation, and the supply-chain hardening enterprise procurement evaluates against. The platform is local-first per the architectural commitments: production swap is configuration via `padhanam/config/`, not a refactor. Local development uses mkcert TLS at the edge and accepts plaintext inside the Compose network; production deploys with mTLS internally.

**What's the data-residency story?**

Jurisdiction is a first-class architectural attribute. Tenant context carries jurisdiction from inception; every component that touches customer data — databases, object storage, identity, trace store, LLM endpoints — is built to be regionally partitionable. Phase 1 deploys a single region for evaluation; Phase 2 activates multi-region operation. Adding a region is a separate infrastructure event from adding a tenant. Per-tenant Postgres instances keep tenant data isolated to the tenant's jurisdiction at the database boundary, not at the row boundary.

**What's the cost model?**

Consumption-based against per-tenant cost attribution. Every model completion through the inference path emits four cost attributes on the trace span (`gen_ai.cost.input_usd`, `gen_ai.cost.output_usd`, `gen_ai.cost.total_usd`, `gen_ai.cost.pricing_status`). The pricing table covers the routed model set; vendor pricing is reviewed monthly. Per-tenant cost rollups are a single SELECT on the trace store; cost ceilings and progressive throttling activate in Phase 2 — the configuration columns are landed and the schema-level CHECK constraints pin the action enum so the enforcement architecture has a stable surface to consume.

**What's the SLA story for Phase 2?**

Phase 2-specific. Phase 1 is evaluation-grade single-region local deployment; SLAs activate alongside production deployment readiness in Phase 2. The architectural commitments that SLAs depend on — TLS via the configuration layer, mTLS in production posture, encryption-at-rest on persistent volumes via cloud KMS, audit-chain integrity, supply-chain hardening — are committed and shipping. The operational commitments — uptime targets, response times, support tiers — are framed at Phase 2 open.

**How does the optimisation recommendation surface integrate with existing AI Labs evaluation infrastructure?**

Padhanam's evaluation harness implements canonical interaction-set storage, replay engines, deterministic scoring, LLM-as-judge scoring, and regression reporting. Cost-per-successful-task is the lead metric; the recommendation engine consumes evaluation results alongside trace data and active-test reports. AI Labs teams running existing evaluation infrastructure (Promptfoo, RAGAS, OpenAI Evals, custom eval harnesses) integrate at the canonical-interaction-set boundary: import existing eval suites; the harness produces the regression reports and the recommendation surface consumes them. Direct adapters to specific eval frameworks activate as customer demand surfaces; the abstraction is in place to support them.

**What's the integration shape with existing identity providers?**

Phase 1 ships authentication middleware with a development signed-token backend, plus a Keycloak-shaped production backend stubbed at the interface. Federated identity (Keycloak realm, OIDC, SAML SP, SCIM 2.0) activates at Phase 2 per D52, in supersession of D3's original Phase 1 commitment; the architecture is identity-ready, but real federated identity demonstrations against enterprise IdPs require production deployment context Phase 1 does not have. AI Labs teams evaluating Phase 1 use the dev signed-token backend; pilot deployments at Phase 2 connect to the customer's existing IdP through the production-shaped Keycloak backend.

**What's the multi-tenant architecture?**

Database-per-tenant: every tenant has its own Postgres instance with per-tenant Alembic migration tracks. The control-plane Postgres instance holds the tenant registry and operator-administered data; tenant data planes are separate Postgres instances. Credentials live in the tenant registry as envelope-encrypted blobs, with three leak-prevention controls (logging filter, AST test forbidding plaintext-in-state, tenant-isolation tests). Tenant isolation is verified by red-team-shaped tests: every adapter touching tenant-scoped data has cross-tenant access tests that attempt unauthorised reads and assert they fail. Adding a tenant is an idempotent provisioning workflow; in Phase 1 dev, instance creation is operator-manual via Compose; in Phase 2, infrastructure-as-code automates instance creation.

---

## v2 in-flight correction (Phase 1 / Phase 2 boundary strategic block, 2026-05-13)

D93 (the Phase 1 / Phase 2 boundary strategic block) commits Phase 2 direction to methodology-as-product positioning with focus purely on UX/UI. The commitment supersedes D51's voice-and-audience choice for PRFAQ v3 at the Phase 1 close audit at P12 close per D45's living-artefact cadence.

v2 content reflects D51's voice and audience: vendor product-launch voice; AI Labs teams and procurement audience. Specific elements now misaligned with D93's direction:

- **Press release framing.** v2 announces Padhanam as a platform for AI Labs teams ("Padhanam is available now for evaluation deployments with AI Labs teams"). D93 commits methodology-as-product positioning; v3's press release reframes around the methodology and the discipline pattern productised for senior product leaders, CPOs, and consultancies per `bet.md` line 57.
- **Customer quote.** v2's customer quote is attributed to "Head of Platform Engineering at a frontier AI Labs customer" focused on observability dashboards and per-tenant cost attribution at the trace level. D93's audience is senior product leaders; v3's customer-equivalent quote reframes around methodology adoption and the productised discipline.
- **Founder quote.** v2's founder quote names Phase 2 production deployment with federated identity, multi-region operation, and SLA commitments as the path. D93's Phase 2 path is purely UX/UI on top of complete Phase 1 substrate, with the methodology-as-product commercialisation path per `bet.md` line 67 ("L&D, advisory, content, and senior-role positioning rather than a product company"). v3's founder-equivalent quote reframes around methodology-as-product positioning rather than platform-as-product.
- **FAQ orientation.** v2's eight FAQ questions answer procurement-shaped concerns (vs Datadog/Honeycomb, deployment, data residency, cost model, SLA, evaluation integration, identity integration, multi-tenant architecture). D93's audience asks methodology-shaped questions: what methodology does this productise, what does adoption look like, how does the discipline pattern travel, what's the L&D and advisory path. v3's FAQ reframes around the methodology-as-product audience's questions.

v2 body preserved verbatim above per D43's append-only-at-version-level discipline; this correction is recorded as a separate section rather than as an in-place edit to v2. v3 revoice lands at the Phase 1 close audit at P12 close per D45's living-artefact cadence (every phase audit produces a new PRFAQ version). The Phase 1 close audit refresh also absorbs the dogfooding scenario acknowledgment per D77 and D78 per the existing carryover entry in `charter/current-package.md`.

## Phase 2: methodology-as-product (PRD section, post-v2 extension; v3 revoice defers to Phase 2-A close audit)

Padhanam ships Phase 2 as methodology-as-product per D93. The platform's Phase 1 substrate (procurement-grade defensibility, hash-chained audit trail, OpenAPI-specified consumer surfaces) is the foundation; Phase 2 surfaces the methodology that the substrate makes operable.

**Three-mode operation.** The Padhanam Private Assistant operates in three modes that share one substrate. Attentional mode primes the user's attention at the threshold of context with declarative briefings. Workflow mode executes tasks on the user's request, with consent gates at permission moments. Observation-and-suggestion mode tracks the user's world quietly and surfaces gaps as offers phrased as questions. The three modes are not separate products; they are aspects of one assistant.

**Meta-layer positioning.** Padhanam is a meta-layer over the user's existing apps. Calendar apps stay the calendar. To-do apps stay the to-do list. Email clients stay the email client. Padhanam reads from these for observation and writes to them on request, but does not duplicate their function. The platform does not do reminders; the user's reminder app does. The platform aggregates, primes, observes, and suggests; it does not replace the surfaces that already work.

**Substrate vocabulary.** Phase 2 commits to a domain vocabulary: Case, Data Point, Assertion, Workflow, Step, Signal, Gate, Intake, Provenance. This vocabulary is shared across Phase 2 surfaces, audit-trail records, and the methodology library. The vocabulary aligns with the karma prior-art specification per the karma-lineage discipline.

**Forward-compat posture (Layer 1 positioning).** Phase 2-A ships narrow at surface and deep-where-deferral-forces-refactor at substrate. The platform commits foundational substrate now if deferring would force a major code refactor when the substrate becomes operational; the platform defers substrate with a named activation trigger otherwise; the platform flags build-now substrate that operator dogfooding does not exercise, with the test-coverage gap documented for Phase 2-A close audit. The discipline is named "deferral-forces-refactor" and runs as a build-methodology candidate through Phase 2-A. Per-substrate Layer 2 classification lives at `charter/packages/p13-epic.md` and updates at each Phase 2-A package framing.

**Senior-leader-ICP commitment.** Phase 2 ships to a senior product leader as the first user, with the operator-as-first-instance acting as the proof point. The ICP commitment lives at `charter/phase-2-user-segment.md`; the test condition for Phase 2-A close validates that the operator-as-first-instance behaviour generalises to the broader ICP at signal strength sufficient to commit Phase 2-B scaling.

**Phase 2-A close gate condition.** Phase 2-A closes against operational thresholds plus dogfooding-evidence thresholds. The gate condition tests both that the substrate runs reliably under real use and that the operator-as-first-instance signals validate the senior-leader-ICP test condition. The full prfaq v3 revoice lands at the close audit with Phase 2-A build evidence behind it.

**Communication discipline.** Padhanam's surfaces honour the Private Assistant Communication Discipline (declarative not imperative; suggestion-as-question; subtle not pushy; specific over generic; visible reasoning; no compliance language) committed at `charter/principles.md` at P13. This discipline binds every Phase 2 surface design decision regardless of channel.

---

## Version log

- **v1** (P3 post-close strategic session). Initial draft. Press-release and FAQ sections drafted in case-study framing per D39's reframe. Operator rewrite required before this version is read as load-bearing.
- **v2** (P4-post carryover-cleanup strategic session, 2026-05-06). Press release and FAQ rewritten in vendor product-launch voice for AI Labs teams and procurement audience per D51, in supersession of D45's case-study-voice-and-audience commitment. D45's living-artefact commitment, append-only version log, and phase-audit refresh cadence preserved unchanged. Press-release shape standardised on vendor-PR form: vendor announces platform, named target customer quote attributed to representative role ("Head of Platform Engineering at a frontier AI Labs customer") rather than fabricated name, named executive quote attributed to representative role ("Padhanam's founder") rather than fabricated name. Real names land at v3 onward if real partners or operator name attribution becomes appropriate. FAQ rewritten to answer eight procurement-shaped questions (versus general-purpose observability tools, deployment, data residency, cost model, SLA, evaluation integration, identity integration, multi-tenant architecture). v1 preserved verbatim above with the v1-framing note that relocates the original "drafts below are scaffolding" paragraph as v1-context per D43's append-only-at-version-level discipline. Reasoning category implicit per D51: the case-study voice misjudged the structural form of the PRFAQ artefact; v1's `[OPERATOR REWRITE — ...]` markers signalled the mismatch as canary signal that prompted D51.
