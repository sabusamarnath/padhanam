# Padhanam Architecture

This document is the architectural synthesis surface for Padhanam. It organises architectural commitments into a coherent narrative with diagrams, supporting onboarding-time, phase-audit-time, and procurement-grade-touch reading. It does not duplicate binding rules (`charter/principles.md`) or full reasoning (`charter/decisions.md` plus per-phase archives at `docs/archive/decisions/`); it synthesises them.

## Overview

Padhanam is a public demonstration that a senior product leader can direct the end-to-end implementation of an enterprise-grade agentic platform through Claude Code without writing code (see [`charter/bet.md`](bet.md)). The architectural commitments below exist because the proposition is being tested at the level of complexity that real enterprise software requires: multi-tenant, identity-federated, audit-chained, jurisdiction-aware, OTel-instrumented. A demonstration that AI-assisted development can produce a single-tenant prototype answers nothing useful; the architecture's discipline is the substrate of the proposition.

The platform's substrate (Phase 1, packages P1 through P12) supports an agent layer that demonstrates methodology embedding across professional functions. The four-context P11 substrate scaffold (`contexts/retrieval_evaluation/`, `contexts/run_history/`, `contexts/audit/`, `contexts/optimization/`) is the procurement-grade-defensibility surface that closes the bet's success criterion 4: the trace capture layer surfaces optimisation recommendations procurement readers can verify end-to-end with full evidence-citation traceability.

Architectural decisions read like "what enterprise procurement requires for purchase" — literally so, since enterprise procurement is the level at which the proposition is being tested rather than preparation for a sales motion. The architecture commits to abstractions; protocol choices, vendor selections, and operational specifics are configuration above the abstractions. Vendor lock-in is not architectural per the procurement-grade commitment at `charter/principles.md`.

The seven sections below organise architectural commitments thematically:

1. **Architectural patterns** — hexagonal architecture within a context; bounded contexts at the top of the codebase; observability as foundation; binding specifications live in charter.
2. **Tenancy and jurisdiction** — database-per-tenant; jurisdiction as first-class architectural attribute; tenant onboarding as configuration not deployment; customer-specific behaviour as configuration.
3. **Vendor and dependency posture** — vendor flexibility; LLM-provider-agnostic via LiteLLM; hybrid retrieval; OTel as observability portability boundary; audit hash-chain primitive at platform layer.
4. **Domain primitives** — role-first agent identity; methodology as defaults plus envelopes; four-layer constraint stack; recommendation-shaped optimisation output.
5. **The four-context substrate** — retrieval_evaluation, run_history, audit, ingestion as producers; optimization as consumer; HTTP transport with OpenAPI specification.
6. **Cross-document map** — three-document relationship (principles → decisions → architecture); reading modes; this document's place in the charter.

## Architectural patterns

Four architectural patterns anchor the codebase: hexagonal architecture within each bounded context; bounded contexts at the top of the codebase; observability as foundation rather than feature; binding specifications living in charter.

### Hexagonal architecture within a context

Every bounded context follows a hexagonal-layered structure: a `domain/` core carries value objects, aggregates, and pure domain logic with no framework or vendor imports; an `application/` layer carries use cases that orchestrate domain logic and call out through ports; a `ports/` directory exposes Protocol-typed boundaries the application layer depends on; an `adapters/` directory implements the ports against external systems (Postgres, Neo4j, Langfuse, vendor LLM gateways) with `inbound/` for transport-driven adapters (HTTP routes, CLI commands) and `outbound/` for storage-and-service adapters. Import-linter contracts enforce the layering at CI per D16: domain never imports from application or adapters; application never imports from adapters; adapters depend on ports.

```mermaid
flowchart LR
    subgraph context[Bounded Context]
        direction LR
        domain[domain/<br/>value objects<br/>aggregates<br/>pure logic]
        application[application/<br/>use cases]
        ports[ports/<br/>Protocols]
        inbound[adapters/inbound/<br/>HTTP, CLI]
        outbound[adapters/outbound/<br/>Postgres, Neo4j, LLM]
        domain --> application
        application --> ports
        inbound --> application
        outbound -.implements.-> ports
    end
    external_in([HTTP request<br/>CLI command]) --> inbound
    outbound --> external_out([Postgres<br/>Neo4j<br/>Langfuse<br/>LLM gateway])
```

The hexagonal pattern lets the domain layer stay framework-free and vendor-free, which is the foundation that makes the vendor-flexibility commitment per D111 mechanical rather than aspirational. Adapter replacement is vendor swap; domain code does not change. See `charter/principles.md` "Hexagonal throughout" (per D4, D16).

### Bounded contexts at the top of the codebase

The codebase organises around bounded contexts at the top level, with cross-cutting platform concerns in `padhanam/`, a strictly bounded `shared_kernel/`, and deployable units in `apps/`. Each context has its own hexagonal layering; contexts communicate via published query APIs for reads and a domain event bus for state changes per D17; direct cross-context imports are forbidden by import-linter per D16. The `shared_kernel/` contains only types that must be referentially equal across contexts (`TenantId`, `Jurisdiction`) and forbids Pydantic imports to prevent framework-version coupling.

```mermaid
flowchart TB
    subgraph apps[apps/ — deployable units]
        cli[apps/cli/]
        api[apps/api/]
    end
    subgraph contexts[contexts/ — twelve bounded contexts]
        direction TB
        agent[agent/]
        audit[audit/]
        evaluation[evaluation/]
        inference[inference/]
        ingestion[ingestion/]
        methodology[methodology/]
        observability[observability/]
        optimization[optimization/]
        retrieval_eval[retrieval_evaluation/]
        run_history[run_history/]
        tenancy[tenancy/]
        tools[tools/]
    end
    subgraph cross_cut[padhanam/ — cross-cutting platform]
        config[config/]
        security[security/]
        persistence[persistence/]
        observability_lib[observability/ — span emission]
        events[events/ — domain event bus]
    end
    sk[shared_kernel/<br/>TenantId, Jurisdiction]
    cli --> contexts
    api --> contexts
    contexts --> cross_cut
    contexts --> sk
    cross_cut --> sk
```

Twelve bounded contexts at Phase 1 close: agent, audit, evaluation, inference, ingestion, methodology, observability, optimization, retrieval_evaluation, run_history, tenancy, tools. The split between `contexts/observability/` (analysis-layer domain logic) and `padhanam/observability/` (span emission infrastructure) is structurally honest per D16: cross-cutting plumbing belongs in `padhanam/`, domain logic belongs in `contexts/`. See `charter/principles.md` "Bounded contexts at the top of the codebase" (per D16, D17, D28).

### Observability as foundation

Trace capture starts from the first LLM call. OTel GenAI conventions are the portability boundary per D27; vendor-specific observability code is confined to adapters. Span attributes carry tenant_id, jurisdiction, cost-per-token, and (from D27) trace_id as a join key into the run-history projection. The audit context is bounded (`contexts/audit/`), not cross-cutting plumbing; hash-chained append-only storage records every state change with actor, tenant, jurisdiction, timestamp, action verb, resource, before/after state, and correlation ID per D26. The observability foundation is what makes the optimisation layer's recommendation-shaped output (per D9) procurement-grade-defensible: traces with cost dimension surface "this costs N% more for M% quality at the same task type" recommendations that procurement readers can verify against citations. The "Vendor and dependency posture" section below covers OTel + Langfuse adapter detail; the "The four-context substrate" section below covers the audit context's read surface.

### Binding specifications live in charter

Brand identity (`charter/brand-guidelines.md`, `charter/brand/tokens.css`) and bounded-context architecture (`charter/contexts/*`) are commitments the platform stands behind, not implementation detail. Implementation reads specification; specification does not live in implementation. Per D91. The charter is the methodology's primary artefact surface; the binding-specifications discipline ensures the charter is read-as-truth rather than aspirational-or-decorative content.

## Tenancy and jurisdiction

Four tenancy commitments anchor the platform: database-per-tenant topology; jurisdiction as first-class architectural attribute; tenant onboarding as configuration rather than deployment; customer-specific behaviour as configuration via tools plus bounded extensions.

### Database-per-tenant topology

Tenancy is database-per-tenant per D1: each tenant has its own Postgres data plane, separate from the control plane and from every other tenant's data plane. A control-plane Postgres instance carries the tenant registry, role-revisions, methodology-revisions, tool-revisions, and other platform-managed shared content. Per-tenant Postgres instances carry the tenant's own data (sources, chunks, agents, gold-sets, runs, audit chain). The connection routing layer per D36 resolves the per-tenant data plane from the TenantContext propagated through the call stack.

```mermaid
flowchart TB
    subgraph cp[Control plane Postgres]
        tenant_registry[(tenant_registry)]
        role_revisions[(role_revisions)]
        methodology_revisions[(methodology_revisions)]
        tool_revisions[(tool_revisions)]
        platform_audit[(tenant_audit — platform)]
    end
    subgraph t1[Tenant A data plane Postgres]
        t1_sources[(sources)]
        t1_chunks[(chunks)]
        t1_agents[(agents)]
        t1_gold_sets[(gold_sets)]
        t1_runs[(runs)]
        t1_audit[(tenant_audit)]
    end
    subgraph t2[Tenant B data plane Postgres]
        t2_sources[(sources)]
        t2_chunks[(chunks)]
        t2_agents[(agents)]
        t2_gold_sets[(gold_sets)]
        t2_runs[(runs)]
        t2_audit[(tenant_audit)]
    end
    request([Inbound HTTP request<br/>JWT-resolved tenant_id])
    tc[TenantContext<br/>tenant_id, jurisdiction,<br/>cost_attribution_id]
    routing[Per-tenant connection<br/>routing layer]
    request --> tc
    tc --> routing
    routing --> t1
    routing --> t2
    tc -.shared content.-> cp
```

`TenantContext` is the shared-kernel value object carrying `tenant_id`, `jurisdiction`, and `cost_attribution_id` per D50; it propagates through every layer that touches tenant-scoped data. Tenant isolation is verified by `tests/contract/tenant_isolation/` red-team-shaped tests against every adapter per D24. Per-tenant connection caching at `padhanam/persistence/routing.py` per D36 keeps the topology efficient without weakening isolation. See `charter/principles.md` "Database-per-tenant" (per D1, D32). For the Phase 2 production-deployment revisit on Neo4j topology (currently shared with property-based scoping per D63), see `charter/deferred-decisions.md` under "Production-deployment readiness".

### Jurisdiction as first-class architectural attribute

`Jurisdiction` is a first-class architectural attribute carried in `TenantContext` from P3 onward per D12. Every component that touches customer data (databases, object storage, identity, trace store, LLM endpoints) is built to be regionally partitionable. Phase 1 deploys a single region; the architecture does not assume a single region anywhere in code. The discipline is "by construction, not by policy" — adding it later is a refactor across forty tables and every interface signature; building it in from inception is free at the data-model layer and cheap at the interface layer. See `charter/principles.md` "Jurisdiction is a first-class attribute" (per D12).

### Tenant onboarding as configuration not deployment

Per-tenant decisions (jurisdiction, identity federation, classification policy, model endpoints, retention) live in the tenant registry as configuration per D13. Adding a tenant to an existing regional stack is an idempotent provisioning workflow; adding a region is a separate infrastructure event scoped explicitly when a customer's residency requirement crosses an existing region boundary. The architectural commitment that adding a tenant requires no code changes is what makes the platform sellable to enterprise customers with custom IdP, jurisdiction, and classification requirements. See `charter/principles.md` "Tenant onboarding is configuration" (per D13).

### Customer-specific behaviour as configuration

Tools (external services called by the platform on the tenant's behalf) cover most customer-supplied logic per D14. Bounded extensions exist for residual cases at named interfaces (RetrievalClient, scorer, pre-processor), sandboxed per tenant. The platform is designed so forking is unnecessary per D76; observed forks signal extension surface failure to be addressed upstream. The forking-phrasing refinement at D76 supersedes D14's original "forbidden" wording without rewriting D14 itself, preserving the audit trail per the append-only discipline. See `charter/principles.md` "Customer-specific behaviour is configuration" (per D14, D76).

## Vendor and dependency posture

Vendor flexibility is a procurement-grade commitment per D111: external dependencies — LLM provider, embedding model, database backend, vector store, graph store, audit target, observability target — sit behind ports; vendor swap is configuration or adapter replacement, never domain change. Operationalised at the producer-context level through MetricCalculator and RecommendationRule pluggable domain abstractions in `contexts/optimization/` (Phase 1, per D111); ported domain-layer pluggability is the same principle applied to pluggable evaluation techniques and recommendation rules.

```mermaid
flowchart LR
    subgraph domain[Domain ports]
        llm_port[LLMPort]
        embedder[ChunkEmbedderPort]
        retrieval[RetrievalClient]
        audit_port[AuditPort]
        obs_port[ObservabilityPort]
        metric_calc[MetricCalculator]
        rec_rule[RecommendationRule]
    end
    subgraph adapters[Adapters]
        litellm[LiteLLM adapter]
        ollama_embed[Ollama embedder adapter]
        pgvector[pgvector adapter]
        neo4j_adapter[Neo4j adapter]
        otel_adapter[OTel adapter]
        langfuse_adapter[Langfuse adapter]
        postgres_audit[Postgres audit adapter]
    end
    subgraph external[External systems]
        ollama_local[Ollama local]
        anthropic[Anthropic API]
        openai[OpenAI API]
        postgres[Postgres]
        pgvector_db[(pgvector)]
        neo4j_db[(Neo4j)]
        langfuse[Langfuse server]
    end
    llm_port -.-> litellm
    embedder -.-> ollama_embed
    retrieval -.-> pgvector
    retrieval -.-> neo4j_adapter
    audit_port -.-> postgres_audit
    obs_port -.-> otel_adapter
    otel_adapter --> langfuse_adapter
    litellm --> ollama_local
    litellm --> anthropic
    litellm --> openai
    pgvector --> pgvector_db
    neo4j_adapter --> neo4j_db
    postgres_audit --> postgres
    langfuse_adapter --> langfuse
```

### LLM-provider-agnostic via LiteLLM

LLM access flows through a LiteLLM gateway behind `LLMPort` per D4. The development default is Ollama serving Qwen 2.5 7B per D15 (tool-calling fidelity at the embedding-cost ceiling); production swap is configuration through `padhanam/config/`. No vendor SDKs in domain code; import-linter contracts enforce `no-vendor-sdks-in-domain` at CI. See `charter/principles.md` "LLM-provider-agnostic via LiteLLM" (per D4, D15).

Phase 2 extends the LiteLLM abstraction with latency-tier inference routing per D122. Call sites pass tier hints; the gateway routes per tier configuration in `padhanam/config/inference.py`. See `charter/architecture.md` "Phase 2 architectural primitives" "Latency-tier inference routing" subsection for full specification.

### Hybrid retrieval via pgvector and Neo4j

Retrieval is hybrid: vector via pgvector (HNSW cosine, nomic-embed-text embeddings per D62), graph via Neo4j (shared instance with property-based tenant scoping per D63), both behind the `RetrievalClient` port per D5. Strategy selection at runtime per D66's agent-runtime-executed-composition pattern; the strategy catalogue ships vector_only, graph_only, and parallel_rrf (the last currently deferred per `charter/deferred-decisions.md`). See `charter/principles.md` "Hybrid retrieval" (per D5).

### OTel as observability portability boundary

Observability uses OpenTelemetry GenAI conventions as the portability boundary per D27. Span attributes carry tenant_id, jurisdiction, cost-per-token, and trace_id. Vendor-specific observability code is confined to adapters; the trace store is self-hosted Langfuse 3 per D7 behind an `ObservabilityPort`. Production swap to a different observability vendor is adapter replacement.

### Hash-chain primitive at the platform layer

The hash-chain primitive (canonical-JSON-sorted-keys plus SHA-256 with chain-link) lives at `padhanam/security/hash_chain.py` per D75 (promoted from `contexts/methodology/` at S24). Multiple contexts reuse it: the audit context (`contexts/audit/`) per D26 for append-only audit-event chains; the methodology context for revision-with-hash-chain; the retrieval_evaluation context per D109 for gold-set revisions; the optimization context per D111 for recommendation evidence-citation tamper-evidence. The cross-context reuse pattern is structurally honest because the hash-chain primitive is general (any append-only-with-content-integrity surface uses the same shape) while the input-shaping per context lives at each context's domain layer.

## Domain primitives

Four domain primitives anchor the platform's product-shaped surfaces: role-first agent identity; methodology as defaults plus envelopes; the four-layer constraint stack; recommendation-shaped optimisation output.

### Role-first agent identity

Roles are the primary identity for agents per D86. The agent's job is the role it occupies. Methodologies are playbooks the role applies (situationally); skills are granular capabilities the agent invokes. The role-first model lets methodologies compose at runtime via lineage rather than at design-time via inheritance — an agent has a single role identity throughout its lifetime, and the methodologies it has adopted are recorded as a lineage that affects its constraint bundle without changing its identity. See `charter/principles.md` "Role-first agent identity" (per D86).

### Methodology as defaults plus envelopes

When an agent adopts a methodology, the methodology is embedded as defaults for tuning surfaces and as envelopes for security, budget, and scope surfaces per D81. Defaults activate at decision points, encode the right thing for the chosen methodology, and yield to user intent at low cost. Envelopes bind hard and are validated at agent write time. The product surface treats user intent as primary for tuning; envelopes are non-overridable by the agent and exist to protect the tenant and the platform. The methodology document is the long form of the operating model; the methodology context (`contexts/methodology/`) is the runtime layer.

Per-field binding-mode discipline at D81 commits three hard-bound fields and six soft-bound fields as platform convention. The override mechanism for methodology-author-driven per-field binding deviation defers to Phase 2 per the deferred-decisions entry on "Per-role binding-mode override".

### Four-layer constraint stack

Per D80, agent runtime constraints stack in four layers, applied in order:

```mermaid
flowchart TB
    subgraph stack[Constraint application order]
        direction TB
        agent_layer[4. Agent layer<br/>per-instance overrides<br/>e.g. system_prompt, temperature]
        workflow[3. Workflow layer<br/>opt-in via invocation context<br/>e.g. workflow-scope constraints]
        methodology[2. Methodology layer<br/>opt-in via role lineage<br/>defaults plus envelopes per D81]
        platform[1. Platform invariants<br/>universal floor<br/>D82 invariants 1-5]
        platform --> methodology
        methodology --> workflow
        workflow --> agent_layer
    end
    output([Effective agent constraint bundle<br/>at invocation time])
    agent_layer --> output
```

Platform invariants per D82 are the universal floor — non-overridable, applied to every agent invocation regardless of methodology lineage, workflow context, or per-agent overrides. The five Phase 1 close invariants (no financial execution without per-transaction authorization; no outbound communication without per-invocation authorization; no acceptance of legal commitments without explicit user action; no auto-modification or auto-deletion of user-authored content; no transmission of tenant data outside tenant-configured tool paths) protect the tenant and the platform. Each invariant maps to safety dimensions (privacy, integrity, reversibility, transparency, control, auditability) per `charter/principles.md` "User safety".

Methodology layer applies if the agent has methodology lineage; envelopes bind hard, defaults are tuning suggestions. Workflow layer applies if the agent is invoked within a workflow context (Phase 2 per D83). Agent layer is per-instance: the agent's authored constraints (system_prompt, model_selection, retrieval bounds) plus the override-mode space per D87 (augment/replace/tighten per-field).

### Recommendation-shaped optimisation output

Per D9, optimisation output is recommendation-shaped, not chart-shaped. Every dashboard view ties to a recommended action. The principle extends to the agent layer per `charter/principles.md` "Padhanam-as-intelligence-layer": Padhanam produces recommendations, analyses, and drafts; consequential actions on the user's behalf require user-in-the-loop authorization at appropriate granularity per the platform invariants.

The recommendation aggregate at `contexts/optimization/` carries five fields per D108 (category, subject, text, evidence_citations, status); numeric confidence scores stay out on D9 grounds (a single floating-point "confidence" would be chart-shaped). The four Phase 1 recommendation categories are retrieval_strategy, model_choice, prompt_revision, cost_optimization per D108 commitment 5. Evidence citations are a discriminated union with structured CaveatAnnotation per D111; the citation surface lets procurement readers trace prose → rule → citation → producer-context records without ambiguity.

## Phase 2 architectural primitives

Six architectural primitives anchor Phase 2-A and carry forward to Phase 2-B. The primitives surfaced at Step 5 of the Phase 2 design 7-Step arc as cross-sub-problem patterns and committed at Step 6 Pass 1 dispositions. Each primitive commits at Phase 2-A with operational delivery per the package structure at `charter/packages.md` P13-P16; Phase 2-B expansions follow per P17-P20.

### Revision-with-lineage standard interface

Per D114. The Revisable Protocol provides revision-with-lineage semantics for aggregates that mutate state through user-initiated or platform-initiated revisions. Three contexts implement the protocol at Phase 2-A: the portfolio context (per 1.3 state persistence; revisions for status transitions and content edits), the methodology context (per 2.1 methodology adaptation; user-adapted methodology revisions preserve genealogy from parent methodology), and the goal context (per 4.2 goal-state tracking; goal revisions preserve lineage and transfer linked items per the revision-with-lineage discipline). The pattern saturated across 2.1, 4.2, 3.2, 6.5 per Step 5 Pass 2 Work-stream 2 architectural patterns. CI-enforceable conformance via contract tests at `tests/contract/revisable/`. Cross-context reuse pattern structurally honest: the Revisable Protocol is general (any append-only-with-lineage surface uses the same shape) while input-shaping per context lives at each context's domain layer. References D26 (append-only audit chain), D31 (revisions pattern), and the hash-chain primitive at `padhanam/security/hash_chain.py` per D75.

### Conversation flow standard interface

Per D115. The ConversationFlow Protocol provides conversation-shaped surface semantics for user-invoked review and platform-initiated review-or-confirmation flows. Two contexts implement at Phase 2-A: the audit context (per 5.1 audit-conversation; broad audit review, filtered-by-event-class queries, item-specific drill-downs, goal-specific drill-downs, reflection-shaped queries) and the portfolio context (per 4.1 mirror-conversation; user invocation, narrative-response structure, drill-down conversation paths). Across-the-board at Phase 2-A per Step 5 Pass 2 Work-stream 2. Cross-context reuse pattern: the protocol carries the conversation-shaped surface contract; per-context content discipline lives at each context's domain layer (audit-narrative composition is technical-writer discipline with per-event-class templates; mirror-narrative composition is technical-writer discipline with narrative-language overlay). CI-enforceable conformance via contract tests at `tests/contract/conversation_flow/`.

### Three-tier consent-and-awareness framework

Per D116. Three tiers govern platform-initiated action surfacing: Tier 1 real-time review for high-danger classes (financial execution, outbound communication, legal commitments, irreversible operations); Tier 2 surfaced operation with user-controlled digest review cadence (routine reversible actions with audit visibility); Tier 3 silent operation does not exist per D121. Tier-depends-on-initiation refinement: same operation operates at different tiers depending on initiation context, not on operation type. Platform-initiated drops sit at Tier 1 (reversibility-sensitive); user-initiated drops follow the 1.5 commit-and-notify pattern. Native specification at sub-problem 5.4; cross-cuts surfacing mechanics at 3.1, drop-suggestion logic at 3.2, methodology adaptation at 2.1, goal-revision at 4.2, audit-conversation at 5.1, status-veracity at 6.3, correction mechanics at 6.5. The framework operationalises the existing consent-granularity-proportionate-to-danger principle at `charter/principles.md` without replacing it; framework operates as commercial positioning differentiator beyond safety hygiene per the procurement-grade audit-trailed-approval-first defensibility pattern identified in May 2026 competitor research at `charter/competitors.md`. References D82 (platform invariants) and D116.

### Tiered-by-salience

Per D117. Salience classification drives per-action surface depth across six surfaces: surfacing-decision logic at 3.1 (single-most-urgent platform-initiated default; batched narrative for user-invoked); drop-suggestion triggers at 3.2 (salience-weighted trigger evaluation); mirror-response density at 4.1 (configurable depth per user salience preference); audit-narrative density at 5.1 (per-event-class salience-weighted summarisation); status-veracity surface granularity at 6.3 (lower-pressure status options for low-salience items); methodology-applied importance threshold at 2.1 (salience-weighted methodology-recommendation surfacing). High-salience surfaces receive richer treatment; low-salience surfaces receive lighter treatment. Salience classification per surface is rules-driven at Phase 2-A (item-type rules; user-declared preferences; methodology-applied importance signals); learned-pattern-based salience defers to Phase 2-B Cluster B4 per the deferred-decisions entry on pattern-based triggers.

### Two-vector decay model

Per D118. Methodology-applied calibrations stale on two orthogonal vectors. Age vector: time-based decay; each methodology declares stale-after-N-time-units (RICE quarterly cadence; LVT six-month cadence; Kano roughly twelve-month cadence; McKinsey 7-Step faster). Information vector: event-driven decay; each methodology declares "events of type X make my application stale for items I have been applied to if [matching condition]" (RICE: new customer-research events, new effort estimates, new competitor moves; LVT: new initiative, new strategic priority shift, new resource constraint; Kano: new competitor offering changing user baseline expectations; McKinsey 7-Step: new stakeholder input, new evidence at any of the seven steps). Phase 2-A ships age-based freshness operational; information-based gets architectural commitment with Phase 2-B Cluster B3 operational delivery per P19 contents. Staleness produces two suggestion types at the methodology layer: drop suggestion (item no longer engaged; lives at 3.2) or rescore suggestion (methodology rescoring opportunity; lives at 2.1 methodology layer). References Step 5 Pass 1 sub-problem 3.2 finding introducing both vectors.

### Latency-tier inference routing

Per D122. Architectural extension of D4's LiteLLM abstraction pre-existing slot. Phase 2 call sites pass tier hints to the LLM port. Tier classification: real-time-required for user-invoked surfaces plus Tier 1 confirmation dialogs (latency budget under one second; latency-optimised model selection plus routing target); async-tolerant for substrate ingestion analysis, surfacing-decision logic, methodology-applied judgment calculations, freshness checks across both vectors, audit narrative composition, mirror data composition, drop-suggestion generation, goal-to-item linking inference (latency budget seconds-to-minutes; quality-optimised model selection plus higher-context routing target). Tier classification per call site is declared at call site annotation; LiteLLM gateway routes per tier configuration in `padhanam/config/inference.py`. Phase 1 call sites preserve current behaviour with opt-in retrofit. Orthogonal axis to the 5.4 three-tier consent-and-awareness framework at D116; both classifications apply at every platform action. The architecture commits to tier classification at every call site as Phase 2 discipline; tier-specific model selection plus routing configuration evolves with Phase 2-A dogfooding evidence. See also `charter/architecture.md` Vendor and dependency posture section for the LiteLLM gateway architecture this primitive extends.

### Phase 2 domain vocabulary

Phase 2 commits a domain vocabulary that aligns with the karma prior-art specification. Items here are domain entities or domain concepts that recur across the substrate and need consistent naming.

Origin: karma prior-art product specification §7 Domain Model, transplanted at P13 framing per Decision 6 option (c). The vocabulary alignment ensures Phase 2 charter prose, code identifiers, and audit-trail records use one canonical name for each concept.

- **Case.** A first-class domain entity representing a coherent unit of work or attention. Phase 2-A populates with portfolio items (deals, relationships, projects). The substrate accepts other Case types at later phases without schema break.
- **Data Point.** A first-class domain entity representing a specific assertion or observation attached to a Case. Examples: a goal on a deal, a status on a relationship, a methodology application on a project. Each Data Point carries an authority (who authored) and a certainty (how confident).
- **Assertion.** A versioned statement of a Data Point's value at a moment in time. The Revisable Protocol per D114 produces Assertions when a Data Point revises. Assertions are immutable; revisions append rather than overwrite.
- **Workflow.** A declarative sequence of steps the platform executes on the user's behalf. Each workflow has a methodology origin (P14 methodology library), an actor scope (who is the workflow acting for), and a gate set (which steps require explicit consent).
- **Step.** A discrete unit of work within a Workflow. Steps may be platform-executed (LLM call, data lookup) or user-gated (consent moment).
- **Signal.** A condition that triggers a Workflow to begin or to advance to the next Step. Examples: a calendar event approaches, an email arrives, a goal-state deviates.
- **Gate.** A consent moment where the platform pauses execution and asks the user's permission before proceeding. The three-tier consent-and-awareness framework per D116 classifies Gates by their consent shape (silent acceptable, awareness required, explicit consent required). Gate entity lands at P14.
- **Intake.** A record captured before any execution path begins, representing the entry of work into the system. Intake records are queryable, immutable, and the canonical entry point for the audit trail of any later execution. Intake records land at S44 (P13).
- **Provenance.** The traceability of any artefact back to the inputs and decisions that produced it. Phase 2-A operator dogfooding exercises provenance at the Case-to-Data-Point-to-Assertion chain. Later waves extend provenance across methodology executions and gate decisions.

## The four-context substrate

The P11 substrate ships a four-context scaffold that closes the bet's success criterion 4: the trace capture layer surfaces optimisation recommendations procurement readers can verify end-to-end with full evidence-citation traceability. Four producer contexts emit evidence; one consumer context (`contexts/optimization/`) consumes the evidence via reader ports and produces rule-derived recommendations with citations.

```mermaid
flowchart LR
    subgraph producers[Producer contexts]
        direction TB
        retrieval_eval[contexts/retrieval_evaluation/<br/>D105, D109, D110<br/>gold sets, evaluation runs,<br/>recall@k, precision@k, MRR]
        run_history[contexts/run_history/<br/>D94, D95, D96, D97<br/>per-tenant runs, chunk citations,<br/>entity citations]
        audit[contexts/audit/<br/>D22, D26, D102<br/>append-only hash-chained<br/>audit events]
        ingestion[contexts/ingestion/<br/>D60-D65<br/>sources, chunks, embeddings,<br/>graph extraction]
    end
    subgraph consumer[Consumer context]
        optimization[contexts/optimization/<br/>D108, D111<br/>OptimizationRun, Recommendation,<br/>RecommendationRule, MetricCalculator,<br/>EvidenceCitation discriminated union]
    end
    subgraph rules[Recommendation rules]
        retrieval_rule[retrieval_strategy_rule<br/>recall@k delta]
        model_rule[model_choice_rule]
        prompt_rule[prompt_revision_rule]
        cost_rule[cost_optimization_rule<br/>cost-per-successful-task]
    end
    subgraph transport[HTTP transport per D112]
        openapi[OpenAPI specification<br/>JWT-resolved tenancy<br/>cursor pagination<br/>discriminated-union DTOs]
        gold_set_routes[/gold-sets, /retrieval-candidates,<br/>/evaluation-runs/]
        run_routes[/runs/]
        audit_routes[/audit, /platform/audit/]
        opt_routes[/optimization-runs,<br/>/recommendations/]
    end
    retrieval_eval -.evidence.-> optimization
    run_history -.evidence.-> optimization
    audit -.evidence.-> optimization
    ingestion -.evidence.-> optimization
    optimization --> rules
    rules --> recommendations[Recommendations<br/>with evidence citations]
    retrieval_eval --> gold_set_routes
    run_history --> run_routes
    audit --> audit_routes
    optimization --> opt_routes
    gold_set_routes --> openapi
    run_routes --> openapi
    audit_routes --> openapi
    opt_routes --> openapi
```

### The four producer contexts

**`contexts/retrieval_evaluation/`** (D105, D109, D110): tenant-authored gold sets with revision-with-hash-chain aggregate; evaluation runs with per-query plus aggregated result records; starter metric set recall@k, precision@k, MRR at k of 1/3/5/10; binary relevance (graded relevance deferred per the deferred-decisions entry); offline-only at P11 (online retrieval evaluation deferred). Procurement-grade defensibility: the runner produces recall@k differentials that distinguish retrieval-quality state across strategies; the all-zero CaveatAnnotation on graph_only flags substrate state transparently when graph extraction is incomplete.

**`contexts/run_history/`** (D94, D95, D96, D97): per-tenant Postgres `runs`, `run_chunk_citations`, and `run_entity_citations` tables with rendering-grade snapshot columns alongside technical references; single-transaction write at invocation completion; consumer-defined `RunHistoryReader` port with `RunRecord`-as-aggregate read DTO; cursor pagination matching the reader layer. The four-filter `RunListFilters` vocabulary covers Phase 2 UX consumption shape.

**`contexts/audit/`** (D22, D26, D102): hash-chained append-only `tenant_audit` tables on every per-tenant Postgres data plane plus a control-plane `tenant_audit` table; two-destination read model with chain integrity verified on read at page granularity reusing `compute_event_hash` and `GENESIS_HASH` primitives; separately authorized HTTP routes (`/audit` under principal-derived tenant context, `/platform/audit` under the platform-operator claim per D103). The audit chain is the procurement-grade tamper-evidence surface.

**`contexts/ingestion/`** (D60-D65): asynchronous ingestion pipeline shape; sources flow through parse → chunk → embed → extract-graph states; markdown and plain text at S19 (PDF, DOCX, HTML defer per D61); chunks carry pgvector embeddings via nomic-embed-text per D62; graph extraction via Qwen 2.5 7B with single `:Entity` node shape per D64; tenant-scoped Neo4j sessions enforced through `TenantScopedNeo4jSession` wrapper per D63.

### The optimization consumer

**`contexts/optimization/`** (D108, D111): the consumer of producer evidence and producer of recommendation output. `OptimizationRun` and `Recommendation` aggregates carry the five-field recommendation shape (category, subject, text, evidence_citations, status); pluggable `RecommendationRule` and `MetricCalculator` Protocol abstractions operationalise the vendor-flexibility principle at consumption-pattern granularity; discriminated `EvidenceCitation` union with structured `CaveatAnnotation` keeps procurement-grade-honesty about substrate gaps; audit-chain absorbs both the engine invocation and the recommendation lifecycle (acknowledge/apply/reject transitions) with five chain-anchoring points per citation.

Four default rules ship at P11 close per D111 commitment 5: `retrieval_strategy_rule` (0.15 absolute recall@3 delta threshold); `model_choice_rule`; `prompt_revision_rule`; `cost_optimization_rule` ($0.10 cost-per-successful-task starter threshold). Starter threshold values are Phase 2-tuning candidates per the deferred-decisions entry on "Optimization-engine cost-per-successful-task threshold tuning" — Phase 1's local Ollama regime puts costs at $0.000246 mean, well below the threshold; production LLM regimes shift the threshold by orders of magnitude.

### HTTP transport surface

Per D112, the HTTP transport surface ships routes for the retrieval_evaluation and optimization producer-context substrates with JWT-resolved tenancy, cursor pagination, Pydantic discriminated-union DTOs, and OpenAPI specification as procurement-grade Phase 2 UX-consumer documentation. Combined with the run-history HTTP routes per D98 (S34), the audit HTTP routes per D103 (S37), and the ingestion-management HTTP routes per D104 (S38), the consumer surface for all four producer contexts plus the optimization consumer context is complete.

A Phase 2 frontend developer reads `/openapi.json` (17 P11 operationIds plus the carryover operations from S34, S37, S38) and integrates against the platform without needing to read source. The two-step gold-set discovery decomposition preserves human-in-the-loop content-fit discipline at the HTTP layer per the S40b precedent; the recommendation lifecycle through HTTP lands equivalently to the CLI exercise; tenant isolation holds with no information leakage (verified by 148 tenant_isolation contract scenarios plus 18 HTTP-layer contract scenarios at Phase 1 close).

### End-to-end procurement-grade traceability

The four-context substrate plus optimization consumer plus HTTP transport produces end-to-end procurement-grade defensibility. A procurement reader can:

1. Read a recommendation's prose at `/recommendations/{id}` via OpenAPI.
2. Trace the prose to its `RecommendationRule` via the `category` discriminator and the citation surface.
3. Trace each `EvidenceCitation` to its producer-context record (an `EvaluationRun` at `/evaluation-runs/{id}`; a `Run` at `/runs/{id}`; an `AuditEvent` at `/audit?run_id=...`; an ingestion `Source` at the ingestion management routes).
4. Verify chain integrity on the audit events via the `/audit` route's embedded page-granularity verifier.
5. Inspect the optimisation engine invocation's audit events to verify the recommendation was produced by the rule it claims.

The verification is end-to-end through the platform's own tooling; no out-of-band assertions are required. This is the bet's success criterion 4 in its substrate form. Phase 2 UX completes the criterion by surfacing the recommendation surface to procurement readers in product form per D93's methodology-as-product positioning.

## Cross-document map

Padhanam's charter system uses three documents for three reading modes:

- **`charter/principles.md`** (read every session) — binding rules with D-entry references. Compact prose at session-open. The principles file is the architect's contract: rules that must hold, parenthetical references back to the load-bearing D-entries that committed them. Compact, scannable, present at every session-open per CLAUDE.md's session-start reading order.
- **`charter/decisions.md`** (consult on demand; archived per-phase to `docs/archive/decisions/phase-N.md`) — full Choice / Reasoning / Alternatives / Kano per D-entry. Cold-path audit-time reading. New D-entries in the active phase land in `charter/decisions.md` until phase close, at which point they archive per the methodology document's per-phase archival pattern. Procurement readers verifying any architectural decision against alternatives land here.
- **`charter/architecture.md`** (read at onboarding, phase audits, procurement-grade-touch moments) — architectural synthesis with diagrams. Warm-path synthesis-time reading (this document). Procurement readers, new contributors, and Phase 2 strategic-mode framing read this document for the coherent architectural picture without needing to consult D-entries one at a time.

The three documents serve different reading audiences and different reading moments. They do not duplicate content; they cross-reference. principles.md restates the load-bearing rules with D-entry pointers; decisions.md owns the reasoning behind each rule; architecture.md narrativises the rules and the reasoning together with diagrams that make the structure visible.

Two further charter documents complete the system:

- **`charter/methodology.md`** — the build methodology (how Padhanam itself is built). Distinct from this document, which covers the architecture (what Padhanam is built as). Methodology covers operator discipline, build process, framing-prompt patterns, refactoring conventions, session shapes, measurement model. This document covers the platform's architecture as the artefact the methodology produces.
- **`charter/product-methodology.md`** — the product methodology layer (what the platform encodes for users at the agent layer). Distinct from this document and from `charter/methodology.md`. Product methodology covers the methodology embeddings the agent layer applies across professional functions (Product Management, Marketing, Learning and Development, Project and Programme Management) per `charter/bet.md`.

See `charter/bet.md` for the strategic intent the architecture serves; `charter/prfaq.md` for the external-voice articulation; and `charter/p12-audit-findings.md` for the Phase 1 close architectural verdict.
