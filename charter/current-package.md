# Current Package

Active package details. Updated when a new package starts. Archived to `docs/archive/packages/` at package close.

## P8 active — S29b in flight

P8 opened on 2026-05-11. S26 split per D86 into S26a (methodology v3 migration with role aggregate) and S26b (McKinsey 7-Step authoring against the role-first model). S26a further split at scope-meets-reality into S26a-1 (control-plane work) and S26a-2 (per-tenant work).

**S28b closed on 2026-05-12.** Ten commits landing the tool registry generalisation: a new `contexts/tools/` bounded context with `Tool` + `ToolRevision` aggregates and six-category D89 classification taxonomy on control plane per the user-question resolution (alternative (h) in D89); Alembic 0009 creating the tables and seeding retrieval at a well-known UUID; classification filter + defensive invariant check at the invocation boundary with the three-to-three mapping (financial→1, communication→2, legal→3); `role.tool_allowlist` migrated from `tuple[str, ...]` to `tuple[ToolAllowlistEntry, ...]` (ToolAllowlistEntry lives in `shared_kernel/types.py`) via two Alembic migrations (control-plane 0010 + per-tenant 0010 with cross-plane backfill); two thin ports at agent context (`ToolDefinitionsLookup`, `ToolInvoker`) — third reinforcement of the consumer-port-plus-wiring-adapter pattern from S26a-1, S26a-2, S27b — now a Phase 1 norm; `AgentLoopExecutor` retires the hardcoded retrieval branch and consumes the ToolInvoker port with `TerminationReason.INVARIANT_BLOCKED` translating high-classification blocks to structured loop termination; schema-diff backward-compatibility stub at revision creation storing `BCResult` on `ToolRevision.bc_result` and feeding the `RoleToolBinding.can_auto_adopt` adoption-candidate query; wiring adapters at `apps/cli/_cross_context.py` (ToolDefinitionsLookupAdapter + ToolInvokerAdapter with retrieval-specific helpers relocated from the executor); `padhanam tool create | get | list` CLI with Phase 1 authoring prohibition on financial/communication/legal; tenant-isolation contract test extension covering the tool-invocation path's tenant_context threading. 709 tests pass across unit + AST enforcement + apps/cli integration + contract + other integration (up from 619 at S27b close; +90 net); 24 import-linter contracts kept (up from 23); four Alembic migrations forward-and-back-verified twice each. The fifth instance of pre-write-reconciliation-as-architectural-discovery (storage-location resolution at the user-question moment); promotion to `charter/methodology.md` warranted at next phase audit. Brief preserved at `briefs/p8/s28b.md`. D89 absorbs the storage choice as alternative (h); three deferred-decisions entries activate at first authoring evidence for the per-invocation confirmation pathway, rich BC testing, and automated adoption flow.

**S29b in flight.** Streaming runtime substrate. Eleven domain-layer event types at `contexts/agent/domain/events.py` (InvocationStarted, IterationStarted, LLMCallStarted, ContentDelta, ToolCallProposed, ToolCallExecuting, ToolCallCompleted, IterationCompleted, InvocationCompleted, InvocationFailed, InvariantBlocked) expose the runtime's state machine to consumers as a transport-neutral substrate the gallery-pre-population work at Phase 2 demos against. `AgentExecutor.execute` refactors to yield an async iterator of events; non-streaming callers wrap via `collect_to_result`. Inference port gains `stream_complete`; LiteLLM adapter vendor-isolation preserved. Nested OTel span hierarchy (invocation → iteration → LLM call + tool call) with cost roll-up per D49 extended; audit stays at two rows per invocation per D26. SSE endpoint at `apps/api/routers/agent.py` adopts the existing principal-derived tenant convention. The transport-neutral domain placement is the fourth reinforcement of the consumer-port-plus-wiring-adapter pattern (after S26a-1, S26a-2, S27b, S28b) — the pattern is now a settled Phase 1 norm. D90 absorbs the four sub-choices (event vocabulary, nested-trace-simple-audit asymmetry, streaming-only executor, domain-layer event placement) plus the three S29b pre-write reconciliation outcomes (URL shape stays principal-derived per existing convention; method names preserved as `execute` and `stream_complete` for symmetry). S30b lands the operator-facing `padhanam agent run` CLI and the LVT PM agent end-to-end demonstration with operator-uploaded sources including a drafted-artifact-as-deliverable shape exercising the intelligence-layer commitment in product form.

**S26a closed on 2026-05-12** with S26a-1 (six commits, control-plane scope) and S26a-2 (seven commits, per-tenant + cross-plane scope). The split-at-implementation-reality decision yielded two clean sessions of comparable size and audit weight rather than one overloaded one; the original S26a brief's commit-4-to-5 boundary held up as a cut point through implementation.

**S26a-1 (closed 2026-05-12).** Six commits: control-plane Alembic 0005_role_tables + 0006_methodology_role_refs + 0007_lvt_split (all forward-and-back-verified); role aggregate within `contexts/methodology/` (domain, port, postgres adapter, five use cases); methodology refactor to role_refs with hash re-anchoring at the migration boundary; role-aware MethodologyLookupAdapter at `apps/cli/_cross_context.py`; LVT methodology + LVTGuide role split via the rename migration; round-trip integration test exercising the role-first composition end-to-end. 157 methodology/role/agent/CLI/tenant-isolation tests pass; import-linter's 23 contracts kept; AST enforcement passes. Brief preserved at `briefs/p8/s26a-1.md`.

**S26a-2 (closed 2026-05-12).** Seven commits: per-tenant Alembic 0009_agent_role_lineage (cross-plane backfill from control-plane methodology revisions to populate `source_role_id` + `source_role_version` on tenant rows; forward-and-back-verified); `AgentTemplate` domain gains the role lineage pair (paired-null invariant per D86 alongside D75's methodology pair, applied independently); `MethodologyView` consumer-side DTO extended to carry resolved `role_id` + `role_version` (pre-write reconciliation: the brief's assumption that the view already carried these was wrong — extension was the cleanest path because the role-aware adapter already resolves role_refs[0]); new `RoleLookup` port + `RoleView` DTO + `create_agent_from_role` use case + `RoleLookupAdapter`; `padhanam role` CLI namespace (five commands) + `padhanam agent create-from-role`; tenant isolation contract test for the new column; restored S25 docker-based clone-and-edit e2e against the role-aware shape (full rewrite landing both create-from-methodology and create-from-role; 103s end-to-end against the live Compose stack). 561 unit + integration + tenant-isolation + AST tests pass; 23 import-linter contracts kept. Brief preserved at `briefs/p8/s26a-2.md`.

**S26b closed on 2026-05-12.** Five commits authoring the McKinsey 7-Step methodology and its seven role aggregates (ProblemFramer, Disaggregator, Prioritiser, Planner, Analyst, Synthesiser, Communicator) into the platform-managed methodology surface against D86's role-first model and the new D87 override-mode framing. D87 surfaced at pre-write reconciliation as a refinement of D86's sub-commitments (b) and (e): the brief's "system_prompt addition" semantics for each of the seven McKinsey roles read as augment, not the literal replace D86 specified for soft fields; the user-question pattern elevated the choice from "encode mode in the migration's overrides shape" to "amend the substrate's binding-mode taxonomy with the three-mode space {augment, replace, tighten}". D87 commits the mode space, the per-field default-mode table (system_prompt → augment, soft fields → replace, hard fields → tighten), the structured `{mode, value}` on-disk shape for `RoleRef.overrides`, the authoring projection from flat to structured, and the admissibility validation. Substrate-side: `RoleRef.overrides` tightened from `Mapping[str, Any] | None` to `dict[str, dict[str, Any]]` defaulted to empty dict; new module `contexts/methodology/domain/overrides.py` exports `DEFAULT_MODE_BY_FIELD`, `validate_override`, `project_overrides`, `OverrideValidationError`; the canonical encoder maps empty overrides to `None` for byte-stability with pre-D87 LVT hashes; the postgres materialiser normalises both `null` and `{}` JSONB to the empty-dict default. Migration-side: `0008_create_mckinsey_7_step` inserts seven `role_templates` + seven `role_revisions` (revision 1 chained from genesis) plus one `methodology_templates` + one `methodology_revisions` (revision 1 with role_refs JSONB carrying seven references in the brief's sequential order, each with a single augment-mode `system_prompt` override verbatim from the brief); forward-and-back-verified against the live control-plane Postgres; idempotent on re-run. Test surface: 599 tests pass across unit + contract + methodology integration + CLI integration + AST enforcement (24 new D87 substrate unit tests + 5 new McKinsey integration tests with golden-hash assertions). Four pre-existing methodology integration fixtures updated to scope truncation to non-migration actors (`created_by_user_id NOT LIKE 'migration:%'`) so migration-owned rows survive cross-test ordering — a structurally-honest finding the McKinsey integration test surfaced because the migration owns persistent content. 23 import-linter contracts kept; 9 AST enforcement tests pass. Brief preserved at `briefs/p8/s26b.md`. D87's surfacing through brief reconciliation is the architectural anchor: the first authoring-evidence moment refined the substrate ahead of the content authoring it would have constrained.

**S27b closed on 2026-05-12.** Nine commits landing the first demonstrable agent invocation against the McKinsey methodology authored at S26b. The bet's success criterion 2 at Phase 1 close (one agent running) is met: a McKinsey ProblemFramer agent runs end-to-end against the live LiteLLM gateway + Qwen 2.5 7B via Ollama, with the D87 augment composition (role base + "\n\n" + SCQ override) reaching the LLM call verbatim and two audit rows landing on tenant alpha's chain with intact hash integrity. D88 absorbs four pre-write architectural sub-choices resolved at the user-question moment: (1) extending the InferencePort for tool-aware chat (preserving D4's single vendor-isolation seam at the LiteLLM adapter); (2) defining `AgentRetrievalClient` at agent context with strategy translation at the wiring adapter rather than direct cross-context import; (3) defining a runtime `MethodologyOverridesLookup` port distinct from clone-time `MethodologyLookup`; (4) the two-newline augment separator with reflection at session close as the forcing function for richer framing if LLM behaviour demands. The agent context's port surface lands clean: `AgentExecutor` Protocol at `contexts/agent/ports/executor.py` with `AgentInvocationContext + AgentResult + AgentSignal + InvocationMessage + TerminationReason` DTOs; `EffectiveConstraintBundle` at `contexts/agent/domain/effective_bundle.py`; `AgentRetrievalClient + RetrievedChunk` and `MethodologyOverridesLookup` at `contexts/agent/application/ports/`. The composition resolver at `contexts/agent/application/composition.py` implements every (field, mode) admissibility per D87 with 20 unit tests covering augment/replace/tighten/no-overrides plus malformed-entry defence. The `AgentLoopExecutor` at `contexts/agent/adapters/outbound/agent_loop_executor.py` implements the hand-rolled LLM-with-tool-loop with `MAX_ITERATIONS=10` plus retrieval-as-only-callable per D88. The `invoke_agent` use case at `contexts/agent/application/use_cases.py` handles the three lineage paths (blank-created, role-cloned, methodology-cloned). `AuditPort.emit` widened to return the persisted event so the agent runtime captures the authoritative chain hashes on `AgentResult`. `Completion` gained `cost_usd: Decimal` so per-invocation cost aggregates from per-call deltas without OTel-span introspection. The new wiring adapters at `apps/cli/_cross_context.py` (`AgentRetrievalClientAdapter`, `MethodologyOverridesLookupAdapter`) follow the api-facade-via-callable pattern from D17 for the third time, reinforcing it as a Phase 1 norm. 619 tests pass across unit + tenant-isolation contract + AST enforcement at session close (up from 599 at S26b close); the integration test against the live stack passes with a real Qwen call; 23 import-linter contracts kept. Brief preserved at `briefs/p8/s27b.md`; `compose.yaml`'s padhanam-api digest pin moved to `sha256:108f92b9...` to reflect the rebuilt image carrying the agent runtime code.

**S28b next.** Tool registry bounded context. The agent runtime's tool surface at Phase 1 is retrieval-as-only-callable; S28b ships a tool aggregate with classification taxonomy and invariant enforcement per D82, replacing the hardcoded retrieval branch in `AgentLoopExecutor` with a registry lookup. The reflection at S27b close named three extension points S28b should preserve: per-tool result formatting; classification-driven invariant checks injected before tool invocation; iteration cap as a per-role concern. The tool registry generalises without restructuring the loop's control flow because the branching on `completion.tool_calls` empty-vs-populated and the four-mode `TerminationReason` enum are already structurally tool-agnostic.

P8-internal architectural anchor: roles are first-class primary aggregates per D86. Methodology is a playbook composing roles via `role_refs` plus workflow specification plus per-role overrides; methodology v2 from D81 (roles JSONB embedded on methodology) was skipped in favour of v3 directly. The role-first commitment shapes the rest of P8: S27b's agent runtime invokes against role-bound or methodology-bound agents; S28b's tool registry binds classifications via the role's `tool_allowlist`; the four-layer constraint stack from D80 reads as a five-concept stack per D86 (platform invariants, role envelope, methodology overlay, workflow orchestration, agent instance).

## Carryovers active across the P7→P8 boundary

- **Hierarchical multi-agent topology design.** Closed at strategic-mode commit 6f66f71 (D80 through D85). Role-first refinement (D86) closed at this commit.
- **Layer A policy authoring.** Follow-on strategic block authoring
  the ten policy scaffolds at `charter/compliance/` per the
  compliance-as-shared-responsibility principle. Scheduled at
  operator discretion between P7 build sessions or after P7 close;
  does not block any P7 build session because the substrate (D-entries
  D69-D73, the principle, the scaffold structure) is in place. Authoring
  effort estimated at one strategic block session.
- **Retrieval-evaluation design session.** Queued strategic-mode
  conversation ahead of P11 (recommendation engine). The audience
  is the existing eval harness from P5 and the optimisation layer
  at P11; the design space (gold-set construction, offline versus
  online relevance signals, recall@k versus precision@k tradeoffs,
  test corpus shape) warrants its own focused session at the
  audience-relevant moment. Must-have for the bet's optimisation
  claim because the optimisation layer has to distinguish retrieval
  failures from reasoning failures; deferred at the data-retrieval
  design session on Kano-versus-RICE asymmetry grounds (must-have
  on Kano, high effort on RICE relative to its on-runtime impact).
- **Product methodology selection-space.** P7 commits to LVT as
  the first methodology per D68; the LVT methodology template
  lands at S25. Other methodologies in
  [charter/product-methodology.md](product-methodology.md)
  activate as evidence pulls them in (operator authors as needed);
  per-domain methodology selection surfaces at the framing of each
  domain-bearing package.
- **Production CLI tenant resolution via the registry.** Phase 2
  shape; `apps/cli/_runtime.py`'s hardcoded test-set mapping is
  honest about its dev-only scope. Activates when production
  deployment context arrives.
- **Multi-baseline regression reports.** Deferred per D58;
  single-baseline at S18. Activates at P11's recommendation
  engine when run-history infrastructure exists from P9.
- **PRFAQ phase-audit refresh.** Cadence per D45 (every phase
  audit). The v2 PRFAQ from the P4-post carryover-cleanup
  strategic session stands until the Phase 1 close audit. The
  Phase 1 close audit refresh additionally absorbs the dogfooding
  scenario acknowledgment per D77 and D78 (operator runs a private
  deployment for personal use as evidence of D14's customer-
  deployment scenario).
- **Personal-use deployment of public Padhanam (Phase C).**
  Operator-controlled deployment of public Padhanam as a real
  instance of the customer-deployment scenario per D78, exercising
  D14's configuration + tools + bounded-extensions model. Phase C
  activates concretely after P8 close (when agent runtime exists);
  preparatory work (operator-authored tool services and methodology
  template authoring) can start after P7 close in parallel with P8
  build, subject to operator capacity per the all-or-nothing
  posture. PRFAQ acknowledgment lands at the next phase audit.
- **Calendar tool service as platform capability.** Deferred-
  decisions entry per the P7 mid-package strategic block on
  consumer-direction placement; activation when public Padhanam
  needs a calendar integration for any package work or when the
  personal-use deployment Phase C activates per D78, whichever
  comes first.
- **Email tool service as platform capability.** Deferred-decisions
  entry, same activation shape as the calendar tool entry.
- **Scheduled-runs primitive.** Deferred-decisions entry; activates
  when public Padhanam needs scheduled agent execution (likely P11
  or P12 territory) or when personal-use deployment Phase C needs
  daily-review-style triggers, whichever comes first. Two
  implementation candidates (platform primitive versus external
  trigger); choice settles when implementation begins.

## Deferred items remaining visible

- **Per-tenant Neo4j topology.** Activated at S21 per D63 with
  Phase 1 shared-instance + property-based scoping; the
  deferred-decisions entry remains as the production-deployment
  revisit marker with three named triggers (residency, blast
  radius, security-review).
- **Within-tenant segmentation primitive.** Held in the P6-open
  strategic-block conversation; activates at the consumer-driven
  session that demands it (likely P8 agent runtime). No schema
  commitment at P6 beyond tenant.
- **Classification field on TenantContext.** Deferred per S15
  framing decision option C; lands at the package that genuinely
  consumes it (P7 or P8 per the P4 epic note's out-of-scope
  section). TenantContext at P6 close still carries three fields,
  not four; adding the field later is a one-line edit on the
  value object plus a registry-row column.
- **Cost-ceiling forward-affordance columns.** Configuration
  columns landed at S14 alongside the cost-attribution column per
  D41. Reading and enforcing the columns defers to Phase 2 per
  [charter/deferred-decisions.md](deferred-decisions.md).
- **Pricing-table monthly review.** Cadence in
  `ops/scheduled_checks.yaml` per D41; first run scheduled
  2026-06-05.
- **Pricing-table format evolution.** S14 reflection forward-note;
  the format-(b) Pydantic + dict shape evolves to YAML/TOML under
  `ops/` when multi-region rates, time-zoned rates, or rate-card
  complexity arrives. Phase 2 framing.
- **PRFAQ operator-voice rewrite.** Follow-on strategic
  conversation, queued at operator discretion.
- **Phase 1 PRD operator-review** of the problem-statement and
  target-user sections. Operator discretion.
- **Production-shaped tenant onboarding workflow** (full D13
  implementation): awaits production deployment context.
- **Cross-replica cache invalidation for the routing layer**
  (D36): single-replica dev makes this a non-issue.
- **Hash chain caching as a performance optimisation** (D37):
  deferred until measurement justifies.
- **Methodology mechanical-enforcement upgrades.** Tracked in
  [charter/deferred-decisions.md](deferred-decisions.md). The
  framing-prompt-as-recommendation and pre-write reconciliation
  promotions at this commit move two items off the
  Patterns-observed candidate list onto the prescriptive
  principle surface; the user-driven course-correction Patterns-
  observed entry lands at the same commit.
- **Platform-baseline scoring sheet library** (deferred per D53;
  activates at real onboarding flow or a cross-tenant curated
  library with a real consumer).
- **Human-review UI for evaluation** (deferred per D53; lands at
  P10 or P11 territory).
- **Multi-currency cost reporting** (deferred per the strategic
  commit `24561c9` deferred-decisions entry; activates at the
  Phase 2 multi-region deployment context).
- **Per-criterion cost breakdowns in
  `CostPerSuccessfulTaskResult`** (P11 territory).
- **Calibration learning loops over `automated_score` vs
  `human_score`** (P11 territory; data substrate lives at
  rubric_applications per D55).
- **Trace_id-based recommendation queries beyond
  cost-per-successful-task** (P11 territory).
- **HTTP API for ingestion management** (deferred per the P6
  out-of-scope; CLI is the user surface at P6; HTTP API ships
  when a UI consumer arrives at P9 or P10).
- **HTTP API for evaluation management** (deferred; activates
  when a UI consumer arrives at P10 or P11).
- **Sheet/interaction-set management commands in the CLI**
  (deferred; activates when CRUD UI is needed).
- **Personalization as a runtime concern.** Deferred-decisions
  entry from P6 mid-package absorption (Ask David external
  reference); activates at P8 agent runtime or whichever
  predecessor orchestration session demands it.
