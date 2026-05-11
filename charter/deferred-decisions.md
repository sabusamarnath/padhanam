# Deferred Architectural Decisions

Architectural commitments deferred to future sessions. They are inherited by sessions when their context activates. Reviewed at phase audits.

Format mirrors `decisions.md` but each entry names the package or session that will activate the commitment and lock it as a numbered D-entry.

## Orchestration architecture

Activates when orchestration enters the codebase (P5 or wherever orchestration first lands).

**Orchestration is a context with multiple ports, each modelling a distinct mode of operation.** At minimum, `WorkflowExecutor` for workflow orchestration (operator-defined steps and transitions; LangGraph, Temporal, CrewAI in declarative mode, future entrants) and `AgentExecutor` for agent orchestration (operator-provided tools and instructions; model-defined runtime control flow; OpenAI Agents SDK, Anthropic agent loop patterns, CrewAI in autonomous mode, future entrants). Additional ports for additional modes as they prove necessary.

**The discipline rule applies to both modes.** Business logic does not live in orchestration code. For workflows: use cases own decisions, the workflow definition is the bridge. For agents: tools own capabilities, the agent definition is the boundary. Use cases and tools are shared across all orchestrators within their respective modes.

**Adapters declare which ports they implement.** LangGraph implements `WorkflowExecutor`. OpenAI Agents SDK implements `AgentExecutor`. CrewAI implements both. New entrants implement whichever ports fit. Configuration in `apps/*/main.py` wires the right adapter for each port based on `padhanam/config/`.

**Provider coupling is configuration.** Provider-coupled agent orchestrators (OpenAI Agents SDK, Anthropic-specific patterns) are legitimate adapters. The routing logic in `padhanam/config/` decides when their use is appropriate. D4's provider-agnosticism applies to the default path; provider-specific paths are opt-in per workload.

**Tools are domain artefacts with a port abstraction.** When tools enter the codebase, they live behind a domain-level `Tool` abstraction. Adapters expose domain tools in specific protocols and formats. MCP is a strong default for tool exposition where external interoperability is intended, given its momentum, but the architectural commitment is to the domain port, not the MCP protocol specifically. If MCP consolidates as the cross-vendor standard, Padhanam leans on it. If a successor protocol emerges, Padhanam adapts. The protocol choice is configuration; the abstraction is architecture.

**Cross-orchestrator portability has defined bounds.** Use cases and tools are portable across all orchestrators that can invoke callables. Workflow definitions are portable across workflow orchestrators within feature-parity bounds. Agent definitions are portable across agent orchestrators within feature-parity bounds. Cross-mode portability (workflow as agent or vice versa) is not supported and should not be attempted; the modes are different operations. Framework-specific features are exposed through clearly-marked escape hatches (e.g., `langgraph_specific_features` namespace) and are framework-locked by acknowledgement.

**Feature promotion process for orchestration ports.** When a feature originating in one framework appears to be supported by others, promotion from framework-specific escape hatch to portable abstraction follows a defined process: (1) at least three independent frameworks support the feature with stable semantics; (2) Padhanam has at least one workload that has needed the feature in production or evaluation; (3) the feature can be expressed in domain terms without reference to any specific framework's idiom. Promotion is a deliberate session: the feature is added to the relevant domain abstraction, every adapter implements or declares unsupported, the contract test suite gains coverage, escape-hatch usages migrate, and the promotion is recorded as an architectural decision. The escape-hatch alias remains for one promotion cycle (approximately six months) before removal. Periodic audits at phase boundaries review escape-hatch contents for promotion candidates and for removal of features that never proved useful.

**A/B testing across orchestrators is supported via parallel adapter execution.** The same `WorkflowDefinition` or `AgentDefinition` runs through multiple adapters; the comparison harness in `tests/integration/orchestration/` (or in a dedicated benchmark module) captures outputs and traces for evaluation. Orchestrator parity is a contract test category: every adapter implementing a port must pass the same orchestration contract tests, ensuring that "swap" means something at runtime, not just at design time.

**Specific D-entries land when each adapter lands.** Premature commitment to specific frameworks ahead of integration is paper architecture.

### Data-plane ownership

Activates in Phase 2 architectural commitments.

**Trace history that feeds the recommendation engine flows into Padhanam-owned storage, not Langfuse-only.** Architectural reason: a multi-tenant platform serving analytical workloads over trace data should not depend on a single observability vendor's data layer for queries that go beyond operational observability. Vendor lock-in at the analytical-data layer is the kind of architectural debt that compounds and is expensive to unwind later. Traces flow into Langfuse for operational observability *and* into Padhanam's own store for analytical use, behind a unified retrieval interface. This commitment is independent of any future decision about whether the platform is commercialised; the architectural correctness holds either way.

**Durable agent state lives in domain tables, not orchestrator-managed checkpointers.** When stateful long-running agents land (Phase 2 or later), the durable state lives in Padhanam-owned Postgres tables. Orchestrator checkpointers are for ephemeral graph state only. This makes orchestrator swap meaningful even for stateful agents and keeps long-lived state under the same tenant-isolation, audit, and jurisdiction guarantees as other domain data. Treating durable state as orchestrator-managed would couple the platform to a specific framework's lifecycle assumptions and undermine the multi-orchestrator portability that the orchestration architecture commitment is built around.

Both architectural commitments will be made explicit in Phase 2 with specific D-entries when the data shapes are known.

## Per-tenant supply-chain surveillance for tenant-supplied tools and extensions

Activates when tools and extensions enter the codebase (P5 or wherever tools and extensions first land).

**Tenant-supplied artefacts have their own dependency trees and require per-tenant surveillance distinct from platform supply-chain monitoring.** Each tenant's registered tools (external services called on the tenant's behalf, per D14) and uploaded extensions (sandboxed code at named interfaces, per D14) carry their own dependencies. Padhanam scans these at registration, re-scans on a schedule against updated CVE databases, and notifies the tenant of vulnerabilities in their artefacts.

**The mechanism is the tool-and-extension registry, not the platform supply-chain process.** Different system, different cadence, different audience. Platform supply-chain checks (governed by `ops/scheduled_checks.yaml`) are operator-reviewed and operator-merged. Per-tenant artefact scanning is tenant-notified and tenant-actioned, with platform-side enforcement (e.g., disabling a tool registration with a critical CVE that the tenant has not addressed within a defined window).

**Configuration scope follows tenant agency.** Tenants have agency over which tools they register and which extensions they upload, and therefore over the surveillance posture for those artefacts (notification preferences, severity thresholds for auto-disable, grace periods). They do not have agency over the platform's own supply-chain monitoring.

**The specific D-entry lands when tools and extensions enter the codebase.** Premature commitment to specific scanning tools, severity thresholds, or notification mechanisms ahead of integration is paper architecture.

## Methodology metrics

Activates at first package close for the package-level computation, and at first phase audit for the phase-level computation. Session-level capture begins immediately upon adoption of the tagging format that will be specified in `methodology.md` (pending operator authorship per D39).

**The methodology is measured against DORA Four Keys and CORE4 dimensions.** Capture at every session, computation at every package close, trend analysis at every phase audit. The metrics are reported publicly as part of the case study, with package-level numbers added to package retrospectives and phase-level numbers added to phase audit entries.

**Definitions are explicit and adapted where necessary.** Deployment frequency uses "merged-to-main frequency" as a proxy in Phase 1 and shifts to traditional deployment frequency from Phase 2 onwards if a hosted environment exists. Change failure rate is defined as sessions whose output is later corrected by a subsequent session within the same phase. The full definitions are pending in `methodology.md` per D39 and D40.

**Reporting tooling is deferred.** Initial computation is manual at package close and phase audit; if and when the manual computation becomes a meaningful overhead, a small script under `tools/metrics/` computes the numbers from session log tags. Premature tooling commitment ahead of the data shape stabilising is paper architecture.

**Honest reporting is a discipline.** Periods of poor methodology performance are reported alongside periods of strong performance. The case study's credibility depends on honest measurement, including when the metrics do not flatter the proposition. If at any phase audit the trend suggests the methodology is not sustaining performance, the bet document and methodology document are revised to reflect what was actually learned.

**The specific D-entry lands at the first package close with computed metrics.** The architectural commitment is recorded now in `decisions.md`; the operational commitments (specific computation tooling, specific reporting format, specific benchmark comparisons) are made when the data exists to inform them.

## Cost ceilings, multi-tier model routing, progressive throttling

Activates at Phase 2 framing.

**Per-tenant USD ceilings, multi-tier model routing based on task complexity, and progressive throttling at named thresholds.** D41 commits cost capture and per-tenant attribution from Phase 1 (P4 wiring and P4 schema migration) but defers the enforcement architecture to Phase 2. Phase 1 runs single-model in dev (D15: Qwen 2.5 7B via Ollama), so there is no multi-tier routing to enforce against and no production traffic against which ceilings would bite. The configuration columns for ceilings can land in P4 alongside the cost-attribution column to avoid retrofit; the enforcement architecture (which tier to route which task type to, which threshold triggers throttling, what the operator-facing controls look like) lands at Phase 2 when production traffic exists and routing has signal to react to.

**The specific D-entry lands when ceiling enforcement enters the codebase.** Premature commitment to specific threshold percentages, throttling mechanisms, or routing tiers ahead of integration is paper architecture.

## Multi-currency cost reporting

Activates at Phase 2 framing when the first non-USD-jurisdiction tenant enters scope.

**Cost reporting evolves from USD-only to amount-plus-currency shape.** Phase 1 cost capture (D49) and the cost-query path (D57) embed USD across OTel span attributes (`gen_ai.cost.input_usd`, `gen_ai.cost.output_usd`, `gen_ai.cost.total_usd`), the `CostBreakdown` value object on TraceQueryPort, and the `CostPerSuccessfulTaskResult.cost_per_task_usd` field. The single-currency commitment was implicit, falling out of vendor pricing being in USD plus dev-environment defaults; the architectural commitment was not made deliberately, which the methodology Failure modes section records.

**The evolution shape is amount-plus-currency at every cost-bearing surface.** OTel span attributes shift to `gen_ai.cost.input.amount` plus `gen_ai.cost.input.currency` (or whatever the OTel GenAI conventions group converges on); `CostBreakdown` and `CostPerSuccessfulTaskResult` gain explicit currency fields; the pricing table at `padhanam/config/inference.py` declares per-model currency. Vendor pricing remains USD-quoted in dev; production deployments with non-USD-jurisdiction tenants resolve currency conversion at the trace-store query layer (per-tenant currency preference applied at read time, not write time, so historical traces remain queryable in their original currency).

**The specific D-entry lands when the first non-USD tenant arrives.** Premature commitment to specific currency-conversion mechanics, specific FX-data sources, or per-tenant currency-preference-resolution policy ahead of integration with a real non-USD-jurisdiction customer is paper architecture. D12 commits jurisdiction as the architectural attribute that drives the evolution; the migration follows D12's "by construction, not by policy" framing once the second jurisdiction enters scope.

## Step-mode-shaped automation for narrow task types

Activates at Phase 1 close audit, with implementation at Phase 2 if the audit produces a safe-task-type list.

**Step-mode-shaped agent assistance for routine task types.** Once Phase 1 produces sustained methodology evidence, certain task types may become safe for higher automation: dependency bumps following `ops/scheduled_checks.yaml`, schema migrations following established patterns, eval-harness execution against pre-designed tests, supply-chain scanning and triage in pre-defined categories. Full auto mode stays out permanently because it conflicts with the architect-implementer pattern's append-only discipline, the D-entry alternatives requirement, the reflection-density expectation, and the two-surface mode-declaration discipline (D47). Step-mode-shaped engagement preserves operator approval at every unit boundary.

**The Phase 1 close audit produces the safe-task-type list.** That list is the input to the Phase 2 D-entry that commits to specific automation surfaces.

## Brownfield-shaped onboarding artefact for additional contributors

Activates when a contributor (human or model) approaches the project who has not been part of the existing operator-led history.

**Brownfield-shaped onboarding artefact synthesised from the charter.** The charter is currently the operating context, hand-maintained, and onboarding is the operator reading it. The moment a second contributor arrives, the friction surfaces as a real gap. The cheap version is a script that walks the charter and produces a single distilled `ONBOARDING.md`; the expensive version is full brownfield codebase scanning. The activation condition is contributor scaling becoming a real planning question, not an anticipation of it.

**The specific D-entry lands when contributor scaling becomes a real planning question.** Premature commitment to specific synthesis tooling is paper architecture.

## Full DORA and CORE4 instrumentation

Activates at Phase 2 framing.

**Full DORA instrumentation when production deployment exists.** D40 commits the methodology to DORA Four Keys and CORE4 measurement; `methodology.md` (pending operator authorship per D39) will adapt the definitions for Phase 1 (deployment frequency proxied by merged-to-main frequency; mean time to restore deferred until production traffic exists; change failure rate defined per same-phase corrective sessions). Phase 2 framing activates the full instrumentation when a hosted environment exists, deployment frequency means deploys-to-production, and MTTR measures real restoration. CORE4's effective developer experience axis activates fully when team scaling or productisation makes it load-bearing; Phase 1 partial coverage tracks what is tractable now via reflection density and operational-friction signals.

**The specific D-entry lands at Phase 2 framing.** Operational commitments (tooling, format, benchmarks) are deferred per D40's deferral structure.

## Methodology mechanical-enforcement upgrades

Items absorbed from the methodology comparison process that are committed in principle but await mechanical implementation. The principle landings live in `charter/methodology.md`; this section tracks what activates each upgrade.

**Decision-to-code translation gate.** A CI test that walks new D-entries and asserts they appear in commits or session prompts within N sessions of being committed. Promotes the existing operator-discipline check into mechanical enforcement. Activation: when the discipline-adherence metrics in `charter/methodology.md` produce a measured baseline against which the gate's threshold can be set honestly. Earliest meaningful activation: Phase 1 close audit.

**Per-package reconciliation gate (mechanical).** D43 commits the structural pattern: epic note at package open, archive at package close, delta as audit deliverable. Mechanical enforcement would assert that every closed package has both files and that the archive references the epic note's commitments. Activation: when the epic-note convention has run for at least two packages (P4 and P5) and the reconciliation pattern has stabilised. Earliest activation: P5 close.

**Adaptive per-package reassessment as explicit prompt.** Standing reflection prompt at session close: does the rest of the package plan still hold given what this session surfaced? Activation: integrated into the session-close template at the next P-boundary strategic session (P4→P5 boundary).

**`make doctor` for operational drift.** Detection of orphan Compose projects, stale virtualenv interpreters, port collisions, drifted image digests, basic git hygiene. Activation: when operational drift surfaces as a session-open failure mode three times across the package boundary, per the structural-promotion threshold from the S11–S12 reflection. Tracked at session opens; the count is the activation condition.

**Session-close walkthrough template (checkpoint-preview pattern).** Standing template: what was the intent, what changed, what was verified, what is the residual risk. Activation: integrated into the session-close template at the next P-boundary strategic session (P4→P5 boundary), alongside the adaptive reassessment prompt above.

**Edge-case hunter procedural shape in phase-audit template.** Procedural checklist for phase audits: boundary input, empty input, malformed input, concurrent actor, retry, partial failure. Activation: integrated into the Phase 1 close audit template; reviewed for coverage at the audit and refined for Phase 2.

**Proper-noun-attribution check on model-drafted vendor-voice artefacts.** A check flagging named-person or named-company attributions introduced in model-drafted artefacts in external/vendor voice (PRFAQ, press-release-shaped content, case-study quotes), requiring explicit operator confirmation before the commit lands. Surfaced from the second Failure modes entry in `charter/methodology.md` (2026-05-06, fabrication-class drift in model-drafted vendor-voice content). Until the mechanical check lands, the operator's discipline is to challenge any name attribution surfaced in model-drafted external-voice content with a "who is [name]?" question. Activation: a recurrence of proper-noun-attribution drift in any model-drafted vendor-voice artefact, or routine pull from the upgrades backlog at a phase audit.

These are performance-category improvements: each scales the bet linearly by reducing operator-discipline reliance in favour of mechanical enforcement. None is must-have for Phase 1 close, which is why they sit here rather than in the active package's scope. Phase audits review the activation backlog and pull items into specific packages where conditions warrant.

## Learning store for accumulated knowledge

Activates at Phase 2 alongside the workflow context implementation per D83.

**Accumulated knowledge persists separately from any specific framework output.** As an agent works across sessions, it builds product-specific learning (what the user prefers, what's worked, what hasn't, accumulated context). This learning is separate from any specific playbook's outputs (LVT bets, RICE scores, Kano classifications). The learning store is what feeds revision-mode invocations of playbooks; the agent draws on accumulated knowledge to revise prior outputs.

**Shape choice deferred.** Two candidates: a generic learning store as its own bounded context (`contexts/learning/` or similar); or accumulated knowledge as agent-state extensions per agent. Choice settles when the workflow context lands and the revision-mode mechanics are designed against real consumers.

**Specific D-entry lands at Phase 2** when the data shape stabilises against real workflow context implementation.

## Revision mode in playbooks

Activates alongside the learning store at Phase 2.

**Each playbook needs a revision mode in addition to its initial-application mode.** The LVT playbook applied for the first time decomposes from scratch (bet, initiative, epic, story). The LVT playbook applied in revision mode loads existing bets, picks up accumulated learning from the learning store, and walks the user through "which bets still hold; which should change; what's new." Same shape for RICE (re-score as evidence shifts) and Kano (reclassify as options evolve).

**Playbook authoring includes both modes.** A methodology aggregate at Phase 2 contains both initial-mode and revision-mode logic per role-reference. Phase 1 playbooks (LVT, McKinsey 7-Step authored at S26b) declare the modes structurally without runtime support; Phase 2 implementation activates revision execution.

**Specific D-entry lands at Phase 2** when the runtime mechanics design against real consumers.

## Output aggregates for framework outputs

Activates alongside the learning store and revision mode at Phase 2.

**Framework outputs need structured persistence.** When an agent applying LVT produces a bet definition, the output currently lives only in the conversation. For revision-mode later, the agent needs a stored record of what it concluded. Bets, RICE scores, Kano classifications, McKinsey 7-Step intermediate artefacts all become stored outputs the agent can reference across sessions.

**Aggregate shape candidates.** Three candidates: a generic output aggregate that holds typed outputs (bets, scores, classifications) with a discriminator; per-playbook output aggregates (LVTOutput, RICEScore, KanoClassification); outputs as agent-state extensions. Choice settles when revision-mode design forces the shape.

**Specific D-entry lands at Phase 2** when the design stabilises.

## Skills aggregate (Phase 2 capability concept)

Activates at Phase 2 alongside the gallery shape per D77 and D78.

**Skills are agent-acquired procedural capabilities modelled on the Claude Skills pattern.** A skill is a folder with SKILL.md plus resources, context-activated at runtime. Multiple agents can reference the same skill. Methodologies recommend skills per role (soft); agents own skill selection.

**Bounded context shape deferred.** Two candidates: `contexts/skills/` as a new bounded context (sharp independence; sibling to `contexts/methodology/`); or skills within `contexts/methodology/` (smaller architectural shift; lower bounded-context-count cost). Phase 2 evidence on cross-methodology reuse patterns and gallery surfaces drives the choice.

**Adapter choice.** Claude Skills is one adapter to the skills abstraction per D17 (no vendor SDKs in domain code; architecture commits to abstraction; adapter is configuration).

**Specific D-entry lands at Phase 2** when consumer evidence drives the bounded-context choice and the runtime mechanics design.

## Per-tenant topology for Neo4j

Activated at S21 per D63 with the choice of a shared Neo4j 5 Community instance and property-based tenant scoping enforced through a `TenantScopedNeo4jSession` wrapper at the adapter boundary (raw `neo4j` driver imports forbidden outside the wrapper by the `neo4j-confined` import-linter contract plus AST enforcement test) plus tenant-isolation contract tests on both reads and writes. The entry remains as the activation marker for the production-deployment revisit, when per-tenant Neo4j containers may earn back their roughly 1GB-RAM-per-tenant local-dev cost against production isolation, residency, or operational requirements that Phase 1 does not yet exercise.

**Tenant isolation is non-negotiable however the topology lands.** Property-based scoping at Phase 1 is structurally gated by the wrapper plus contract tests; per-tenant containers at production-deployment context would shift the structural gate from the wrapper to the connection-resolution layer (one bolt URL per tenant, mirroring D36's per-tenant Postgres engine cache) without changing the discipline at the integration test layer.

**Revisit triggers.** Production-deployment context with one or more of: (1) a tenant whose data-residency requirements forbid co-location of graph data even under property scoping; (2) measured operational pressure where a single shared Neo4j instance's blast radius (one tenant's runaway extraction job degrading every other tenant's read latency) becomes a real production concern; (3) a security-review finding that property-based scoping is insufficient against a specific threat model the production deployment must defend. None of the three apply at Phase 1 scope; all three are credible at production scale.

## Personalization as a runtime concern

Activates at P8 agent runtime or whichever predecessor orchestration session demands it.

**Personalization is runtime presentation logic conditioned on user context, not retrieval scope or agent reasoning.** The same retrieved data and the same agent reasoning render differently based on who is asking. A specialist user with deep domain context receives a detailed answer; a generalist user receives a summary version. The shape is presentation conditioned on identity, not different paths through retrieval or different agent decisions.

**The user context object carries the conditioning attributes.** Tenant, jurisdiction, and cost_attribution_id are already present in `TenantContext` per D50. Role and possibly user-preference fields extend the context object when personalization enters. The orchestration layer carries the context through to the personalization point.

**Personalization architecturally separates from retrieval and from agent reasoning.** Retrieval scope (what data is accessible) is a separate concern from presentation (how accessible data is rendered). Agent reasoning (what the answer should be) is separate from presentation (how the answer is shown). Conflating any of the three produces logic that is hard to evaluate independently and hard to extend without refactor.

**The specific D-entry lands at P8 framing or the orchestration session that introduces a personalization consumer.** The architectural shape commits in advance; the implementation choice (separate orchestration node, parameter on response template, dedicated personalization port) settles when the consumer arrives.

## Per-tenant compliance evidence aggregation (Layer B)

Activates when a real tenant compliance use case demands it, or at Phase 2 framing as a candidate package, whichever surfaces first.

**The substrate already exists.** Audit chain per D26 and D35 records every state change with actor, jurisdiction, before/after state, and correlation ID. Supply-chain scanning per D25 produces dated scan output via `make scan` and `ops/scheduled_checks.yaml`. Tenant isolation contract tests per D24 produce pass-rate evidence via `make test`. Conventional commits referencing package and session number per the Engineering practice principle constitute change-management evidence. Package retrospectives in `log/packages.md` per D40 constitute operation-of-controls evidence over time.

**What defers is the report-shaping pipeline.** Audit-chain queries scoped per tenant; evidence aggregation use cases composing the substrate above into auditor-consumable reports; the auditor-export format (PDF, structured JSON, or specific GRC-platform import shape); the tenant-facing CLI or UI surface for evidence retrieval.

**The specific D-entry lands when the package frames.** Premature commitment to specific report shapes ahead of a real tenant audit consumer is paper architecture. Estimated package size when activated: medium. Sized similar to P10 audit log viewer.

## Workflow compliance frames (Layer C)

Activates when three prerequisites all hold: (1) Padhanam's own SOC 2 Type II or ISO 27001 audit has completed (Phase 2 production deployment work; the inheritance map cannot reference controls in a report that does not yet exist); (2) the workflow taxonomy has stabilised across multiple methodologies (post-P7 with at least three methodology templates in production, so the frame structure is not authored against a single workflow's idiosyncrasies); (3) tenant demand for tenant-product attestation has surfaced as a real procurement requirement rather than a hypothetical one (real-consumer prerequisite mirroring the S15 classification deferral pattern).

**Frame structure when authored.** Each workflow compliance frame carries: data-flow defaults, sensitivity classification defaults, retention defaults, incident shape defaults (the C1 data-protection scaffolds); control objective mappings naming SOC 2 Trust Services Criteria and ISO 27001 Annex A controls applicable to applications built with this workflow; CUEC inheritance map showing which Padhanam controls cover which tenant control objectives, with residual control objectives flagged as tenant-operated; control activity scaffolds describing typical implementations for tenant-operated controls in this workflow class (the C2 framework-attestation inheritance maps).

**Methodology aggregate field extension.** When Layer C activates, the methodology aggregate at `contexts/methodology/domain/methodology.py` extends with a compliance-frame field. Per D31's revision-shape, this lands as a future revision rather than a schema migration; existing methodology templates inherit a default empty frame until populated.

**The specific D-entry lands when the package frames.** Premature commitment to specific frame structures ahead of the audit-completion prerequisite is paper architecture. Estimated package size when activated: large. Sized as a multi-session package given the per-workflow content authoring effort.

## Forkable-vs-non-forkable architecture for commercial deployment

Activates if Phase 2 takes commercial direction.

**Candidate separation lines.** Open-and-forkable (core platform, generic methodology templates, generic tool implementations) versus hosted services (recommendation engine, optimisation surfaces, multi-tenant administrative dashboard) versus licensed content (premium methodology library, sector-specific compliance scaffolds, expert-authored agent templates). The separation is not architectural until Phase 2 frames commercial direction; the candidate lines are surfaced here to seed the future commitment rather than to fix it now.

**Relationship to D14 and D76.** D14 commits the customer-deployment scenario (configuration + tools + bounded extensions, no fork) and D76 refines the principle to "designed so forking is unnecessary." Both hold for the open Phase 1 codebase. Commercial direction at Phase 2 introduces the licensing-and-trademark question that D76 explicitly excluded from its scope: which mechanisms (open licence terms, hosted-service exclusives, trademark-protected branding, premium licensed content) actually enforce the platform's commercial commitments without retreating to "forking is forbidden" wording the open-source community sees through.

**The specific D-entry lands when Phase 2 commercial framing is committed.** Premature commitment to specific separation lines ahead of Phase 2 framing context is paper architecture per the project's deferred-decisions discipline. If Phase 2 does not take commercial direction, this entry is closed without a numbered D-entry landing.

## Calendar tool service as platform capability

Activates when public Padhanam needs a calendar integration for any package work (potentially P9 source ingestion, P10 active testing, or P11 recommendation surfaces) or when the operator's personal-use deployment Phase C activates (post-P8 close per D78), whichever comes first.

**Calendar tool is a generic capability with broad applicability.** Implementation lives as a separate service per D14's tools-as-configuration commitment; the platform calls the calendar tool through whatever protocol the tool exposes (HTTP or MCP) without absorbing calendar logic into Padhanam's codebase. The service handles OAuth, scope management, and the calendar provider's API; Padhanam's tool registry stores the configuration that points to it.

**The specific D-entry lands when implementation begins**, capturing protocol choice (HTTP versus MCP), authentication shape, and integration scope. Premature commitment to a specific calendar provider, protocol, or authentication mechanism ahead of integration is paper architecture.

## Email tool service as platform capability

Activates when public Padhanam needs an email integration for any package work (potentially P9 source ingestion, P10 active testing, or P11 recommendation surfaces) or when the operator's personal-use deployment Phase C activates (post-P8 close per D78), whichever comes first.

**Email tool is a generic capability with broad applicability.** Same architectural shape as the calendar tool entry: separate-service implementation per D14, tool-registry configuration points to it, protocol-and-auth choice deferred to the implementation moment.

**The specific D-entry lands when implementation begins**, capturing protocol choice, authentication shape, and integration scope. Premature commitment ahead of integration is paper architecture.

## Scheduled-runs primitive

Activates when public Padhanam needs scheduled agent execution (potentially P11 recommendation engine or P12 active testing for periodic regression checks) or when the operator's personal-use deployment Phase C activates and needs daily-review-style triggers (per D78), whichever comes first.

**Two implementation candidates.** Platform primitive (Padhanam supports cron-shaped agent triggers internally) versus external trigger (cron job or scheduled task calling Padhanam's API on schedule). The platform-primitive shape would live under `padhanam/orchestration/` as a scheduling concern coordinated with the agent runtime; the external-trigger shape would live as a documented operational pattern with the API as the integration boundary.

**The specific D-entry lands when implementation begins**, capturing the choice with reasoning about operator-deployment ergonomics, multi-tenant fairness under shared scheduling load, and the failure-mode boundary (a scheduled run that fails: who notices, who retries, where the audit lands). Premature commitment ahead of a real consumer is paper architecture.

## Generic personal-productivity methodology templates as public reference content

Activates if the operator finds during Phase C of the personal-use deployment (post-P8 close per D78) that generic methodology templates (GTD, Eisenhower matrix, time blocking) authored for the operator's personal deployment have value as reference implementations for future tenants of the public Padhanam codebase.

**Public versus private template distinction.** The operator's privately-iterated working version stays in the operator's personal control plane regardless of any public-reference decision. The candidate is a separate generic template authored on the public Padhanam control plane that surfaces personal-productivity methodology in the same shape as LVT, RICE, Kano, and other professional methodologies will: as platform-managed templates that any tenant can clone into their own agent.

**The specific D-entry lands at the moment the operator decides to author a public reference template**, capturing scope and the public/private template distinction. The activation is operator-discretion at Phase C; this entry exists to surface the option, not to commit to it.

## Cascading-harm invariant shape

Activates when multi-agent workflows or persistent agents enter the codebase.

**Cascading-harm invariant captures bounded blast radius, per-invocation cost ceilings beyond per-agent limits, rate limits on outbound effects, and propagation containment.** Single-agent invocation at Phase 1 does not produce the risk surface; one agent invocation cannot amplify into many downstream consequences. Workflow execution (Phase 2 per D83) and persistent agents (the scheduled-runs primitive deferred-decisions entry) both introduce the risk surface and trigger this invariant's specific shape.

**The specific D-entry lands at the package or session that activates the invariant**, capturing the shape (workflow-level rate limits, cascade-detection heuristics, abort-on-budget-exceeded semantics, audit signal shape) with reasoning about the consumer that pulled it in. Premature commitment to specific cascade-prevention mechanics is paper architecture.

## Retrieval-bound hard-constraint shape on methodology roles

Activates when methodology evidence shows soft-binding of retrieval fields insufficient.

**Per-field hard caps on a role's retrieval surface (max_top_k, allowed_strategies, min_min_score, max_filter_complexity).** Current D81 commitment treats `retrieval_strategy`, `filter_tree`, `top_k`, `min_score` as soft-bound (methodology defaults; agent overrides freely). The captures synthesis named retrieval bounds as one of the four constraint surfaces methodology declares per role; D81 deferred the hard-constraint shape pending consumer evidence.

**The specific D-entry lands at the methodology authoring session that surfaces the need**, with consumer evidence about which retrieval fields require hard caps. Premature commitment ahead of consumer evidence risks over-constraining methodology authors.

## Per-role binding-mode override

Activates when methodology evidence shows the platform-level binding-mode convention (three hard, six soft per D81) insufficient for a specific methodology's needs.

**Methodology authors choose binding mode per role per field, overriding the platform-level default.** Current D81 commitment is a platform-level convention: methodology authors do not choose binding mode based on the field's nature; the platform decides. The override is forward affordance for compliance-shaped methodologies (a regulatory methodology might want `system_prompt` hard for control purposes, or `model_selection` hard for jurisdiction-specific reasons).

**The specific D-entry lands at the methodology authoring session that surfaces the need**, with reasoning about the override mechanism (per-field annotation on the role bundle; precedence between platform default and role override). Premature commitment ahead of consumer evidence adds complexity without benefit.
