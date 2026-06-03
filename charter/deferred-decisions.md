# Deferred Architectural Decisions

Architectural commitments deferred to future sessions. They are inherited by sessions when their context activates. Reviewed at phase audits.

Format mirrors `decisions.md` but each entry names the package or session that will activate the commitment and lock it as a numbered D-entry.

When a numbered D-entry closes a deferred entry, the entry gains a "Status: closed by D<n>, <date>" header line; the body remains for audit-trail purposes per the append-only discipline.

## Table of contents

1. [Architectural primitives awaiting activation](#architectural-primitives-awaiting-activation)
2. [Phase 2 substrate completion](#phase-2-substrate-completion)
3. [Production-deployment readiness](#production-deployment-readiness)
4. [Workflow context extensions](#workflow-context-extensions)
5. [Methodology and governance enhancements](#methodology-and-governance-enhancements)
6. [Compliance and security](#compliance-and-security)
7. [Tool registry and authoring](#tool-registry-and-authoring)
8. [Phase 1 close audit findings](#phase-1-close-audit-findings)
9. [Phase 2 design 7-Step deferrals](#phase-2-design-7-step-deferrals)
10. [Phase 2-A P13 framing deferrals](#phase-2-a-p13-framing-deferrals)
11. [P13 S45 deferrals](#p13-s45-deferrals)

## Architectural primitives awaiting activation

### Orchestration architecture

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

#### Data-plane ownership

Activates in Phase 2 architectural commitments.

**Trace history that feeds the recommendation engine flows into Padhanam-owned storage, not Langfuse-only.** Architectural reason: a multi-tenant platform serving analytical workloads over trace data should not depend on a single observability vendor's data layer for queries that go beyond operational observability. Vendor lock-in at the analytical-data layer is the kind of architectural debt that compounds and is expensive to unwind later. Traces flow into Langfuse for operational observability *and* into Padhanam's own store for analytical use, behind a unified retrieval interface. This commitment is independent of any future decision about whether the platform is commercialised; the architectural correctness holds either way.

**Durable agent state lives in domain tables, not orchestrator-managed checkpointers.** When stateful long-running agents land (Phase 2 or later), the durable state lives in Padhanam-owned Postgres tables. Orchestrator checkpointers are for ephemeral graph state only. This makes orchestrator swap meaningful even for stateful agents and keeps long-lived state under the same tenant-isolation, audit, and jurisdiction guarantees as other domain data. Treating durable state as orchestrator-managed would couple the platform to a specific framework's lifecycle assumptions and undermine the multi-orchestrator portability that the orchestration architecture commitment is built around.

Both architectural commitments will be made explicit in Phase 2 with specific D-entries when the data shapes are known.

### Personalization as a runtime concern

Activates at P8 agent runtime or whichever predecessor orchestration session demands it.

**Personalization is runtime presentation logic conditioned on user context, not retrieval scope or agent reasoning.** The same retrieved data and the same agent reasoning render differently based on who is asking. A specialist user with deep domain context receives a detailed answer; a generalist user receives a summary version. The shape is presentation conditioned on identity, not different paths through retrieval or different agent decisions.

**The user context object carries the conditioning attributes.** Tenant, jurisdiction, and cost_attribution_id are already present in `TenantContext` per D50. Role and possibly user-preference fields extend the context object when personalization enters. The orchestration layer carries the context through to the personalization point.

**Personalization architecturally separates from retrieval and from agent reasoning.** Retrieval scope (what data is accessible) is a separate concern from presentation (how accessible data is rendered). Agent reasoning (what the answer should be) is separate from presentation (how the answer is shown). Conflating any of the three produces logic that is hard to evaluate independently and hard to extend without refactor.

**The specific D-entry lands at P8 framing or the orchestration session that introduces a personalization consumer.** The architectural shape commits in advance; the implementation choice (separate orchestration node, parameter on response template, dedicated personalization port) settles when the consumer arrives.

### Skills aggregate (Phase 2 capability concept)

Activates at Phase 2 alongside the gallery shape per D77 and D78.

**Skills are agent-acquired procedural capabilities modelled on the Claude Skills pattern.** A skill is a folder with SKILL.md plus resources, context-activated at runtime. Multiple agents can reference the same skill. Methodologies recommend skills per role (soft); agents own skill selection.

**Bounded context shape deferred.** Two candidates: `contexts/skills/` as a new bounded context (sharp independence; sibling to `contexts/methodology/`); or skills within `contexts/methodology/` (smaller architectural shift; lower bounded-context-count cost). Phase 2 evidence on cross-methodology reuse patterns and gallery surfaces drives the choice.

**Adapter choice.** Claude Skills is one adapter to the skills abstraction per D17 (no vendor SDKs in domain code; architecture commits to abstraction; adapter is configuration).

**Specific D-entry lands at Phase 2** when consumer evidence drives the bounded-context choice and the runtime mechanics design.

### Scheduled-runs primitive

Activates when public Padhanam needs scheduled agent execution (potentially P11 recommendation engine or P12 active testing for periodic regression checks) or when the operator's personal-use deployment Phase C activates and needs daily-review-style triggers (per D78), whichever comes first.

**Two implementation candidates.** Platform primitive (Padhanam supports cron-shaped agent triggers internally) versus external trigger (cron job or scheduled task calling Padhanam's API on schedule). The platform-primitive shape would live under `padhanam/orchestration/` as a scheduling concern coordinated with the agent runtime; the external-trigger shape would live as a documented operational pattern with the API as the integration boundary.

**The specific D-entry lands when implementation begins**, capturing the choice with reasoning about operator-deployment ergonomics, multi-tenant fairness under shared scheduling load, and the failure-mode boundary (a scheduled run that fails: who notices, who retries, where the audit lands). Premature commitment ahead of a real consumer is paper architecture.

### API mediation layer at the consumer boundary

Activates at Phase 2 framing if any of the following surface: heterogeneous consumer surfaces (mobile alongside web alongside partner integrations), third-party API consumers, or scale where systematic demand-supply visibility across producers and consumers becomes operationally useful.

**The pattern is real and has names.** Anti-corruption layer in domain-driven design, API gateway at the infrastructure level, backend-for-frontend when one mediator serves each consumer surface, GraphQL as the fully-realized exchange (producer publishes a schema, consumers query what they want, resolvers match demand to supply), and CQRS read models when each consumer projects its own view of producer events.

**Padhanam already uses a lightweight version of this.** The consumer-port-plus-wiring-adapter pattern, reinforced four-plus times across S26a through S29b and on the candidate list for methodology promotion, is itself a mediation layer at the cross-context boundary. The consumer defines a port shaped to its DTO; the producer exposes use cases at its `api.py`; the wiring adapter at the application layer matches between them. What this lightweight version does not provide is the demand-supply visibility surface a formal mediation layer offers: there is no queryable artefact for "what each context publishes versus what consumers actually use." That visibility is currently a code-review concern, not a first-class output.

**Why the formal mediation layer does not earn its place at Phase 1.** The market dynamics that justify it do not apply: one team building both sides, six bounded contexts not sixty, one main consumer surface (CLI now, Phase 2 UX next). The slowdown identified in the framing conversation (three parties to align instead of two, every change touching the mediator) would be a real tax against thin benefit at this scale. Schema drift is not yet a real problem because the codebase is young and refactoring is fast.

**Where the formal mediation layer might earn its place at Phase 2.** The HTTP API surface that Phase 2 UX consumes is producer-defined by necessity, and a GraphQL-shaped surface there gives Phase 2 the demand-supply matching property explicitly: producer publishes a schema, consumers query exactly what they need, resolvers handle the match. BFF-per-consumer is the alternative if heterogeneous consumer surfaces materialize (mobile and web wanting different shapes of the same data). Both shapes sit cleanly on top of the per-tenant Postgres substrate P9 ships, so no Phase 1 commitment forecloses either path.

**The specific D-entry lands at Phase 2 framing when the actual consumer surface is concrete.** Premature commitment ahead of that context is paper architecture.

### Multi-scope monitoring architecture

Activates at the Phase 2 framing strategic block, when workspace and authoring substrates land alongside multi-tenant deployment.

**Substrate is largely in place from Phase 1.** OTel trace attributes carry scope identifiers (tenant_id at minimum; workspace_id, agent_id, user_id once Phase 2's authoring and workspace substrates land), the trace store at P9 is the canonical event source, the structured event vocabulary from S29b's agent runtime carries per-iteration data, and the cost-per-task dimension from D41+D49 is wired through every LLM call. The monitoring surface itself, how that substrate gets aggregated and presented per scope, is the Phase 2 design surface.

**Scope hierarchy is explicit:** platform > client (tenant) > workspace > agent/workflow > user. Each scope has owner/admin views covering their scope and below, plus self views covering only themselves. The user-scope view is the smallest scope; what was previously framed as a separate "end-user-facing monitoring" surface is the user-scope view in this hierarchy, not a parallel architecture.

**Three architectural commitments anticipated.**

First: per-scope aggregation, shared substrate. The trace store is the canonical surface; per-scope monitoring is a subscriber pattern filtering the same event stream by scope attributes. Aggregation logic is scope-parameterised, not duplicated per surface. Cost-per-task at client scope sums across workspaces; at workspace scope, per-agent; at agent scope, per-invocation; at user scope, per-session.

Second: RBAC follows scope hierarchy. Permission to view monitoring at a given scope inherits from the existing tenancy model. A client admin sees client-and-below; a workspace admin sees workspace-and-below; users see only their own invocations.

Third: CLI-first, web-dashboard-later. The `padhanam monitor` shape gains scope flags (`--scope workspace --id <uuid>`). The web dashboard sits downstream of the CLI substrate and lands as part of the Phase 2 product UI surface.

**Four open architectural questions resolve at adoption.**

First: metric-to-scope mapping. Cost-per-task probably appears at all scopes. Per-LLM-call latency probably useful only at agent/workflow scope and below. Queue depths probably only at platform scope. The explicit mapping needs framing at the design block.

Second: cross-scope views. A workspace admin sometimes wants to compare two agents within their workspace; a client admin sometimes wants to compare two workspaces. Cross-scope-comparison is a separate surface from filter-and-aggregate; whether it gets a first-class shape or composes from existing scope views is open.

Third: end-user UX commitments at user-scope. Progress indicators with ETA, "what's happening right now" views, transparent failure messaging are product features that depend on Phase 2's UI commitments. The substrate (SSE event stream from S29b) is in place; the product UX surface isn't.

Fourth: relationship to P11 optimization recommendations. P11 currently consumes trace data and produces recommendations at single-scope. Multi-scope monitoring implies P11 also gains scope-awareness; the recommendation engine becomes scope-parameterised. This is a non-trivial extension of P11's current shape and may itself merit a separate deferred-decisions entry once the monitoring framing is settled.

**Design reference.** Karma's scope-attached-resource framework provides the structural precedent for how monitoring views attach to specific scopes; the same shape that informs the user-authored-taps and multi-stage-gates deferred entries extends to scope-attached-monitoring-views. The CLI shape mirrors `padhanam monitor` against the existing `padhanam agent`, `padhanam role`, and `padhanam methodology` command family.

**The specific D-entries land at the Phase 2 framing strategic block** when the workspace and authoring substrates land. The architectural commitments above anticipate the substrate; the four open questions resolve at adoption.

## Phase 2 substrate completion

### HTTP API for ingestion management (Phase 2 substrate completion)

Status: closed by D104, 2026-05-14.

Activates when a UI consumer (Phase 2 frontend or external tool) needs HTTP-driven ingestion management. Triggers at the first concrete user story demanding it.

**The P6 deferred carryover absorbed into P9 at framing did not land within P9.** D60's original carryover deferred the HTTP API "until a UI consumer arrives at P9 or P10"; D93 reframed the UI consumer as Phase 2 UX; the P9 epic note at framing absorbed the carryover into P9 substrate-completion. S34's strategic-mode framing settled the pivot from ingestion-management to run-history HTTP routes on Kano-must-have-for-Phase-2-UX grounds; S35 closes P9 via end-to-end demonstration of the run-history substrate rather than landing the ingestion-management API, because the CLI surface for ingestion is in place at Phase 1 and no Phase 2 UX consumer has materialised to justify sequencing the API ahead of P10/P11 optimisation substrate.

**The substrate is fully in place.** The ingestion use cases at `contexts/ingestion/application/` exist, are exercised by the CLI, and are tenant-scoped via `TenantContext`. The HTTP exposure is mechanical: principal-derived tenant context per the S29b precedent at `apps/api/routers/agent.py`, error response shape per the S34 D98 precedent at `apps/api/_errors.py`, route definitions wrapping the existing use cases. Estimated work when activated: one session.

**The specific D-entry lands at the activating session.** Premature commitment to specific route shapes, payload structures, or error vocabulary ahead of a real Phase 2 UX consumer story is paper architecture. References: D60 (the original P6 deferral with HTTP-API-after-UI-consumer framing); D98 (the run-history HTTP shape the ingestion API would mirror at the request and error layers).

### Per-invocation retrieval constraint threading at the ToolInvoker (refined scope per D105)

Per-role retrieval constraints (top_k, min_score, strategy overrides) flowing through to the ToolInvoker on each invocation. D105 closes the allowlist piece (adding the retrieval tool to role allowlists at P11 open) and narrows this entry to the per-invocation constraint threading work only.

**Activation trigger.** First Phase 2 use case demanding per-invocation override of role-level retrieval defaults.

### Platform-curated cross-tenant retrieval gold sets

Tenants author their own gold sets at P11 per D105. Platform-curated cross-tenant gold sets defer to the same activation condition D53 set for platform-curated scoring sheets.

**Activation trigger.** A real onboarding flow per D13, or a cross-tenant curated gold-set library with at least one real consumer beyond demoware.

### Phase 2 UX for richer gold-set authoring

The Phase 1 substrate is the CLI flow (query, retrieve, mark, save) per D105. Phase 2 UX adds richer authoring: browsing past agent runs, converting their citations from `run_chunk_citations` and `run_entity_citations` into candidate gold-set entries, suggested chunks based on the retrieval surface.

**Activation trigger.** Phase 2 methodology-as-product UX work reaches the gold-set authoring surface per D93's wave sequencing.

### Graded relevance and nDCG metric

Binary relevance (chunks marked correct or not, ordered list as the entry shape) at P11 per D105. Graded relevance (per-chunk 0/1/2 grades) and the nDCG ranking-aware metric land if consumer evidence demands.

**Activation trigger.** Recommendation engine surfaces evidence that binary relevance is losing signal worth capturing, or a methodology-specific gold set demands graded relevance.

### Online retrieval evaluation (extracting signal from production agent runs)

Offline gold-set evaluation only at P11 per D105. Online signals defer because they require a labelling layer (human judgement on production retrieval quality) which is the same shape as D55's calibration loop.

**Activation trigger.** P11 close audit surfaces evidence that offline-only evaluation misses production retrieval problems the recommendation engine should be catching.

## Production-deployment readiness

### Cost ceilings, multi-tier model routing, progressive throttling

Activates at Phase 2 framing.

**Per-tenant USD ceilings, multi-tier model routing based on task complexity, and progressive throttling at named thresholds.** D41 commits cost capture and per-tenant attribution from Phase 1 (P4 wiring and P4 schema migration) but defers the enforcement architecture to Phase 2. Phase 1 runs single-model in dev (D15: Qwen 2.5 7B via Ollama), so there is no multi-tier routing to enforce against and no production traffic against which ceilings would bite. The configuration columns for ceilings can land in P4 alongside the cost-attribution column to avoid retrofit; the enforcement architecture (which tier to route which task type to, which threshold triggers throttling, what the operator-facing controls look like) lands at Phase 2 when production traffic exists and routing has signal to react to.

**The specific D-entry lands when ceiling enforcement enters the codebase.** Premature commitment to specific threshold percentages, throttling mechanisms, or routing tiers ahead of integration is paper architecture.

### Multi-currency cost reporting

Activates at Phase 2 framing when the first non-USD-jurisdiction tenant enters scope.

**Cost reporting evolves from USD-only to amount-plus-currency shape.** Phase 1 cost capture (D49) and the cost-query path (D57) embed USD across OTel span attributes (`gen_ai.cost.input_usd`, `gen_ai.cost.output_usd`, `gen_ai.cost.total_usd`), the `CostBreakdown` value object on TraceQueryPort, and the `CostPerSuccessfulTaskResult.cost_per_task_usd` field. The single-currency commitment was implicit, falling out of vendor pricing being in USD plus dev-environment defaults; the architectural commitment was not made deliberately, which the methodology Failure modes section records.

**The evolution shape is amount-plus-currency at every cost-bearing surface.** OTel span attributes shift to `gen_ai.cost.input.amount` plus `gen_ai.cost.input.currency` (or whatever the OTel GenAI conventions group converges on); `CostBreakdown` and `CostPerSuccessfulTaskResult` gain explicit currency fields; the pricing table at `padhanam/config/inference.py` declares per-model currency. Vendor pricing remains USD-quoted in dev; production deployments with non-USD-jurisdiction tenants resolve currency conversion at the trace-store query layer (per-tenant currency preference applied at read time, not write time, so historical traces remain queryable in their original currency).

**The specific D-entry lands when the first non-USD tenant arrives.** Premature commitment to specific currency-conversion mechanics, specific FX-data sources, or per-tenant currency-preference-resolution policy ahead of integration with a real non-USD-jurisdiction customer is paper architecture. D12 commits jurisdiction as the architectural attribute that drives the evolution; the migration follows D12's "by construction, not by policy" framing once the second jurisdiction enters scope.

### Per-tenant topology for Neo4j

Activated at S21 per D63 with the choice of a shared Neo4j 5 Community instance and property-based tenant scoping enforced through a `TenantScopedNeo4jSession` wrapper at the adapter boundary (raw `neo4j` driver imports forbidden outside the wrapper by the `neo4j-confined` import-linter contract plus AST enforcement test) plus tenant-isolation contract tests on both reads and writes. The entry remains as the activation marker for the production-deployment revisit, when per-tenant Neo4j containers may earn back their roughly 1GB-RAM-per-tenant local-dev cost against production isolation, residency, or operational requirements that Phase 1 does not yet exercise.

**Tenant isolation is non-negotiable however the topology lands.** Property-based scoping at Phase 1 is structurally gated by the wrapper plus contract tests; per-tenant containers at production-deployment context would shift the structural gate from the wrapper to the connection-resolution layer (one bolt URL per tenant, mirroring D36's per-tenant Postgres engine cache) without changing the discipline at the integration test layer.

**Revisit triggers.** Production-deployment context with one or more of: (1) a tenant whose data-residency requirements forbid co-location of graph data even under property scoping; (2) measured operational pressure where a single shared Neo4j instance's blast radius (one tenant's runaway extraction job degrading every other tenant's read latency) becomes a real production concern; (3) a security-review finding that property-based scoping is insufficient against a specific threat model the production deployment must defend. None of the three apply at Phase 1 scope; all three are credible at production scale.

### Cost-per-retrieval-query as a load-bearing metric

Captured on the evaluation result record at P11 per D105 but not load-bearing because Phase 1 retrieval is local (Ollama embedding, local pgvector, local Neo4j) and costs are essentially zero.

**Activation trigger.** Production deployment with non-zero embedding or vector-search cost.

### Full DORA and CORE4 instrumentation

Activates at Phase 2 framing.

**Full DORA instrumentation when production deployment exists.** D40 commits the methodology to DORA Four Keys and CORE4 measurement; `charter/methodology.md` (the active living-hypothesis surface per D113) adapts the definitions for Phase 1 (deployment frequency proxied by merged-to-main frequency; mean time to restore deferred until production traffic exists; change failure rate defined per same-phase corrective sessions). Phase 2 framing activates the full instrumentation when a hosted environment exists, deployment frequency means deploys-to-production, and MTTR measures real restoration. CORE4's effective developer experience axis activates fully when team scaling or productisation makes it load-bearing; Phase 1 partial coverage tracks what is tractable now via reflection density and operational-friction signals.

**The specific D-entry lands at Phase 2 framing.** Operational commitments (tooling, format, benchmarks) are deferred per D40's deferral structure.

## Workflow context extensions

### Gate-as-workflow-step topology category

Activates at Phase 2 workflow context implementation per D83.

**The workflow context admits a fourth topology category beyond sequential, conditional, and reflective: gate.** A gate step pauses workflow execution for explicit human action, distinct from agent-to-agent handoff in the three currently-committed categories. The gate step's authoring surface carries gate_type, required_role or required_roles (mutually exclusive, single and multi-signatory cases), available_actions (the action vocabulary the human can take), visibility_scope (which signals and step outputs the human sees), entry_condition (signal-based gate-firing logic), signatory_mode (single or multi), and ownership_rules.

**The gate-type vocabulary commits at the topology amendment.** Karma's framework named seven action-time gate types (escalation, confirmation, exception, feedback_loop_cap, conflict_resolution, structured_correction, approval) and six reserved lifecycle-transition gate types (agent_upgrade, imported_agent_drift, workflow_upgrade, workflow_deprecate, workflow_archive, model_upgrade). Padhanam adopts the categorical separation: action-time gates ship at workflow context implementation; lifecycle-transition gates remain reserved for the dependency-version-pinning surface when it lands.

**Multi-signatory gates are first-class from inception.** Per-signatory state rows track approval state; decline on any row resets every row to pending; the schema accommodates both single and multi-signatory modes without retrofit. Karma's Phase 1 brief warned specifically against retrofitting this later; Padhanam adopts the warning.

**Tool-boundary invariants and workflow-step gates are complementary surfaces, not alternatives.** D82's invariants enforce structural safety at every tool invocation regardless of workflow shape (per-classification consent at the tool layer). Workflow-step gates author explicit human-decision moments at the methodology layer (a methodology author can design "after draft, before send, the human reviews and edits"). Padhanam needs both. The gate category does not loosen tool-boundary invariants; it adds a separate surface for explicit authoring of workflow-internal HITL moments.

**Design reference.** Karma's GateConfigSubDTO and GateSignatory at `docs/notes/prior-art-karma/authoring-contract.md` §5.3.2 and §5.3.5; multi-signatory state machine at karma's GateSignatory model; gate-rendering UX surfaces at karma's WorkflowCanvas.jsx EdgeConfigPanel.

**The specific D-entry lands at the Phase 2 workflow context strategic block.** The amendment to D83's topology categories from three to four is the primary commitment. Sub-commitments on gate-type vocabulary, signatory shape, and entry-condition semantics land in the same strategic block. Premature commitment to specific gate types or signatory state machines ahead of Phase 2 implementation is paper architecture.

### User-authored taps as workflow-attached checkpoints

Activates at Phase 2 workflow context implementation, no later than the first power-user-customisation surface.

**Power users attach observability and governance hooks to workflow scopes.** Padhanam already commits to observability as foundation: trace capture from the first LLM call per D7, run history at P9, optimization dashboard at P11. The trace store is the platform-level read-only observability surface. Taps add a tenant- or user-authored extension layer: a tap fires at a named trigger point within a workflow run and invokes a tap agent that emits its own observations to the audit trail, the trace store, or the run-history view.

**Tap mechanics extend the role-first substrate per D86.** A tap is a role-attached observability agent. A user authors the tap agent as a role with a constraint bundle (read-only tool allowlist, evaluation-shaped output contract) and attaches it at a workflow scope with a trigger declaration carrying trigger_point, optional trigger_signal, and policy fields (loop_mode, loop_failure_policy). The trigger taxonomy follows karma's framework: before_execution, after_execution, on_output_signal. Padhanam's reflective topology category from D83 may require a fourth trigger (on_iteration); the strategic block resolves this.

**Tap loop semantics need explicit commitment.** Karma's framework declared three loop_mode values (stateless, cumulative, trajectory) shaping what context a tap agent sees across loop iterations, and three loop_failure_policy values (inform_loop, cap_loop, block_loop) shaping what the workflow does when a tap fails inside a loop. Padhanam adopts the categorical separation at Phase 2 implementation; specific mode and policy values may be refined per authoring-evidence at adoption time.

**Taps do not loosen platform invariants.** D82's invariants are platform commitments at the tool boundary, non-overridable. Taps are tenant capability extension at the workflow boundary, user-authored. Capability expansion that does not loosen invariants is exactly what D82's evolution discipline accommodates. Tap agents themselves are subject to the same invariants as any other agent: their tool allowlist is classification-checked at invocation, their outbound communications require per-invocation consent, their data flows through tenant-configured tool paths.

**Three open architectural questions resolve at the Phase 2 strategic block.** First: tap scope. Karma's Phase 1 shipped scope-level taps only (attached to a client or workspace scope); agent-level and workflow-level tap composition deferred. Padhanam can ship narrow or broad; the cheaper move is scope-level first with agent-level added when authoring evidence forces it. Second: tap identity. Tap-as-role-attached-agent is one shape; tap-as-distinct-aggregate is another. The role-first model accommodates the first naturally; the strategic block confirms or chooses otherwise. Third: trigger taxonomy. Karma's three trigger points work for sequential workflows; reflective topologies and gate steps may require additional triggers.

**Design reference.** Karma's tap framework at `docs/notes/prior-art-karma/taps-and-dispatcher.md` (extracted from karma's TapDeclaration model, ScopeGovernanceConfiguration, and taps/dispatcher.py); karma's authoring contract §6.1 through §6.4 covers tap composition mechanics.

**The specific D-entry lands at the Phase 2 workflow context strategic block.** The taps-as-power-user-customisation framing is the primary commitment; the three open architectural questions resolve at the same block. Premature commitment to specific scope levels, identity shape, or trigger names ahead of Phase 2 implementation is paper architecture.

### Learning store for accumulated knowledge

Activates at Phase 2 alongside the workflow context implementation per D83.

**Accumulated knowledge persists separately from any specific framework output.** As an agent works across sessions, it builds product-specific learning (what the user prefers, what's worked, what hasn't, accumulated context). This learning is separate from any specific playbook's outputs (LVT bets, RICE scores, Kano classifications). The learning store is what feeds revision-mode invocations of playbooks; the agent draws on accumulated knowledge to revise prior outputs.

**Shape choice deferred.** Two candidates: a generic learning store as its own bounded context (`contexts/learning/` or similar); or accumulated knowledge as agent-state extensions per agent. Choice settles when the workflow context lands and the revision-mode mechanics are designed against real consumers.

**Specific D-entry lands at Phase 2** when the data shape stabilises against real workflow context implementation.

### Revision mode in playbooks

Activates alongside the learning store at Phase 2.

**Each playbook needs a revision mode in addition to its initial-application mode.** The LVT playbook applied for the first time decomposes from scratch (bet, initiative, epic, story). The LVT playbook applied in revision mode loads existing bets, picks up accumulated learning from the learning store, and walks the user through "which bets still hold; which should change; what's new." Same shape for RICE (re-score as evidence shifts) and Kano (reclassify as options evolve).

**Playbook authoring includes both modes.** A methodology aggregate at Phase 2 contains both initial-mode and revision-mode logic per role-reference. Phase 1 playbooks (LVT, McKinsey 7-Step authored at S26b) declare the modes structurally without runtime support; Phase 2 implementation activates revision execution.

**Specific D-entry lands at Phase 2** when the runtime mechanics design against real consumers.

### Output aggregates for framework outputs

Activates alongside the learning store and revision mode at Phase 2.

**Framework outputs need structured persistence.** When an agent applying LVT produces a bet definition, the output currently lives only in the conversation. For revision-mode later, the agent needs a stored record of what it concluded. Bets, RICE scores, Kano classifications, McKinsey 7-Step intermediate artefacts all become stored outputs the agent can reference across sessions.

**Aggregate shape candidates.** Three candidates: a generic output aggregate that holds typed outputs (bets, scores, classifications) with a discriminator; per-playbook output aggregates (LVTOutput, RICEScore, KanoClassification); outputs as agent-state extensions. Choice settles when revision-mode design forces the shape.

**Specific D-entry lands at Phase 2** when the design stabilises.

### Retrieval-bound hard-constraint shape on methodology roles

Activates when methodology evidence shows soft-binding of retrieval fields insufficient.

**Per-field hard caps on a role's retrieval surface (max_top_k, allowed_strategies, min_min_score, max_filter_complexity).** Current D81 commitment treats `retrieval_strategy`, `filter_tree`, `top_k`, `min_score` as soft-bound (methodology defaults; agent overrides freely). The captures synthesis named retrieval bounds as one of the four constraint surfaces methodology declares per role; D81 deferred the hard-constraint shape pending consumer evidence.

**The specific D-entry lands at the methodology authoring session that surfaces the need**, with consumer evidence about which retrieval fields require hard caps. Premature commitment ahead of consumer evidence risks over-constraining methodology authors.

### Per-role binding-mode override

Activates when methodology evidence shows the platform-level binding-mode convention (three hard, six soft per D81) insufficient for a specific methodology's needs.

**Methodology authors choose binding mode per role per field, overriding the platform-level default.** Current D81 commitment is a platform-level convention: methodology authors do not choose binding mode based on the field's nature; the platform decides. The override is forward affordance for compliance-shaped methodologies (a regulatory methodology might want `system_prompt` hard for control purposes, or `model_selection` hard for jurisdiction-specific reasons).

**The specific D-entry lands at the methodology authoring session that surfaces the need**, with reasoning about the override mechanism (per-field annotation on the role bundle; precedence between platform default and role override). Premature commitment ahead of consumer evidence adds complexity without benefit.

## Methodology and governance enhancements

### Methodology metrics

Activates at first package close for the package-level computation, and at first phase audit for the phase-level computation. Session-level capture begins immediately upon adoption of the tagging format specified at `charter/methodology.md`, the active living-hypothesis surface per D113.

**The methodology is measured against DORA Four Keys and CORE4 dimensions.** Capture at every session, computation at every package close, trend analysis at every phase audit. The metrics are reported publicly as part of the case study, with package-level numbers added to package retrospectives and phase-level numbers added to phase audit entries.

**Definitions are explicit and adapted where necessary.** Deployment frequency uses "merged-to-main frequency" as a proxy in Phase 1 and shifts to traditional deployment frequency from Phase 2 onwards if a hosted environment exists. Change failure rate is defined as sessions whose output is later corrected by a subsequent session within the same phase. The full definitions live at `charter/methodology.md` per D40 and D113.

**Reporting tooling is deferred.** Initial computation is manual at package close and phase audit; if and when the manual computation becomes a meaningful overhead, a small script under `tools/metrics/` computes the numbers from session log tags. Premature tooling commitment ahead of the data shape stabilising is paper architecture.

**Honest reporting is a discipline.** Periods of poor methodology performance are reported alongside periods of strong performance. The case study's credibility depends on honest measurement, including when the metrics do not flatter the proposition. If at any phase audit the trend suggests the methodology is not sustaining performance, the bet document and methodology document are revised to reflect what was actually learned.

**The specific D-entry lands at the first package close with computed metrics.** The architectural commitment is recorded now in `decisions.md`; the operational commitments (specific computation tooling, specific reporting format, specific benchmark comparisons) are made when the data exists to inform them.

### Step-mode-shaped automation for narrow task types

Activates at Phase 1 close audit, with implementation at Phase 2 if the audit produces a safe-task-type list.

**Step-mode-shaped agent assistance for routine task types.** Once Phase 1 produces sustained methodology evidence, certain task types may become safe for higher automation: dependency bumps following `ops/scheduled_checks.yaml`, schema migrations following established patterns, eval-harness execution against pre-designed tests, supply-chain scanning and triage in pre-defined categories. Full auto mode stays out permanently because it conflicts with the architect-implementer pattern's append-only discipline, the D-entry alternatives requirement, the reflection-density expectation, and the two-surface mode-declaration discipline (D47). Step-mode-shaped engagement preserves operator approval at every unit boundary.

**The Phase 1 close audit produces the safe-task-type list.** That list is the input to the Phase 2 D-entry that commits to specific automation surfaces.

### Brownfield-shaped onboarding artefact for additional contributors

Activates when a contributor (human or model) approaches the project who has not been part of the existing operator-led history.

**Brownfield-shaped onboarding artefact synthesised from the charter.** The charter is currently the operating context, hand-maintained, and onboarding is the operator reading it. The moment a second contributor arrives, the friction surfaces as a real gap. The cheap version is a script that walks the charter and produces a single distilled `ONBOARDING.md`; the expensive version is full brownfield codebase scanning. The activation condition is contributor scaling becoming a real planning question, not an anticipation of it.

**The specific D-entry lands when contributor scaling becomes a real planning question.** Premature commitment to specific synthesis tooling is paper architecture.

### Methodology mechanical-enforcement upgrades

Items absorbed from the methodology comparison process that are committed in principle but await mechanical implementation. The discipline articulation lives at `charter/methodology.md` under the "Mechanical enforcement upgrades" sub-section per the principles-decisions-methodology pattern; this section tracks what activates each upgrade.

**Decision-to-code translation gate.** A CI test that walks new D-entries and asserts they appear in commits or session prompts within N sessions of being committed. Promotes the existing operator-discipline check into mechanical enforcement. Activation: when the discipline-adherence metrics in `charter/methodology.md` produce a measured baseline against which the gate's threshold can be set honestly. Earliest meaningful activation: Phase 1 close audit.

**Per-package reconciliation gate (mechanical).** D43 commits the structural pattern: epic note at package open, archive at package close, delta as audit deliverable. Mechanical enforcement would assert that every closed package has both files and that the archive references the epic note's commitments. Activation: when the epic-note convention has run for at least two packages (P4 and P5) and the reconciliation pattern has stabilised. Earliest activation: P5 close.

**Adaptive per-package reassessment as explicit prompt.** Standing reflection prompt at session close: does the rest of the package plan still hold given what this session surfaced? Activation: integrated into the session-close template at the next P-boundary strategic session (P4→P5 boundary).

**`make doctor` for operational drift.** Detection of orphan Compose projects, stale virtualenv interpreters, port collisions, drifted image digests, basic git hygiene. Activation: when operational drift surfaces as a session-open failure mode three times across the package boundary, per the structural-promotion threshold from the S11–S12 reflection. Tracked at session opens; the count is the activation condition.

**Session-close walkthrough template (checkpoint-preview pattern).** Standing template: what was the intent, what changed, what was verified, what is the residual risk. Activation: integrated into the session-close template at the next P-boundary strategic session (P4→P5 boundary), alongside the adaptive reassessment prompt above.

**Edge-case hunter procedural shape in phase-audit template.** Procedural checklist for phase audits: boundary input, empty input, malformed input, concurrent actor, retry, partial failure. Activation: integrated into the Phase 1 close audit template; reviewed for coverage at the audit and refined for Phase 2.

**Proper-noun-attribution check on model-drafted vendor-voice artefacts.** A check flagging named-person or named-company attributions introduced in model-drafted artefacts in external/vendor voice (PRFAQ, press-release-shaped content, case-study quotes), requiring explicit operator confirmation before the commit lands. Surfaced from the second Failure modes entry in `charter/methodology.md` (2026-05-06, fabrication-class drift in model-drafted vendor-voice content). Until the mechanical check lands, the operator's discipline is to challenge any name attribution surfaced in model-drafted external-voice content with a "who is [name]?" question. Activation: a recurrence of proper-noun-attribution drift in any model-drafted vendor-voice artefact, or routine pull from the upgrades backlog at a phase audit.

These are performance-category improvements: each scales the bet linearly by reducing operator-discipline reliance in favour of mechanical enforcement. None is must-have for Phase 1 close, which is why they sit here rather than in the active package's scope. Phase audits review the activation backlog and pull items into specific packages where conditions warrant.

### Generic personal-productivity methodology templates as public reference content

Activates if the operator finds during Phase C of the personal-use deployment (post-P8 close per D78) that generic methodology templates (GTD, Eisenhower matrix, time blocking) authored for the operator's personal deployment have value as reference implementations for future tenants of the public Padhanam codebase.

**Public versus private template distinction.** The operator's privately-iterated working version stays in the operator's personal control plane regardless of any public-reference decision. The candidate is a separate generic template authored on the public Padhanam control plane that surfaces personal-productivity methodology in the same shape as LVT, RICE, Kano, and other professional methodologies will: as platform-managed templates that any tenant can clone into their own agent.

**The specific D-entry lands at the moment the operator decides to author a public reference template**, capturing scope and the public/private template distinction. The activation is operator-discretion at Phase C; this entry exists to surface the option, not to commit to it.

### Forkable-vs-non-forkable architecture for commercial deployment

Activates if Phase 2 takes commercial direction.

**Candidate separation lines.** Open-and-forkable (core platform, generic methodology templates, generic tool implementations) versus hosted services (recommendation engine, optimisation surfaces, multi-tenant administrative dashboard) versus licensed content (premium methodology library, sector-specific compliance scaffolds, expert-authored agent templates). The separation is not architectural until Phase 2 frames commercial direction; the candidate lines are surfaced here to seed the future commitment rather than to fix it now.

**Relationship to D14 and D76.** D14 commits the customer-deployment scenario (configuration + tools + bounded extensions, no fork) and D76 refines the principle to "designed so forking is unnecessary." Both hold for the open Phase 1 codebase. Commercial direction at Phase 2 introduces the licensing-and-trademark question that D76 explicitly excluded from its scope: which mechanisms (open licence terms, hosted-service exclusives, trademark-protected branding, premium licensed content) actually enforce the platform's commercial commitments without retreating to "forking is forbidden" wording the open-source community sees through.

**The specific D-entry lands when Phase 2 commercial framing is committed.** Premature commitment to specific separation lines ahead of Phase 2 framing context is paper architecture per the project's deferred-decisions discipline. If Phase 2 does not take commercial direction, this entry is closed without a numbered D-entry landing.

### Maintenance and continuous-operation discipline as methodology workitem

Activates as load-bearing methodology articulation at Phase 1 close from a strategic-mode conversation; evidence-bearing instances accumulate from the personal-use deployment per D78 from Phase C onward and from any Phase 3 or later customer-deployment work.

**The methodology document's current articulation covers new-work session shape** (brief, pre-write reconciliation, commit, reflection) and audit boundaries (package retrospectives, phase audits). It does not articulate the discipline for ongoing production work: drift detection against the charter, regeneration triggered by spec changes, recurrence-of-incidents promotion to systemic patterns, audit cadence under continuous-operation load.

**Procurement adoption is the escalator.** The post-Phase-1 strategic block at 2026-05-20 (this entry's authoring session) confirmed maintenance and continuous-operation discipline as absolute must for enterprise adoption; the methodology cannot stay forward-engineering-only and meet procurement readiness.

**The specific D-entry lands at the methodology authoring session that consolidates the initial articulation**, drawing on D78 personal-use evidence if accumulated by that point and on the architect-implementer pattern's existing primitives (append-only audit chains, observability substrate, optimisation rules) that already provide partial coverage.

### Multi-implementer extension hypothesis: teams and team-of-teams

Activates much later than Phase 1, when resources or external-adopter evidence permits work at multi-implementer scale; the entry exists to carry the forward hypothesis the methodology takes about how the discipline expands, not to commit to articulation at any specific phase boundary.

**The architect-implementer pattern is currently exercised solo** per the Phase 1 capacity constraint named in `charter/bet.md`. The methodology's existing invariants (charter as load-bearing spec, brief discipline with pre-write reconciliation, append-only decision log with alternatives and Kano category, recurrence-promotion of methodology lines, five-role function audit at phase boundaries) are hypothesised to be actor-count-independent. The hypothesis is untested at any non-solo altitude.

**Two altitudes of expansion.** Single team (multiple human and AI implementers coordinated through the discipline) is the closer-in altitude. Team-of-teams (multiple teams coordinating, each operating the discipline locally) is the longer-horizon altitude per McChrystal's framing.

**Hypothesise, test, iterate.** Per the standard Padhanam discipline. The methodology document does not articulate definitive invariants for non-solo altitudes ahead of evidence; the deferred-decisions log preserves the hypothesis so future strategic-mode sessions read it when evidence accumulates. Premature articulation ahead of evidence commits the methodology to claims the discipline has not earned at scale.

**Activation triggers.** Resource availability permitting multi-implementer work; external adopters reporting instances of the discipline at non-solo scale; procurement engagement requesting evidence at team or team-of-teams scale.

**The specific D-entry lands at the strategic-mode session that surfaces first evidence at a non-solo altitude**, with full hypothesis-test-iterate articulation building from that evidence rather than from anticipation.

### Methodology comparison act for the case-study deck

Activates at Phase 2 close, when the drafted methodology comparison content is verified and integrated into `charter/deck.html`.

**A methodology comparison act is drafted but not yet published.** The post-P12 strategic block at 2026-05-20 drafted a "How this compares" act for the case-study deck: an operator-authored preamble and close, and a seven-methodology comparison table across eight dimensions (vibe coding, GSD, BMAD-METHOD, GitHub Spec Kit, AWS Kiro, Trey Research 3-3-3, Padhanam). The draft lives at `charter/methodology-comparison.md`.

**The draft is not published because the table makes procurement-facing factual claims about six named third-party methodologies that have not passed human verification.** The external-methodology cells were model-drafted from web research and carry explicit accuracy flags, including unresolved source conflicts on GitHub Spec Kit's brownfield support and on Trey Research 3-3-3 phase timing, plus product-branding and creator-attribution checks. Publishing unverified third-party claims to the public deck would violate the proper-noun-attribution discipline named in the "Methodology mechanical-enforcement upgrades" entry above.

**Verification and integration happen together at Phase 2 close** per the operator decision at the 2026-05-20 strategic block. Phase 2 close is the natural moment on two grounds: the deck is a living artefact that refreshes at phase boundaries per D45, and Phase 2's outcome will itself reshape several Padhanam-row cells, since the actor-model, maintenance, and throughput cells all point at forward work that Phase 2 advances.

**This entry closes when the comparison content is verified and integrated at Phase 2 close.** The integration is deck-content work and does not require a numbered D-entry; the Phase 2 close audit records the verification outcome.

## Compliance and security

### Tenant-content-at-rest encryption classification (portfolio Case titles / DataPoint values; intake hints; pending-clarification summaries)

Surfaced by the S55b-2 audit `after_state` encryption-posture backward check (`log/captures.md` 2026-06-03 [S55b-2]). The check confirmed there is **no audit-leak gap today** — every audit `after_state` matches its store's encryption posture, and `meeting_citation` (calendar) is the first and only case where the store envelope-encrypts content (D21), which the citation snapshot also encrypts. But it surfaced an upstream classification question that pre-dates calendar: **portfolio Case `title` (`sa.Text`) and DataPoint `value` (`pg.JSONB`) are stored plaintext at rest** (no `enc_*` columns; D124-era choice), as are intake `intent_hint` and messaging `proposed_action_summary` in their audit `after_state`. Calendar deliberately envelope-encrypts Meeting content because attendee emails/locations were judged more sensitive than portfolio Cases (D148); whether portfolio/intake/messaging content warrants the same D21 treatment is an unmade classification decision.

**What defers.** The decision whether tenant-authored portfolio content (and the intake/messaging echoes of it) must be envelope-encrypted at rest per D21, like calendar Meeting content. If yes, it is a package-sized hygiene item: envelope-encrypt the portfolio store columns *and* backfill the historical plaintext audit `after_state` rows, and it flips the deferred general "no plaintext D21-classified content in any audit `after_state`" guard (currently two-threshold-deferred with calendar as the lone instance) to **overdue** (portfolio's `after_state` becomes a second instance). If no (the classification stays "portfolio content is not D21-sensitive"), the current posture is consistent and the general guard stays deferred.

**Revisit triggers.** A procurement/compliance review that requires all tenant-authored content encrypted at rest; or a tenant whose data carries content (health, legal, financial specifics in Case titles/values) that clearly warrants envelope encryption; or a second cell freezing encrypted-store content into audit `after_state` (which makes the general guard overdue independent of this decision). Estimated size when activated: medium (store migration + audit backfill + the general `after_state` guard).

### Per-tenant supply-chain surveillance for tenant-supplied tools and extensions

Activates when tools and extensions enter the codebase (P5 or wherever tools and extensions first land).

**Tenant-supplied artefacts have their own dependency trees and require per-tenant surveillance distinct from platform supply-chain monitoring.** Each tenant's registered tools (external services called on the tenant's behalf, per D14) and uploaded extensions (sandboxed code at named interfaces, per D14) carry their own dependencies. Padhanam scans these at registration, re-scans on a schedule against updated CVE databases, and notifies the tenant of vulnerabilities in their artefacts.

**The mechanism is the tool-and-extension registry, not the platform supply-chain process.** Different system, different cadence, different audience. Platform supply-chain checks (governed by `ops/scheduled_checks.yaml`) are operator-reviewed and operator-merged. Per-tenant artefact scanning is tenant-notified and tenant-actioned, with platform-side enforcement (e.g., disabling a tool registration with a critical CVE that the tenant has not addressed within a defined window).

**Configuration scope follows tenant agency.** Tenants have agency over which tools they register and which extensions they upload, and therefore over the surveillance posture for those artefacts (notification preferences, severity thresholds for auto-disable, grace periods). They do not have agency over the platform's own supply-chain monitoring.

**The specific D-entry lands when tools and extensions enter the codebase.** Premature commitment to specific scanning tools, severity thresholds, or notification mechanisms ahead of integration is paper architecture.

### Per-tenant compliance evidence aggregation (Layer B)

Activates when a real tenant compliance use case demands it, or at Phase 2 framing as a candidate package, whichever surfaces first.

**The substrate already exists.** Audit chain per D26 and D35 records every state change with actor, jurisdiction, before/after state, and correlation ID. Supply-chain scanning per D25 produces dated scan output via `make scan` and `ops/scheduled_checks.yaml`. Tenant isolation contract tests per D24 produce pass-rate evidence via `make test`. Conventional commits referencing package and session number per the Engineering practice principle constitute change-management evidence. Package retrospectives in `log/packages.md` per D40 constitute operation-of-controls evidence over time.

**What defers is the report-shaping pipeline.** Audit-chain queries scoped per tenant; evidence aggregation use cases composing the substrate above into auditor-consumable reports; the auditor-export format (PDF, structured JSON, or specific GRC-platform import shape); the tenant-facing CLI or UI surface for evidence retrieval.

**The specific D-entry lands when the package frames.** Premature commitment to specific report shapes ahead of a real tenant audit consumer is paper architecture. Estimated package size when activated: medium. Sized similar to P10 audit log viewer.

### Workflow compliance frames (Layer C)

Activates when three prerequisites all hold: (1) Padhanam's own SOC 2 Type II or ISO 27001 audit has completed (Phase 2 production deployment work; the inheritance map cannot reference controls in a report that does not yet exist); (2) the workflow taxonomy has stabilised across multiple methodologies (post-P7 with at least three methodology templates in production, so the frame structure is not authored against a single workflow's idiosyncrasies); (3) tenant demand for tenant-product attestation has surfaced as a real procurement requirement rather than a hypothetical one (real-consumer prerequisite mirroring the S15 classification deferral pattern).

**Frame structure when authored.** Each workflow compliance frame carries: data-flow defaults, sensitivity classification defaults, retention defaults, incident shape defaults (the C1 data-protection scaffolds); control objective mappings naming SOC 2 Trust Services Criteria and ISO 27001 Annex A controls applicable to applications built with this workflow; CUEC inheritance map showing which Padhanam controls cover which tenant control objectives, with residual control objectives flagged as tenant-operated; control activity scaffolds describing typical implementations for tenant-operated controls in this workflow class (the C2 framework-attestation inheritance maps).

**Methodology aggregate field extension.** When Layer C activates, the methodology aggregate at `contexts/methodology/domain/methodology.py` extends with a compliance-frame field. Per D31's revision-shape, this lands as a future revision rather than a schema migration; existing methodology templates inherit a default empty frame until populated.

**The specific D-entry lands when the package frames.** Premature commitment to specific frame structures ahead of the audit-completion prerequisite is paper architecture. Estimated package size when activated: large. Sized as a multi-session package given the per-workflow content authoring effort.

### Cascading-harm invariant shape

Activates when multi-agent workflows or persistent agents enter the codebase.

**Cascading-harm invariant captures bounded blast radius, per-invocation cost ceilings beyond per-agent limits, rate limits on outbound effects, and propagation containment.** Single-agent invocation at Phase 1 does not produce the risk surface; one agent invocation cannot amplify into many downstream consequences. Workflow execution (Phase 2 per D83) and persistent agents (the scheduled-runs primitive deferred-decisions entry) both introduce the risk surface and trigger this invariant's specific shape.

**The specific D-entry lands at the package or session that activates the invariant**, capturing the shape (workflow-level rate limits, cascade-detection heuristics, abort-on-budget-exceeded semantics, audit signal shape) with reasoning about the consumer that pulled it in. Premature commitment to specific cascade-prevention mechanics is paper architecture.

## Tool registry and authoring

### Calendar tool service as platform capability

Activates when public Padhanam needs a calendar integration for any package work (potentially P9 source ingestion, P10 active testing, or P11 recommendation surfaces) or when the operator's personal-use deployment Phase C activates (post-P8 close per D78), whichever comes first.

**Calendar tool is a generic capability with broad applicability.** Implementation lives as a separate service per D14's tools-as-configuration commitment; the platform calls the calendar tool through whatever protocol the tool exposes (HTTP or MCP) without absorbing calendar logic into Padhanam's codebase. The service handles OAuth, scope management, and the calendar provider's API; Padhanam's tool registry stores the configuration that points to it.

**The specific D-entry lands when implementation begins**, capturing protocol choice (HTTP versus MCP), authentication shape, and integration scope. Premature commitment to a specific calendar provider, protocol, or authentication mechanism ahead of integration is paper architecture.

**Status: closed by D148, 2026-05-28.** Activated at P15 framing (2026-05-27): operator chose self-hosted Nango under Elastic License for the tool service substrate, kept inside operator-controlled infrastructure (Path B). Path A (Padhanam-owned tool services) activation triggers named at the new "Path A migration from Nango self-hosted" entry below: vendor pricing inversion at Phase 2-B+; privacy compliance escalation; feature divergence. The protocol/auth/scope D-entry landed at S55a as D148 (Nango Proxy pull-on-demand via the five verified handles; `calendar.readonly`; separate-service per D14; Meeting as event-id-keyed mutable cache; substrate-inheritance survey result), with the live integration verification (the Nango provisioning green stage-6 gate). S55a splits the original S55 into the calendar data substrate (S55a) and the calendar conversation (S55b).

### Email tool service as platform capability

Activates when public Padhanam needs an email integration for any package work (potentially P9 source ingestion, P10 active testing, or P11 recommendation surfaces) or when the operator's personal-use deployment Phase C activates (post-P8 close per D78), whichever comes first.

**Email tool is a generic capability with broad applicability.** Same architectural shape as the calendar tool entry: separate-service implementation per D14, tool-registry configuration points to it, protocol-and-auth choice deferred to the implementation moment.

**The specific D-entry lands when implementation begins**, capturing protocol choice, authentication shape, and integration scope. Premature commitment ahead of integration is paper architecture.

**Status: activated at P15 framing (2026-05-27).** Operator chose self-hosted Nango under Elastic License symmetric to the calendar tool entry above (Path B). The specific D-entry covering the protocol/auth/scope choice lands at S56 (email substrate session) with the live integration verification. Path A migration triggers apply identically to the calendar tool service entry.

### Per-invocation human-in-the-loop confirmation pathway for high-classification tools

Activates when the first tool of classification `financial`, `communication`, or `legal` is authored for a tenant.

**The pathway shape commits at the activating session.** Three shape candidates: hand-off (agent drafts the proposed action; user acts out-of-band through the relevant external system); pause-and-confirm (agent loop pauses at the invocation boundary; user reviews proposed call + arguments in-context; agent resumes on confirmation); queue-and-resume (run terminates with `awaiting_confirmation` status; user reviews out-of-band; resumption is a new run that carries forward the prior context). Each shape has different blast radius, UX latency, audit-trail implications, and runtime-state complexity. The choice depends on consumer evidence: which surface (CLI, future UI, API client) is the actual user environment; whether the action is reversible if mis-authorised; how long the user needs to review; whether the user holds context for the full agent invocation or just the proposed action.

D89 commits the substrate (`Classification` enum, classification-to-invariant mapping, `INVARIANT_BLOCKED` termination signal, Phase 1 authoring prohibition) without committing the pathway shape. The activating session's D-entry captures shape reasoning and the consumer evidence that drove it. Until then, the Phase 1 authoring prohibition is the operative guardrail.

### Rich backward-compatibility testing for tool revisions

Activates when the second tool revision in a tenant produces a false positive (BC stub passed but the new revision actually broke a consumer) or a false negative (BC stub failed but the new revision is actually safe for adoption).

**Refines the BC test surface beyond the schema-diff stub.** Three candidate sophistications: contract tests per tool (the tool author provides a contract test suite that the BC check runs against revision Rn+1's behaviour to validate semantic compatibility, not just schema compatibility); scenario-based regression (a corpus of representative invocations is captured per tool revision; BC check replays the corpus against Rn+1 and diffs results); schema diff with type-evolution rules (codified rules for Pydantic-aware schema evolution — e.g., `int → int | None` is compatible if no consumer requires non-null, `str → enum` is compatible only if all prior values are in the enum, `list[X] → list[Y]` is compatible if Y is a strict superset of X). The right shape depends on whether the first false result is a behavioural drift (suggests contract tests or scenarios) or a schema-evolution gap (suggests typed rules).

D89 commits the schema-diff stub as Phase 1 substrate. The activating session's D-entry chooses the next sophistication based on the actual false-result evidence.

### Automated adoption flow for backward-compatible tool revisions

Activates when the first BC-passed revision lands in production with an existing role-tool binding pointing at the prior revision.

**Designs the adoption UX that consumes the `RoleToolBinding.can_auto_adopt` signal D89 commits as substrate.** Three candidate flows: auto-adopt on BC pass with notification (binding silently updates to the new revision; user gets a digest notification listing what changed); review-required on BC fail (binding does not auto-adopt; user sees a review queue with the BC failure reason and decides per binding); opt-in adoption with BC result as recommendation strength (binding does not auto-update; the recommendation surface shows "BC passed — safe to adopt" or "BC failed — review required" with the user explicitly choosing every adoption). The trade-off is between notification fatigue (auto-adopt is the lowest-touch but bypasses user awareness), review fatigue (review-required is the highest-touch but ensures intentionality), and recommendation-quality dependence (opt-in lives or dies on whether the recommendation strength is well-calibrated).

D89 commits the `list_roles_using_tool` query surface and the `can_auto_adopt` signal at the binding DTO. The activating session's D-entry commits the adoption UX based on the consumer surface (CLI, future UI) and the operator's preference for autonomy versus review.

## Phase 1 close audit findings

### Optimization-engine cost-per-successful-task threshold tuning

D111 commitment 5 ships `cost_optimization_rule` with starter threshold $0.10 cost-per-successful-task. The threshold is tuned for the development regime (local Ollama models with effectively zero per-token cost); production LLM regimes (vendor APIs, hosted models) shift the threshold by orders of magnitude. S41 smoke produced substrate-honest zero emission against $0.000246 mean (well below threshold; ~400x threshold-vs-actual gap). The 0.15 absolute recall@3 delta threshold on `retrieval_strategy_rule` carries the same starter-value posture against the same Phase 1-vs-production regime gap. D111 names the thresholds as "starter; tuning is Phase 2 evolution as consumer evidence accumulates"; this entry formalises the deferral with explicit activation-trigger language.

**Activation trigger.** P12 audit (2026-05-16) reviewed and confirms parked state holds. Specific Phase 2 trigger: a tenant operating against vendor APIs at non-trivial cost rates with a real cost-per-successful-task aggregation surface across at least one full month of run history, OR a Phase 2 UX-driven swap surface for tenant-operator-configurable thresholds. Premature commitment to specific threshold values ahead of consumer evidence is paper architecture against the bet's procurement-grade-defensibility commitment.

### `parallel_rrf` retrieval-strategy implementation

D66 catalogues `parallel_rrf` as the third entry in the three-strategy starter catalogue alongside vector-only and graph-only. `AgentRetrievalClientAdapter` at [apps/cli/_cross_context.py:322-462](apps/cli/_cross_context.py#L322-L462) ships no fusion-merge code at S40: the adapter dispatches on `{"primary": "vector"}` and `{"primary": "graph"}` and falls through to an empty `RetrievalResult` for any other strategy mapping (verified at S40 pre-write reconciliation Finding 2). The Reciprocal Rank Fusion algorithm, the parallel dispatch of `search_vector` plus `traverse_graph` from the same query, and the seed-entity derivation that the graph leg would need to produce honest fusion results are all deferred. D110 commitment 6 ships the runner against the two executing strategies projected to canonical identifiers `vector_only` and `graph_only`; D110 alternative (h) records the rejection of bundling fusion-merge implementation into the S40 runner session; D110 alternative (i) records the rejection of rewriting D66 to match the as-built two-strategy surface.

**Activation trigger.** P12 audit surfaces a Phase 1 procurement-grade need for three-strategy comparison (i.e. the bet's criterion-4 procurement-grade demonstration requires fusion as visible evidence), or a Phase 2 session is framed explicitly for retrieval-adapter extension. References D66; supersedes D66's implied "all three ship in Phase 1" framing without rewriting D66 itself.

### Gold-set aggregate-level audit emission

The gold-set substrate at `contexts/retrieval_evaluation/` ships at S39 without audit-event emission on aggregate-level mutations (creation, append-entry, finalize-revision, name update, deletion). Revision content is covered by hash-chain self-containment per D109; aggregate-level mutations rely on per-tenant DB integrity, which is not procurement-grade tamper-evidence. The S39b rename of the synthetic gold-set illustrates the gap concretely: a direct SQL UPDATE on `gold_sets.name` is hash-chain-invariant and emits no audit event. Verified at S40 pre-write reconciliation Finding 6 across [contexts/retrieval_evaluation/application/](contexts/retrieval_evaluation/application/) and [contexts/retrieval_evaluation/adapters/outbound/postgres/repository.py](contexts/retrieval_evaluation/adapters/outbound/postgres/repository.py). D110 establishes audit-event emission for the runner records (platform-computed regime per D110 commitment 7's three-regime distinction) but does not back-fill gold-set audit emission inside S40 scope. Back-fill to the audit-event regime per D110 commitment 7's reasoning is procurement-grade necessary before Phase 1 close.

**Activation trigger.** P12 audit (2026-05-16) reviewed and refreshes the trigger as follows: back-fill is procurement-grade-necessary for Phase 2-entry readiness; explicit deferral to a Phase 2-entry hygiene workitem rather than landing within P12 audit per the audit's "no code changes at P12" scope. The Phase 2 inputs file at `charter/p12-phase-2-inputs.md` names the workitem with operational specificity: extend `contexts/retrieval_evaluation/application/` use cases for create_gold_set / append_entry_to_revision / finalize_revision / rename_gold_set to emit audit events; the rename surface needs an explicit `rename_gold_set` use case which today does not exist (S39b's rename was a direct SQL UPDATE, which is part of the audit-emission gap surfacing in the first place). The bet's audit-evidence claim holds at the audit-event-chain level for tenant-authored content; the gold-set-aggregate-level gap is honestly framed as a known carryover with named Phase 2-entry remediation rather than overstated as covered.

### Graph-extract pipeline reliability — reclaim-after-timeout policy

The `EXTRACTING` state in `contexts/ingestion/domain/state.py` has no reclaim-after-timeout transition implemented. A worker dying mid-extraction (LLM-call hang, container kill, transaction-rollback edge case) leaves the source stuck in `EXTRACTING` indefinitely; no other worker picks the row up; the source never reaches `INDEXED` or `EXTRACTION_FAILED`. The extraction LLM call at `contexts/ingestion/adapters/outbound/extraction/litellm_extractor.py` has no timeout enforcement at the worker boundary either; an inference-side hang produces the same stuck state. Surfaced at S40b smoke as graph_only retrieval consistently returning all-zero aggregates because the S25/S39b corpus's extraction pipeline did not complete reliably on every source. Pre-P12 hygiene Finding 1 investigation confirms the structural shape — bounded fix not available because `EXTRACTING` is terminal-until-success without a reclaim mechanism.

Three structural pieces missing for a reliable extract pipeline:

1. **Reclaim policy.** A source in `EXTRACTING` for longer than a configurable timeout (proposed 5 minutes for Phase 1; LLM calls bounded by LiteLLM gateway timeouts at lower granularity) is reclaimed by a worker via a new `claim_extracting_for_reclaim` transition. The reclaim transitions back to `PENDING_EXTRACT` for another worker (or the same worker on next iteration) to pick up. Per-row reclaim counter to bound retry attempts; on N-th reclaim the source transitions to `EXTRACTION_FAILED` with `extraction_error_text="reclaim_limit_exceeded"`.

2. **Worker-side timeout enforcement.** The `extract_source` use case at `contexts/ingestion/application/extract_source.py` wraps the extractor call in an asyncio timeout matching the reclaim timeout; on timeout the use case raises `ExtractorError("timeout_exceeded")` and the existing `EXTRACTION_FAILED` path fires cleanly. The worker exits its current iteration without leaving the row stuck.

3. **Reclaim safety against split-brain.** The reclaim transition uses an optimistic-concurrency-control idiom (transition succeeds only if the source's `state` is `EXTRACTING` AND `state_updated_at < now() - timeout`). Two workers competing for the same reclaim see one succeed and the other no-op; the winning worker proceeds with extraction; the losing worker continues its claim loop.

**Operational mitigation at Phase 1.** Manual re-trigger via CLI: operator inspects `SELECT id, state, state_updated_at FROM sources WHERE state = 'extracting' AND state_updated_at < now() - interval '5 minutes';` against the per-tenant database, then issues a forced `UPDATE sources SET state = 'pending_extract' WHERE id = '<id>';` to return the row to the queue. The forced UPDATE is procurement-grade-invisible (no audit event emission); the manual-mitigation gap is part of the reliability finding the structural reclaim policy resolves.

**Activation trigger.** Any Phase 1 close or Phase 2 work that depends on graph retrieval producing entities reliably — workflow agents that depend on graph evidence, recommendation rules that cite graph state, P12 audit's procurement-grade demonstration if it includes a graph-retrieval-bearing scenario. Forward-relevance: production deployment with multiple worker processes amplifies the failure mode (worker death is more common at scale); the reclaim policy is required-not-optional at the production-deployment context. Referenced in `charter/p12-audit-inputs.md` entry 13 with the same structural-finding framing.

P12 audit (2026-05-16) refresh: the P12 audit reviewed the deferral and confirms hold. Production-grade graph retrieval reliability is the prerequisite for Phase 2 workflow agents that depend on graph evidence; the reclaim policy is non-negotiable at production-deployment context. The audit-findings document at `charter/p12-audit-findings.md` entry 13 carries the same disposition; the Phase 2 inputs file at `charter/p12-phase-2-inputs.md` names this as a Phase 2-entry workitem alongside the gold-set audit-emission back-fill.

## Phase 2 design 7-Step deferrals

Architectural decisions deferred at Phase 2 design 7-Step Step 6 Pass 1 dispositions. Each entry names the activation trigger and the activating session or context.

### Phase 2-B Wave 4 versus Phase 3 boundary

Per Step 6 Pass 1 Q8 disposition. Several P20 Wave 4 candidates may legitimately slip to Phase 3: Cluster B1 remainder (work-app cells beyond operator stack); Cluster B7 conditional (watching, delegated additions); Cluster B9 second wave (skills-per-role surface refinement if not landed at P17); Cluster B5 conditional (normalised value units if Phase 2-A per-methodology friction).

**Activation trigger.** Approaching Phase 2-B Wave 4 (P19 close). Decision made when concrete context exists about what is ready to ship versus what carries to Phase 3.

**The specific D-entry lands at the activating session.** References Step 6 Pass 2 P20 Wave 4 contents.

### Tier 4 sub-problem activation triggers

Per Step 6 Pass 1 Q9 disposition. Single deferred entry covering all eight Tier 4 sub-problems from Step 3 prioritisation (1.2, 2.2, 2.3, 2.5, 3.3, 3.4, 4.5, 5.2, 5.3, 6.1, 6.2 with 2.2 plus 2.4 plus 4.5 plus 6.1 plus 6.2 plus 6.5 carrying into Phase 2-B clusters per Step 5 activation map). Tier 4 sub-problems that do not activate through Phase 2-B clusters remain Tier 4 deferred.

**Activation trigger.** Per Tier 4 sub-problem detailed design when the sub-problem's containing Phase 2-B cluster (per Step 5 activation map) enters package scope. Sub-problems not activated through Phase 2-B clusters review at Phase 3 framing.

**The specific D-entries land per sub-problem at activating session.** References Step 5 Work-stream 4 Tier 4 activation map.

### Identity-fork schema-based threshold

Per Step 6 Pass 1 Q10 disposition. The identity-fork mechanism for methodology adaptation crossing structural threshold (when an adapted methodology has diverged so far from parent that it is structurally a different methodology rather than a revision). Step 5 surfaced schema-based threshold detection as candidate; final threshold definition defers to detailed design at Phase 2-B Cluster B3 activation.

**Activation trigger.** Phase 2-B Cluster B3 detailed design session (P19; methodology layer depth wave).

**The specific D-entry lands at the activating session.** References Step 5 Pass 1 sub-problem 2.1 finding plus Pass 1 Q11 reconciliation.

### Twelve event classes confirmation

Per Step 6 Pass 1 Q12 disposition. The audit visibility (5.1) workplan committed twelve event classes at Step 5 Pass 1 finding (six workplan plus five Pass 1 design refinements plus one 5.4 central-storage refinement). Confirmation of the twelve-class scope plus any additional event classes surfacing during 5.1 detailed design defers to the 5.1 detailed design session at Phase 2-A Wave 3 (P15).

**Activation trigger.** Phase 2-A P15 5.1 audit visibility detailed design session.

**The specific D-entry lands at the activating session.** References Step 5 Pass 1 sub-problem 5.1 finding.

## Phase 2-A P13 framing deferrals

Architectural decisions deferred at the Phase 2-A P13 framing substantive conversation per the forward-compat substrate-depth classification (Decision 7). The classification table lives at `charter/packages/p13-epic.md`. This section holds two defer-with-named-activation-trigger entries plus six flag-for-future-testing entries; the flag-for-future-testing entries are build-now substrate that Phase 2-A operator dogfooding does not exercise, and each names the Phase 2-A close audit's test-coverage gap.

### Role hierarchy with inheritance machinery

Per the P13 framing forward-compat substrate-depth classification (defer-with-trigger category). Phase 2-A operates at operator-role only. The ActorContext extension (S44) carries a role list, and the authorisation decorator (S44) enforces role checks at the use case boundary; both are built so a role hierarchy with inheritance machinery is a pure extension rather than a refactor.

**Activation trigger.** Phase 2-B or Phase 3+ adds a second role beyond operator.

**The specific D-entry lands at the activating session.** References the P13 ActorContext extension plus authorisation decorator substrate, which supports role hierarchy as a pure extension.

### Principal polymorphic shape — machine-actor variant

Per the P13 framing forward-compat substrate-depth classification (defer-with-trigger category). Verified at P13 framing: the current S34/S37/D103 principal shape uses a `PrincipalType` StrEnum discriminator (TENANT and PLATFORM_OPERATOR variants) and is already polymorphic. Adding a third principal type — a machine-actor for API callers — is additive: a new StrEnum value plus a new dependency resolver path, with existing call sites unchanged.

**Activation trigger.** An API caller arrives at Phase 2-B+.

**The specific D-entry lands at the activating session.** References D103 (principal polymorphic shape) and S37.

### Authorisation paths beyond operator-role check

Per the P13 framing forward-compat substrate-depth classification (flag-for-future-testing category). The authorisation decorator ships at S44 with operator-role-only checks; the rejection paths exist in the substrate but Phase 2-A dogfooding never traverses them.

**Activation trigger.** Phase 2-B+ adds a second role.

**Phase 2-A test coverage gap.** No Phase 2-A scenario trips an authorisation rejection path. This entry is a Phase 2-A close audit input; the close audit reads it directly from this file.

### Governance hierarchy levels above Organisation and below default Workspace

Per the P13 framing forward-compat substrate-depth classification (flag-for-future-testing category). The governance artefact hierarchy shape (Platform / Organisation / Workspace / Agent inheritance) lands at P14; Phase 2-A operates at operator-as-organisation level with a single default workspace.

**Activation trigger.** Phase 3+ commercial deployment, or Phase 2-B Cluster B9 extensions.

**Phase 2-A test coverage gap.** Phase 2-A has no Platform-level or sub-Workspace inhabitants, so multi-level governance resolution is never exercised. This entry is a Phase 2-A close audit input; the close audit reads it directly from this file.

### Multi-signatory Gate paths

Per the P13 framing forward-compat substrate-depth classification (flag-for-future-testing category). The Gate entity lands at P14 with a signatory rule abstraction; Phase 2-A operates single-signatory (operator only).

**Activation trigger.** A Phase 2-B+ surface adds multi-actor scenarios.

**Phase 2-A test coverage gap.** Phase 2-A is single-signatory; multi-signatory Gate paths are never exercised. Flagged alongside the Gate entity at P14. This entry is a Phase 2-A close audit input; the close audit reads it directly from this file.

### Intake authority profiles beyond operator-authority

Per the P13 framing forward-compat substrate-depth classification (flag-for-future-testing category). The Intake record lands at S44 (P13) as the canonical boundary of incoming work; Phase 2-A's only intake source is the operator.

**Activation trigger.** Phase 2-B+ adds additional intake sources with different authority profiles.

**Phase 2-A test coverage gap.** Phase 2-A has no intake sources beyond the operator, so intake authority profiles beyond operator-authority are never exercised. This entry is a Phase 2-A close audit input; the close audit reads it directly from this file.

### Methodology-step-and-signal declarations beyond P14's four methodologies

Per the P13 framing forward-compat substrate-depth classification (flag-for-future-testing category). The methodology-as-workflow data model lands at P14 with explicit steps and signals declarations; P14's four methodologies populate a subset of the shapes the substrate accepts.

**Activation trigger.** P17 Cluster B9 methodology authoring adds new methodology shapes.

**Phase 2-A test coverage gap.** The substrate accepts more step-and-signal declaration shapes than four-methodology testing exercises. Flagged alongside the methodology-as-workflow data model at P14. This entry is a Phase 2-A close audit input; the close audit reads it directly from this file.

### Case-DataPoint-Assertion shapes beyond portfolio-item-shaped use

Per the P13 framing forward-compat substrate-depth classification (flag-for-future-testing category). The Case, Data Point, and Assertion entities land at S43 (P13) as first-class domain vocabulary; the substrate accepts Case types beyond PORTFOLIO_ITEM and Data Point types beyond goal/status/methodology-application.

**Activation trigger.** Phase 2-B+ adds new domain entity types.

**Phase 2-A test coverage gap.** Phase 2-A operator dogfooding generates portfolio-item-shaped Cases only; non-portfolio Case and Data Point shapes are never exercised. This entry is a Phase 2-A close audit input; the close audit reads it directly from this file.

## P13 S45 deferrals

Architectural decisions deferred at S45 (the messaging substrate plus ConversationFlow Protocol plus structured-output session). Each names an activation trigger and the surface the activating package or strategic block reads it from.

### Structured-output-to-agent-tool convergence

The LLM-call structured-output discipline at D130 (`shared_kernel/structured_output.py` — a request, a response, and a port for LLM calls that must return a schema-conforming structured value) and the agent-tool calling shape (the tool-definition and tool-invocation surfaces at the agent context per D88/D89) are structurally similar concerns: both describe a schema a model is asked to conform its output to. Whether they converge onto one primitive or stay deliberately separate is a future-package question. At Phase 2-A they are distinct surfaces — structured output is the LLM-call boundary discipline, agent-tool calling is the agent-runtime orchestration shape — and S45 does not couple them.

**Activation trigger.** A future package where agent-tool surfaces and the structured-output discipline meaningfully overlap — for example, an agent-runtime surface that wants to consume the D130 primitive directly, or a structured-output consumer that needs tool-call semantics.

**The specific D-entry lands at the activating session.** References D130 (structured-output discipline), D88 (agent runtime architecture), D89 (tool registry).

### Multi-channel UX architectural readiness

**Status (S47 update).** Architectural commitments landed at D136 covering all four sub-surfaces. Implementation deferred to existing activation triggers below. The entry stays here for the implementation triggers; the architectural disposition is settled at D136.

S45 lands the messaging substrate for a single channel (WhatsApp via Twilio per D119/D129). When users interact across multiple messaging channels — WhatsApp, Slack at P15, SMS, future Copilot, future voice — Padhanam needs four surfaces the single-channel substrate does not yet build: identity reconciliation across per-channel identities (one user, many channel-addresses); channel preference resolution for platform-initiated outbound (which channel to reach the user on); cross-channel session continuity (a conversation that spans channels); and channel-aware affordances at the routing layer (a channel's capabilities shape what the response can contain). The S45 substrate is structurally channel-agnostic where it matters — the Message entity carries a `channel` enum, ActorContext is channel-free, the ConversationFlow Protocol is transport-neutral, and the IntakeSource enum admits per-channel inbound variants — so the four surfaces are additive rather than a refactor.

**Activation triggers (still in force for implementation).** Multi-channel work begins when any of: (a) the Phase 2-A operator starts using more than one channel; (b) Padhanam initiates outbound conversations at P14+ where channel selection matters; (c) Phase 2-B+ introduces multiple users with multiple channels.

**Architectural disposition.** D136 commits the four primitives. The forward UX convergence strategic block (captured at `log/captures.md` 2026-05-22 [S45]) closed at S47. P14 framing (2026-05-26) confirms no D136 primitive activates at P14: Primitives 1 (User as first-class concept), 2 (channel preference for outbound), and 4 (ChannelCapabilities descriptor) stay deferred at their existing activation triggers; Primitive 3 (PendingClarification user-scoped) stays active from S47 unchanged. References D119 (WhatsApp channel commitment), D129 (messaging substrate), D115 (ConversationFlow Protocol), D136 (multi-channel UX architectural primitives).

**P14 close confirmation (2026-05-27).** S52 close confirms no D136 primitive activates during P14 beyond the additive `target_cell` extension at D140 (Primitive 3's user-scoping discipline holds unchanged; the target_cell extension identifies *which cell* owns a pending without changing the user-scope). Primitives 1, 2, and 4 stay deferred at their existing activation triggers.

**P15 S53 activation (2026-05-27).** Primitive 2 (channel preference for outbound) activates at D144: ChannelResolver Protocol with static-configuration adapter at Phase 2-A. The user-scoped channel preference state defers to the second-channel activation trigger per Primitive 1's User aggregate root dependency. The Phase 2-A degenerate-static shape honors D136 Primitive 2's commitment exactly. Primitives 1 (User aggregate) and 4 (ChannelCapabilities descriptor) stay deferred at their existing activation triggers; Primitive 3 (PendingClarification user-scoped + target_cell extension) stays active unchanged.

### Shared-kernel CitedResponse base type or Protocol

D131's first instance at S46 (the manual entry cell's CellResponse value object carries citation fields directly per the convention altitude). D135 at S47 commits the convention discipline at Phase 2-A and defers the structural-enforcement question (a shared-kernel CitedResponse base type or Protocol that future ConversationFlow implementers conform to structurally) to the P14 second-instance trigger.

**Activation trigger.** P14 ConversationFlow implementers at audit-conversation (5.1) and mirror-conversation (4.1). When both implementers land within one framing or one session, the shared-kernel base type emerges at that framing. If they land sequentially across two sessions, the trigger fires at the second one.

**Status: closed by D138, 2026-05-26 (P14, S51 framing).** Runtime-checkable Protocol with three citation tuple fields at `shared_kernel/conversation_flow.py` (single-file alongside the existing ConversationFlow Protocol per pre-write reconciliation Finding 2). The shape committed at D138 plus ArtefactCitation typed value object (`artefact_id: UUID` plus `artefact_type: str` discriminator) authored fresh at S51 (the framing-time framing of ArtefactCitation as "currently at the manual entry cell module" was structurally false per pre-write reconciliation Finding 4). Heterogeneous-citations shape adopted per operator architectural disposition on Finding 4. Empty-field-at-first-instance gap closes on the read-side at audit-conversation; no write-result DTO extension required at P14.

**The specific shape lands at the activating session.** References D131 (provenance-aware response composition), D115 (ConversationFlow Protocol), D135 (rendering pattern; structural enforcement question deferred here), D138 (closure D-entry).

### Cost-aware routing policies at the LiteLLM gateway

D133 commits the gateway-as-resolution-point shape and the model registry's cost-per-call audit capture. Routing policies that consume cost as a dimension (failover, cost-aware routing within tenant-tier contracts, rate-limit awareness, tenant-tier-driven model selection) defer to Phase 3+ activation.

**Activation trigger.** Padhanam-provides-LLM business-model activation at Phase 3+ when multi-ICP customer deployments make Padhanam directly responsible for inference cost. Tenant-tier contracts and cost budgets become real configuration surfaces.

**The specific policy shapes land at the activating session(s).** References D133, D14 (customer-deployment model; tenant-tier contracts), principles.md lines 10-11 (vendor flexibility and architectural-commitments-evolve).

## P14 framing deferrals

Architectural decisions deferred at P14 framing (2026-05-26). Each names an activation trigger.

### Calendar-read and email-read cells at P14 versus P15+

The original `charter/packages.md` P14 line scoped 1.1 calendar-read cells (Google, MS365) plus 1.1 email-read cells (Gmail, Outlook) as Wave 2 substrate alongside other work-streams. P14 framing 2026-05-26 narrowed the P14 scope to the two ConversationFlow implementers (audit-conversation, mirror-conversation) and deferred the calendar-read and email-read cells.

**Activation trigger.** P15 framing. Same disposition for email-read cells (Gmail, Outlook). The intake-canonical commitment at D128 inherits transparently: calendar-read and email-read cells at P15 will land as intake-canonical orchestrations per the D127 precedent.

**Status: deferred at P14 framing (2026-05-26).** References D127 (intake-canonical orchestration substrate), D128 (intake-canonical commitment), the original `charter/packages.md` P14 line that surfaces this deferral.

### Mirror-conversation drill-down persisted state entity

Mirror-conversation drill-down navigation at P14 is stateless re-classification per turn against conversation history per D138 extension and architecture.md mirror-conversation drill-down stateless-per-turn sub-section. The design resists a second user-scoped state machine alongside PendingClarification at Phase 2-A.

**Activation triggers.** A persisted state entity becomes the right shape if any of: (a) operator dogfooding surfaces drill-down misclassification rate exceeding the gold-set threshold established at S52's gold-set authoring; (b) conversation-history-as-classifier-context fails at recurring sub-cases such as long pauses, context-window saturation, or cross-channel navigation when a second channel arrives; (c) a future ConversationFlow implementer at P15+ surfaces a parallel navigation-state requirement that would benefit from a shared state entity.

**Architectural disposition.** S52 commits the stateless-per-turn pattern; the entity defers at the activation triggers above. References D134 (PendingClarification entity; the precedent state machine the drill-down resists duplicating), D138 (CitedResponse Protocol; mirror-conversation response value object), D141 (cell_payload persistence; the additive-metadata mechanism the stateless-per-turn pattern uses for cross-turn focus extraction), D129 (messaging substrate; conversation history persistence).

**S52 build evidence (2026-05-27).** Stateless-per-turn drill-down with cell_payload extraction operational at mirror-conversation context per D141. Activation triggers from P14 framing remain in force; risk-shape disposition holds. First dogfooding evidence at the post-S52 procedural smoke; the activation trigger fires if operator dogfooding evidence surfaces brittleness.

### D137 substrate parameterisation over multiple intent surfaces

D137 commits the intent-classification evaluation substrate at `contexts/intent_classification_evaluation/` with `INTENT_CLASSES` at the domain shape hard-coded to the manual entry cell's intent surface (`create_case`, `add_data_point`, `revise_data_point`, `unclear`). S51 framing (P14 audit-conversation) added the audit-conversation intent surface to `INTENT_CLASSES` as a tuple extension; the gold-set domain shape and YAML fixture loader now serve two intent surfaces (manual entry plus audit) by string-membership against the extended tuple.

**Activation trigger.** A third ConversationFlow implementer's gold-set authoring (P14 S52 mirror-conversation adds the third intent surface; P15+ surfaces add fourth and beyond). When the tuple-extension pattern becomes operationally cumbersome (substring collision; per-surface metric calculation; per-surface latency budget; per-surface model-tier selection), promote the domain shape to a parameterised intent surface (an `IntentSurface` value object carrying the intent class set plus per-surface metadata, with `IntentClassificationGoldSet` holding a reference to one surface).

**Architectural disposition.** S51 extends `INTENT_CLASSES` as a minimal tuple extension (the cheapest possible adaptation). S52 may extend again the same way; the parameterisation triggers at the third-or-later instance where the tuple-extension stops carrying the cumulative weight. References D137 (substrate D-entry), D127 alternative (d) (build-at-second-instance discipline; this entry inverts the discipline by deferring parameterisation past two instances to surface the third-instance concrete evidence).

**S52 exercise (2026-05-27).** S52 adds two intent surfaces (`dispatch_classifier` from D140 plus `mirror_conversation` from the mirror-conversation cell), bringing the substrate to four registered surfaces (manual_entry, audit_conversation, dispatch_classifier, mirror_conversation). The tuple-extension pattern still carries the load operationally at four surfaces; per-surface metric calculation, per-surface latency budget, and per-surface model-tier selection have not surfaced as drivers. The activation trigger holds for a future P15+ surface that materially diverges in any of those dimensions.

## P14 close deferrals

Architectural decisions deferred at P14 close (2026-05-27). Each names an activation trigger.

### Cell-payload schema registry at messaging context

D141 commits per-implementer `cell_payload` JSONB on the messages table with implementer-side validation on read: each ConversationFlow implementer defines and validates its own payload shape. At P14 close mirror-conversation is the only implementer with a non-null payload shape (`{"current_focus_artefact": {"artefact_id": str, "artefact_type": str}}`); audit-conversation and manual_entry do not populate the column.

**Activation trigger.** Third or fourth ConversationFlow implementer with substantial cell_payload shape, where coordination across implementers becomes valuable. Indicators: (a) two or more implementers want to read each other's cell_payload (cross-cell focus continuity); (b) a future implementer's cell_payload shape would benefit from versioning (e.g., schema-evolution sub-cases that the implementer's own validation would need to track explicitly); (c) tooling or analytics surfaces that consume cell_payload across all implementers need a registry to discover the per-implementer shapes.

**Architectural disposition.** At P14 close the implementer-side validation discipline carries the load (one implementer with one payload shape). The registry shape (a cross-context registration surface mapping cell-identifier to payload-schema, with the dispatch_inbound use case or a sibling surface enforcing the registration) defers to the activation trigger. References D141 (cell_payload persistence D-entry), D115 (ConversationFlow Protocol), D140 (meta-classifier dispatch routing; the CellIdentifier enum would carry the registry's keys).

## P15 framing deferrals

Architectural decisions deferred at P15 framing (2026-05-27). Each names an activation trigger.

### Background sync for calendar and email at messaging context

P15 framing Surface 5 Sub-question 5.6 committed pull-on-demand sync mechanics at Phase 2-A: the calendar-conversation (S55) and email-conversation (S56) ConversationFlow implementers fetch external state at WhatsApp turn boundaries through the Nango-fronted HTTP adapters per D14. Background sync (periodic poll-and-store; webhook-driven push-and-store) is not committed at Phase 2-A.

**Activation triggers.** Background sync activates if (a) the ThresholdEvaluator (S57) extends to external-data threshold detection (calendar-event-arrived; email-matching-pattern-received) and pull-on-demand latency makes the evaluation surface fail (the periodic threshold-evaluation latency window cannot accommodate a synchronous external fetch per evaluation iteration); (b) operator dogfooding evidence surfaces query-latency complaints from pull-on-demand at WhatsApp turn boundaries (the operator types a calendar query and the response delay exceeds a tolerable threshold for the conversational shape).

**Architectural disposition.** Phase 2-A commits pull-on-demand only. The specific persistence shape (per-tenant calendar_events and email_messages tables vs. event-store-shaped tables vs. domain-driven aggregates per calendar/email contexts) commits at the activating session with the latency-evidence the activation produced. References D14 (separate-service for tool capabilities), D110 (audit-event-level tamper-evidence — background sync would emit per-fetch audit events).

### MCP transport swap for calendar and email tool services

P15 framing Surface 5 Sub-question 5.1 committed HTTP transport for tool service consumption at Phase 2-A: the calendar (`contexts/calendar/`) and email (`contexts/email/`) contexts consume Nango self-hosted via HTTP adapter per D14 separate-service pattern.

**Activation triggers.** The MCP transport swap activates if (a) the tool service ecosystem standardizes on MCP and Nango (or its successor) ships MCP as the preferred transport for the consumed services; (b) Padhanam itself adopts MCP for other tool integrations (the existing agent-runtime tool registry per D89 is the candidate first MCP integration site within the codebase; if it adopts MCP, the calendar/email contexts inherit the same transport pattern for consistency).

**Architectural disposition.** Protocol-based adapter pattern at calendar and email contexts supports the swap; the consumer-defined port (CalendarReader, EmailReader) stays unchanged; only the HTTP adapter swaps to an MCP adapter at composition root. ChannelResolver Protocol-equivalent abstraction stays unchanged. References D14 (tools-as-configuration; protocol-agnostic adapter pattern), D89 (tool registry; candidate first MCP integration site), principles.md "Integration protocol choice is scenario-driven and vendor-readiness-modulated" (per-integration disposition).

### Path A migration from Nango self-hosted

P15 framing committed Path B (source tool services externally) with self-hosted Nango under Elastic License as the operator's tool-service substrate, sitting alongside padhanam-api as parallel infrastructure work outside Padhanam's package boundary. Path A (Padhanam-owned tool services) defers.

**Activation triggers.** Migration to Path A activates if any of: (a) vendor pricing inversion at Phase 2-B+ scale — monthly Nango spend exceeds the loaded cost of Padhanam-owned OAuth substrate plus the relevant per-service integrations; (b) privacy compliance escalation — Padhanam-owned ICP requires attestations vendor pass-through cannot satisfy (the operator-controlled self-hosted Nango at Phase 2-A keeps data inside operator infrastructure, but a regulated-customer deployment may need Padhanam-owned cryptographic custody of tokens at a finer granularity than self-hosted Nango exposes); (c) feature divergence — the bet's substrate evolution requires OAuth handling or tool-service capability that Nango does not provide and that maintaining a fork against Nango would cost more than building Padhanam-native.

**Architectural disposition.** D14's separate-service pattern plus D144's port-based ChannelResolver abstraction plus consumer-defined CalendarReader / EmailReader ports at calendar/email contexts support the migration without domain code changes — only adapter swaps at composition root. The specific Path A scope (which providers; OAuth flow shape; token persistence) commits at the activating session per the migration trigger evidence. References D14 (tools-as-configuration), D144 (ChannelResolver Protocol; port-based-abstraction precedent), the operator-tool-service-sourcing strategic decision recorded at `log/captures.md` 2026-05-27.

## P15 S54 deferrals

Architectural decisions deferred at P15 S54 framing (2026-05-27). Each names an activation trigger.

### fired_triggers two-phase commit semantics

D147 commits the fired_triggers table with race-safe idempotency via `INSERT ... ON CONFLICT DO NOTHING` and best-effort delivery between INSERT and BroadcastDispatch invocation. The fired_triggers row plus the BROADCAST_INITIATED audit event together record the attempt; if dispatch fails after INSERT succeeds, the operator misses that day's briefing on rare failures and structured logging captures the failure.

**Activation triggers.** Two-phase commit semantics (status tracking; `attempt_count`; `last_attempted_at` columns; compensating-update on dispatch failure) activate if operator dogfooding surfaces unacceptable failure recovery — multiple missed briefings within a short window; unclear failure attribution; recurring dispatch failures that retry storms would aggravate. Activation trigger fires at the first dogfooding evidence of recurring failure.

**Architectural disposition.** The fired_triggers table accommodates extension without restructuring (additive columns; no UNIQUE constraint changes). The FireTrigger use case sequence stays the same; the additional status-tracking logic lives at the use case boundary. References D147 (Failure handling section).

### fired_triggers retention policy

D147 commits no explicit retention policy at Phase 2-A. The fired_triggers table grows at one row per tenant+user+day at Phase 2-A dogfooding scale (low growth).

**Activation triggers.** Phase 2-B+ scale (multi-tenant deployment; multiple broadcast types per day per user; multi-year operation) activates a retention policy — typically delete rows older than 90 days. Trigger fires at multi-tenant deployment or at fired_triggers table-size operational evidence (the table outgrowing the diagnostic-read pattern's responsiveness).

**Architectural disposition.** A scheduled retention job (cron-driven via the existing HTTP trigger endpoint substrate; or a database-side scheduled task) deletes rows older than the configured window. The UNIQUE constraint on `(tenant_id, user_id, trigger_type, idempotency_key)` is not affected because retained rows are all in the historical past. References D147 (Retention section).

### TriggerContext metadata schema completion at activation triggers

S54 commits TriggerContext discriminated-helper dataclasses for DAILY_SCHEDULED (empty payload) and MANUAL (optional `caller_note`). The shared TriggerContext.metadata field stays as `dict[str, Any]` per pre-write reconciliation Finding 3 at S54 (preserves S53 test stability); typed metadata classes act as convenience constructors that serialise into the dict.

**Activation triggers.** Each future trigger type commits its metadata schema at the session that activates the trigger:

- THRESHOLD_CROSSED metadata commits at S57: fields `matched_audit_event_id`, `rule_id`, `matched_value`.
- CALENDAR_EVENT metadata commits at the Phase 2-B+ session activating external-data threshold detection on calendar events.
- EMAIL_RECEIVED metadata commits at the Phase 2-B+ session activating external-data threshold detection on email patterns.

**Architectural disposition.** The idempotency key resolver at `contexts/messaging/domain/idempotency.py` raises `NotImplementedError` for trigger types whose metadata schema has not yet been committed. References D142 (TriggerContext shape), D147 (idempotency key semantics per trigger type).

### Daily-briefing cell_payload activation trigger

D146 commits daily-briefing without cell_payload persistence at first instance. Broadcasts do not have user-driven follow-up turns the way ConversationFlow implementers do; no cross-turn state extraction is required.

**Activation triggers.** Cell-payload persistence for daily-briefing activates if (a) a future daily-briefing rendering needs the previous briefing's attention items for continuity (e.g., "you flagged these last time; status is now ..."); (b) any other BroadcastFlow implementer requires cross-turn state extraction symmetric to mirror-conversation's drill-down focus.

**Architectural disposition.** D141's cell_payload persistence mechanism is already established and operates additively. The activation requires an implementer-side payload-shape commitment plus extract-on-read logic; no schema change at the messages table. References D141 (cell-payload persistence; implementer-side validation).

### Audit-chain change-data-capture for substrate state changes (provenance completeness)

Surfaced by the S57 D153 reconciliation. The threshold-evaluator evaluates over the calendar *state* store rather than the audit chain because `sync_calendar` emits no audit events — calendar state changes (cancel/move) live in the meetings store as upserts/tombstones, not as audit-chain records. D153 preserves traceability of the *crossing* (the THRESHOLD_CROSSED outcome is audited with rule_id + google_event_id + cancelled_at), but the underlying substrate change itself is not in the chain.

**What defers.** Whether the audit chain should eventually capture substrate state-changes as full change-data-capture (every calendar tombstone/upsert, every email upsert/tombstone emitting an audit event) for end-to-end provenance completeness — so the chain answers "what changed in the operator's calendar/inbox and when," not only "what the platform did about it." This is a real procurement-hardening question (a buyer auditing the platform may want the substrate deltas in the tamper-evident chain, not only the platform's reactions), but it is a P15-audit or Phase 2-B question, not a close-session one: it touches every substrate's sync path (AuditPort + emission), adds chain volume, and wants a deliberate classification of which substrate deltas are audit-worthy.

**Activation trigger.** A procurement/compliance requirement for substrate-delta provenance (a buyer or the senior-leader ICP asks "show me the audit trail of calendar/inbox changes themselves"), or a second proactive surface that genuinely needs to match on substrate-change *events* rather than current state. Until then the state-store-evaluation model (D153) holds and the crossing-outcome audit is the traceability surface. References D153, D148/D149 (calendar substrate), D151 (email substrate), D102/D131 (audit chain + citation traceability).

### Stable original cancellation timestamp + cancellation-title enrichment (threshold-briefing)

Surfaced by the S57 live smoke. Two coupled calendar-substrate limitations the threshold-briefing works around but does not fix:

1. **`cancelled_at` is not the original cancellation time.** `tombstone_meeting` (calendar) sets `cancelled_at` to the refresh time on every sync, so a still-cancelled event that Google keeps returning is re-tombstoned with `cancelled_at=now` each scan. D153's threshold design works around this (cancellation identity excludes `cancelled_at`; the scan-window match is lower-bound only), but the *true* original cancellation instant is lost. The deeper fix is to make `tombstone_meeting` preserve the original `cancelled_at` (set it only on the first transition to cancelled), which would let the threshold scan window mean "cancelled in the last N hours" literally and would restore `cancelled_at` as a meaningful audit field.

2. **The tombstone purges meeting content.** `tombstone_meeting` NULLs the encrypted content (title/description/location) and the embedding, so a cancellation briefing reads "(untitled)" from the store and can only say "a meeting was cancelled" without naming it. Naming the cancelled meeting needs the pre-cancellation title, which the calendar `meeting_citation` audit snapshots retain (D148 option b) but the threshold evaluator does not consult. Enrichment options: retain a plaintext title on the tombstone (a classification call — titles were judged D21-sensitive at D148), or have the evaluator look up the last `meeting_citation` snapshot for the event.

**What defers.** Both are calendar-substrate (or threshold-to-audit-coupling) changes deliberately not taken at the P15-closing session (Design 1's no-substrate-touch principle, D153). **Activation trigger.** Dogfooding signal that "a meeting was cancelled" without the title is too low-signal to earn the interruption (the reverse-Kano test applied to the briefing's *content*, not just its firing), or a need for a literal original-cancellation-time audit field. References D153, D148 (calendar Meeting content encryption), the reverse-Kano discipline.
