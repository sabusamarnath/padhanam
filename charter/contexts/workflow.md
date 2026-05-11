# Workflow Context

Architectural commitments for the workflow bounded context at `contexts/workflow/`. Phase 1 commits the architecture in charter; Phase 2 implements code. See D83 for the underlying decision.

## What this is

Workflow is a new architectural primitive distinct from methodology and agent. Workflow composes agents (potentially across methodologies), declares routing topology, termination criteria, version pinning, and aggregate budgets. The workflow bounded context lives at `contexts/workflow/` per D16's hexagonal-on-bounded-contexts shape.

## Aggregate shape

Two frozen-dataclass aggregates following D31's revision-shape precedent and inheriting D74/D75 patterns.

`WorkflowTemplate` carries the human-stable identity:

- id (UUID)
- name (string)
- description (string)
- source_methodology_template_id (UUID, nullable for cross-methodology or no-methodology workflows; immutable when set)
- created_by_user_id (UUID)
- created_at (timestamp)
- archived_at (timestamp, nullable)

`WorkflowRevision` carries per-revision content plus hash chain:

- workflow_template_id (UUID)
- version (integer)
- definition (JSONB; see below)
- created_by_user_id (UUID)
- created_at (timestamp)
- previous_revision_hash (string, SHA-256 hex; genesis is "0" * 64)
- this_revision_hash (string, SHA-256 hex)

Revisions are immutable per D31. Hash chain follows D26's audit-chain pattern: SHA-256 over canonical JSON of the revision content payload plus previous_revision_hash.

## Definition JSONB shape

The workflow's definition lives in the `definition` JSONB field of `WorkflowRevision`. Phase 1 names the categories; Phase 2 implementation chooses specific serialisation.

The definition carries:

- **Agent slots.** Each slot binds to either a methodology+role (methodology_template_id + methodology_version + role_name) or a fixed agent template (agent_template_id + agent_revision_version). Version pinning is mandatory; slots carry the version they were authored against.
- **Topology.** One of three categories at Phase 1: sequential (predefined order), conditional (LLM-judged or rule-based branching), reflective (review and possibly loop).
- **Edges.** Typed by topology. Sequential edges carry no condition; conditional edges carry a condition predicate; reflective edges carry a convergence criterion.
- **Termination criteria.** One or more from five categories: step count, output condition, budget exceeded, sequence completion, reflective convergence.
- **Aggregate budget.** USD per workflow invocation per D49 and the existing currency-evolution deferral. Enforcement at workflow runtime defers to Phase 2.

## Storage pattern

Control-plane for platform-curated workflow templates (gallery items per D33 and the captures' gallery pre-population framing). Per-tenant for tenant-authored workflows per D32. Mirrors the methodology context's split.

## Cross-context relationships

Workflow reads methodology and agent via api-facade-via-callable per D17. The workflow context's application layer defines:

- `MethodologyView` DTO carrying the methodology+role data the workflow needs (role_name, system_prompt, tool_allowlist, source_filter, retrieval_strategy, etc.)
- `AgentView` DTO carrying the agent template plus revision data for fixed-agent slots

No type imports from `contexts.methodology` or `contexts.agent` at the domain or application layer; the wiring layer translates producer aggregates to consumer-shaped DTOs.

## WorkflowExecutor port

The orchestration architecture deferred-decisions entry commits the `WorkflowExecutor` port for workflow orchestration. Method signature:

```
class WorkflowExecutor(Protocol):
    async def execute(
        self,
        workflow_revision: WorkflowRevision,
        inputs: dict,
        tenant_context: TenantContext,
    ) -> AsyncIterator[ExecutionState]: ...
```

`ExecutionState` carries per-step results, current step, accumulated cost, and final output when complete. Implementation defers to Phase 2.

## LangGraph adapter

LangGraph implements `WorkflowExecutor` per the orchestration architecture deferred-decisions entry. Adapter implementation lands at Phase 2 alongside the workflow context's persistence and use-case layers per D83 and D84.

The adapter translates the workflow's domain-shaped definition (agent slots, topology, edges, termination, budget) into LangGraph's state graph idiom at execution time. The translation surface is internal to the adapter; the workflow definition is the abstraction.

## Auth posture

Operator-context for control-plane templates per D33 and D34. Tenant-context-or-operator-context for tenant-authored workflows per D75's pattern.

## Tenant isolation

Per-tenant workflows: standard D32 routing through `TenantContext`. Control-plane workflows: standard D33 routing.

Tenant isolation contract tests extend `tests/contract/tenant_isolation/` per D24 when implementation lands at Phase 2. Cross-tenant access tests assert that a tenant cannot read or write another tenant's workflows.

## CLI surface

Implementation deferred to Phase 2. The shape:

- `padhanam workflow create --tenant <tenant> --config <path>` (tenant-authored) or `--control-plane` (gallery template)
- `padhanam workflow get --tenant <tenant> --id <id> [--version <n>]`
- `padhanam workflow list --tenant <tenant> [--control-plane]`
- `padhanam workflow update --tenant <tenant> --id <id> --config <path>` (creates new revision)
- `padhanam workflow retire --tenant <tenant> --id <id>` (marks archived)
- `padhanam workflow run --tenant <tenant> --id <id> --inputs <json>` (invokes via WorkflowExecutor; Phase 2)

## Phase 2 implementation scope

Phase 2 implements the workflow context end-to-end:

- Aggregate dataclasses (`WorkflowTemplate`, `WorkflowRevision`)
- Alembic migrations for workflow tables (control-plane and per-tenant)
- Repository adapter (`WorkflowRepositoryPort` and implementation)
- CRUD use cases mirroring methodology and agent context patterns
- LangGraph adapter implementing `WorkflowExecutor`
- CLI command implementations
- Tenant isolation contract tests
- Tenant-facing UI for workflow authoring
- Gallery browsing UI
- Gallery pre-population content (seven seed categories from the captures: physical activity, mental health, sleep hygiene, cooking and nutrition, habit formation, home projects, learning a skill)
- Multi-tenant gallery curation tooling
- Workflow runtime cost ceiling enforcement (extends the existing cost ceiling deferral per D81's role-level cost_ceiling field)

## Out of scope for Phase 1

- Any workflow context code
- LangGraph adapter implementation
- Tenant-facing UI surfaces
- Gallery pre-population content
- Workflow execution
- Cost ceiling enforcement at workflow runtime
- Cross-tenant gallery sharing

## Composition terminology

"Composition" has two distinct meanings in the codebase.

Retrieval composition (D66) sits at the agent runtime layer: vector and graph results merged into a single ranked chunk list for one agent's retrieve() call.

Agent composition (this context) sits at the workflow layer: multiple agents orchestrated together with topology, termination, and budgets.

The two are structurally separate. No code or config is shared. The captures synthesis's wording suggesting D66 and D67 "get a clearer home" in workflow context is reconciled at D83: D66 and D67 stay where they are.
