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

## Data-plane ownership

Activates in Phase 2 architectural commitments.

**Trace history that feeds the recommendation engine flows into Padhanam-owned storage, not Langfuse-only.** Padhanam's commercial differentiator is the optimization layer that builds recommendations from trace history. The recommendations are Padhanam's IP; the trace data they build on is the substrate. Long-term, that data should not live exclusively in Langfuse. The architecture commits to a Padhanam-owned trace data plane for the data the recommendation engine consumes: traces flow into Langfuse for operational observability *and* into Padhanam's own store for analytical use.

**Durable agent state lives in domain tables, not orchestrator-managed checkpointers.** When stateful long-running agents land (Phase 2 or later), the durable state lives in Padhanam-owned Postgres tables. Orchestrator checkpointers are for ephemeral graph state only. This makes orchestrator swap meaningful even for stateful agents.

Both architectural commitments will be made explicit in Phase 2 with specific D-entries when the data shapes are known.

## Per-tenant supply-chain surveillance for tenant-supplied tools and extensions

Activates when tools and extensions enter the codebase (P5 or wherever tools and extensions first land).

**Tenant-supplied artefacts have their own dependency trees and require per-tenant surveillance distinct from platform supply-chain monitoring.** Each tenant's registered tools (external services called on the tenant's behalf, per D14) and uploaded extensions (sandboxed code at named interfaces, per D14) carry their own dependencies. Padhanam scans these at registration, re-scans on a schedule against updated CVE databases, and notifies the tenant of vulnerabilities in their artefacts.

**The mechanism is the tool-and-extension registry, not the platform supply-chain process.** Different system, different cadence, different audience. Platform supply-chain checks (governed by `ops/scheduled_checks.yaml`) are operator-reviewed and operator-merged. Per-tenant artefact scanning is tenant-notified and tenant-actioned, with platform-side enforcement (e.g., disabling a tool registration with a critical CVE that the tenant has not addressed within a defined window).

**Configuration scope follows tenant agency.** Tenants have agency over which tools they register and which extensions they upload, and therefore over the surveillance posture for those artefacts (notification preferences, severity thresholds for auto-disable, grace periods). They do not have agency over the platform's own supply-chain monitoring.

**The specific D-entry lands when tools and extensions enter the codebase.** Premature commitment to specific scanning tools, severity thresholds, or notification mechanisms ahead of integration is paper architecture.
