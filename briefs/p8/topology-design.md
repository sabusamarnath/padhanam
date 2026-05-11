# Strategic-mode session prompt — Topology design session at P7→P8 boundary

Preserved per the session-brief preservation convention (S17b forward; see `charter/methodology.md` "Session brief preservation"). The prompt as authored numbered the six new D-entries D79–D84; at execution the next available D-number was D80 (D79 was taken by the S25 close commit on cross-context `create_agent_from_methodology`), so the entries land as D80–D85 with cascading cross-reference updates throughout the strategic commit. The renumbering is mechanical; the content is preserved verbatim from the prompt below.

Mode: strategic-mode session, deliverable is charter content. Single commit per the captures' "single strategic block recommended" framing. Conventional commit tag: `docs(p8/topology-design): ...` per D47.

Save this prompt at `briefs/p8/topology-design.md` before commit per the session-brief preservation convention.

## Goal

At session close the repository carries the following new and revised charter content, committed in a single strategic-mode commit ahead of any P8 code:

- Six new D-entries (D79-D84) in `charter/decisions.md`
- New file `charter/contexts/workflow.md`
- Revised `charter/p8-epic.md`
- Revised `charter/principles.md` (new User safety section; refined methodology-embedded principle)
- Revised `charter/packages.md` (P8 line)
- Revised `charter/roadmap.md` (version entry with discovery reasoning)
- Revised `charter/current-package.md` (between-packages entry)
- Revised `charter/deferred-decisions.md` (three new entries)
- Session log entry at `log/sessions.md`
- Captures triage update at `log/captures.md`

## Context to read first

1. `charter/principles.md`
2. `charter/current-package.md`
3. `charter/decisions.md` for D14, D17, D26, D31, D32, D33, D34, D49, D57, D60, D66, D67, D68, D74, D75
4. `charter/deferred-decisions.md` orchestration architecture section
5. `log/captures.md` 2026-05-11 P7 strategic block synthesis entry

## Charter content

### Append to `charter/decisions.md`

---

**D79: Four-layer constraint stack — platform invariants, methodology, workflow, agent** (P8 framing, topology design session, 2026-05-11)

**Choice.** Four layers constrain platform behaviour at runtime. Platform invariants form the universal floor binding every entity regardless of context per D81. Methodology binds agents that adopt a methodology, opt-in via methodology lineage per D74 and D80; agents created without lineage skip the layer. Workflow binds agents invoked within a workflow, opt-in via invocation context per D82; agents invoked outside a workflow skip the layer. Agent carries per-instance choices within all applicable upper-layer constraints. Each layer constrains layers below for entities to which the upper layer applies.

**Reasoning.** The 2026-05-11 captures synthesis named workflow as a new architectural primitive at the P7-to-P8 boundary, requiring an explicit layering model to anchor the relationship between methodology, workflow, and agent. The four-layer stack with explicit conditionality at the methodology and workflow layers preserves the methodology-embedded-not-gated principle (agents that do not adopt a methodology skip the layer; agents not invoked within a workflow skip the layer) while making the universality of platform invariants explicit. Without the conditionality framing, "each layer constrains layers below" would imply mandatory layers, contradicting D68's blank-agent path and creating an inconsistent picture of when constraints apply.

**Alternatives considered.** (a) Strict layered model with all layers mandatory; rejected because it contradicts D68's `create_blank_agent` path and would require methodology adoption for all agents which is not the existing commitment. (b) Two-layer model with platform and agent only; rejected because it collapses methodology and workflow into the platform layer, contradicting the captures' explicit framing of workflow as a distinct primitive. (c) Methodology and workflow as siblings rather than ordered layers; rejected because workflow composes agents that may have methodology lineage, which positions workflow above methodology in the constraint flow when workflows invoke methodology-bound agents.

**Kano.** Must-have. The stack frames the architectural relationship between methodology (D74, D80), workflow (D82), agent (D75), and platform invariants (D81); without an explicit layering commitment future sessions inheriting these contexts would resolve the relationship inconsistently.

---

**D80: Methodology aggregate v2 — multi-role refinement with per-field binding mode** (P8 framing, topology design session, 2026-05-11; v2 to D74)

**Choice.** `MethodologyRevision` carries a `roles` JSONB array replacing the previous flat content fields. Each role element is a constraint bundle: `role_name` (unique within methodology), `description`, `system_prompt`, `source_filter` (replaces `source_ids` at methodology level), `tool_allowlist`, `retrieval_strategy`, `filter_tree`, `top_k`, `min_score`, `model_selection`, `cost_ceiling`. The `cost_ceiling` field is new and carries USD per agent invocation per D49 and the existing currency-evolution deferral. Methodology revision retains metadata fields (id, methodology_template_id, version, created_by_user_id, created_at, previous_revision_hash, this_revision_hash); the hash chain payload includes the entire roles array.

Per-field binding mode is platform-level convention at Phase 1. Hard-bound envelope fields: `tool_allowlist`, `source_filter`, `cost_ceiling`. Soft-bound tuning fields: `system_prompt`, `retrieval_strategy`, `filter_tree`, `top_k`, `min_score`, `model_selection`. Three hard, six soft.

`AgentTemplate` gains `source_methodology_role_name` (string, nullable for blank-created agents, immutable after revision 1, paired-NULL invariant with `source_methodology_template_id` and `source_methodology_template_version`). Records which role the agent was cloned from for lineage audit.

Agent create and update use case validates each content field against the role's binding-mode contract at write time. Hard violations reject with explicit error naming the field and the role's constraint. Soft writes pass through. Runtime enforcement of `cost_ceiling` defers per the existing deferred-decisions entry; `tool_allowlist` runtime enforcement lands at P8 with tool invocation; `source_filter` write-time validation fires only when set (always null at Phase 1).

LVT methodology template migrates from single-role-implicit to single-role-array shape via Alembic migration at S26: wrap existing flat content fields in `roles = [{role_name: "LVTGuide", description: "Lean Value Tree guide role", ...existing_fields, source_filter: null, cost_ceiling: null}]`. One-time genesis re-anchoring of methodology hash chain at migration time with explicit migration commentary. The PM agent at tenant alpha is unaffected because D75's agent revision carries flat content fields independent of methodology shape; the agent's `source_methodology_role_name` back-fills as "LVTGuide" alongside existing lineage fields.

**Reasoning.** The captures synthesis refined methodology-as-constraint-contract to option d: methodology declares roles agents can occupy and constraints attached to each role (tools, sources, retrieval bounds, cost ceilings). Roles as JSONB array on `MethodologyRevision` is the smallest diff from D74 that supports the multi-role framing; preserves the single-aggregate single-hash-chain pattern; matches the existing JSONB-as-configuration pattern (`filter_tree` and `retrieval_strategy` already JSONB). The captures' "each layer constrains layers below" framing required a precise resolution between the methodology-embedded-not-gated principle and the constraint contract framing; per-field binding mode resolves the tension by distinguishing envelope surfaces (security, budget, scope; bind hard) from tuning surfaces (overrides cheap per the methodology-embedded principle). The agent's content fields stay flat per D75 to preserve D68's independent-clones commitment; the binding-mode contract is enforced at write time against the role snapshot at clone time, not at runtime against the live methodology (methodology updates do not propagate to existing agents per D68). McKinsey 7-Step as forcing test case: seven roles (ProblemFramer, Disaggregator, Prioritiser, Planner, Analyst, Synthesiser, Communicator) in one methodology, each with its own constraint bundle; the methodology aggregate accommodates this shape without proliferation.

**Alternatives considered.** (a) Roles as separate aggregates parented to `MethodologyTemplate` with their own revision and hash chain; rejected because methodology hash chain has to incorporate role revision hashes which complicates the existing single-chain pattern, role-level versioning has no Phase 1 consumer, and migration to this shape is a clean refactor later when role-level versioning has a real consumer at Phase 2 gallery curation. (b) Methodology stays flat at P7 close; role becomes a separate top-level concept tied to methodology by reference; rejected because it contradicts the captures' "methodology declares roles" framing and produces a methodology that is near-content-free, which is the same shape problem D74 rejected when considering one bounded context for both methodologies and agents. (c) Defer multi-role methodology entirely; treat 7-Step as seven methodologies composed in a workflow; rejected because it contradicts the captures' explicit framing and produces methodology proliferation as the gallery grows. (d) Per-role binding-mode declaration where methodology authors choose binding mode per role per field; rejected at Phase 1 because it adds complexity without consumer evidence; defers to a new deferred-decisions entry for activation when methodology evidence shows the convention insufficient. (e) Single binding mode (all hard or all soft); rejected because cost ceilings and tool allowlist are real security and budget surfaces that should bind hard, while system prompt and model selection are tuning surfaces that should override cheaply. (f) Methodology constraints propagate to existing agents on methodology update; rejected because it contradicts D68's independent-clones commitment and produces silent drift on methodology evolution. (g) Retrieval bounds as hard constraints (max_top_k, allowed_strategies); rejected at Phase 1 because it needs consumer evidence before commitment; defers to a new deferred-decisions entry for activation when methodology evidence shows soft-binding insufficient.

**Kano.** Must-have on the multi-role refinement (gates the methodology and workflow contracts; without it the captures' constraint contract framing has no architectural home). Performance on the specific binding-mode classification defaults (the defaults evolve as evidence accumulates).

---

**D81: Platform invariants and Padhanam-as-intelligence-layer** (P8 framing, topology design session, 2026-05-11)

**Choice.** Platform invariants are the platform's dynamic capability posture under user-safety load-bearing. They name what the platform does not enable at the current state of guardrail and capability evolution. Six user-safety dimensions anchor the set: privacy, integrity, reversibility, transparency, control, auditability. Adding a new invariant requires naming which dimensions it serves; removing an invariant requires demonstrating the dimensions are still served by other means.

Five starting invariants at Phase 1 close, danger-targeted:

1. **No financial execution without explicit per-transaction authorization.** Tool-layer classification at P8 prevents financial-execution tools from invoking without per-transaction user confirmation. Dimensions: reversibility, control.

2. **No outbound communication to third parties without explicit per-invocation authorization.** Tools that send to non-Padhanam recipients require user review and confirmation per send; user sees content and recipient before send. Dimensions: control, transparency.

3. **No acceptance of legal commitments without explicit user action.** Tools accepting terms, signing agreements, agreeing to contracts require deliberate user action, not just confirmation of an agent-initiated request. Dimensions: control, integrity.

4. **No auto-modification or auto-deletion of user-authored content within Padhanam's storage.** Sources, methodology templates, agent revisions, workflow templates, audit records: append-only or immutable per D26 and D31. Edits create new revisions; deletes are user-initiated only. Dimensions: reversibility, integrity.

5. **No transmission of tenant data outside tenant-configured tool paths.** Tenant data flows only through tools the tenant has configured per D14. Dimensions: privacy, control.

Consent-granularity principle anchors the set: consent granularity is proportionate to danger class. Per-transaction for financial. Per-invocation for outbound communication. Explicit user action for legal commitments. Standing consent at tool configuration for routine reversible actions, optionally with per-invocation review where the tool's classification specifies.

Padhanam-as-intelligence-layer commitment: the platform produces recommendations, analyses, and drafts; consequential actions on the user's behalf require user-in-the-loop authorization at appropriate granularity per the invariants and the consent-granularity principle. This is the platform's commercial differentiator from autonomous-agent platforms. Extends the existing "Optimization output is recommendation-shaped, not chart-shaped" principle from the optimisation layer to the agent layer.

Three layers of enforcement. Capability layer: the platform does not have native capabilities for invariant-blocked actions. Tool layer: tool registration and invocation at P8 enforce platform invariants; classification mechanism per the P8 tool registry D-entry. Methodology and agent layer: additional opt-in restrictions on top of platform invariants.

Health and safety content framing lands separately as a content principle in `charter/principles.md` (not an invariant; different shape — about output framing rather than capability).

**Reasoning.** The captures synthesis framed user safety as load-bearing principle for the architecture's evolution. Three platform invariants were named conservatively in the captures (no-STP for personal work, no financial execution, no auto-delete). The five-invariant danger-targeted refinement maps the captures' three to specific actionable danger classes (financial harm, reputational and identity harm, legal harm, data destruction within Padhanam, privacy harm) while sharpening the "no-STP for personal work" to the specific danger surfaces of outbound communication and legal commitments. The "intelligence layer not action layer" framing from the captures reframes as commercial positioning rather than strict no-action invariant; mass-consumer use cases require agents to act with consent at routine boundaries (calendar updates with standing consent, document generation, drafting), which the consent-granularity principle accommodates. Procurement-defensibility shape: an audit at a point in time captures the invariant set as it stood; the set is versioned in `charter/principles.md` per the existing append-only principle. Promotions in (adding capabilities) and promotions out (loosening invariants) are recorded as charter commits with the dimension-justification reasoning.

**Alternatives considered.** (a) Strict intelligence-layer commitment forbidding all agent actions on the user's behalf; rejected on mass-consumer-UX grounds because auto-update calendar, document generation, spreadsheet generation, draft creation are routine reversible actions that mass consumers expect and that the consent-granularity principle accommodates safely. (b) Captures' "no-STP for personal work" as a single broad invariant; rejected because it is too broad to enforce mechanically; sharpened into invariants 2 and 3 which target the specific danger surfaces. (c) Health and safety output framing as an invariant; rejected because it is a different shape from the capability invariants (about output framing rather than capability constraint); lands as a content principle in `charter/principles.md`. (d) Cascading-harm invariant at Phase 1; rejected because it is not yet a real risk at Phase 1 single-agent invocation; defers via new deferred-decisions entry activating when multi-agent workflows or persistent agents enter the codebase. (e) Identity-credential exposure as a new invariant; rejected because existing security posture covers this via field-level encryption, `padhanam/observability/security_events.py`, no plaintext credentials in traces. (f) Per-invocation confirmation for all user-affecting actions; rejected because it is too restrictive for mass consumers who expect standing consent at tool configuration for routine reversible actions.

**Kano.** Must-have. The invariant set is procurement-grade audit defence and consumer-grade safety floor; without it the platform's user-safety commitments are implicit rather than declared. The platform-invariants-as-evolving framing distinguishes capability promotion from architectural drift.

---

**D82: Workflow as architectural primitive — contexts/workflow/ commitments and Phase 2 implementation** (P8 framing, topology design session, 2026-05-11)

**Choice.** Workflow lands as a new bounded context at `contexts/workflow/` per D16, distinct from methodology and agent. Workflow composes agents (potentially across methodologies), declares routing topology, termination criteria, version pinning, and aggregate budgets. Phase 1 commits the architecture in charter (`charter/contexts/workflow.md`); Phase 2 implements code alongside consumer-grade UX and the LangGraph adapter.

Aggregate shape. `WorkflowTemplate` and `WorkflowRevision` mirroring D74 and D75 patterns. `WorkflowTemplate` carries id, name, description, source_methodology_template_id (nullable for cross-methodology workflows; immutable when set), created_by_user_id, created_at, archived_at. `WorkflowRevision` carries workflow_template_id, version, definition (JSONB), created_by_user_id, created_at, plus hash-chain fields per D26.

Definition JSONB shape. Agent slots (each binding to methodology+role or fixed agent template, with version pinning), topology (sequential, conditional, or reflective), edges (typed by topology), termination criteria, aggregate budget. Phase 2 implementation chooses specific serialisation per category.

Topology categories at Phase 1 architecture: sequential, conditional, reflective. Termination criteria categories: step count, output condition, budget exceeded, sequence completion, reflective convergence. Aggregate budget: USD per workflow invocation per D49 and the deferred currency-evolution entry; enforcement at workflow runtime defers to Phase 2.

Storage pattern: control-plane for platform-curated workflow templates (gallery items per D33); per-tenant for tenant-authored workflows per D32. Mirrors methodology and agent contexts.

Cross-context relationships: workflow reads methodology and agent via api-facade-via-callable per D17. `WorkflowView`, `MethodologyView`, `AgentView` DTOs defined in workflow context's application layer. No type imports from `contexts.methodology` or `contexts.agent` at the domain or application layer; the wiring layer translates producer aggregates to consumer-shaped DTOs.

`WorkflowExecutor` port: named per the deferred-decisions orchestration architecture entry. Method signature `execute(workflow_revision, inputs, tenant_context)` returning streaming execution state. Implementation deferred. LangGraph adapter named as Phase 2 implementation target.

Auth posture: operator-context for control-plane templates per D33; tenant-context-or-operator-context for tenant-authored per D75 pattern. Tenant isolation contract tests extend `tests/contract/tenant_isolation/` per D24 when implementation lands.

CLI surface shape: `padhanam workflow create | get | list | update | retire | run`. Implementation deferred.

Composition terminology distinction. The captures synthesis's wording suggesting D66 and D67 "get a clearer home here" reconciles as: D66 (retrieval composition at agent runtime layer) and D67 (filter expression translation at ingestion adapter layer) stay where they are. The workflow context gets a structurally separate agent-composition concern that happens to share the word "composition." No edits to D66 or D67.

**Reasoning.** The captures synthesis named workflow as a new architectural primitive distinct from methodology and agent, with explicit cross-methodology composition capability. The new bounded context follows the established pattern from D60 (ingestion), D74 (methodology), D75 (agent): revision-shaped per D31, hash-chain audit per D26, control-plane plus per-tenant storage split, cross-context api-facade-via-callable per D17. Phase 1 charter-only commitment respects operator capacity per `status-2026-05-06.md`'s throughput question; implementation defers alongside Phase 2's consumer-grade UX surface per the captures' "Phase 1 ships the substrate; Phase 2 ships the consumer-grade authoring surface" framing. The workflow context's architecture is sufficiently specified that Phase 2 implementation does not re-litigate decisions; the cost is that the architecture is unverified by code at Phase 1 close, which is consistent with how other deferred-decisions architectural commitments operate.

**Alternatives considered.** (a) Workflow as a refinement to the agent context rather than a new bounded context; rejected because agent and workflow have different audiences, different lifecycle, different audit shape — same reasoning D16 and D74 used to split methodology from agent. (b) Workflow context implementation at Phase 1 alongside agent runtime at P8; rejected because it is roughly 3x P8 scope, the operator capacity constraint is real, and the bet's success criterion 2 is met at agent-runtime-only. (c) Workflow definition shape that is LangGraph-specific; rejected because it contradicts the orchestration architecture deferred-decisions entry's commitment to portability across workflow orchestrators within feature-parity bounds. (d) Methodology and workflow merged into a single "process" context; rejected because methodology declares roles and constraints while workflow composes agents through roles, which are different concerns the captures synthesis explicitly separated. (e) Cross-mode portability between workflow and agent definitions; rejected per the orchestration architecture entry's existing commitment that cross-mode portability is not supported.

**Kano.** Must-have on the architectural commitments (gates Phase 2 implementation; commits the workflow primitive that the four-layer stack depends on; commits the Phase 2 scope boundary). Performance on the specific JSONB definition shape and CLI surface (the specifics can evolve at Phase 2 implementation per consumer evidence).

---

**D83: P8 agent runtime adapter shape and LangGraph deferral to Phase 2** (P8 framing, topology design session, 2026-05-11)

**Choice.** P8 ships agent runtime with a hand-rolled `AgentLoopExecutor` implementing the `AgentExecutor` port per the orchestration architecture deferred-decisions entry. The executor handles the LLM-with-tool-loop pattern (model proposes tool calls in its responses; runtime executes tools and feeds results back) against existing LiteLLM (D4), retrieval (D60, D66), tool registry (new at P8 per D68's deferred surface), audit (D26), and trace capture (D49, D57) surfaces. LangGraph does not ship at P8.

LangGraph adapter implementation defers to Phase 2 alongside workflow context implementation per D82. The orchestration architecture deferred-decisions entry's commitment to LangGraph implementing `WorkflowExecutor` stands; the implementation timing moves.

P8's `charter/packages.md` text revises from "P8: Agent runtime. LangGraph orchestrator behind interface. SSE-streamed responses. Full instrumentation" to "P8: Agent runtime. AgentLoopExecutor behind AgentExecutor interface. SSE-streamed responses. Full instrumentation. Workflow context architecture committed for Phase 2 implementation."

`charter/roadmap.md` gets a version update reflecting the P8 text revision; reasoning category per D44: discovery (workflow primitive surfaced from the 2026-05-11 captures entry after the original packages.md was authored).

**Reasoning.** LangGraph at agent runtime is over-architected for single-agent invocation. The LLM-with-tool-loop pattern is roughly 100-200 lines of Python against LiteLLM and the tool registry; LangGraph adds graph machinery that single-agent invocation does not need. Hand-rolling is faster, simpler, and more inspectable for the operator. Provider agnosticism per D4 holds: the hand-rolled loop runs against LiteLLM rather than against any provider-specific SDK. When workflow context implementation lands at Phase 2, LangGraph is the right fit because workflow execution genuinely benefits from graph machinery. Operator capacity per `status-2026-05-06.md` throughput question favours the smaller P8 scope; expanding P8 to ship agent runtime plus full workflow context plus LangGraph adapter is roughly 3x the original P8 scope.

**Alternatives considered.** (a) LangGraph implements both `AgentExecutor` and `WorkflowExecutor` at P8; rejected because it doubles P8 scope without benefit, LangGraph's graph idiom does not fit single-agent invocation cleanly, and the hand-rolled adapter is faster and more inspectable. (b) OpenAI Agents SDK as the agent runtime adapter at P8; rejected on provider-coupling grounds at the default path per D4. (c) Workflow context implementation at P8 alongside agent runtime, without LangGraph; rejected because workflow context without execution adapter is a partial commitment, and structurally better to commit architecture only or commit fully. (d) Agent runtime defers to Phase 2 alongside workflow context; rejected because the bet's success criterion 2 requires one agent running at Phase 1 close.

**Kano.** Performance. The P8 scope choice and adapter shape preserve the architectural commitments (D4 provider-agnosticism, D68 tool registry deferral, D66 retrieval composition at agent runtime layer) that future packages consume; alternative shapes would force retrofit at Phase 2 when workflow context implementation lands.

---

**D84: McKinsey 7-Step methodology authoring placement** (P8 framing, topology design session, 2026-05-11)

**Choice.** McKinsey 7-Step methodology template authoring lands as a separate strategic block, post-topology-design and pre-P8 build sessions. The block produces one `MethodologyTemplate` row on control plane with one `MethodologyRevision` carrying seven role elements (ProblemFramer, Disaggregator, Prioritiser, Planner, Analyst, Synthesiser, Communicator). Each role's constraint bundle authored against the methodology aggregate v2 shape per D80.

**Reasoning.** 7-Step is a second concrete methodology template after LVT. Structurally cheap once D80's methodology-as-constraint-contract is settled; authoring against an undecided contract risks rework. 7-Step authoring is methodology-template work, not architectural-decision work; bundling into the topology session dilutes the architectural focus and roughly doubles scope. Post-topology placement gives P8's first build sessions a second methodology template (when consumer evidence at Phase 2 workflow context implementation activates the workflow shape, the 7-Step becomes a workflow composing seven agents, exercising the multi-role surface end-to-end). The 7-Step's seven-role shape exercises the multi-role methodology surface per D80, surfacing any practical authoring friction with the role bundle JSONB shape before Phase 2 implementation work begins.

**Alternatives considered.** (a) Author 7-Step before topology design session as forcing example; rejected because authoring against an undecided architecture risks rework, and the topology session uses 7-Step as a thought experiment for the role-shape decision without committing template content. (b) Author 7-Step during topology design session; rejected because it doubles session scope and dilutes architectural focus. (c) Author 7-Step after P8 build complete; rejected because it misses the opportunity to exercise the methodology aggregate v2 shape early. (d) Defer 7-Step authoring to Phase 2 alongside workflow context implementation; rejected because 7-Step is methodology-template work not workflow work; the coupling is only at the workflow-uses-methodology level which the captures' cross-methodology framing handles cleanly.

**Kano.** Performance. The placement choice preserves the architectural commitment to one methodology at P7 close per D68 while adding a second template at a structurally cheap moment.

---

### Remaining prompt sections (workflow.md, p8-epic.md, principles.md edits, packages.md edit, roadmap.md edit, current-package.md edit, deferred-decisions.md three entries, captures triage update, commit shape, acceptance criteria, reflection prompts, out of scope, session log entry instruction)

The prompt's full text for the remaining sections is preserved verbatim in the session-execution commit; the brief here captures the prompt's structure and the D-entry bodies that anchor the strategic commit. The execution renumbered D79–D84 to D80–D85 throughout per the brief-preservation note above.
