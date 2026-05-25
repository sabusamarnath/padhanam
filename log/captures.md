# Captures

Mid-session catch surface per D48. Append-only. Stray thoughts during sessions go here so they neither derail the current session nor get lost.

Triage at session close (or at package close for less time-critical captures): each entry classified into one of five impact types, then either acted on, deferred, or archived.

Triage taxonomy:

- **quick task** — small enough to handle this session.
- **inject** — insert into the current package's session sequence.
- **defer** — forward to the next package or to `charter/deferred-decisions.md`.
- **replan** — large enough to warrant rethinking scope; trigger course-change in `charter/roadmap.md`.
- **note** — record only; no action implied.

Format per entry:

```
- YYYY-MM-DD [session-id] capture text
  - triaged: <classification> on YYYY-MM-DD
  - resolution: <what was done, or where it was forwarded>
```

---

[Captures begin below this line.]

## 2026-05-07 — Enterprise multi-agent QA system case study

Source: enterprise case study presented at the 2025 LangChain interrupt conference. Approach diagram and full transcript captured by the operator.

Architectural shape observed: domain-specific QA system with hierarchical multi-agent topology, intent-based routing to specialised sub-agents, runtime personalization conditioned on user role, reflection/judge gating before answer ships, memory layer for cross-conversation continuity, and human-in-the-loop escalation.

Observations and where each lands:

- **Hierarchical multi-agent topology with intent-routed subgraphs.** Design-session candidate; queued at P8 framing or as pre-P8 strategic block.
- **Personalization as a runtime concern** (same data renders differently based on user role). Landed as deferred-decisions entry this commit.
- **Build pattern: start simple, refactor often.** Landed as methodology discipline this commit.
- **Data retrieval as a multi-path architectural concern**, with each path having distinct evaluation needs and architectural posture. Design-session candidate; queued after P6 close, scope possibly large enough to earn package status on the roadmap.
  - triaged: design-session candidate on 2026-05-07
  - resolution: data-retrieval design session held 2026-05-07 between P6 close and P7 framing; output landed as D66 (hybrid composition architecture) and D67 (filter expression architecture); no package elevation needed because implementation lands in P7 (agent config schema) and P8 (runtime orchestrator and filter translator); retrieval-evaluation surface deferred to its own strategic-mode session ahead of P11 on Kano-versus-RICE asymmetry grounds.
- **Memory as a first-class agent surface.** Deferred-decision candidate; activates when an agent runtime use case demands cross-conversation context the audit and trace substrates cannot synthesise cleanly.
- **Runtime reflection as an orchestration node.** Deferred-decision candidate; activates when an agent runtime use case requires answer-quality gating before user surfacing.
- **Evaluation-driven development with sub-agent independent evaluation.** Corroborates Padhanam's eval-before-agent sequencing (P5 closed before P8 ships); no new commitment.

Bet corroboration: an enterprise of the kind Padhanam's bet names as the procurement test condition shipping this shape publicly is signal that the procurement-grade orchestration posture Padhanam architects toward is what enterprise teams actually deploy in 2025-2026. Worth citing at the Phase 1 close audit as enterprise reference architecture. Padhanam's own architecture may end up looking different; the corroboration value is in the procurement-grade posture, not in the specific implementation choices.

## 2026-05-09 — P7 mid-package strategic block — Architectural-mapping exercise for customer customisation

Source: P7 mid-package strategic block on consumer-direction placement.

Architectural exercise surfaced for any future customer customisation conversation. Classify each customisation requirement:

- **Configuration** (changes a tenant registry value or methodology template content) → no code change anywhere
- **Tool** (calls an external service to do something Padhanam doesn't natively do) → tool service lives outside Padhanam in its own codebase, configuration points to it
- **Extension** (logic running inside Padhanam at one of the named interfaces per D14) → bounded extension, sandboxed, per-tenant
- **Platform change** (none of the above fit) → upstream contribution to public Padhanam, no forking

Most things should fit in #1 or #2. Few in #3. Almost nothing should fit in #4 if the platform is well-designed; if many things fit in #4, the platform's customisation surface has gaps requiring architectural attention.

  - triaged: methodology-pattern candidate on 2026-05-09
  - resolution: noted at the strategic block's reflection section as a reusable architectural exercise; not promoted to methodology document at this commit because single-instance observation. Recurrence test continues at the next strategic block touching customer customisation; promotion threshold is two further instances per the existing methodology-promotion convention.

## 2026-05-09 — P7 mid-package strategic block — User-driven course-correction sixth instance

Source: P7 mid-package strategic block on consumer-direction placement.

Sixth named instance of the user-driven course-correction Patterns-observed entry from P6 close. Two course-corrections fired during this strategic block:

1. Operator caught the "Padhanam-lite as separate consumer build" framing accumulating across early conversation turns and pulled the framing back to "personal use as own instance of public Padhanam," reconnecting the conversation to D14's customer-deployment model. Without the catch, the strategic block would have produced a separate-build commitment despite the substrate-mismatch and attention-split concerns.

2. Operator caught the "private fork" recommendation surfaced mid-conversation and pulled it back to D14's no-fork architectural commitment by asking the broader client-customisation question. The catch surfaced the principle's overclaim ("forbidden" as performative rather than enforceable), triggered the principle revision now landing as D76, and clarified that the personal-use case is fully covered by the configuration + tools + bounded-extensions model without any need to fork.

The pattern continues to do load-bearing work at strategic-mode conversations and remains the most frequently-firing methodology pattern of the run. Recommend formal promotion to a methodology document entry at the next phase audit (P7 close), with the recurrence-test now satisfied at six instances across distinct strategic moments.

  - triaged: methodology-recurrence note on 2026-05-09
  - resolution: surfaced at the strategic block's reflection section as continuing pattern. Phase audit promotion candidate.

## 2026-05-10 — Consumer-direction architectural exploration (historical context for D77's alternatives-considered)

Source: OpenClaw analysis triggered post-S23/S24 brief drafting; multi-day strategic exploration spanning 2026-05-09 to 2026-05-10. The exploration considered a separate-consumer-build path before the strategic block landed D77; D77 superseded that path by placing the consumer-direction thread within D14's customer-deployment model rather than as a separate build (commit 1fb7712, P7 mid-package strategic block on consumer-direction placement). The architectural details below are recorded as historical context for the alternatives D77's alternatives-considered section names — specifically alternative (a) "Separate consumer build (Padhanam-lite as standalone product)" and alternative (c) "Bet expansion to second methodology demonstration." Not load-bearing for public Padhanam.

### Architectural shape (rejected separate-consumer-build path)

The separate-consumer-build path would have shaped as M3 hybrid (on-device plus hosted), three-tier with deterministic core dominant:

- **Architecture:** Tier 0 deterministic core (scheduler, integrations, templates, structured logging) handling the majority of routine interactions; Tier 1 local LLM (Apple Intelligence on capable iPhones, Gemini Nano on capable Androids) augmenting where available; Tier 2 hosted LLM for complex reasoning. Device-fragmentation constraint dissolves at Tier 0 in this shape; the product would have addressed the full mobile install base.
- **Mobile:** design constraint not initial scope. Architecture would have supported eventual mobile clients without retrofit.
- **Push:** Shape M2 server-side scheduler with FCM. Phone-triggered local LLM for routine proactive cases (no platform push infrastructure required); FCM-mediated server-push for hosted-LLM cases.
- **Privacy:** user-controlled tier. Closed mode (no LLM outside container; local LLM only), Sandboxed mode (hosted LLM with confidential-computing guarantees), Standard mode (hosted LLM with opt-in feedback). Default-candidate from the exploration: Sandboxed where device and provider supported confidential-computing guarantees; Standard otherwise.
- **LLM economics:** tiered approach was the resolution to the consumer adoption problem. Most interactions would invoke no LLM; Tier 2 would justify cost when invoked. Pricing candidate: freemium with premium tier for T2-heavy use cases.
- **Iteration loop:** methodology-as-iteration-unit with local replay against user history. Structured failure signals (decision-points tagged, inputs typed, outputs scored on dimensions, failures classified) would aggregate to platform without exposing user content. LLM-augmented operator analytics would propose specific changes with rationale and projected impact.
- **Distribution:** standalone app primary; MCP secondary surface for Claude users (a possible fourth distribution channel).
- **Design philosophy:** default-quiet, escalate-gracefully, do-not-over-prompt. "Staying human" as constraint on all agent behaviour, not a separate feature.

### Use case portfolio (rejected separate-consumer-build path)

Eleven real-life use cases stress-tested the rejected architecture across goal-driven, habit-driven, relational, reflective, and operational personas (reading a book a week, learning a new language, learning work-related, applying for a new role, managing family life, assisting friends, day-to-day job, meds, health, catching up with friends, staying human):

- T0-dominant (7 of 11): reading, meds, health, social catch-up, day-to-day job, family life, assisting friends.
- T2-weighted (2 of 11): language conversation practice, work-learning curriculum design.
- T2-heavy outlier (1 of 11): job applications. Would have implied a separate pricing tier or BYOK.
- Boundary case (1 of 11): staying human. Treated as design constraint rather than feature.

Pattern observed: agent-persona spectrum implies N agents per user sharing substrate, methodology-driven differentiation, cross-agent context as second-order value driver. The pattern is recorded as historical context only; it is not load-bearing for public Padhanam under D77.

### Strategic placement outcome

Placement landed as personal-use deployment of public Padhanam per D77 and D78. The four options framed during the strategic exploration (adjacent exploration, second methodology demonstration, pivot to consumer, MCP-layer agent platform) plus the separate-consumer-build path that this capture records were each weighed against the bet's load-bearing claims. D77 records the rationale for each rejection and the structurally honest answer (placement within D14's customer-deployment architecture).

### Methodology observations

- **Pre-build review with code-reading verification and deliberate-silence-detection** fired its third instance, this time against operator-uploaded OpenClaw documents containing fabricated specifics (founder status, infostealer targeting framing, valuation claims). The first two instances landed in build-session brief reviews (S23, S24); this third instance fires in a strategic-mode context against external source documents, suggesting the pattern's load-bearing scope extends beyond brief review to any source-document review where load-bearing technical or factual commitments are present. Recurrence test positive across two distinct contexts; recommend promotion to a methodology-document Patterns-observed entry at the next phase audit (P7 close).
- **Polished-AI-output-as-failure-mode**: progressive hallucination under pressure for "comprehensive" output without source-verification discipline. Distinct from the 2026-05-06 fabrication-class-drift Failure modes entry (which covered model-drafted vendor-voice content) because the new pattern is about polish-pressure-driven fabrication during multi-turn exploration rather than vendor-voice path-of-least-resistance fabrication during artefact drafting. New pattern; first observation; awaiting recurrence before phase-audit promotion.
- **Strategic-placement-deferred-to-allow-architectural-settlement**: sequencing pattern. Separate "what is true" from "what should we do" when reversibility differs sharply across options. Held during the strategic exploration that produced this capture: architectural outcomes settled across multiple turns before the placement question converged on D77 and D78 in the parallel placement-strategic block. New sequencing-pattern candidate; first observation; awaiting recurrence before phase-audit promotion.

  - triaged: historical-context note on 2026-05-10
  - resolution: architectural details preserved as historical context for D77's alternatives-considered section, specifically the separate-consumer-build alternative; not load-bearing for public Padhanam under D77's placement; no deferred-decisions entries land for the consumer-direction architectural questions because they would re-elevate architectural details that D77 superseded.

## 2026-05-10 — Claude.ai conversation surface as lead-up to D77

Source: Claude.ai conversation "P7 active-build state and strategic-mode surface" (be66aaed-9918-4a4d-8a97-9df0be9ea7ba), 2026-05-09 to 2026-05-10. The conversation opened on S23 brief-drafting framing and accumulated consumer-direction architectural exploration mid-thread when OpenClaw analysis surfaced post-S24 close. The exploration's architectural details (M3 hybrid three-tier with deterministic core dominant, M2 server-side scheduler with FCM, privacy-as-user-controlled-tier with local replay, eleven use-case stress test, MCP as fourth distribution surface) are recorded at the prior 2026-05-10 captures entry "Consumer-direction architectural exploration (historical context for D77's alternatives-considered)" and not duplicated here.

This entry adds a single traceability link: the architectural reasoning that fed D77's alternatives-considered section (a) "Separate consumer build (Padhanam-lite as standalone product)" was developed across this Claude.ai conversation's mid-thread; the D77 commit itself (1fb7712) was prompted from a separate Claude.ai conversation that absorbed the exploration and reframed it within D14's customer-deployment model. Pre-write reconciliation against decisions.md within this conversation surfaced the placement conflict and superseded the conversation's own drafted prompt; the conversation closed with deferral to D77 rather than producing a competing commitment.

  - triaged: traceability note on 2026-05-10
  - resolution: trail recorded for audit-trail completeness; the prior architectural-details captures entry remains the substantive record; no charter commitments altered.

## 2026-05-11 — S25 closed with synthetic LVT sources in tenant alpha

Source: P7 S25 live-stack work; Claude Code generated synthetic LVT-shaped markdown sources for tenant alpha's PM agent rather than operator-uploaded content per the brief's goal #6 specification. Operator accepted synthetic at build-time as a deliberate sequencing decision with planned remediation.

The PM agent at tenant alpha currently retrieves against two Claude-Code-generated source files (0e42829c... and 7ee7f8d9...) ingested via the standard pipeline. Architectural flow exercised end-to-end; the agent functions; only the source-content provenance differs from the brief.

Remediation trigger: before P8's first runtime test against the PM agent. P8's runtime is the first consumer that exercises sources for retrieval-augmented generation; synthetic content invalidates whatever signal P8's tests produce against this agent specifically. Operator uploads real LVT-relevant source content (strategy docs, bet articulations, OKRs, or equivalent) and re-ingests before P8 runs runtime tests.

  - triaged: deferred-action note on 2026-05-11
  - resolution: deferred-action; trigger named (before P8 runtime testing of the PM agent); operator owns remediation; no charter commitment beyond this note required because the trigger is build-session-shaped not architecture-shaped.

## 2026-05-11 — P7 strategic block — architecture and product direction synthesis ahead of topology design session

Source: Claude.ai strategic conversation during P7 build (post-S24, S25 build pauses, S25 close). Multi-thread exploration covering methodology-as-constraint-contract, workflow as new architectural primitive, four-layer constraint stack, mass-market UX direction, gallery pre-population strategy, and capability-evolution framing for platform invariants. Output is preparatory material for the hierarchical multi-agent topology design session at the P7-to-P8 boundary, which now has materially expanded scope.

Architecture refinements explored.

Methodology refined to agent-level constraint contract (option d from the altitude framing): methodology declares roles agents can occupy and constraints attached to each role (tools, sources, retrieval bounds, cost ceilings). Tightens D68's methodology-as-platform-service framing without breaking it.

Workflow surfaces as new architectural primitive distinct from methodology and agent. Workflow composes agents (potentially across methodologies), declares routing topology (sequential, conditional, reflective), termination criteria, version pinning, and aggregate budgets. Workflow lands as its own bounded context at contexts/workflow/ per D16, tenant-managed per D32, revision-shaped per D31. Composition orchestrator (D66) and filter-tree translator (D67) get a clearer home here.

Four-layer constraint stack: platform invariants (non-overridable by user-authored content), methodology (per methodology, constrains agents), workflow (per workflow, constrains topology), agent (per instance). Each layer constrains layers below.

Platform invariants treated as dynamic state of platform's safety posture rather than fixed list. Starting set is conservative (no-STP for personal work, no financial execution, no auto-delete). Capabilities promote in over time as guardrails strengthen. User safety as the load-bearing principle (privacy, integrity, reversibility, transparency, control, auditability).

Product direction.

Mass-market UX as Phase 2 commitment with Phase 1 architectural implications. Phase 1 ships the substrate; Phase 2 ships the consumer-grade authoring surface. Reframes the bet positioning from "procurement-grade enterprise demonstration" toward "procurement-grade architecture with consumer-grade UX" (Notion precedent: enterprise architecture, consumer UX). Mass-market-first acts as architectural forcing function for safe-path-equals-easy-path.

Gallery pre-population as validation strategy. Solves blank-slate friction (users see options not prompts), source credibility (authoritative-source attribution), and partial validation (well-known methodology shapes test platform substrate even without consumer users). Seven seed categories suggested: physical activity (Southridge Video), mental health (Southridge Video or NICE), sleep hygiene (Southridge Video or CDC), cooking and nutrition (Southridge Video Eatwell), habit formation (Charles Duhigg, James Clear), home projects, learning a skill. Restricted to authoritative sources and non-controversial domains.

Padhanam positioning explored as intelligence layer rather than action layer. Platform produces recommendations and analyses; user executes consequential actions in their own systems. Product differentiator against autonomous-agent platforms.

Three gaps surfaced for forward resolution.

Gap 1: Bet articulation has not caught up to consumer-UX-plus-enterprise-architecture refinement. Resolution surface: Phase 1 close audit per D45's living-artefact discipline.

Gap 2: Validation strategy for mass-market UX is partial; gallery handles blank-slate and credibility but not UX itself. Resolution surface: Phase 2 framing.

Gap 3: D78's "operator deploys public Padhanam personally" scope grows if operator becomes a real consumer of the gallery rather than staying in PM-tooling mode. Resolution surface: next phase audit alongside Gap 1.

  - triaged: strategic-input note on 2026-05-11
  - resolution: topology design strategic block executed 2026-05-11 at the P7→P8 boundary. Architectural scope absorbed: D80 (four-layer constraint stack), D81 (methodology aggregate v2 with multi-role refinement and per-field binding mode), D82 (platform invariants and Padhanam-as-intelligence-layer with five danger-targeted invariants), D83 (workflow as architectural primitive with Phase 2 implementation), D84 (P8 agent runtime adapter shape and LangGraph deferral), D85 (McKinsey 7-Step methodology authoring placement). New charter file at charter/contexts/workflow.md. Revised charter/packages/p8-epic.md. New User safety section in charter/principles.md with refined methodology-embedded principle. charter/packages.md P8 line revision. charter/roadmap.md v4 entry with discovery reasoning. charter/current-package.md transition. Three new deferred-decisions entries (cascading-harm invariant shape; retrieval-bound hard-constraint shape; per-role binding-mode override). Three gaps land at named future surfaces per original triage (Gap 1 at Phase 1 close audit per D45; Gap 2 at Phase 2 framing; Gap 3 at next phase audit alongside Gap 1).

## 2026-05-12 — Pre-write reconciliation as architectural discovery: methodology-document promotion candidate at five reinforcements

Source: S28b session close.

Pattern: pre-write reconciliation as architectural discovery. Distinguishing characteristic worth naming for promotion: this pattern catches cross-document architectural inconsistencies that prose review at prompt-drafting time cannot catch, because the prompt-drafter sees local consistency within the prompt and misses implicit dependencies on charter documents authored at different times against different consumers. The mechanism is mechanical: at session start, the implementer reads every file the prompt names before drafting code; if the read surfaces inconsistency with the prompt's assumptions, the implementer raises a user question; the architect resolves with an explicit decision (often a new or amended D-entry); code lands only after reconciliation.

S28b instance: prompt's "per-tenant tools" framing (inherited from p8-epic line carrying D32 reference) contradicted "tuple-shape pin at control-plane role authoring" (D86 commitment). Pre-write reconciliation surfaced the cross-plane reference tension. User-question moment resolved to control-plane tool storage at Phase 1, with per-tenant tool authoring deferred to Phase 2 per the customer-deployment-evidence trajectory. D89 absorbs the choice as alternative (h).

Recurrence count: five reinforcements per operator count at S28b close. S4 Langfuse vendor-version drift is the originating precedent.

  - triaged: note on 2026-05-12
  - resolution: forwarded to Phase 1 close audit prep as a methodology-document Patterns-observed promotion candidate. The audit's strategic-mode conversation drafts the formal entry per the build-versus-strategic discipline (build sessions do not write to charter/methodology.md directly per D47).

## 2026-05-12 — Consumer-port-plus-wiring-adapter pattern altitude-agnostic: methodology-document promotion candidate at four reinforcements

Source: S29b session close.

Pattern: consumer-port-plus-wiring-adapter as an altitude-agnostic abstraction. Distinguishing characteristic worth naming for promotion: the same shape (consumer-side port defined against a consumer-shaped DTO; wiring adapter at `apps/cli/_cross_context.py` or `apps/api/adapters/` translating producer aggregates or transport wire formats to consumer DTOs) now applies at three architectural altitudes:

- **Cross-context.** S26a-1 (MethodologyLookup), S26a-2 (RoleLookup), S27b (AgentRetrievalClient + MethodologyOverridesLookup), S28b (ToolDefinitionsLookup + ToolInvoker). Consumer context defines the port against its own DTO; producer context exposes use cases at `api.py`; wiring adapter joins them at `apps/cli` without leaking producer aggregates into consumer code.
- **Intra-context wiring.** S28b's ToolInvoker. The agent context's executor consumes the ToolInvoker port; the wiring adapter at `apps/cli` composes tool-context use cases plus retrieval-context use cases plus agent-side helpers into one consumer-shaped surface.
- **Transport.** S29b's SSE adapter. Domain-shaped events flow through a consumer port (the runtime yields AgentEvent); the wiring adapter at `apps/api/adapters/sse_event_translator.py` translates to W3C EventSource wire format. The transport is another consumer of the runtime's port; the adapter pattern absorbs the transport-specific impedance.

The mechanism is the same at every altitude: define the port with the consumer's DTO, never import the producer's aggregate, wire the impedance mismatch at the application composition layer (`apps/cli` or `apps/api`). The altitude-agnostic shape is what lifts the pattern from a build-time tactic to a Phase 1 methodology principle candidate.

Recurrence count: four reinforcements across five sessions in a row (S26a-1 as first instance; S26a-2, S27b, S28b, S29b as four reinforcements). The S29b session-log methodology line 2 names this explicitly as a Phase 1 close audit methodology-promotion candidate. The pre-write reconciliation captures entry above is the structural precedent for this entry's shape.

  - triaged: note on 2026-05-12
  - resolution: forwarded to Phase 1 close audit prep as a methodology-document Patterns-observed promotion candidate. The audit's strategic-mode conversation drafts the formal entry per the build-versus-strategic discipline (build sessions do not write to `charter/methodology.md` directly per D47).

## 2026-05-13 [S30b] — Test-fixture leak wipes methodology rows while filter-protected role rows survive

Source: S30b pre-session smoke run against the rebuilt padhanam-api container. The smoke run surfaced an empty `methodology_templates` table and a missing `LVTGuide` role on the control plane, against an Alembic state that reports `0010_role_tool_allowlist_pin` (latest). The seven McKinsey role rows (`migration:0008_create_mckinsey_7_step` provenance) survived; the McKinsey methodology row and the LVT methodology row plus LVTGuide role did not.

Symptom: cross-test ordering against the live control-plane DB wipes methodology-owned rows while leaving role-owned rows intact. S26b's session-log entry named the fix as "Four pre-existing methodology integration fixtures updated to scope truncation to non-migration actors (`created_by_user_id NOT LIKE 'migration:%'`) so migration-owned rows survive cross-test ordering." The fix landed at four named fixtures; the asymmetric outcome (roles survive, methodologies do not) suggested at least one methodology-touching test path remained unfiltered.

Identification: two offending fixtures named at S30b.

1. `tests/contract/tenant_isolation/test_methodology_isolation.py:133-135` (setup) and `:157-159` (teardown) issued bare `sa.delete(methodology_revisions)` and `sa.delete(methodology_templates)` with no `.where(...)` clause. Lives at the contract-test path (`tests/contract/tenant_isolation/`), not the integration path (`tests/integration/contexts/methodology/`) that S26b's fix covered. This is the active offender — fires in normal test cycles when the control plane is reachable.

2. `tests/e2e/agent/test_create_from_methodology_flow.py:154-158` (`_truncate_methodology_and_role` helper called by the `clean_state` fixture) issued raw `TRUNCATE TABLE methodology_revisions, methodology_templates, role_revisions, role_templates` against the control plane. Latent offender — fires only in opt-in e2e runs but wipes all four tables (methodology + role) when it does. TRUNCATE cannot carry a WHERE clause so the fix switches to per-table `DELETE WHERE created_by_user_id NOT LIKE 'migration:%'`.

LVTGuide's absence (vs the seven McKinsey roles surviving) traces to fixture 2 firing earlier in the DB's history. After it wiped role_templates, migration 0007's `_rename_role` could not anchor against `LVTRole` (it had been wiped before 0006 ran or 0007's idempotency guard saw nothing to rename); LVTGuide was never reconstructed. Fixture 1's recent firing then wiped methodology_templates entirely, taking out both LVT and McKinsey methodology rows but leaving the seven McKinsey role rows (which fixture 1 does not touch) untouched.

Recovery at S30b: ad-hoc CLI authoring via `padhanam methodology create` (LVT and McKinsey 7-Step) and `padhanam role create` (LVTGuide) against the live control plane, with content reconstructed from `briefs/p7/s25.md` (LVT system prompt) and `briefs/p8/mckinsey-7-step.md` (McKinsey per-role overrides). The recreated rows carry the operator's `cli-operator` actor (no `migration:` prefix), so the now-filter-protected fixtures would no longer wipe them.

In-session fix: both fixtures patched at S30b to carry the `created_by_user_id NOT LIKE 'migration:%'` filter. Fixture 1 switches the SQLAlchemy `sa.delete(...)` calls to `sa.delete(...).where(table.c.created_by_user_id.notlike("migration:%"))`. Fixture 2 switches from `TRUNCATE` to four `DELETE FROM <table> WHERE created_by_user_id NOT LIKE 'migration:%'` statements ordered children-before-parents to satisfy FK constraints.

  - triaged: fix on 2026-05-13
  - resolution: both fixtures patched in-session at S30b with the S26b filter pattern. Subsequent test runs preserve migration-seeded rows. The S26b fix's "four fixtures" framing carried an implicit completeness claim that did not hold across the broader test surface — the structural lesson is that filter-pattern application at a single audit moment needs a grep-driven completeness check rather than a per-file enumeration.

## 2026-05-15 [S39b] — Migration name-length convention

Alembic revision strings must stay ≤32 characters to fit the `alembic_version.version_num VARCHAR(32)` column. S39's initial revisions exceeded the ceiling (`0012_role_allowlist_retrieval_closure` at 37 chars, `0013_retrieval_evaluation_substrate` at 35 chars) and `make migrate` failed with `StringDataRightTruncation` on the `alembic_version` UPDATE at version-bump time; the transactional DDL rolled back the failed upgrade cleanly, no partial state. Shortened in place at smoke time to `0012_role_allowlist_retrieval` (29 chars) and `0013_retrieval_eval_substrate` (29 chars).

Convention forward: revision-string components should fit `NNNN_<short_slug>` where `<short_slug>` stays under ~25 chars to leave headroom for the four-character zero-padded number plus underscore. File names (e.g. `YYYY_MM_DD_NNNN_<slug>.py`) can be longer; only the `revision: str = "..."` declaration inside the file must stay short.

  - triaged: convention captured on 2026-05-15
  - resolution: convention recorded in this file as a project-tooling constraint. No D-entry required — this is a vendor-tooling constraint (alembic's VARCHAR(32) column ceiling), not an architectural decision. Future migrations should keep this in mind; if a third instance of name-length truncation surfaces, consider promoting to a project-tooling note in `charter/principles.md` Token discipline section.

## 2026-05-15 [S41] — Scope-check-at-substrate-application-boundary as candidate methodology default

Source: S41 mid-session reconciliation. The original S41 brief framed 12 commits. The pre-write reconciliation Finding 3 zero-recommendation-surface push-back (the (δ) disposition committing OptimizationRun as a coupled aggregate) expanded scope by ~15-20% — adds an aggregate root + repository + reader + Postgres adapters + migration table + list/get use cases + CLI subcommands. The expansion was structurally honest (substrate symmetry with EvaluationRun); the framing did not anticipate it.

Mid-execution at the substrate-application boundary (between commit 3 closing the domain layer and commit 4 opening the application/rules work), operator pause caught the scope-versus-framing divergence. Reasoning: domain layer is shape-stable and tested; smoke at end of session is load-bearing structural-honesty surface and carries more risk after long single-stretch execution than after focused work units; recognising scope expansion is structurally honest rather than powering through a now-larger-than-framed session.

Observation: substrate sessions may benefit from a planned scope-check at the domain-application boundary rather than discovering scope creep at execution time. The boundary is naturally where the new context's shape stabilises (domain landed) and the next work unit's character changes (application use cases, engine logic, persistence). A planned scope-check at that boundary would let the operator decide split-vs-continue with full information about both what shipped and what remains.

  - triaged: pending — flagged for P12 audit methodology candidates list
  - resolution: candidate observation; promotion to charter/methodology.md if the pattern recurs at one or two more substrate sessions, or if P12 audit deems substrate sessions a distinct shape worth methodology treatment.

## 2026-05-15 [S41] — Principle-versus-framing drift as distinct methodology candidate

Source: S41 commit 4 (rules placement). The brief framed
`contexts/optimization/domain/rules/` as the placement for the four
default rule implementations. Writing the code surfaced the layering
violation: the rules import producer-context reader ports and consume
the application-layer `EvidenceContext`, so they cannot live at the
domain layer without breaching hexagonal intent. Placement corrected
to `contexts/optimization/application/rules/` at commit time.

This finding is structurally distinct from the three previous P11 mid-
session drift surfacings:

- S39 sibling-in-pattern (D109 framing referenced contexts/evaluation/
  scoring-sheet as the structural precedent; the scoring-sheet aggregate
  was read-only at S16 with no hash-chain, breaking the framing).
- S40 D66 framing-versus-as-built (D66 catalogued three retrieval
  strategies; the adapter implemented two, with parallel_rrf unimplemented).
- S40b graph_only infrastructure substrate (S40 framing assumed the
  graph retrieval leg would be exercised at runner time; graph-extract
  reliability surfaced as a substrate gap).

All three previous findings were as-built-versus-as-framed drift: the
brief framed against a specific codebase reality and the reality was
different from the framing. Pre-write reconciliation, by reading the
codebase before writing, catches this class.

This finding is principle-versus-framing drift. The brief framed
against no specific as-built reality; the framing simply contradicted
the hexagonal layering principle the codebase commits to at D16. No
pre-write reconciliation against codebase reality could catch it
because there was no codebase reference to reconcile against; only
writing the code and watching the import pattern surface the principle
violation catches the drift.

Mitigation surface is different from the previous three. Pre-write
reconciliation is the right discipline for as-built drift; for
principle drift, the mitigation surface is closer to "check the framing
against the principles file before writing the prompt." A brief-review
checkpoint at strategic-mode close that walks the framing against
`charter/principles.md` would catch this class of drift before the
build session opens.

  - triaged: pending — flagged for P12 audit methodology candidates list
  - resolution: candidate observation; promotion to charter/methodology.md
    if the pattern recurs at one or two more sessions, or if P12 audit
    deems the distinct mitigation surface (brief-vs-principles check vs
    brief-vs-codebase check) worth methodology treatment.

## 2026-05-15 [S41-post] — Container-image-lag pattern resolved via Makefile targets

Source: S41 session log methodology line 4 (container-image-lag at
smoke time at third P11 instance). The S41 session log promotion
question — "should the dev workflow include a documented fast-path
code sync into running container for smoke, or should the operator-
driven smoke loop assume container rebuild as baseline?" — resolves
to BOTH paths supported via Makefile targets.

Root cause: `apps/api/Dockerfile` uses `COPY` to bake source into
the image at build time; compose.yaml pins `padhanam-api:dev@sha256:
DIGEST` as an immutable reference. Local rebuilds get new digests,
so the pin becomes stale. Source changes don't reach the running
container without either (a) rebuild + digest-pin update or (b)
ad-hoc `docker compose cp`. Three P11 instances (S39, S40, S41)
each used (b) inline.

Resolution: two Makefile targets at `Makefile`:

- `make build-api`: rebuilds the image, captures the new sha256
  via `docker image inspect`, and sed-substitutes the compose.yaml
  digest pin in place. Production-shaped path; same code path
  production would exercise. Slower (a few minutes per rebuild)
  but verifies the actual image artefact.

- `make sync-code`: `docker compose cp` of source trees (contexts,
  apps, padhanam, shared_kernel, alembic) into the running
  padhanam-api container. Dev fast-path: CLI invocations via
  `docker compose exec ... python -m apps.cli.main` start fresh
  Python processes that import from disk, so synced source is
  picked up immediately. Server inside the container would
  require restart; smokes typically invoke CLI not server.

Both targets shipped at standalone commit (separable from any
session's substrate work). Future smokes choose the target at
smoke time based on what's being verified: tight iteration on a
session's code uses sync-code; production-shaped verification at
session close uses build-api.

  - triaged: resolved 2026-05-15
  - resolution: Makefile targets land; methodology candidate
    closed without P12 promotion (resolved at session-close, not
    deferred). The underlying observation — that compose-image
    pinning creates dev-friction proportional to rebuild
    frequency — remains a Phase 2 deployment-shape concern (the
    compose.yaml comment at line 374-375 anticipates this; the
    production manifest replaces the build-context form with an
    upstream-image digest pin where the friction disappears).

## 2026-05-15 [S42] — `make build-api` target broken by digest-in-image-tag

Source: S42 smoke. The post-S41 `make build-api` target at
`Makefile` invoked `docker compose build padhanam-api` to rebuild the
image; the compose `image:` directive carries a digest pin
(`padhanam-api:dev@sha256:...`) which is not a valid build tag, so the
target failed with "build tag cannot contain a digest" the first time
it was exercised at S42 smoke.

In-session fix at the Makefile: replaced `$(COMPOSE) build padhanam-api`
with `docker build -t padhanam-api:dev -f apps/api/Dockerfile .` —
matches the S37 smoke's direct-docker-build pattern and produces an
image tagged without the digest, which the subsequent
`docker image inspect` step then converts into the new digest pin.

Methodology candidate observation: the resolution of the
container-image-lag pattern at S41 close (commit 0e8041f) shipped two
Makefile targets without exercising either against the production-shape
flow. The bug was structurally invisible to unit tests (Makefile is
not test-covered) and to the resolution commit's smoke (which used the
pre-existing `docker build` pattern). The first production-shaped use
at S42 surfaced the bug. Promotion candidate: smoke-time verification
of dev-workflow tooling at the same session that ships it. Recurrence
test continues at the next dev-workflow tooling addition.

  - triaged: fix on 2026-05-15
  - resolution: Makefile target patched in-session; the fix lands as
    part of the S42 commit chain. Captured here as a methodology
    candidate (smoke-time verification of dev-workflow tooling).

## 2026-05-15 [S42] — Audit chain rows from S40/S41 carry empty correlation_id

Source: S42 smoke Stage 8. The S37 audit reader's
`AuditEventRecord.__post_init__` validator requires `correlation_id`
to be a non-empty string. The retrieval_evaluation and optimization
audit-event drafts at `contexts/retrieval_evaluation/application/audit_events.py`
and `contexts/optimization/application/audit_events.py` default
`correlation_id=""` (no calling context populates it yet), so audit
rows emitted by the S40 evaluation runner and the S41 optimization
engine fail the validator at read time.

Symptom at smoke: `GET /audit/events` without filters returns 500
because the reader iterates rows and the validator chokes on the
first empty-correlation_id row. Filtering by `resource_type=agent`
narrows to rows with valid correlation_ids and the route succeeds.

The S37 single-event read path is unaffected when the requested event
has a valid correlation_id; affected when targeting a row from S40 or
S41. The chain-integrity computation at page granularity is computed
from the rows that DO deserialize, so the reported `partial` status
on the agent-filtered page reflects the filter-vs-chain divergence
not the chain itself.

Two plausible mitigations for the pre-P12 hygiene session:

(a) Loosen the validator to allow empty correlation_id (treat as "no
    inbound request context for this event"). Honest about the
    cross-context audit semantics: not every audit event traces back
    to an HTTP request with a correlation_id (engine internals,
    background work). Cheap fix, no migration.

(b) Tighten the audit-event drafts to always supply a non-empty
    correlation_id (e.g. derive from the parent run_id or use a
    sentinel like "engine-internal:<run_id>"). Requires a backfill
    migration to repair the existing rows.

Recommend (a) at pre-P12 hygiene with a one-line validator change;
the backfill in (b) is heavier and the empty-string state is a
legitimate "no inbound HTTP context" signal that should not require
data shaping.

  - triaged: deferred-to-hygiene on 2026-05-15
  - resolution: captured for the pre-P12 hygiene session; S42 smoke
    workaround uses `resource_type=agent` filter to bypass affected
    rows. S37 single-event lookup against agent-context rows verified
    working; the route surface itself holds, only the cross-context
    data shape is inconsistent.

## 2026-05-20 — P13 framing Decision 6 framing miss: karma prior art, not external spec

The P13 framing brief at `briefs/p13/framing.md` Decision 6 frames the operator-supplied product specification as external architectural input being absorbed for the first time, with methodology line 2 framing the pattern as first-instance spec-as-architectural-input absorption. Both framings are incorrect in kind.

**The spec is karma prior art.** Karma is the operator's prior project at `/Users/sabu/karma2/`. Padhanam's brand was transplanted from karma at the karma transplant strategic block on 2026-05-12 per `charter/brand-guidelines.md:7` and D91 brand-as-charter-grade placement. The product specification at `docs/notes/spec-private-assistant-platform.md` is karma's canonical product specification, not an external reference.

**Preservation closes part of Block 2 Part B.** The karma transplant was a three-block sequence per `docs/archive/sessions/p8.md:244-260`. Block 2 Part B planned `docs/notes/prior-art-karma/` as a reference directory holding 11 pattern notes plus 4 karma reference docs; the directory was absent from the working tree at Block 2 close and surfaced as an open thread for future strategic-block consideration. The P13 framing brief commit preserved the spec at `docs/notes/spec-private-assistant-platform.md` rather than at `docs/notes/prior-art-karma/`. Whether to move the spec under the karma prior-art directory, whether to revive the full 11+4 corpus, and what granularity of pattern notes to extract from karma2 are strategic sub-decisions for the P13 framing substantive conversation or a subsequent strategic block.

**Three deferred-decisions entries already reference karma frameworks** at `charter/deferred-decisions.md`: multi-scope monitoring architecture (line 127); gate-as-workflow-step topology category (lines 225-231); user-authored taps as workflow-attached checkpoints (lines 241-249). The gate-as-workflow-step entry cites `docs/notes/prior-art-karma/authoring-contract.md` and the user-authored-taps entry cites `docs/notes/prior-art-karma/taps-and-dispatcher.md` — both prior-art-karma files that do not yet exist; the multi-scope monitoring entry references karma's scope-attached-resource framework as structural precedent without a file citation. These entries are settled-not-to-relitigate at P13 framing; the substantive conversation respects their existing activation triggers.

**Routing for P13 framing substantive conversation.** Decision 6's "spec-as-architectural-input absorption" framing should be re-read as "karma prior-art reference set completion plus partial Block 2 Part B closure." The decision's option (c) recommendation (specific extracts as charter additions; spec preservation at docs/notes/; substrate vocabulary aligned) still holds in substance; the framing reconciliation lands in the substantive conversation's audit of pre-conversation decisions plus in the subsequent commit session's framing of the spec-extracted charter additions and the spec-placement decision.

**Methodology line 2 reframing.** The brief's methodology line 2 names "spec-as-architectural-input absorption pattern, first instance." The accurate framing is "karma prior-art reference set partial completion at P13 framing brief commit; closes part of Block 2 Part B open thread per `docs/archive/sessions/p8.md:244-260`." The recurrence test the methodology line proposes is wrong in kind: the pattern is not absorption of additional external specifications but completion of karma prior-art reference set as substrate landing for already-committed deferred-decisions entries.

  - triaged: 2026-05-21 (resolved by the P13 framing landing commit session)
  - resolution: spec relocated to `docs/notes/prior-art-karma/spec.md`, creating the prior-art-karma directory as partial Block 2 Part B closure per Decision 6 Sub-decision A. Decision 6 reframed at the P13 framing substantive conversation from "spec-as-architectural-input absorption" to "karma prior-art reference set completion"; recorded in close deliverable 1. The `authoring-contract.md` and `taps-and-dispatcher.md` pattern notes remain deferred to their activation triggers per the existing deferred-decisions entries; full karma corpus revival not undertaken.

## 2026-05-21 — [S43/S43b] Planned-bridge-session sub-variant (methodology candidate)

S43 → S43b is the first instance of a *planned* bridge session: a deliberate substrate-and-transport split, taken at the substrate-completion boundary because the substrate alone consumed full session scope. It is distinct from the two prior bridge instances at P11 — S39 → S39b (verification-and-hygiene) and S40 → S40b (methodologically-clean-artefact authoring) — which were *unplanned* corrections discovered at substrate close. The planned split carries a `paired_with` metrics relationship rather than `corrects` / `corrected_by`: S43b completes a planned split, it does not correct S43. The split produced real signal — the transport work (~1,500 lines across thirteen files) ran with a fresh reconciliation pass and an un-rushed live smoke rather than as the fatigue-taxed tail of a single ten-commit session. First-instance evidence; structural novelty (a new bridge sub-variant). Recorded at the S43 and S43b session-log methodology lines.

  - triaged: defer on 2026-05-21
  - resolution: forwarded to `charter/methodology.md` promotion at second instance — a future bounded-context substrate session producing the same substrate-and-transport split shape. Promotion threshold is second instance per the bridge-session-shape precedent.

## 2026-05-21 — [S43/S43b] Brief path-drift at third instance (methodology candidate, promotion-ready)

Three instances of one drift class across three sessions: S40 (an adjacent retrieval_evaluation adapter shape), S43 (the brief named a flat `adapters/postgres_portfolio.py` path; the actual convention is `adapters/outbound/postgres/`), and S43b (the brief named a `tests/contract/http/portfolio/` subdirectory; the actual convention is flat `tests/contract/http/test_*.py` files). The S43 session-log entry set the promotion threshold at "a third instance promotes it." S43b is that third instance — promotion-ready.

Proposed methodology line, roughly: "Brief drafts naming adapter, test, or contract paths must reconcile against the actual `adapters/outbound/{vendor}/`, `tests/contract/*`, and equivalent codebase conventions before commit 1. Pre-write reconciliation explicitly checks path naming, not only shape." Placement: `charter/methodology.md`, work-organisation super-section or equivalent.

  - triaged: 2026-05-21 — promoted to a `charter/methodology.md` sub-paragraph under the pre-write reconciliation Patterns-observed entry at the pre-S44 hygiene session
  - resolution: methodology document updated with a *Path-naming sub-pattern.* paragraph adjacent to the Mid-build sub-pattern paragraph; the discipline addition is the explicit path-naming check at the pre-write reconciliation surface, and future briefs include path naming in the reconciliation surface enumeration. Promoted at two verified instances (S43, S43b), not the three this entry's body carries: promotion-time verification against the S40 session-log methodology lines found strategy-enumeration drift (D66 catalogues three retrieval strategies, the adapter executes two), a different drift class, so the S40 instance reclassified and fell out. Two-instance promotion holds per the corrective-discipline-on-first-instance precedent (the metric-threshold and reproducibility-artefacts methodology entries both promoted at one instance).

## 2026-05-21 — [S43/S43b] Substrate-completion-versus-deployment honesty (methodology candidate)

S43b reconciliation surface 5 caught a drift class: a migration commits to the source tree, contract tests pass against synthetic databases the harness provisions itself, and the running deployment is none the wiser. At S43 close the `0016` migration was committed but the `padhanam-api` image predated it, so `make migrate` (running inside that image's container) applied only through `0015`. The assumption gap is that "migration committed" means "migration deployed." Distinct mitigation surface from the brief-path-drift candidate: this one points at a CI / merge-gate fix (run `make migrate` against tenant containers as part of the gate, or a per-substrate-session deployment-verification commit), not a brief-drafting discipline fix. First-instance evidence as a named drift class, though the container-image-lag pattern it generalises has recurred across S41, S42, and S43→S43b.

  - triaged: defer on 2026-05-21
  - resolution: also added as the second entry of the Phase 2-A close hygiene list at `charter/phase-2-audit-inputs.md` this commit (migration-deployment verification surface). Forwarded to Phase 2-A close for the architecture-or-tooling decision (CI / merge-gate surface versus per-session verification commit). The S43b local fix — a durable structural test — already landed.

## 2026-05-22 — [S44a] Forward-commitment-evaluation pattern (methodology candidate)

D124 (S43) carried a forward commitment: ActorReference "is superseded at S44 by the full ActorContext ... the supersession extends shape and home without renaming," covering both the Revisable Protocol's `actor` parameter and the `authored_by` field. S44a pre-write reconciliation evaluated that commitment against the live codebase and found it structurally unsound for `authored_by`: the `data_points` and `assertions` tables persist authoring identity as a single `authored_by_user_id` text column, and a request-scoped ActorContext (carrying `authorisation_set`) cannot be honestly reconstructed from it or frozen onto a permanent record. D126 supersedes the forward commitment — the first instance of a D-entry superseding a forward commitment carried by an earlier D-entry.

The pattern worth naming: a forward commitment embedded in a D-entry is a hypothesis about future structure, not a binding instruction. The session that reaches the commitment's activation point evaluates it against the live codebase at pre-write reconciliation and supersedes with reasoning if it proves structurally wrong, rather than implementing it literally. The supersession D-entry preserves the audit trail; the superseded D-entry is not rewritten. First-instance observation. Recurrence test: the next D-entry carrying a forward commitment that is evaluated at a future session.

  - triaged: defer on 2026-05-22
  - resolution: forwarded to `charter/methodology.md` promotion candidacy. First instance; recurrence test named. Recorded at the S44a session-log methodology line 1.

## 2026-05-22 — [S44a] Brief-vs-domain-model drift at the type altitude (methodology candidate)

S44a pre-write reconciliation surface 5 directed a search for ActorReference consumers; the brief asserted "only the four portfolio use cases plus the Revisable Protocol consume it." The verification found a materially wider surface: ActorReference is the declared type of `DataPoint.authored_by` and `Assertion.authored_by` — persisted domain-entity fields — plus the Postgres reader, the CLI, the HTTP response DTO, the audit-event drafts, and five test files.

This is a sub-class of the brief path-drift pattern promoted at the pre-S44 hygiene session, but at a different altitude: path drift is about file-location naming; this is about which layers a type identifier reaches. The brief's framing came from the S44-framing mental model (ActorReference as an application-layer placeholder) rather than a fresh grep across `contexts/`, `apps/`, and `shared_kernel/`. The same drift class also surfaced the brief's omission of the fifth use case (`create_data_point`), found because the brief's use-case inventory came from the S43-close framing rather than a read of `contexts/portfolio/application/`. The mitigation surface is the same as path drift (pre-write reconciliation reading at session open), but the discipline addition is distinct: a brief that names a type or a use-case set verifies it with an explicit identifier search across every layer — domain, application, adapter, transport, CLI, tests — not only the layer the brief frames it at. First-instance candidate.

  - triaged: defer on 2026-05-22
  - resolution: forwarded to `charter/methodology.md` promotion candidacy as a type-altitude sub-class of the brief-vs-codebase drift pattern. Recorded at the S44a session-log methodology line 2.

## 2026-05-22 — [S44a] File topology budget first-instance load-bearing evidence (methodology candidate)

S44a is the first instance of the file topology budget discipline (the brief carried a budget table plus a sixth pre-write reconciliation surface verifying current file sizes against targets). The discipline did load-bearing work at first instance: surface 6 caught `apps/api/_errors.py` at 729 lines — far past any reasonable ~400-line ceiling for the router-error-handler file class — and the budget table's row for `_errors.py` ("delta +12, split trigger: None") carried no current size, so the overage would have gone unnoticed. The discipline both prevented the AuthorisationDenied handler from landing in `_errors.py` (it was redirected to `apps/api/_auth_errors.py` per D104's auth-cross-cutting placement, which is also structurally correct) and surfaced the existing 729-line overage for forward triage.

Without the budget verification surface, the AuthorisationDenied handler would have landed at `_errors.py` (the path the brief named) and the 729-line file would have grown further before P13 close. The discipline's load-bearing claim sits at first-instance validation, not only at recurrence.

  - triaged: defer on 2026-05-22
  - resolution: the `_errors.py` split is forwarded to the Phase 2-A close hygiene list at `charter/phase-2-audit-inputs.md`. The file topology budget discipline promotes to a `charter/methodology.md` entry at P13 close per the S44-framing settlement, with this first-instance evidence cited. Recorded at the S44a session-log methodology line 3.

## 2026-05-22 — [S44b] File topology budget second-instance evidence (methodology candidate)

S44b is the second instance of the file topology budget discipline (S44a was the first). Pre-write reconciliation surface 6 caught `apps/api/_agent_runtime_wiring.py` at 912 lines — past the brief's own budget-table split trigger for that file ("Multi-context wiring file approaches 600 lines"). S44a's first instance caught `apps/api/_errors.py` at 729 lines. Two instances, two genuine overages, each redirecting new code away from the over-budget file: at S44a the AuthorisationDenied handler went to `_auth_errors.py`; at S44b the intake write-surface wiring went to a new `apps/api/_intake_wiring.py` rather than growing `_agent_runtime_wiring.py`.

Two-instance load-bearing evidence. The discipline does not merely measure — it redirects placement decisions. Strong promotion candidate to `charter/methodology.md` at P13 close per the framing-conversation settlement.

  - triaged: defer on 2026-05-22
  - resolution: forwarded to P13-close methodology-document promotion with two-instance evidence (S44a `_errors.py`; S44b `_agent_runtime_wiring.py`). The `_agent_runtime_wiring.py` split is forwarded to `charter/phase-2-audit-inputs.md` alongside the `_errors.py` split.

## 2026-05-22 — [S44b] Cross-context-contract verification as a pre-write reconciliation surface (methodology candidate)

The S44b brief framed the intake-canonical orchestrations as use cases in `contexts/intake/application/` directly invoking `contexts/portfolio/application/` use cases, and AC 13 asserted "cross-context imports allowed at the application layer only" — the exact inverse of the import-linter "Cross-context: application layers are independent" contract (D16/D17/D28). The codebase carries the consumer-port-plus-wiring-adapter pattern at 12-plus reinforcements, yet the brief still inverted the rule.

The lesson: even a well-established architectural pattern surfaces drift at brief-drafting time, because the brief drafter reasons about intent ("the orchestration belongs at the intake boundary") without checking the brief's mechanism against the binding contract. The discipline addition is an explicit pre-write reconciliation surface: for any new cross-context dependency a brief introduces, verify import-linter contract conformance before drafting the work decomposition. The operator added this as standing surface 8 from S44b forward.

  - triaged: defer on 2026-05-22
  - resolution: forwarded to `charter/methodology.md` promotion candidacy. Surface 8 (cross-context-contract verification) added to the pre-write reconciliation surface set from S44b forward. First-instance evidence; recurrence test at the next brief introducing a cross-context dependency. Recorded at the S44b session-log methodology lines.

## 2026-05-22 — [S44b] Scope-completeness for D-entry architectural-posture commitments (methodology candidate)

D128's framing claimed "every persisted state change in the platform traces to an IntakeRecord." S44b pre-write reconciliation Finding 2 caught that the brief made `Assertion.intake_id` required-at-domain-level but provided no intake path for `create_data_point` (the INITIAL-assertion creator) — the universal claim could not hold. D128 was rescoped to "every persisted state change at the platform's write surfaces," and a third orchestration (`record_intake_and_create_data_point`) plus a POST `/api/v1/data_points` route closed the gap.

The pattern: a D-entry asserting a platform-wide architectural posture needs explicit enumeration against all currently-implemented write surfaces before its prose drafts. A universal-quantifier claim ("every ...") in a D-entry is a hypothesis to verify against the surface inventory, not a settled fact. First-instance candidate.

  - triaged: defer on 2026-05-22
  - resolution: forwarded to `charter/methodology.md` promotion candidacy. Recorded at the S44b session-log methodology lines.

## 2026-05-22 — [S44b] Adapter-level transaction-semantics verification before commitment (methodology candidate)

The S44b brief asserted the orchestration's two writes (intake, then portfolio) happen "within a single database transaction" that "rolls back both" on downstream failure. Pre-write reconciliation Finding 3 caught that the current adapter shape — each adapter method opens its own `session.begin()` — cannot provide a shared transaction without a unit-of-work refactor. D128 was rewritten to two-transaction intake-first ordering, with the orphaned-intake-on-failure framed as the honest canonical record-of-attempt.

The pattern: a structural claim about transaction semantics, atomicity, or unit-of-work boundaries needs adapter-level capability verification at pre-write reconciliation before a D-entry commits the claim. Transaction-boundary assertions are constrained by what the adapter layer can actually provide. First-instance candidate.

  - triaged: defer on 2026-05-22
  - resolution: forwarded to `charter/methodology.md` promotion candidacy. The unit-of-work refactor (a genuine shared cross-context transaction) is forwarded to `charter/phase-2-audit-inputs.md` for Phase 2-A close consideration. Recorded at the S44b session-log methodology lines.

## 2026-05-22 — [S44b] Distinct-architectural-concern, not instance count, triggers a new bounded context (note)

D127 alternative (d) originally framed "a third orchestration" as the activation trigger for a `contexts/orchestration/` bounded context. S44b's Finding-2 resolution landed a third orchestration (`record_intake_and_create_data_point`); the disposition clarified that three orchestrations of the same pattern — intake-canonical for a downstream-context write, dual-decorator, intake-then-write structure, intake_id propagation — constitute one architectural concern, not three. They stay at `contexts/intake/application/`.

The forward discipline: a new bounded context is triggered by a *distinct architectural concern*, not by instance count. The `contexts/orchestration/` trigger is an orchestration concern that cannot be characterised as intake-canonical-for-downstream-write — e.g. a multi-step saga, or branching orchestration across three-plus contexts. Future intake-then-methodology or intake-then-calendar orchestrations remain the same pattern and stay at `contexts/intake/`.

  - triaged: note on 2026-05-22
  - resolution: recorded as a forward-looking discipline note; the clarification is captured in D127 alternative (d)'s landed prose. No separate methodology-document promotion sought — a refinement of an existing trigger, not a recurring build pattern.

## 2026-05-22 — [pre-S45 principles assessment] Code-altitude assessment surfaces findings charter-altitude inference structurally cannot (methodology candidate)

The pre-S45 software-engineering-principles assessment was the first code-altitude principle audit the project has run. It surfaced three classes of finding that no charter-altitude reading would have produced. First, structural facts absent from every charter document: `apps/cli/_cross_context.py` at 1704 lines is the single largest file in the codebase, appears in no charter document and on no hygiene list, and was invisible because no recent session touched it heavily — the brief's own SRP watch-points (drawn from session-log findings) named the second- and third-largest composition files but not the largest. Second, code-level patterns no D-entry describes: the `if "tenant" in str(exc)` exception-message-sniffing repeated ten times across three routers, and the audit-event-draft inline-versus-helper drift between two sibling contexts written one session apart. Third, places the charter *overstates* — three charter surfaces (D114, D125, `architecture.md:274`, `schema.md`) assert a Revisable contract-test harness at `tests/contract/revisable/` that does not exist.

The observation: charter-altitude auditing verifies decisions against their stated intent and catches drift between charter prose and D-entry ground truth; it cannot catch what was never written down. A code-altitude pass reads the artefact directly and finds both un-charted structure and charter overclaim. The two audit altitudes are complementary, not redundant. First-instance observation; recurrence test is the next code-altitude assessment (a Phase 2 close principles re-run or an equivalent).

  - triaged: defer on 2026-05-22
  - resolution: forwarded to the post-assessment disposition conversation and to `charter/methodology.md` promotion candidacy. First instance; recurrence test named. Recorded at the pre-S45 session-log methodology line.

## 2026-05-22 — [pre-S45 principles assessment] Per-principle audit structure forces artificial separation of cross-principle findings (methodology candidate)

The brief structured the assessment one section per principle (KISS, DRY, SOLID×5, YAGNI, TDA), each with methodology / metrics / findings / severity / actions. The structure worked for principle-local findings but forced roughly four genuinely cross-principle findings to be split and cross-referenced rather than stated once: the cursor-codec duplication is DRY and KISS; the 800-line composition files are SRP and the file-topology-budget methodology; the inert forward-compat affordances are KISS and YAGNI; the use-case ActorContext-unpack is DRY, KISS, and TDA. The findings synthesis section's "cross-principle pattern findings" sub-section partly recovered the loss, but only after each fragment had already been stated under its principle.

The observation: a principle is a lens, not a partition; real findings frequently refract through several lenses. A future principle audit may be better served by a finding-first structure (enumerate findings, tag each with the principles it touches) with the per-principle sections as an index, or by drafting the cross-principle synthesis first and decomposing into per-principle evidence second. The per-principle structure is not wrong — it makes the methodology paragraphs and metrics clean — but it should not be the unit of finding-discovery. First-instance observation.

  - triaged: defer on 2026-05-22
  - resolution: forwarded to the post-assessment disposition conversation as input to any future principle-audit brief structure. First instance; recurrence test is the next principle audit. Recorded at the pre-S45 session-log methodology line.

## 2026-05-22 — [pre-S45 principles assessment] Metrics-versus-judgement balance is uneven across the seven principles (methodology candidate)

The assessment's quantitative metrics were load-bearing for three principles and thin-to-noise for the other four. KISS and SRP rested squarely on numbers — the cyclomatic-complexity distribution (82 of 87 Phase 2-A functions at CC ≤ 5) *is* the KISS verdict, and the file-size distribution *is* the SRP verdict. DIP rested on the import-linter run (29/29) plus a vendor-import scan. For DRY, OCP, LSP, ISP, YAGNI, and TDA the metrics were either weak proxies (a port's method count does not by itself decide ISP) or had to be constructed by hand (counting `.role_list` readers, diffing seven cursor files), and the actual finding came from structural judgement. Manufacturing a metric where the principle resists quantification (an "OCP score") would have produced noise that obscured the judgement.

The observation for future principle audits: state up front which principles a given codebase shape can be measured against and which require judgement with cited evidence, rather than imposing a uniform metrics-then-findings template on all seven. The honest shape is metrics-where-they-decide, judgement-with-evidence-where-they-do-not. First-instance observation.

  - triaged: defer on 2026-05-22
  - resolution: forwarded to the post-assessment disposition conversation as input to future principle-audit brief structure. Pairs with the per-principle-structure candidate above. Recorded at the pre-S45 session-log methodology line.

## 2026-05-22 — [S45] Forward strategic block — UX convergence session

Three architectural concerns interact at the user-experience surface and need cross-cutting design before P14's ConversationFlow implementers land:

1. **Multi-channel UX.** Channel routing, identity reconciliation across per-channel identities, channel preference resolution for outbound, cross-channel session continuity, channel-aware affordances. Captured as the multi-channel UX architectural readiness entry at `charter/deferred-decisions.md` (P13 S45 deferrals section).

2. **Provenance-aware response composition.** D131 landed the architectural posture at S45 — responses cite the source artefacts (IntakeRecords, audit events, retrieved results) that contributed. The read-side counterpart to D128's intake-canonical write-side commitment. No Phase 2-A surface implements it; first implementation at P14.

3. **Confidence-aware response composition.** How response confidence is computed from artefact-and-revision evidence (the D118 two-vector decay model and the D117 tiered-by-salience primitive both feed this), how confidence is rendered to the user, and how it drives channel routing and consent-tier decisions. Not yet committed at any D-entry.

The three are separable as substrate (S45 built the messaging substrate channel-agnostically; D131 committed provenance; D130 carries the structured-output primitive that all three render through) but entangled as *UX design*: a response's confidence shapes which channel it goes to and how its provenance is surfaced. Designing them one at a time at P14/P15 risks three incompatible UX shapes.

**Forward strategic block.** A UX convergence strategic-mode session sitting between S46 close and P14 epic framing. It produces UX architectural commitments combining multi-channel UX, provenance-aware response composition, and confidence-aware response composition into one coherent design — captured as `charter/architecture.md` prose plus possible new D-entries plus possible `charter/principles.md` additions. Its outputs feed P14 epic framing as inherited UX constraints.

  - triaged: defer on 2026-05-22
  - resolution: forward strategic block named; activation trigger is the S46 close marker. Sits between S46 close and P14 epic framing. Not a build session — a strategic-mode conversation producing charter artefacts. Recorded at the S45 charter commit and the S45 session-log entry.

## 2026-05-22 — [S46] D131 first-instance exercise plus structural-enforcement deferral

S46's manual entry cell is the first D131 implementer per the citation-shaped response composition discipline. The citation fields (`cited_intake_records`, `cited_audit_events`, `cited_artefacts`) live on the cell's `CellResponse` value object directly rather than at a shared_kernel base type or Protocol.

**Convention-versus-structural-enforcement gap.** The discipline depends on each ConversationFlow implementer honouring D131's commitment by convention at Phase 2-A; structural enforcement via a shared_kernel `CitedResponse` base or Protocol defers to the second-instance trigger (P14 ConversationFlow implementers at audit-conversation and mirror-conversation surface the second instance). The Phase 3 close audit verifies that all D131-bearing implementers carried citation fields. If the second-instance trigger at P14 fires with multiple implementers landing simultaneously rather than sequentially, the shared_kernel base type emerges at P14 framing rather than at a subsequent session.

**Empty-field-at-first-instance gap.** S46's cell cites `cited_intake_records` and `cited_artefacts` from in-scope IDs (the IntakeRecord id and the Case / DataPoint id the orchestration returns); `cited_audit_events` stays empty because the intake-owned write-result DTOs (`CaseWriteResult`, `DataPointWriteResult`) do not currently surface `audit_event_id`s. Extending three intake-owned DTOs plus their underlying use cases to carry audit-event IDs is out of proportion for the first-instance exercise. The convention-versus-structural-enforcement gap at D131's first instance therefore includes this empty-field gap. The future implementer at P14+ either extends the write-result DTOs to surface audit IDs, or accepts that `cited_audit_events` is an aspirational citation field where `cited_intake_records` plus `cited_artefacts` cover the audit surface in practice (each cited IntakeRecord transitively anchors its own audit-chain entries).

  - triaged: defer on 2026-05-22
  - resolution: forwarded to the Phase 3 close audit for D131-implementer citation-field verification, and to the P14 ConversationFlow-implementer framing for the shared_kernel `CitedResponse` base-type second-instance decision. Recorded at the S46 charter commit and the S46 session-log entry.

## 2026-05-22 — [S46 smoke] Webhook synchronous-cell-run-vs-Twilio-timeout finding

The S46 smoke surfaced that the manual entry cell at `apps/api/routers/messaging.py` runs the cell synchronously inside the Twilio webhook request — including the structured-output LLM call — before returning the webhook response. With `qwen2.5:7b` at REAL_TIME_REQUIRED tier the LLM call latency varies sharply with model warm-state: cold-start runs measured 18–23s (stage 1 at 22.95s, stage 8a at 21.12s, round-2 rephrase 1 at 18.62s, stage 8e-i at 20.97s); warm runs measured 8–9s (round-2 rephrase 2 at 9.07s, round-2 rephrase 3 at 8.05s). Ollama unloads the model after ~5 minutes of inactivity (default keep-alive), so the next message after an idle gap pays the cold-start cost. Twilio's webhook timeout is approximately 15 seconds; cold cascades exceed it (ngrok recorded `status 0` on every cold run), warm cascades complete within it (ngrok `200`). The webhook completes server-side regardless — the outbound reply delivered out-of-band via the separate Twilio REST API call in all cases (Twilio status `read` confirmed at stages 1 and 8e-i).

**Root finding is on webhook-contract grounds, not retry-duplication grounds.** A 23s synchronous handler ties up a server worker for the full duration, writes its response to an already-closed connection, and permanently disconnects the webhook's success signal from the cell's actual outcome. Even at warm 8–9s the synchronous shape is wrong on contract grounds — returning 2xx promptly is the webhook contract. The S46 smoke produced direct empirical evidence on the retry-duplication consequence: across nine cascades (some over the timeout, some under), **no Twilio retry fired** (intakes incremented exactly once per cascade) and **no `11200` retrieval-failure alert landed in the Twilio Monitor** (the Monitor carried only the stale S45-era `12300` invalid-Content-Type alert). This is consistent with Twilio not retrying incoming-message webhooks (unlike status callbacks), but one smoke run is not proof.

**Architectural fix: webhook returns 2xx immediately and dispatches cell run to a background task.** Path A (in-process asyncio task via `asyncio.create_task` or FastAPI `BackgroundTasks`) is the proportionate Phase 2-A shape; Path B (out-of-process task queue) defers to Phase 2-B+ scaling. Path A's trade-off (cell run interrupted by container restart is lost) is acceptable for operator dogfooding; Phase 2-B+ migration to Path B is the right path when customer-volume deployments arrive.

**Paired scope condition on the future build session.** The cell run is currently wrapped in a bare `except Exception: pass` at `apps/api/routers/messaging.py:267`. Moving it to a background task makes silent failure strictly worse (no reply *and* no signal); the Path A change must simultaneously add cell-failure logging at minimum.

  - triaged: defer on 2026-05-22
  - resolution: forwarded to a future build session for the Path A implementation (in-process asyncio dispatch + cell-failure logging). Phase 2-A operator dogfooding accepts the current shape as adequate-for-now (warm latency stays under 15s; cold-start timeout has not produced retry duplication in the observed smoke). Sits between this smoke close and the convergence session; the convergence session may surface related concerns (the latency-versus-channel-routing interaction; the operator-feedback-loop discipline that out-of-band reply hints at). Recorded at the S46 smoke close.

## 2026-05-22 — [S46 smoke] Intent-extraction reliability at REAL_TIME_REQUIRED with qwen2.5:7b finding

The S46 smoke surfaced that `qwen2.5:7b` at the REAL_TIME_REQUIRED latency tier reliably classifies CreateCaseIntent (2/2 successful: stage 1 "Start a case for the Q3 portfolio review." → Case `fa6401b0`; stage 8e-i "Start a case for the Q3 budget review." → Case `4fac3ae0`, including correct disambiguation from the now-similar-named existing case) but cannot reliably classify AddDataPointIntent (0/7 successful classifications across 4 distinct phrasings):

1. Stage 8a original — "Add a goal to the Q3 review: ship Wave 1 by end of May" → UnclearIntent
2. Rephrasing 1 (verb-first with full title) — "Add this goal to the Q3 portfolio review: ship Wave 1 by end of May." → UnclearIntent (2 runs at ~22:07 and ~22:20)
3. Rephrasing 2 (target front-loaded) — "For the Q3 portfolio review case, add a goal: ship Wave 1 by end of May." → UnclearIntent (2 runs)
4. Rephrasing 3 (no-verb noun-phrase opener) — "Goal for Q3 portfolio review — ship Wave 1 by end of May." → UnclearIntent (2 runs)

All seven runs produced byte-identical UnclearIntent clarification replies ("I could not tell what you would like me to do…"). The four phrasings exercised distinct surface-cue patterns (verb-explicit, target-first, no-verb-noun-phrase, simpler form); none classified. The cell's behaviour is contract-correct throughout (UnclearIntent triggers clarification, no portfolio write occurred, no citation line on the reply per D131); the failure is upstream at the model's classification accuracy across the discriminated union's four variants.

**The framing-time assumption that REAL_TIME_REQUIRED + 7B model classifies reliably across the four-variant intent union is empirically wrong.** Classification reliability varies by intent class: CreateCaseIntent works; AddDataPointIntent does not. The framing-time discriminated-union shape (CreateCase, AddDataPoint, ReviseDataPoint, UnclearIntent) settled at S46 Item 2 was correct architecturally but unverified against model-tier-classifier-capability mapping. ReviseDataPointIntent and the no-match / ambiguous resolution paths were never reachable in this smoke because they all gate on AddDataPoint-class classification first.

**Architectural implications for the convergence session — three non-exclusive responses.**

- **Response A: Raise the REAL_TIME_REQUIRED tier model.** Larger model (qwen2.5:14b/32b, or hosted Anthropic/OpenAI model) with better classification accuracy across discriminated unions. The current latency budget is constrained by the synchronous-webhook shape, but the paired webhook-contract finding already requires moving to background-task dispatch, which loosens the latency budget; larger models become viable.
- **Response B: Constrain the classification surface or expand the prompt.** Reduce the discriminated union to fewer classes, or expand the classification prompt with few-shot examples. May improve 7B accuracy at the cost of prompt size and inference token cost.
- **Response C: Render model uncertainty as user-facing clarification more honestly.** The current binary classified-vs-UnclearIntent gate collapses two distinct cases ("I think this is AddDataPoint with 0.6 confidence" vs "I'm not sure what intent this is at 0.4 confidence") into the same clarification ("I could not tell what you would like me to do"). A confidence-aware composition could surface the model's actual uncertainty ("I think you want to add a goal but I'm not sure; is that right?").

The three responses are not mutually exclusive. The convergence session's confidence-aware response composition framing has to address all three.

**Phase 2-A operator-dogfooding-via-WhatsApp viability question.** If a 7B model at REAL_TIME_REQUIRED cannot reliably classify standard manual-entry intents, operator dogfooding hits friction at exactly the path the bet rests on: messaging-first delivery to senior leaders who type natural language into WhatsApp. This finding is first-class convergence-session input rather than mid-stream optimisation.

**Instrumentation gap obscures one architectural distinction.** The Langfuse trace captures the D122/D132 dimensions and token counts but does not capture prompt content or model output. The smoke cannot distinguish whether `qwen2.5:7b` returned clean UnclearIntent JSON (the model knows it doesn't know) or whether `parse_intent` coerced malformed output to UnclearIntent (the model produced something Padhanam can't parse). The two cases have different architectural implications for confidence-aware composition: the first suggests model self-assessment is reliable and the convergence framing can lean on it; the second suggests parse-safety-net is doing the load-bearing work and the convergence framing must handle "model produces unparseable output" as a distinct case. Future observability work behind a debug flag could enable prompt/output capture for this kind of post-hoc analysis (privacy considerations apply; not for production).

  - triaged: defer on 2026-05-22
  - resolution: first-class convergence-session input. Forwarded to the UX convergence session (named at the 2026-05-22 [S45] capture for the forward strategic block; activation trigger is the S46 close marker). The instrumentation-gap sub-finding also flagged for Phase 2-A close hygiene or a dedicated observability session to enable prompt/output capture behind a debug flag. Recorded at the S46 smoke close.

## 2026-05-25 — [S47 / UX convergence] Interface-versus-implementation framing drift (methodology candidate, promotion-ready)

The UX convergence session between S46 smoke close and S47 framing produced four instances across one conversation of architectural framing committing an implementation when the commitment should be the interface. First instance: the dispatch-shape framing for the webhook contract fix initially named "Path A in-process now, Path B out-of-process at the customer-volume trigger" as two implementations in sequence; operator question pulled the framing back to the CellDispatch port at D133 with Path A and Path B as adapters behind the port. Second instance (related but distinct shape): the "routing resolves at the adapter" framing for the gateway was vague about what routing covered; operator question forced specificity to the runtime model-choice question. Third instance: the runtime-model-resolution architecture for the gateway was committed as a substrate-depth investment without business-context justification (hosted providers already perform within-provider optimization at scales the architecture cannot beat; operator dogfooding does not exercise the substrate); operator question pulled the framing back to static-configuration-at-Phase-2-A with the gateway-as-resolution-point shape preserved for Phase 3+ business-model activation. Fourth instance: "self-reported confidence as the Phase 2-A signal" was committed as the architectural primitive at concern 3's initial disposition; operator question pulled the framing back to the ConfidenceCalculator port at D134 with self-reported confidence as the placeholder adapter behind the port.

The pattern: at architectural altitude, drafting tends to commit implementations rather than interfaces. The implementation may be the right Phase 2-A choice, but the architectural commitment should be the interface (the shape future implementations conform to), not the specific implementation that may need to change. The framing-time check is the interface-versus-implementation question: am I committing the shape future implementations conform to, or am I committing one specific implementation that should sit behind a port?

Four-instance evidence across one conversation. Promotion-threshold material at the convergence close.

  - triaged: 2026-05-25 — promotion-ready
  - resolution: forward to `charter/methodology.md` for the interface-versus-implementation discipline addition at the post-S47 hygiene session. The discipline addition is an explicit pre-write reconciliation surface at framing time: any new architectural commitment language is checked against the question "am I committing the interface or the implementation?" before the D-entry prose drafts. The convergence's pre-write reconciliation surface 9 at S47 framing is the first instance of the discipline in action; it caught at draft time rather than at operator review. Recorded at the S47 session-log methodology line. The earlier captures entries from the convergence at "[S45] Forward strategic block — UX convergence session" and the related captures from 2026-05-22 close at this promotion.
