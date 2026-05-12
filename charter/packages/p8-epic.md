# P8 Epic — Agent Runtime

## Goal

P8 ships the agent runtime that invokes agents authored at P7 against the methodology v3 shape from D86 (revising D81's v2 framing to separate role aggregate plus methodology referencing via `role_refs`). By P8 close, the platform runs one agent (the PM agent at tenant alpha cloned from the LVTGuide role of the LVT methodology) with full instrumentation: SSE-streamed responses, trace capture extending D49 and D57, audit hooks per D26, and platform invariant enforcement at the tool layer per D82. The five-invariant user-safety set lands in code at the tool invocation boundary; the AgentLoopExecutor adapter from D84 is the orchestration shape.

## Scope at P8 close

The methodology aggregate migrates to the v3 shape per D86 (separate role aggregate; methodology references roles via `role_refs`; per-field binding-mode platform-level convention from D81 preserved) as the first P8 session (S26a). McKinsey 7-Step methodology authoring against the role-first model lands at S26b. The agent runtime ships behind the AgentExecutor port. Tool registry context lands per D68's deferred surface. Platform invariant enforcement at the tool invocation boundary implements the five danger-targeted invariants from D82. SSE streaming and trace capture extend the existing observability substrate. End-to-end test runs the PM agent against operator-uploaded LVT-relevant sources, remediating the deferred-action note on synthetic sources from the 2026-05-11 captures entry.

The agent runtime invokes a single agent per request. No workflow composition at P8; workflow context architecture committed at D83 and `charter/contexts/workflow.md`, implementation Phase 2.

Two new bounded contexts:

- `contexts/tools/` holds the tool registry per D68's deferred surface. Tool aggregate (`Tool`, `ToolRevision`), tool classification taxonomy (read-only, drafting, user-affecting-with-consent, financial, communication, legal), tool invocation port, platform invariant enforcement at the invocation boundary. Storage: per-tenant per D32 (tenants configure their own tools per D14). Audit: per-tenant per D26.
- `contexts/agent/` gains the runtime use cases. `invoke_agent` use case takes an agent template ID, a user message, and tenant context; resolves the latest agent revision; constructs an LLM call against LiteLLM per D4; manages the LLM-with-tool-loop (model proposes tool calls; runtime executes via tool registry; results feed back); enforces platform invariants at tool boundaries; streams response chunks via SSE; captures trace span attributes per D49 and D57; emits audit events per D26.

`AgentExecutor` port at `contexts/agent/ports/agent_executor.py`. `AgentLoopExecutor` adapter at `contexts/agent/adapters/outbound/agent_loop_executor.py`. Hand-rolled per D84.

Demonstration content at P8 close: PM agent at tenant alpha runs end-to-end against operator-uploaded LVT-relevant sources.

Tenant isolation contract tests extend `tests/contract/tenant_isolation/` per D24 to cover tool registry and agent runtime paths.

## Sessions forecast

Six sessions (S26 split into S26a and S26b per D86; subsequent sessions renumbered S27b-S30b).

### S26a: Methodology v3 migration (roles as separate aggregate)

**Goal at session close.** Methodology v3 migration runs in tenant a. Methodology aggregate refactored to reference roles via `role_refs` rather than embedding role bundles in JSONB. Roles aggregate created as a separate aggregate within `contexts/methodology/` per D86's Y2 sub-choice. LVT methodology splits into:

- LVT methodology aggregate carrying playbook content plus `role_refs` (one entry pointing at LVTGuide).
- LVTGuide role aggregate carrying the role's constraint bundle (system_prompt focused on function, tool_allowlist, source_filter, retrieval_strategy, filter_tree, top_k, min_score, model_selection, cost_ceiling).

PM agent at tenant alpha gains `source_role_id` lineage pointing at LVTGuide; existing `source_methodology_template_id` per D79 remains. Agent's content fields stay flat per D75; lineage extends per D86.

**Acceptance criteria.**

1. Migration script runs against tenant a; methodology v3 lands.
2. LVT methodology aggregate exists with `role_refs` containing one entry pointing at LVTGuide.
3. LVTGuide role aggregate exists with the constraint bundle copied from LVT's prior single-role content.
4. PM agent at tenant alpha gains `source_role_id` lineage; existing methodology lineage intact.
5. Cross-context independence import-linter contracts updated to cover the new role aggregate's relationships.
6. Tenant isolation contract tests cover the roles aggregate.
7. Hash-chain semantics inherited from methodology v2 (per D31 revisions pattern); the role aggregate's revision hash spans the constraint bundle.

### S26b: McKinsey 7-Step methodology authoring (against role-first model)

**Goal at session close.** McKinsey 7-Step methodology and its seven roles land in the platform-managed methodology surface (control plane). Authored against the brief at `briefs/p8/mckinsey-7-step.md`.

**Acceptance criteria.**

1. Seven role aggregates authored as standalone first-class roles: ProblemFramer, Disaggregator, Prioritiser, Planner, Analyst, Synthesiser, Communicator. Each role's content matches the brief.
2. McKinsey 7-Step methodology aggregate authored, referencing the seven role aggregates via `role_refs` with the per-role overrides specified in the brief.
3. The methodology's workflow specification (sequence: ProblemFramer through Communicator) lands per the brief.
4. Hash-chain semantics inherited; methodology revision 1 and each role revision 1 land with deterministic hashes.
5. Authoring is platform-managed (control plane); not tenant-scoped.

**S27b: AgentExecutor port plus AgentLoopExecutor adapter plus agent runtime use case.** Port definition. Hand-rolled LLM-with-tool-loop adapter against LiteLLM per D4 and retrieval per D60, D66. `invoke_agent` use case. Cost capture per D49 and D57 extending to per-agent-invocation cost. Audit events per D26. Tenant-isolation contract tests extension.

**S28b: Tool registry context plus classification taxonomy plus invariant enforcement plus two-thin-ports replacement of retrieval branch plus BC stub at revision creation.** New bounded context at `contexts/tools/`. `Tool` aggregate with revision shape per D31 and hash-chain audit per D26. Classification taxonomy with three-to-three invariant mapping per D89 (financial→1, communication→2, legal→3). Defensive invariant enforcement at the invocation boundary with `TerminationReason.INVARIANT_BLOCKED` termination signal. Schema-diff BC stub at revision creation with query surface for role-tool adoption candidates. CLI: `padhanam tool create | get | list` with Phase 1 authoring prohibition on classifications `financial`, `communication`, `legal`. The hardcoded retrieval branch in `AgentLoopExecutor` retires; retrieval becomes a tool registered in the tool registry, invoked through `ToolInvoker` like any other tool. Two thin ports at agent context (`ToolDefinitionsLookup`, `ToolInvoker`) wired by adapters at `apps/cli/_cross_context.py`. Tenant-isolation contract tests extension (invocation-path scope per D89's control-plane storage choice). Storage on control plane alongside methodologies and roles per D89; per-tenant tool authoring lifts at Phase 2 per the deferred-decisions entry.

**S29b: Streaming runtime with structured event surface, nested trace span hierarchy, SSE transport, per-invocation cost roll-up.** Eleven domain-layer event types at `contexts/agent/domain/events.py` exposing the runtime's state machine. `AgentExecutor.execute` refactored to yield an async iterator of AgentEvent; streaming is the only executor pathway, non-streaming callers wrap via `collect_to_result` helper. Inference port gains `stream_complete` method; LiteLLM adapter implements with vendor isolation preserved. OTel span hierarchy: invocation → iteration → LLM call and tool call; cost attributes roll up per D49 extended. Audit stays start-and-end per D26. FastAPI SSE endpoint at `apps/api/routers/agent.py` (principal-derived tenant context per existing `/inference/completions` and `/tenant/audit` convention) translates domain events to wire format. Integration test against live LiteLLM stack exercises streaming end-to-end. Tenant-isolation contract test extension. D90 absorbs the four sub-choices.

**S30b: CLI plus end-to-end test plus P8 close.** `padhanam agent run --tenant <tenant> --agent <id> --input <message>`. End-to-end test against PM agent with operator-uploaded LVT-relevant sources (remediates the deferred-action note on synthetic sources from the 2026-05-11 captures entry). P8 close archive at `docs/archive/packages/p8.md`. `log/packages.md` measured-outcomes paragraph. `current-package.md` transition. Demonstration includes a drafted-artifact-as-deliverable shape that exercises the Padhanam-as-intelligence-layer commitment in product form (per S28b conversation): the PM agent produces a deliverable a human would then act on, not a deliverable that itself performs an external action.

Lower-end overlap (S29b folding into S27b or S30b) is possible if the operator decides at S27b reflection. Session boundaries settle at the session-by-session framing per the established discipline.

## D-entries forecast

Three to four new D-entries at P8 build sessions, beyond the topology-design-session D-entries D80-D85.

- AgentExecutor port shape and AgentLoopExecutor implementation details (LLM-with-tool-loop control flow, error handling, streaming chunk shape).
- Tool registry aggregate shape (tool template plus tool revision; classification taxonomy specifics; invocation port methods).
- Tool classification taxonomy specifics with platform invariant enforcement mapping (which classifications block per which invariant; the per-invocation confirmation path shape).
- Optional: anything that surfaces during build per the framing-prompt-as-recommendation pattern.

## Out of scope

- Workflow context implementation (Phase 2 per D83).
- LangGraph adapter implementation (Phase 2 per D84).
- Tenant-facing UI for agent or tool authoring (Phase 2).
- Gallery surfaces (Phase 2).
- Cost ceiling runtime enforcement (Phase 2 per the existing deferred-decisions entry).
- Multi-agent composition (Phase 2 alongside workflow).
- Reflective agent loops as a workflow topology (Phase 2 per D83).
- Provider-specific agent SDKs (deferred per the orchestration architecture entry).
- Persistent or long-running agents (activates per the scheduled-runs primitive or memory-as-first-class-agent-surface deferred-decisions entries).
