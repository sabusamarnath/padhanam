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
