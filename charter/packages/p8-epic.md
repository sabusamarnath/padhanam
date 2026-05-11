# P8 Epic — Agent Runtime

## Goal

P8 ships the agent runtime that invokes agents authored at P7 against the methodology v2 shape from D81. By P8 close, the platform runs one agent (the PM agent at tenant alpha cloned from the LVTGuide role of the LVT methodology) with full instrumentation: SSE-streamed responses, trace capture extending D49 and D57, audit hooks per D26, and platform invariant enforcement at the tool layer per D82. The five-invariant user-safety set lands in code at the tool invocation boundary; the AgentLoopExecutor adapter from D84 is the orchestration shape.

## Scope at P8 close

The methodology aggregate migrates to the v2 shape per D81 (multi-role with per-field binding mode) as the first P8 session. The agent runtime ships behind the AgentExecutor port. Tool registry context lands per D68's deferred surface. Platform invariant enforcement at the tool invocation boundary implements the five danger-targeted invariants from D82. SSE streaming and trace capture extend the existing observability substrate. End-to-end test runs the PM agent against operator-uploaded LVT-relevant sources, remediating the deferred-action note on synthetic sources from the 2026-05-11 captures entry.

The agent runtime invokes a single agent per request. No workflow composition at P8; workflow context architecture committed at D83 and `charter/contexts/workflow.md`, implementation Phase 2.

Two new bounded contexts:

- `contexts/tools/` holds the tool registry per D68's deferred surface. Tool aggregate (`Tool`, `ToolRevision`), tool classification taxonomy (read-only, drafting, user-affecting-with-consent, financial, communication, legal), tool invocation port, platform invariant enforcement at the invocation boundary. Storage: per-tenant per D32 (tenants configure their own tools per D14). Audit: per-tenant per D26.
- `contexts/agent/` gains the runtime use cases. `invoke_agent` use case takes an agent template ID, a user message, and tenant context; resolves the latest agent revision; constructs an LLM call against LiteLLM per D4; manages the LLM-with-tool-loop (model proposes tool calls; runtime executes via tool registry; results feed back); enforces platform invariants at tool boundaries; streams response chunks via SSE; captures trace span attributes per D49 and D57; emits audit events per D26.

`AgentExecutor` port at `contexts/agent/ports/agent_executor.py`. `AgentLoopExecutor` adapter at `contexts/agent/adapters/outbound/agent_loop_executor.py`. Hand-rolled per D84.

Demonstration content at P8 close: PM agent at tenant alpha runs end-to-end against operator-uploaded LVT-relevant sources.

Tenant isolation contract tests extend `tests/contract/tenant_isolation/` per D24 to cover tool registry and agent runtime paths.

## Sessions forecast

Five sessions.

**S26: Methodology v2 migration** (D81 commitments). Alembic migration for `methodology_revision.roles` JSONB. LVT template migration from single-role-implicit to single-role-array form. `AgentTemplate.source_methodology_role_name` field. PM agent backfill (`source_methodology_role_name = "LVTGuide"`). Tenant-isolation contract tests update for the new role-bundle shape. End-to-end test verifies the migrated LVT methodology and PM agent function unchanged.

**S27: AgentExecutor port plus AgentLoopExecutor adapter plus agent runtime use case.** Port definition. Hand-rolled LLM-with-tool-loop adapter against LiteLLM per D4 and retrieval per D60, D66. `invoke_agent` use case. Cost capture per D49 and D57 extending to per-agent-invocation cost. Audit events per D26. Tenant-isolation contract tests extension.

**S28: Tool registry context plus tool classification plus invariant enforcement.** New bounded context at `contexts/tools/`. Tool aggregate with revision shape per D31 and hash-chain audit per D26. Tool classification taxonomy. Tool invocation port. Platform invariant enforcement at the invocation boundary per D82's five invariants. CLI: `padhanam tool create | get | list`. Tenant-isolation contract tests.

**S29: SSE streaming plus trace capture for agent runtime.** FastAPI SSE endpoint for agent invocation. OTel span attributes extending D49 and D57. Streaming-aware trace capture. Per-invocation cost roll-up.

**S30: CLI plus end-to-end test plus P8 close.** `padhanam agent run --tenant <tenant> --agent <id> --input <message>`. End-to-end test against PM agent with operator-uploaded LVT-relevant sources (remediates the deferred-action note on synthetic sources from the 2026-05-11 captures entry). P8 close archive at `docs/archive/packages/p8.md`. `log/packages.md` measured-outcomes paragraph. `current-package.md` transition.

Lower-end overlap (S29 folding into S27 or S30) is possible if the operator decides at S27 reflection. Session boundaries settle at the session-by-session framing per the established discipline.

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
