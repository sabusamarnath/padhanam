# P7 Epic — Agent CRUD

## Goal

P7 ships the agent authoring substrate. By P7 close, the platform stores agent specifications, supports CRUD on agents and methodology templates through the CLI, and exposes the abstractions P8's runtime will consume and the P5 eval harness will score against. Methodology embedding from the product reframe lands as platform-managed templates on the control plane that tenants clone into independent agent instances on per-tenant Postgres.

## Scope at P7 close

Two new bounded contexts:

- `contexts/methodology/` holds methodology templates. Storage: control-plane Postgres (the existing tenant registry control-plane database, extended with methodology-template tables). Audience: platform admin (the operator at Phase 1; the product team in Phase 2). Lifecycle: curated and versioned; updates create new revisions; tenants see updates as the platform improves them. Revision shape per D31's scoring-sheet precedent; hash-chain audit per D26.
- `contexts/agent/` holds agent instances. Storage: per-tenant Postgres per D32. Audience: tenant users. Lifecycle: tenant CRUD; revision shape per D31 plus hash-chain audit per D26; full independence after cloning.

The methodology aggregate carries default values for every agent field: system prompt, source IDs (typically empty in templates because sources are tenant-specific), tool allowlist (opaque strings; no registry at P7), retrieval strategy (per D66), filter tree (per D67), top_k, min_score, model selection. Methodology templates also have name, description, and version metadata.

The agent aggregate carries the same fields the methodology populates plus methodology lineage (`source_methodology_template_id` and `source_methodology_template_version` set immutably on revision 1, preserved across all later revisions; nullable for blank-created agents).

CRUD use cases:

- Methodology context: `create_methodology_template`, `get_methodology_template`, `list_methodology_templates`, `update_methodology_template` (creates new revision), `retire_methodology_template` (marks unavailable for new clones; existing clones unaffected).
- Agent context: `create_blank_agent`, `create_agent_from_methodology` (cross-context: reads methodology context's API, copies default fields into the new agent, records lineage), `get_agent`, `list_agents`, `update_agent` (creates new revision), `archive_agent`.

CLI commands at `apps/cli/`:

- `padhanam methodology create | get | list | update | retire`
- `padhanam agent create | create-from-methodology | get | list | update | archive`

Demonstration content authored at P7 close:

- One LVT methodology template (PM domain, LVT methodology) on control plane. The template's system prompt is LVT-shaped (guides users through bet identification, initiative breakdown, epic mapping, story creation). Retrieval and filter defaults appropriate for PM strategy queries. Specific content lands at the implementing session per the framing-prompt-as-recommendation pattern.
- One PM agent cloned from the LVT methodology template in the operator's dev tenant. Operator-uploaded sources attached. Agent ready for P8's runtime to invoke and P5's eval harness to score.

Tenant isolation contract tests extend through the existing `tests/contract/tenant_isolation/` harness per D24 to cover both new contexts; agent isolation is per-tenant as expected; methodology isolation is the inverse of agent isolation (control-plane reads visible across tenants, control-plane writes restricted to platform admin).

## Sessions forecast

Four to five sessions. The methodology-as-platform-service framing expands P7's original Agent-CRUD-only scope to include methodology-template CRUD, two bounded contexts, control-plane schema work, and cross-context flow. Indicative shape:

- **S23** lands the methodology bounded context: full hexagonal layout, methodology aggregate (frozen dataclass plus revision shape), control-plane Postgres migration, methodology repository, CRUD use cases, hash-chain audit, CLI commands at `padhanam methodology ...`.
- **S24** lands the agent bounded context: full hexagonal layout, agent aggregate with revision shape and methodology lineage fields, per-tenant Postgres migration, agent repository, CRUD use cases (excluding cross-context `create_agent_from_methodology`), hash-chain audit, CLI commands at `padhanam agent ...`.
- **S25** lands the cross-context `create_agent_from_methodology` flow plus the LVT methodology template authored on control plane plus one agent cloned from LVT in the operator's tenant. End-to-end test: operator runs the CLI to create LVT, then create the agent from LVT, verifies the agent's defaults match LVT's, edits the agent, verifies independence, and confirms revisions and hash chain are intact.
- **S26** if needed lands P7 close: archive at `docs/archive/packages/p7.md`, `log/packages.md` measured-outcomes paragraph, `current-package.md` transition.

The upper end is more likely than the lower because two bounded contexts each with revision-shape and hash-chain audit is more vendor-surface-equivalent work than P5 or P6 had per single session. Session boundaries settle at the session-by-session framing per the established discipline.

## D-entries forecast

Four to five D-entries beyond D68. Indicative:

- Methodology aggregate shape (revision fields, hash-chain shape, content fields).
- Agent aggregate shape (revision fields, hash-chain shape, methodology lineage fields, retrieval-config fields per D66 and D67).
- Cross-context `create_agent_from_methodology` flow shape (which context owns the cloning logic, how methodology API is consumed, how lineage is recorded).
- LVT methodology template content (system prompt shape, retrieval defaults, filter defaults).
- Optional: anything that surfaces during build per the framing-prompt-as-recommendation pattern.

## Out of scope

- Tool registry and tool invocation (defer to P8).
- Cross-tenant tenant-authored methodology template sharing (Phase 2 platform-baseline-library territory; same shape as D53).
- "Reset agent to methodology defaults" (defers; user can clone fresh).
- "Apply newer methodology version to existing agent" (migration support; defers).
- HTTP API for agent management (defers to P9 or P10 with the rest of UI consumers).
- HTTP API for methodology management (same).
- Multi-methodology agents (composition; defers per D68's alternatives-considered).
- Tenant-facing methodology authoring UI (Phase 2).
- Methodology library curation tooling (cross-tenant sharing, retirement, etc.; Phase 2).
