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

## 2026-05-25 — [S47 / UX convergence] Interface-versus-implementation framing drift (methodology candidate, promotion-ready, five-instance evidence plus pattern-density observation)

The UX convergence session between S46 smoke close and S47 framing produced five instances across one convergence-plus-prompt-drafting arc of architectural framing committing an implementation when the commitment should be the interface.

First instance (concern 4 conversation). The dispatch-shape framing for the webhook contract fix initially named "Path A in-process now, Path B out-of-process at the customer-volume trigger" as two implementations in sequence; operator question pulled the framing back to the CellDispatch port at D133 with Path A and Path B as adapters behind the port.

Second instance (concern 4 conversation, related but distinct shape). The "routing resolves at the adapter" framing for the gateway was vague about what routing covered; operator question forced specificity to the runtime model-choice question.

Third instance (concern 4 conversation). The runtime-model-resolution architecture for the gateway was committed as a substrate-depth investment without business-context justification (hosted providers already perform within-provider optimization at scales the architecture cannot beat; operator dogfooding does not exercise the substrate); operator question pulled the framing back to static-configuration-at-Phase-2-A with the gateway-as-resolution-point shape preserved for Phase 3+ business-model activation.

Fourth instance (concern 3 conversation). "Self-reported confidence as the Phase 2-A signal" was committed as the architectural primitive at concern 3's initial disposition; operator question pulled the framing back to the ConfidenceCalculator port at D134 with self-reported confidence as the placeholder adapter behind the port.

Fifth instance (post-prompt-draft review). The confidence-threshold values 0.8 and 0.5 were committed in D134's prose as configuration in `padhanam/config/messaging.py` without specifying the cell's consumption path; operator question pulled the framing to the ThresholdResolver port with the single-pair adapter as the Phase 2-A implementation behind it. The fifth instance surfaced at the session-prompt-draft review surface — a post-strategic-mode-close verification surface — rather than at the convergence conversation itself.

The pattern: at architectural altitude, drafting tends to commit implementations rather than interfaces. The implementation may be the right Phase 2-A choice, but the architectural commitment should be the interface (the shape future implementations conform to), not the specific implementation that may need to change. The framing-time check is the interface-versus-implementation question: am I committing the shape future implementations conform to, or am I committing one specific implementation that should sit behind a port?

Five-instance evidence across one convergence-plus-prompt-drafting arc is unusually dense. The pattern-density observation: either the strategic-mode architectural altitude inherently tends toward implementation-versus-interface drift more than build-mode work does (in which case the framing-time check is appropriately weighted as a standing pre-write reconciliation surface at every strategic-mode session), or this particular convergence's shape produced the density (in which case the lesson is about strategic-mode conversation discipline rather than a structural drift). The captures entry names this as a forward observation rather than committing to either reading.

Promotion-threshold material at the convergence close; recurrence test at the next strategic-mode session (P14 framing or a future phase-audit session) will distinguish the two readings.

  - triaged: 2026-05-25 — promotion-ready with five-instance evidence
  - resolution: forward to `charter/methodology.md` for the interface-versus-implementation discipline addition at the post-S47 hygiene session. The discipline addition is an explicit pre-write reconciliation surface at framing time and at prompt-drafting time: any new architectural commitment language is checked against the question "am I committing the interface or the implementation?" before the D-entry prose drafts; any session prompt's commit-shape descriptions are checked against the same question before the prompt commits. The convergence's pre-write reconciliation surface 9 at S47 framing is the first instance of the discipline in action at framing time; the post-prompt-draft fifth-instance catch is the discipline's first instance of activation at the prompt-draft surface. The pattern-density observation forwards to the next strategic-mode session for the recurrence test. The earlier captures entries from the convergence at "[S45] Forward strategic block — UX convergence session" and the related captures from 2026-05-22 close at this promotion.
  - resolution (S49, 2026-05-26): PROMOTED to `charter/methodology.md` at S49 with seven-instance evidence across three surfaces (convergence-conversation; strategic-mode framing; prompt-draft-time anticipation). The pattern-density observation closes at seven instances: strategic-mode altitude predictably produces the drift, and the discipline binds at the prompt-drafting surface when explicitly named as a reconciliation surface. Forward-relevance bound at the methodology entry. The captures entries that contributed instances stay here for audit-trail integrity; subsequent instances accumulate at this entry's recurrence log if the methodology promotion's forward-relevance discipline does not fully close the recurrence.

## 2026-05-26 — [S47 smoke] qwen2.5:14b operator-dogfooding viability on commodity hardware

S47 commit 6 bumped the REAL_TIME_REQUIRED tier model pin to qwen2.5:14b per D133/D134 Response A (addressing the S46 smoke's intent-extraction reliability finding at qwen2.5:7b). The S47 live-stack smoke against tenant_a executed the bump and surfaced a hardware-viability gap: 14b's warm-call latency on the cell's intent-extraction prompt (system prompt + JSON schema + user message) showed progressive slowdown across calls: **28s → 48s → 67s → 361s**. The 361s call eventually got captured by the dispatch-port's failure-logging at LiteLLM's tier timeout (bumped to 120s for the smoke); ollama kept processing for the full 6 minutes before unloading the model.

The progressive slowdown signature (each call slower than the last) suggests memory pressure / cache thrashing at the 9.7 GB resident model on this machine (16 GB RAM total). The cold-load disk→memory cost alone is ~107 seconds. Phase 2-A operator dogfooding requires response latencies in the 10-30 second range to feel responsive at the WhatsApp surface; 6-minute latencies make the cell non-viable.

**The S47 substrate is unaffected by the finding.** The dispatch port, ThresholdResolver, PendingClarification lifecycle with FK integrity, multi-turn cascade, D131 rendering, and pattern-2 binding all validated end-to-end against tenant_a (smoke doc at `docs/smoke/p13_s47_multi_turn_cell_end_to_end.md`). What does not validate is the **D133 Response A disposition**: static-configuration-at-Phase-2-A bumping to qwen2.5:14b does not close the S46 smoke's reliability finding when the larger model can't run in operator latency budgets.

The convergence's three responses (A raise tier model; B constrain classification surface or expand the prompt; C render uncertainty more honestly) are not exclusive. Response C (the confidence-aware composition primitive at D134) is fully landed at S47 and operating correctly — even at the 14b pin, the cell at *medium-confidence* classification renders shape-aware clarification rather than acting confidently on an uncertain guess. The S46 binary-gate failure mode is closed structurally by D134 regardless of which model the gateway routes to.

**Architectural implication for the next strategic-mode session.** Three forward paths to consider, none in scope at S47 smoke close:

1. **Hosted REAL_TIME_REQUIRED model.** The InferenceSettings env override (`REAL_TIME_REQUIRED_MODEL=gpt-4o-mini` or `claude-haiku-4-5`) is already a supported override; the LiteLLM gateway needs the corresponding `model_list` entry. This is configuration plus secret management, not code. Operator dogfooding cost shifts from "lots of local memory" to "per-call cents" — typically <$0.001 per intent classification.

2. **Tier-timeout per-model overrides.** The compose-level env passthrough lets the operator tune the tier budget; the InferenceSettings field stays a single tier-wide value. A per-model override surface (e.g. `MODEL_TIMEOUT_QWEN2_5_14B=240`) defers to the next session if needed.

3. **Constrain Response B (classification surface).** The intent-extraction schema includes four variants (CreateCase, AddDataPoint, ReviseDataPoint, UnclearIntent). Reducing to a binary (CreateCase vs other) plus a follow-up clarification turn for non-CreateCase classes simplifies the model's discriminative task. Larger structural change; defers unless Response A's hosted-inference path doesn't close the reliability gap either.

  - triaged: 2026-05-26 — defer
  - resolution (initial): captured for the next strategic-mode session covering inference-model selection or the post-S47 hygiene session. The two structural fixes the smoke surfaced (model-registry-vs-LiteLLM-gateway-routing drift; the FK-integrity threading on the cell's originating_intake_id) landed at commit d63f8a5 at the smoke close. The hardware-viability finding stays as forward observation; no charter change at the S47 smoke close, only this captures entry. The S46 smoke's intent-extraction reliability captures entry (2026-05-22 [S46 smoke]) names Response A/B/C; this captures entry forwards the Response-A-on-this-hardware viability question without superseding the original entry.
  - resolution (S48a close, 2026-05-26): **resolved via swap to `gpt-4o-mini`** per D133's gateway-as-resolution-point shape at S48a commit 1 (`feat(p13/s48a): swap REAL_TIME_REQUIRED tier pin to gpt-4o-mini`, d620692). The S48a live smoke against tenant_a verified `gpt-4o-mini` classifies AddDataPointIntent correctly 4/4 across all four phrasing variants at 1.5-3 s warm latency — comfortably dogfooding-viable. `qwen2.5:14b` is retained in the model registry and gateway model_list as the local-development fallback when hosted-model credentials are unavailable; operators without an OpenAI key can return to the prior pin via `INFERENCE_REAL_TIME_REQUIRED_MODEL=qwen2.5:14b`. Smoke evidence at `docs/smoke/p13_s47_multi_turn_cell_end_to_end.md` under the "S48a re-execution at `gpt-4o-mini`" section. Convergence concern 5 (intent-extraction reliability) closes operationally.

## 2026-05-26 — [S47 smoke] model-registry-vs-LiteLLM-gateway-routing drift class (methodology candidate)

S47 commit 6 seeded qwen2.5:14b in `padhanam/config/model_registry.py` (D133's audit-and-future-policy substrate) but did not update `ops/litellm/config.yaml`'s `model_list` in parallel. The smoke surfaced the gap on the first cell invocation: `litellm.BadRequestError: OpenAIException - /chat/completions: Invalid model name passed in model=qwen2.5:14b`. The model-registry seed is structurally separate from the gateway routing surface; they need to stay in sync but no test enforces the invariant.

The two surfaces have different semantic roles:
- `padhanam/config/model_registry.py` — the audit-and-future-policy catalogue per D133 (provider, account, version, supported operations, latency category, cost-per-call). Phase 2-A consumes this for audit-trail dimension capture per D132; Phase 3+ cost-aware routing policies consume it for routing decisions.
- `ops/litellm/config.yaml` `model_list` — the LiteLLM gateway's accepted model names and their backend bindings. The gateway rejects calls to any model not listed.

A model must appear in both for the audit substrate and the routing surface to work together. The fix at commit d63f8a5 added the qwen2.5:14b entry to the gateway config; the underlying drift class remains structurally unprotected.

**Forward fix candidate.** A structural test that loads `MODEL_REGISTRY` from `padhanam/config/model_registry.py` and asserts each entry's `model` value appears in the parsed `ops/litellm/config.yaml` `model_list`. Modest test: a single pytest function that parses both files and computes set intersection. Lives at `tests/contract/inference/test_model_registry_gateway_sync.py` or similar.

  - triaged: 2026-05-26 — defer
  - resolution: forwarded to the post-S47 hygiene session for the structural-test addition. The fix at d63f8a5 closes the operational symptom; the structural test closes the drift class. Recorded at the S47 smoke session-log entry. Future model additions to either surface should land in both at the same commit; the test makes that discipline mechanical rather than convention.

## 2026-05-26 — [S48a smoke] resolver disambiguation rendering on duplicate-title case collision

The S48a smoke surfaced a substrate gap at the `resolve_target` step inside the `add_data_point` orchestration. When the cell classifies an AddDataPointIntent with `case_reference="Q3 portfolio review"` and the resolver finds multiple cases with that title, the rendering uses only the `title` field as the discriminator, producing identical strings in the disambiguation prompt:

> More than one case matches "Q3 portfolio review" — did you mean one of: Q3 portfolio review, Q3 portfolio review, Q3 portfolio review?

Three cases titled `Q3 portfolio review` exist in tenant_a (one each from S46, S47, S48a smoke runs); a user cannot choose between them given the rendering.

**Design direction (operator-aligned, not yet committed).** The disambiguation prompt should:
- Use conversational discriminators (created_at relative date when recent, absolute date when older, last-activity, count of associated data-point/assertions), not UUIDs.
- Include an explicit `Or start a new one?` option because that is the user's de-facto choice when the existing matches don't match the user's mental case.
- Bind the user's choice (number, relative date phrase) at a follow-up turn that resolves to the actual case UUID.

**Related design thread — detect-at-creation discipline (out of scope at S48a; P14 candidate).** When the cell classifies a `create_case` intent and the resolver finds an existing case with the same title, the cell should ask before minting a new one: `You already have a case 'Q3 portfolio review' from May 22 — start a new one or add to that?`. Same shape as the disambiguation prompt above; this is what would have prevented S46/S47/S48a from each minting a duplicate. The downstream merge/archive thread (the "what to do with the existing duplicates" question) needs user-driven action only — platform invariant 4 (no auto-modification of user-authored content) forbids platform-initiated merges or archival.

  - triaged: 2026-05-26 — defer
  - resolution: forwarded to P14 epic framing or a pre-P14 substrate-hygiene session. The disambiguation rendering is small (cell-side rendering change) and could land as a pre-P14 hygiene workitem. The detect-at-creation discipline is larger (cross-context cell logic plus orchestration ordering plus audit-event shape) and naturally belongs in P14's ConversationFlow implementer expansion. The user-driven merge/archive thread defers further until operator-dogfooding signal makes the missing affordance bite.

## 2026-05-26 — [S48a smoke] cancel-then-fresh-turn double-cost behaviour

When the cell receives a `no`/`cancel` reply to an active PendingClarification, the deterministic cancel-keyword detection fires and resolves the pending in ~10-20 ms with no LLM call. The cell then falls through to fresh-turn handling on the same `no` inbound, which runs the bare token through `gpt-4o-mini` fresh-turn classification (UnclearIntent / low-confidence) and renders a Case 3 generic clarification (`Could you please clarify what you mean by 'no'?` or similar). The fall-through always pays the cost of a second LLM call (~$0.0001, ~3.8 s of latency).

The behaviour is structurally correct per the S47 reflection prompt 5 description (the cell falls through to fresh-turn handling on the correcting inbound) and is friendlier than silent cancellation. But at scale (operator dogfooding for years) the wasted classification cost accumulates.

**Three design alternatives.**
- (a) Accept as-is. Friendlier than silent; LLM cost negligible at dogfooding volume.
- (b) Deterministic cancel acknowledgment. Render `Cancelled. What did you want instead?` without an LLM call. Saves cost and latency but loses any nuance.
- (c) Silent cancel. Render nothing; user sends a fresh turn at their leisure. Saves cost; may feel unresponsive.

  - triaged: 2026-05-26 — note
  - resolution: captured for forward consideration. Not load-bearing at S48a; the operator-dogfooding latency budget tolerates the extra 3.8 s comfortably. Revisit if dogfooding signal indicates the cancel-acknowledgment shape feels off.

## 2026-05-26 — [S48a smoke] auto-expire-prior-pending-on-substantive-new-content (positive substrate observation)

The cell's `next-inbound` handling against an active PendingClarification has three branches: yes/confirm → resolve as confirmed and orchestrate; no/cancel → resolve as cancelled and fresh-turn classify the no; anything else substantive → **expire the prior pending and fresh-turn classify the new content** (potentially creating a new pending if medium confidence).

Surfaced live when the operator sent phrasing 4 with phrasing-3's pending still active. The cell expired `912a7235-…` (phrasing 3) at 10:17:23.925 UTC and created a fresh `74d4210b-…` (phrasing 4) at 10:17:23.928 UTC, all in one cascade. Three audit events emitted: `messaging.pending_clarification.expire`, then `messaging.pending_clarification.create` for the new pending, then the outbound clarification message.

The behaviour matches the user's natural pattern "actually, I meant something else" without requiring the user to explicitly cancel first. The substrate's three-branch handling means the user is never trapped by an in-flight pending; sending any substantive content moves the conversation forward. The audit chain captures the expire+create transition clearly for procurement-grade audit.

  - triaged: 2026-05-26 — note
  - resolution: positive substrate observation; no action required. Recorded for the smoke document and as a structural property of the cell worth surfacing at the P14 ConversationFlow implementer framing — future implementers should preserve this three-branch handling.

## 2026-05-26 — [S48b] Component-quality evaluation distinct from integration smoke (methodology candidate, promotion-ready, two-instance evidence)

Two integration-smoke arcs (S46 and S47) surfaced component-quality findings (intent-classification reliability at qwen2.5:7b; operational latency viability at qwen2.5:14b) from a methodology not built to answer them. Integration smokes verify integration (does the full multi-turn cascade hold; does the audit chain integrity hold; does the channel rendering work end-to-end); component-quality questions (does model X classify reliably; does retrieval strategy Y outperform Z; does prompt P produce schema-conforming output reliably) need dedicated evaluation surfaces that exercise the component in isolation.

The architecture's port-and-adapter shape exists specifically to make component testing possible in isolation. The structured-output port at D130 plus the model registry at D133 plus the four-layer model ontology at D132 together support a dedicated intent-classification evaluation substrate. Building it (D137 at S48b) closes the methodology gap by providing the right surface for the component-quality question; the integration smokes stop carrying load they were not built for.

Two-instance evidence:
- S46 smoke surfaced qwen2.5:7b's intent-classification blind-spot for AddDataPointIntent across four phrasings (0/2 of the template phrasing classified correctly). The reliability question was answered by integration smoke evidence, which is slow, expensive, and confounded with substrate quality.
- S47 smoke surfaced qwen2.5:14b's operational unviability via 28s→361s latency progression on commodity hardware. The model-choice question was answered by integration smoke evidence; the model swap to gpt-4o-mini at S48a is configuration but the model-comparison question persists across future swaps.

Methodology line, roughly: "Component-quality questions (model choice, retrieval strategy, structured-output reliability per class, prompt revision) land at dedicated evaluation substrates; integration smokes verify integration. The architecture's port-and-adapter shape supports component-isolated evaluation; the substrate work to land each component-quality evaluation surface is forward methodology work, not architectural rework."

  - triaged: 2026-05-26 — promotion-ready with two-instance evidence
  - resolution: forward to `charter/methodology.md` for the component-quality-versus-integration-smoke discipline addition at the post-S48 hygiene session. The discipline addition names the surfaces (model choice via intent-classification evaluation substrate per D137; retrieval strategy via the P11 retrieval-evaluation substrate per D110; future structured-output reliability per-class via D130-derived evaluation surfaces; future prompt revision via prompt-evaluation substrates as they arise). The first concrete instance at the post-S48 hygiene captures entry is D137 at S48b. Recurrence test at the next component-quality question that arises: does the question land at a dedicated substrate or does it leak back into integration smokes?
  - resolution (S49, 2026-05-26): PROMOTED to `charter/methodology.md` at S49 with two-instance evidence plus first structural implementation (D137 intent-classification evaluation substrate). The S48b substrate is the methodology line's binding mechanism, not just its evidence; future component-quality questions land at their own dedicated substrates following the D137 shape. The captures entry stays here for audit-trail integrity; future component-quality substrates record their activation at this entry's recurrence log.

## 2026-05-26 — [S48b framing] Scope-discipline drift at brief authoring (first instance; methodology candidate)

The S48b brief committed the full P11-mirror as the default scope. Surface 1 reconciliation treated the mirror as precedent rather than testing whether each piece served a current need; the scope question surfaced only when the full file count emerged at the brief-versus-codebase reading.

The pattern is adjacent to but distinct from the interface-versus-implementation discipline already captured. Both default to maximal commitment when the YAGNI test would reject the excess. Interface-versus-implementation is about whether the abstraction commits at the right altitude (interface or implementation); scope-discipline-at-brief-authoring is about whether each piece of work in a brief earns its place against current need.

The reconciliation moment that surfaced the drift: after path conventions and existing context structure were verified, the file count of a full P11-mirror exceeded ~30 files versus a load-bearing-minimum of ~20-25 files. Option B (slim load-bearing version) ships D137 with revision-lifecycle and compare-run-ids explicitly deferred at named activation triggers.

  - triaged: 2026-05-26 — note (first instance; not yet promotion-threshold)
  - resolution: captured for the post-S48 hygiene methodology review. Recurrence test continues at future brief-authoring sessions. Promotion threshold: two further instances per the existing methodology-promotion convention. Pattern family: strategic-mode-drafting drift toward complexity, alongside interface-versus-implementation.

## 2026-05-26 — [S48b] Structural-test single-source-of-truth binding (methodology candidate, second instance)

At the substrate construction commit for `shared_kernel/intent_classification.py`, a structural test binds the single-source-of-truth claim — assert that the cell's import of `INTENT_EXTRACTION_SCHEMA` and the evaluation runner's import of `INTENT_EXTRACTION_SCHEMA` resolve to the same object (Python identity `is`).

The pattern's first instance was the no-numeric-threshold-literals AST test at S47 addendum commit 4f74509 (the ThresholdResolver port substrate); the second instance is the symbol-identity test for the shared-prompt-and-schema primitive at S48b. Both bind a load-bearing architectural claim in CI rather than relying on convention or reviewer attention.

Pattern shape: when a refactor moves a primitive to a shared location to satisfy a substrate-under-test discipline, a structural test asserting all consumers resolve to the shared primitive lands in the same commit. The test's failure mode is exactly the drift the refactor prevented.

  - triaged: 2026-05-26 — note (second instance; promotion candidate at post-S48 hygiene)
  - resolution: forward to `charter/methodology.md` for the structural-test-binding pattern at the post-S48 hygiene session. The pattern's two instances (no-numeric-thresholds at S47 addendum; symbol-identity at S48b) demonstrate the pattern operating at distinct surfaces (AST literal check; runtime import identity). Recurrence at a third instance promotes to methodology document discipline.
  - resolution (S49, 2026-05-26): PROMOTED to `charter/methodology.md` at S49 with two-instance evidence (S47 addendum no-numeric-threshold-literals AST test; S48b symbol-identity test for cell-runner shared prompt). The discipline binds at the commit that lands the architectural commitment. Future architectural commitments evaluate the structural-test-binding question at draft time per the methodology entry's forward-relevance discipline. The two-instance promotion follows the corrective-discipline-on-first-or-second-instance precedent: the structural-test-binding discipline is itself a corrective addition that closes a class of future drift, and the cost of waiting for a third instance pays additional drift.

## 2026-05-26 — [S48b framing] Scope-discipline drift at brief authoring (methodology candidate, first-instance observation, S49 formalization)

The S48b session-prompt brief drafted at Claude.ai strategic-mode defaulted to the full P11-style intent-classification evaluation substrate (nine commits, 30-40 files, multi-hour execution including revision-lifecycle gold sets and cross-run-comparison CLI). Claude Code's pre-write reconciliation surface 1 treated the P11-mirror as precedent; the scope question (does each piece of the P11-mirror serve a current Phase 2-A need) surfaced only when the full file count emerged at brief-versus-codebase reading. The operator confirmed Option B (the slim load-bearing version: seven to eight commits, 20-25 files, single YAML gold-set fixture, no cross-run-comparison CLI). S48b shipped the slim version with the deferred pieces explicitly named in D137's alternatives-considered and the deferred-decisions activation triggers.

This entry formalizes at S49 the observation already captured at the earlier 2026-05-26 [S48b framing] entry (Scope-discipline drift at brief authoring). The S49 formalization adds the connection to the interface-versus-implementation discipline promoted at S49 commit 1: the pattern is distinct from but adjacent to the interface-versus-implementation discipline. Both default to maximal commitment when the YAGNI test would reject the excess, but they operate at different altitudes:

- Interface-versus-implementation operates at architectural-commitment shape (the brief commits a specific implementation when the architecture should commit the interface).
- Scope-discipline-at-brief-authoring operates at implementation-extent shape (the brief commits the full implementation when Phase 2-A only needs the load-bearing minimum).

The two together form a pattern-family of strategic-mode-drafting drift toward complexity: maximal commitment in the architectural-shape direction; maximal commitment in the implementation-extent direction. The interface-versus-implementation discipline binds through the framing-time and prompt-draft-time reconciliation surfaces (per the S49-promoted methodology entry). The scope-discipline-at-brief-authoring observation needs its own reconciliation binding at brief-drafting: test each piece of the proposed scope against the Phase-current YAGNI question before committing the piece to the brief.

First-instance observation. Recurrence test at the next strategic-mode brief-drafting moment that proposes substantive substrate work: does the brief commit only the load-bearing minimum, or does it default to maximal-scope-by-precedent? Concrete test surface: the next P14 ConversationFlow implementer brief or the next post-resolver-disambiguation build session brief.

  - triaged: 2026-05-26 — first-instance formalization at S49 (recurrence test named)
  - resolution: forward to `charter/methodology.md` promotion candidacy at second instance. The brief-drafting reconciliation binding (test each scope piece against Phase-current YAGNI) addresses the gap at the same surface where the interface-versus-implementation discipline binds. The pattern-family observation (alongside interface-versus-implementation as the two strategic-mode-drafting drift-toward-complexity disciplines) anchors the connection for the second-instance promotion conversation. Recorded at the S49 session-log methodology line.

## 2026-05-26 — [S48b reflection 2] Gold-set authoring composes with confidence-aware composition (methodology candidate, first-instance observation, S49 formalization)

The S48b live-stack evaluation produced 39/40 correct classifications at `gpt-4o-mini` against the 40-entry gold set. The single miss was a revise_data_point entry where the operator-shaped input ("The hiring search status changed: offer extended yesterday") is legitimately ambiguous between add_data_point and revise_data_point: the input could indicate a new data point capturing yesterday's status change, or a revision to an existing data point that records the status change. The gold-set entry expected revise_data_point; the model classified add_data_point; both classifications are defensible interpretations of the operator-shaped phrasing.

The structural observation: gold-set authoring discipline at intent-classification altitude needs to acknowledge that some operator-shaped inputs are genuinely ambiguous, and D134's confidence-aware composition primitive (the shape-aware clarification at medium confidence) is the right architectural response to ambiguity at the production surface. The gold-set entry could either:

- Split into two entries with explicit alternative-acceptable-classifications (a structural change to the gold-set domain shape).
- Stay as legitimate ambiguity evidence with the model's behaviour measured against either classification being acceptable (the metric calculator supports this if extended).
- Stay as evidence that the production cell should route this input to medium-confidence shape-aware clarification rather than forcing a binary classification (the architectural answer per D134).

The third option is the architecturally honest one. The gold-set entry's expected classification stays at the operator's chosen class; the model's miss is recorded as a metric data point; the production behaviour at this input class composes with D134's confidence-aware composition by producing a shape-aware clarification when the model's confidence is medium. The gold-set authoring discipline and the confidence-aware composition primitive compose more closely than either D134's or D137's current prose surfaces.

Forward-relevance bound to multiple surfaces:

- The intent-classification evaluation substrate at D137 may extend at Phase 2-B+ to record gold-set ambiguity-markers and measure model behaviour at ambiguous inputs against either-or-acceptable classifications.
- The P11 retrieval-evaluation substrate at D110 may face analogous ambiguity at gold-set query authoring (which expected chunks are "the right answer" when multiple chunks legitimately match the query); the same composition with confidence-aware composition applies at the retrieval-strategy reliability surface.
- The confidence-aware composition primitive at D134 may extend at Phase 2-B+ to expose ambiguity-aware composition (where the cell explicitly acknowledges multiple plausible interpretations in the shape-aware clarification: "I think you want to add a new data point, but you might also be revising an existing one; which is it?").

The connection between gold-set authoring and D134's confidence-aware composition is structurally significant because the substrate at D137 measures model behaviour against gold-set expectations, but production behaviour at the same input class consumes D134's port. If gold-set authoring treats ambiguity as model failure where D134 treats it as architectural opportunity, the substrate's signal and the production cell's behaviour diverge on the same class of input. Closing that divergence at future extensions of either D137 or D134 keeps the substrate measuring what production behaviour intends to surface.

  - triaged: 2026-05-26 — first-instance formalization at S49 (recurrence test named)
  - resolution: forward to `charter/methodology.md` promotion candidacy at second instance. The connection between gold-set authoring and D134's confidence-aware composition is worth indexing for any future evaluation substrate's gold-set authoring and for any future D134 extension. First-instance observation; recurrence test at the next gold-set authoring activity (D137 alternative (c) revision-lifecycle gold sets; future prompt-revision evaluation substrate; future retrieval-strategy evaluation against new corpus sources) or at the next D134 extension session (audit-conversation ConversationFlow implementer at P14+; ambiguity-aware composition extension). Recorded at the S49 session-log methodology line.

## 2026-05-26 — [S50] Resolution-ambiguity routes to D134's shape-aware clarification surface

The S48a forward finding on resolver behaviour when multiple cases share the same title closes at S50 via cell-layer extension. The architectural disposition: resolution-ambiguity (the cell extracts a high-confidence intent but the case-lookup port returns multiple matches by significant-token-overlap) routes to D134's existing Case 2 shape-aware clarification surface, not to a new fourth case or to a separate disambiguation path.

The cell's three-case discipline at D134 covers intent-classification confidence: Case 1 high-confidence proceed; Case 2 medium-confidence shape-aware clarify; Case 3 low-confidence or parse-failure generic clarify. Resolution-ambiguity sits as a sub-case of Case 2: the cell's structural inability to proceed deterministically (even though intent confidence is high) routes to the same shape-aware clarification surface, with the clarification content surfacing the resolution alternatives (each candidate case rendered with disambiguating signals: creation time, last activity, data-point count) rather than the intent-shape.

PendingClarification persists the resolution-ambiguity state with no schema change. `proposed_intent` carries the classified intent fields plus a `resolution_candidates` sidecar that `parse_intent` ignores; the sidecar maps positional indices to candidate Case ids. `proposed_action_summary` describes the ambiguity (`choose among N cases matching "<reference>"`). The operator's positional reply (bare integer "1", "2", "3", etc.) resolves the pending by selecting one of the candidates; the cell short-circuits a second resolve_target pass and proceeds directly with the selected case as the resolution target via `_dispatch_proceed_against_resolved`.

First instance of resolution-ambiguity at any ConversationFlow implementer. P14 implementers (audit-conversation, mirror-conversation) may face the same sub-case at their resolution surfaces. If a second instance lands, the cross-implementer commitment language warrants explicit architecture.md prose addition under the confidence-aware response composition section. The current disposition is convention-altitude at one instance; the second instance triggers structural enforcement per the build-at-second-instance discipline.

DataPoint resolution-ambiguity stays at the simpler text-join clarification (no pending, no positional reply path) at S50. The S48a finding identified Case-side as the load-bearing closure; DataPoint-side activates as a separate cell-layer extension at second-instance trigger when operator dogfooding surfaces duplicate-label data points.

  - triaged: 2026-05-26 — first-instance observation; recurrence test named at P14 ConversationFlow implementers
  - resolution: cell-layer extension at S50 implements the disposition (PortfolioGateway.CaseSummary discriminator-field extension; TargetCandidate.discriminators and ResolutionOutcome.candidates shape; `_dispatch_resolution_clarify_with_pending` plus positional-reply branch in turn(); `_handle_resolution_selection` with `_dispatch_proceed_against_resolved` short-circuit; 11 new unit tests). Architecture.md prose addition deferred to second instance at P14 framing per the build-at-second-instance discipline. Recorded at the S50 session-log methodology line.

## 2026-05-26 — [P14 framing] S49 scope-discipline three-modes refinement

The S49 scope-discipline-at-brief-authoring captures entry treats scope discipline as binary (load-bearing-minimum-committed; maximal-by-precedent-rejected). S50 framing surfaced a third mode: deferred-to-framing (a decision that defers from brief altitude to a subsequent strategic-mode framing session rather than committing or rejecting at the brief).

P14 framing exercised all three modes operationally: committed (narrow scope at audit + mirror); deferred-to-framing (mirror drill-down state question landed at framing rather than at S52's brief); rejected-by-precedent (calendar-read and email-read pushed to P15+ despite phase-2-design-7step's original P14 line).

Three modes acknowledged: load-bearing-minimum-committed; maximal-by-precedent (rejected at the brief unless framing-altitude reconciliation surfaces it as load-bearing); deferred-to-framing (a third mode where the brief cannot settle the question without strategic-mode framing inheritance).

  - triaged: 2026-05-26
  - resolution: light revision to the S49 captures entry forthcoming at the next captures-entry revision cycle; the three modes carry forward as the discipline's operational shape. P14 framing is the second-instance evidence beyond S49/S50. Recorded at P14 framing strategic-mode close.

## 2026-05-26 — [P14 framing] Interface-vs-implementation operational evidence carryforward

The S49 methodology promotion entry for interface-versus-implementation discipline carries convergence-conversation provenance plus the S50 operational evidence (CaseSummary DTO discriminator-field extension; PendingClarification dict shape, both caught at draft time).

P14 framing exercised the discipline at every architectural commitment shape (CitedResponse Protocol shape; AuditQueryPort shape; intent value object set; response value object shape; conformance scenario shape) and surfaced the discipline's standing-surface binding as operationally enforceable beyond the convergence-conversation provenance.

Forward-relevance update for the methodology entry: surface S50's operational evidence and the P14 framing's exercise as carrying-forward beyond convergence-conversation provenance. The discipline binds at every strategic-mode block and at every brief-authoring step.

  - triaged: 2026-05-26
  - resolution: light revision to the methodology entry forthcoming at the next methodology-entry revision cycle; the forward-relevance prose surfaces S50 plus P14 framing as operational evidence. Recorded at P14 framing strategic-mode close.

## 2026-05-26 — [P14 framing] Mirror-conversation drill-down state-entity activation trigger

Mirror-conversation drill-down navigation at P14 is stateless re-classification per turn against conversation history per D138 extension and architecture.md. The design resists introducing a second user-scoped state machine alongside PendingClarification.

Activation triggers for the state-entity to become the right shape: (a) operator dogfooding surfaces drill-down misclassification rate exceeding the gold-set threshold from S52; (b) conversation-history-as-classifier-context fails at recurring sub-cases (long pauses; context-window saturation; cross-channel navigation when a second channel arrives); (c) a future ConversationFlow implementer at P15+ surfaces a parallel navigation-state requirement that would benefit from a shared state entity.

  - triaged: defer on 2026-05-26
  - resolution: forwarded to charter/deferred-decisions.md as the activation-trigger entry. The captures entry indexes the architectural disposition; the deferred-decisions entry is the activation-trigger surface. Recorded at P14 framing strategic-mode close.

## 2026-05-26 — [P14 framing] S46 cited_audit_events empty-field gap closure

S46's manual entry cell first-instance exercise of D131 carried cited_audit_events empty because intake write-result DTOs (CaseWriteResult, DataPointWriteResult) do not surface audit_event_ids. The S46 captures entry forwarded the gap to either a write-result DTO extension at P14+ or acceptance of cited_audit_events as aspirational where cited_intake_records plus cited_artefacts cover the audit surface transitively.

P14 framing settles: no write-result DTO extension at P14. The gap closes on the read-side at audit-conversation's natural composition (the audit chain query result's audit_event_ids populate cited_audit_events directly; audit_events are the response's primary content, so the citation tuple is non-empty by construction). Mirror-conversation continues to leave cited_audit_events empty (audit chain reachable transitively through cited IntakeRecord audit anchoring per D128). Manual entry cell's CellResponse continues to leave cited_audit_events empty (S46's original disposition holds).

  - triaged: 2026-05-26
  - resolution: closed at D138 (CitedResponse Protocol expected-exercise) and architecture.md (audit-conversation context note). The empty-field gap closes structurally without intake write-result DTO extension at P14. Future write-result DTO extension defers to a later trigger if a downstream consumer demands direct audit_event_id pointers from write results. Recorded at P14 framing strategic-mode close.

## 2026-05-26 — [S51 framing] Substrate-inheritance survey at framing close (methodology candidate, three-instance evidence)

P14 framing committed the S51 brief on substrate-inheritance assumptions that pre-write reconciliation found false at three independent altitudes:

1. **AuditQueryPort framed as new** when the existing AuditEventReader port from S36 covered the seven filter dimensions plus cursor pagination plus chain-integrity verification. The brief committed an Alembic migration and a new Postgres adapter; both dropped at Finding 1 disposition.
2. **shared_kernel/conversation_flow framed as a directory** when the codebase convention is single-file per shared_kernel primitive (intent_classification.py, structured_output.py, inference.py, confidence_thresholds.py, actor_context.py, authorisation.py, revisable.py). The brief committed `shared_kernel/conversation_flow/cited_response.py` and `shared_kernel/conversation_flow/citations.py`; both collapsed to a single-file extension at Finding 2 disposition.
3. **ArtefactCitation framed as "currently at the manual entry cell module"** when ArtefactCitation does not exist anywhere in the codebase. The "move from manual entry cell" framing was structurally false; ArtefactCitation is authored fresh at S51, and CellResponse refactors at S51 commit 2 (the brief's "no shape change to CellResponse" framing was the load-bearing falsity Finding 4 surfaced). Operator selected the symmetric-with-mirror architectural shape after the pick became visible.

The pattern: P14 framing's brief altitude assumed substrate that codebase reality doesn't carry. Each instance was caught at pre-write reconciliation surfaces 1, 2, and 4 respectively (surface 3 — gold-set fixture location — landed as Finding 3 at a different shape: existing convention diverges from brief without a substrate-inheritance miss; the brief framed a new path rather than mis-naming an existing one).

The substrate-inheritance survey discipline: at framing close, before brief preservation, run a survey of each substantive substrate commitment in the brief against current codebase state. For each "X exists at Y" or "X moves from Y to Z" claim in the brief, verify by grep that X actually exists at Y. Each false claim is a structural-honesty finding to surface before code drafting begins.

The three-instance evidence base (one P14 framing, three independent surface misses) carries the discipline to promotion-ready altitude. The S49 promotion of interface-versus-implementation discipline at seven-instance evidence is the precedent; substrate-inheritance survey at three-instance evidence at one framing event is a denser pattern (three brief-altitude misses in one framing session is itself signal).

S51 build-mode added a fourth instance during commit 3 drafting: the brief committed "the dispatch port at D136 routes audit queries to the audit-conversation cell," presupposing dispatch-decision logic that does not exist in the codebase (the S47 CellDispatch port runs one cell; the Twilio webhook always dispatches to manual_entry_cell; no cell-selection mechanism is in place). Finding 5 surfaced this at build-mode pre-write reconciliation rather than framing-mode pre-write reconciliation, raising the question of whether substrate-inheritance survey at framing-altitude can be made tight enough to catch dispatch-shape assumptions that bridge from the message-routing surface (webhook) to the cell-dispatch surface (CellDispatch port). The Finding 5 disposition (option c, defer dispatch routing to S52) avoids the question for now; S52 framing inherits the architectural question of three-cell dispatch logic.

Forward-relevance: the discipline binds at framing close (strategic-mode), at the first action of pre-write reconciliation (build-mode), and at brief-vs-codebase comparison generally. Adjacent to interface-versus-implementation (S49) and scope-discipline-at-brief-authoring (S48b/S49/S50/P14 framing), but distinct: substrate-inheritance is "the brief claims X exists; X does not exist"; interface-versus-implementation is "the brief commits an implementation when the architecture should commit the interface"; scope-discipline is "the brief commits the full implementation when only the load-bearing minimum is needed."

  - triaged: 2026-05-26 — three-instance evidence at single P14 framing event; promotion-ready
  - resolution: forward to `charter/methodology.md` promotion candidacy. The recurrence test is at the next strategic-mode brief-authoring moment: does the brief carry framing-altitude claims about codebase substrate that pre-write reconciliation will need to verify? The pattern-family observation alongside interface-versus-implementation and scope-discipline-at-brief-authoring anchors the connection for the second-instance-of-the-pattern-family promotion conversation. Recorded at the S51 session-log methodology line.

## 2026-05-27 — [P14 close framing] S49 scope-discipline three-modes recurrence at S52 framing

S49 scope-discipline-at-brief-authoring discipline. Three modes: load-bearing-minimum-committed; maximal-by-precedent-rejected; deferred-to-framing.

P14 framing exercised all three modes; S52 framing (the framing-altitude block producing this brief) exercised all three again:
- Load-bearing-minimum-committed: framing committed only meta-classifier dispatch shape, PendingClarification target_cell extension, ConversationFlow cell-payload persistence pattern, and mirror-conversation context shape.
- Maximal-by-precedent-rejected: P14 framing rejected calendar-read, email-read, daily-briefing, threshold-briefing as P15+ scope per the narrow-scope decision; S52 framing rejected unified-intent-classifier-at-dispatch and synchronous-meta-classification as architectural shapes (D140 alternatives b and c).
- Deferred-to-framing: N value for conversation history; exact intent VO schemas; cell-payload persistence shape settled framing-altitude with implementation-shape deferred to brief.

Third-and-fourth-instance evidence beyond the S49 first and S50 second instances. Methodology candidate continues at promotion-ready evidence count.

  - triaged: 2026-05-27
  - resolution: continued recurrence evidence; promotion-readiness for methodology.md hygiene-session promotion holds. Recorded at P14 close framing.

## 2026-05-27 — [P14 close framing] Interface-vs-implementation discipline operational evidence at S52 framing

The S49 promotion's standing-surface binding has now exercised at:
- S50 (CaseSummary DTO discriminator-field extension; PendingClarification dict shape; convergence-conversation provenance)
- S51 framing (5 architectural decisions framed; Findings 1-5 surfaced at brief reconciliation)
- S52 framing (this session; MetaClassifier port shape, MirrorPortfolioReader vs reuse decision, intent VO union shape, response value object extension, cell_payload pattern at architectural altitude rather than implementation altitude)

The discipline binds at every architectural commitment shape. Forward-relevance prose for the methodology entry: at every strategic-mode block and at every brief-authoring step, run the interface-vs-implementation check at every architectural commitment.

  - triaged: 2026-05-27
  - resolution: forward-relevance updates continuing; the discipline is now operationally enforced as standing pre-write reconciliation. Methodology entry's forward-relevance prose may update at the next hygiene session. Recorded at P14 close framing.

## 2026-05-27 — [P14 close framing] Cross-context facade pattern second-and-third-instance application

D16/D17/D28 commit the cross-context discipline: reads through `.api` facades, writes through consumer-defined ports.

Pattern applications across P14:
- First instance (S51 commit 3): messaging.api facade for audit-conversation's reach into messaging context (PendingClarification consumer port access).
- Second instance (S52 commit 6): same messaging.api facade for the dispatch_inbound use case's reach into PendingClarification machinery (the use case lives at messaging.application so it consumes directly without facade; the pattern repeats at the symmetric mirror-conversation reach).
- Third instance (S52 commit 8): same messaging.api facade for mirror-conversation's reach into messaging context (PendingClarification for resolution-ambiguity routing).
- Fourth instance (S52 commit 7): MirrorPortfolioReader consumer port at mirror_conversation context for cross-context write to portfolio context's use cases (the consumer-port-plus-wiring-adapter pattern).

The pattern is established and operational. No architecture.md elevation needed; the pattern's repeated application across two implementers in P14 confirms generalisability. Future ConversationFlow implementers at P15+ inherit structurally.

  - triaged: 2026-05-27
  - resolution: indexed as application-pattern evidence. No promotion-candidacy at methodology.md (the pattern is already committed at D16/D17/D28); the captures entry serves as cross-reference for future audits. Recorded at P14 close framing.

## 2026-05-27 — [S52 framing] Substrate-inheritance survey first-application evidence + Alembic-numbering refinement

S51 framing surfaced five framing-vs-codebase-reality findings at brief-altitude reconciliation. The substrate-inheritance survey methodology candidate was indexed at S51 close as promotion-ready (entry above, 2026-05-26).

S52 framing operationally exercised the survey discipline at framing-altitude before drafting the brief. Five substrate-inheritance surveys ran (MetaClassifier port location; MirrorPortfolioReader wiring adapter target; messaging.api facade; D137 substrate parameterisation; ConversationFlow contract harness registry-discovery). All five returned existing substrate; the brief was drafted against codebase reality.

S52 brief-altitude pre-write reconciliation surfaced **one** finding rather than S51's five: the Alembic-numbering collision (the brief committed migrations 0022 and 0023, but S48b's intent_class_eval_substrate already holds 0022 — pre-write reconciliation Finding 1 at S52, renumbered to 0023 and 0024). This is first-application evidence that the framing-altitude survey discipline reduces brief-altitude reconciliation surface (one finding versus five). The discipline accumulates evidence for methodology.md promotion at the next hygiene session.

**Refinement.** The framing-altitude survey at S52 did not include the Alembic migration-number sequence as a survey surface (the framing survey covered architectural substrate — port locations, use case existence, facade modules, registry-discovery mechanisms — but not configuration sequencing like the next available Alembic number). For future framings that commit new Alembic migrations, the survey should include a one-line "What is the next available Alembic migration number?" check at framing-altitude. The refinement folds into the methodology candidate at the next hygiene session promotion.

  - triaged: 2026-05-27
  - resolution: first-application evidence strengthens the candidate from three-instance (S51 framing) to three-instance-plus-first-application (S51 + S52). The Alembic-numbering refinement is the first specific extension to the survey discipline beyond architectural substrate. The hygiene session promoting to methodology.md should incorporate both the discipline as standing framing-altitude reconciliation and the migration-number sub-surface as a concrete check. Recorded at S52 framing close.

## 2026-05-27 — [S52 framing] PendingClarification schema.md hygiene gap absorbed at S52 commit 1

Pre-write reconciliation at S52 commit 1 surfaced that `charter/schema.md` carries no PendingClarification table section despite the entity landing at S47 with Alembic 0021. The S47 hygiene gap (charter/schema.md should have gained the section per the discipline "schema changes update charter/schema.md in the same commit") went uncaught at S47, S47 addendum, S48a, S48b, S49, S50, and S51.

Disposition: absorb the PendingClarification section at S52 commit 1 alongside the target_cell column addition (D140). The honest fix lands the missing S47 section plus the S52 column addition in one commit. The schema gap closes structurally; no audit-trail loss (the migration history at `alembic/tenant/versions/2026_05_25_0021_pending_clarification.py` carries the canonical record).

This is a substrate-inheritance survey miss at the *charter audit-trail surface* rather than at the codebase substrate surface. The framing-altitude survey at S52 did not include "does charter/schema.md carry sections for every existing per-tenant table?" as a survey question. Adjacent to the Alembic-numbering refinement above.

  - triaged: 2026-05-27
  - resolution: absorbed at S52 commit 1 (this commit). The substrate-inheritance survey methodology candidate's "what to survey" surface gains "charter/schema.md section completeness against the migration directory" as another concrete check alongside the Alembic-numbering refinement. The hygiene-session promotion to methodology.md should include the schema.md-completeness sub-surface. Recorded at S52 framing close.

## 2026-05-27 — [P15 framing] Substrate-inheritance survey three-instance evidence at framing altitude

S52 framing first-application evidence (five surveys ran at framing altitude; brief-altitude reconciliation surface dropped from S51's five findings to S52's one finding). P15 framing applied the discipline at every surface walk and surfaced three corrections at framing altitude:

- Surface 3 (channel preference state): initial lean toward User entity extension corrected when survey revealed D136 Primitive 1 (User aggregate root) defers to second-channel activation trigger. Static-configuration adapter became the right call.
- Surface 5 (external-integration architectural shape): initial framing assumed in-process OAuth at messaging context corrected when survey revealed D14 commits separate-service pattern for calendar/email tools. Consumer-side adapter pattern became the right call.
- Surface 2 (outbound abstraction shape): synthetic-inbound alternative rejected when reasoning surfaced semantic honesty principle. BroadcastFlow Protocol committed.

Three framing-altitude corrections at P15 framing extends the methodology candidate's promotion-readiness. The discipline operates as standing surface at framing-altitude AND at brief-altitude (substrate-inheritance survey runs at every surface walk; brief-altitude reconciliation surface should continue to shrink at S53 onwards).

  - triaged: 2026-05-27
  - resolution: continued recurrence evidence at framing altitude. Methodology candidate promotion-ready for methodology.md at next hygiene session. Recorded at P15 framing close.

## 2026-05-27 — [P15 framing] Operator chose Nango self-hosted for tool service substrate

Strategic disposition at P15 framing. The operator chose Path B (source tool services externally) with self-hosted Nango under Elastic License rather than Path A (build Padhanam-owned tool services) or Composio cloud (third-party SOC2-certified hosting).

Reasoning: Composio's "shallow moat" critique (acknowledged by external observers; the platform's defensibility erodes with provider API changes) concerns vendor-dependency risk; self-hosted Nango keeps OAuth substrate inside operator-controlled infrastructure at $0 ongoing cost with migration-free path to Path A at Phase 2-B+ if needed.

Operator runs Nango container alongside padhanam-api as parallel infrastructure work outside Padhanam's package boundary. The architectural Protocol-based adapter pattern (D14, D144's port-based abstraction) supports any future migration without domain code changes.

Path A migration trigger conditions: vendor pricing inversion at Phase 2-B+ scale; privacy compliance escalation; feature divergence. Recorded at charter/deferred-decisions.md as the Path A migration entry plus the calendar/email activation closures.

  - triaged: 2026-05-27
  - resolution: forwarded to charter/deferred-decisions.md as the Path A activation trigger entry. Operational disposition for parallel infrastructure work outside Padhanam's package boundary. Recorded at P15 framing close.

## 2026-05-27 — [P15 framing] P15 medium scope at five sessions as package-shape evidence

P15 framing settled medium scope (outbound initiation plus calendar-read plus email-read) with wide scope (Slack, methodology library, surfacing mechanics) deferred to P16. The framing surfaced that medium scope at one package is materially larger than P14: three substantial substrates (outbound, calendar, email) each with intake-side AND ConversationFlow-implementer surfaces, estimated five sessions to close.

P14 ran two sessions plus framing (S51 plus S52). P13 ran ten sessions (S43 to S50). P15 at five sessions sits in between but skewed toward P13 size territory.

Methodology observation candidate: package-shape sizing at framing altitude. Three modes observable across packages: small (P4 at two sessions; some P12 work), medium (P14 at two sessions plus framing), large (P13 at ten sessions; projected P15 at five sessions). Operator's preference at framing time (one large package versus split into narrow plus follow-on) is real strategic input that benefits from explicit naming at framing.

Not yet a load-bearing methodology candidate (one observation does not establish a pattern). Forward observation: if P16 framing also surfaces a sizing decision, the candidate evidence grows.

  - triaged: 2026-05-27 — first-instance package-shape sizing observation at framing-altitude
  - resolution: forward-relevance prose carries to P16 framing; methodology candidate evidence accumulates if P16 framing surfaces a sizing decision. Recorded at P15 framing close.

## 2026-05-27 — [P15 framing] BroadcastFlow as second-instance of shared_kernel cross-cutting Protocol pattern

D115 first instance: ConversationFlow Protocol at shared_kernel for cross-context interaction abstraction. D138 second instance: CitedResponse Protocol at shared_kernel for citation-shape conformance. D142 third instance: BroadcastFlow Protocol at shared_kernel for platform-initiated outbound abstraction.

Pattern observation: shared_kernel as the home for cross-context structural Protocols that multiple bounded contexts implement. Each Protocol is runtime-checkable; each is parallel rather than inherited; each enforces structural typing without inheritance coupling.

Observation candidate: shared_kernel Protocol pattern is becoming a recurring architectural shape. Third instance at P15 establishes the pattern; future cross-context structural commitments likely follow the same shape.

  - triaged: 2026-05-27 — third-instance Protocol pattern observation
  - resolution: pattern indexed. No promotion-candidacy yet (the pattern is implicit-but-coherent); future architectural decisions naming new Protocols can reference this pattern. Recorded at P15 framing close.

## 2026-05-27 — [P15 framing] ArtefactCitation discriminator additive extension pattern verified

D138's ArtefactCitation typed value object at shared_kernel carries an artefact_type discriminator (Case, DataPoint at Phase 2-A first instance). P15 framing Surface 6 commits the extension to four types (Case, DataPoint, Meeting, Email). The Protocol stays unchanged; only the discriminator enum widens.

Pattern verified: discriminator extension is additive. New ConversationFlow implementers consuming new artefact types extend the discriminator without forcing Protocol revision. The extension is forward-compatible by construction.

This validates the D138 framing's expectation that the discriminator pattern generalizes. The captures entry indexes the second-instance verification (first instance was D138's own commit; second instance is P15 framing's extension commitment).

  - triaged: 2026-05-27
  - resolution: pattern verified second-instance. The additive-extension shape is now established at two instances; future Phase 2-A or Phase 2-B+ implementers extending the discriminator follow the same shape. Recorded at P15 framing close.

## 2026-05-27 — [S54 framing close] Import-graph topology category folds into substrate-inheritance survey methodology candidate

S53 close surfaced import-graph topology as a third category of substrate-inheritance survey finding (Finding A: ChannelType placement violated platform-to-contexts import-linter contract; lift to shared_kernel required). The category sits alongside substrate-existence and configuration-conventions categories from prior framings.

S54 framing's substrate-inheritance survey at framing altitude exercised all three categories: substrate-existence (DailyBriefingReader port location; AuditEventReader consumed by wiring adapter; portfolio.list_cases use case existence); configuration-conventions (MessagingSettings extension pattern; idempotency_key column shape); import-graph topology (BROADCAST_INITIATED event class location at contexts/audit/domain/ vs the actual per-context audit_events.py pattern; idempotency key resolver function location at contexts/messaging/domain/; cross-context import verification for daily_briefing-application's consumer-DTO discipline).

The substrate-inheritance survey methodology candidate now has three categories of evidence (substrate-existence; configuration-conventions; import-graph topology) plus a four-session reduction trajectory (S51 brief 5 findings → S52 brief 1 finding → S53 brief 1 finding + 1 build-time finding → S54 brief expected near-zero findings if framing-altitude survey holds).

  - triaged: 2026-05-27 — formal capture for next hygiene-session promotion to methodology.md
  - resolution: promotion-ready evidence accumulates. The three-category substrate-inheritance survey discipline is ready to promote at the next hygiene session. The promotion folds the import-graph topology category into the discipline's prose. Recorded at S54 framing close.

## 2026-05-27 — [S54 framing close] Consumer-port-plus-wiring-adapter pattern reaches three-instance evidence

The cross-context discipline (D16/D17/D28) commits consumer-defined ports for cross-context writes. The pattern has three instances now: PortfolioGateway at contexts/messaging/ from S46 (manual_entry cell's consumer port composing portfolio context use cases); MirrorPortfolioReader at contexts/mirror_conversation/ from S52 (mirror-conversation cell's consumer port for read access to portfolio context); DailyBriefingReader at contexts/daily_briefing/ from S54 (daily-briefing implementer's consumer port composing multiple producer contexts).

The pattern's generalizability is now operationally established at three instances. Each consumer context owns its consumer ports; the wiring adapter at composition root delegates to producer-context use cases; cross-context boundaries respect the discipline. S54 adds a sub-pattern: the consumer port also defines its own DTOs (DailyBriefingCase, DailyBriefingIntakeRecord, DailyBriefingAuditEvent) so the application layer does not import producer-context domain modules — preserving import-graph independence at the application-to-domain cross-context surface. This mirrors mirror-conversation's MirrorCaseSummary discipline.

Future ConversationFlow and BroadcastFlow implementers that need cross-context reads follow the same pattern without architectural commitment work; the pattern is implicit-but-coherent. No methodology candidate promotion-candidacy at architecture.md (the pattern is already committed at D16/D17/D28); the captures entry indexes the operational evidence.

  - triaged: 2026-05-27
  - resolution: pattern verified at three instances. Future Phase 2-A and Phase 2-B+ implementers extending the pattern continue to validate it. No architecture.md elevation needed beyond the existing D16/D17/D28 commitment. Recorded at S54 framing close.

## 2026-05-27 — [S54 framing] Endpoint-level idempotency over implementer-level emerges as pattern

S54 framing Surface 2 walked four options for daily-briefing idempotency mechanism and three options for the check's location within the dispatch flow (endpoint-level, dispatch-level, implementer-level). The endpoint-level choice settled D147.

The choice has architectural implications for future broadcast implementers. Threshold-briefing at S57 follows the same endpoint-level idempotency pattern (its IdempotencyKeyResolver returns the composite key per matched event per rule). Future BroadcastFlow implementers consume the same fired_triggers substrate; the idempotency_key column's generic shape accommodates per-trigger-type semantics without schema variation.

This is a pattern-formation observation rather than a methodology candidate. The endpoint-level idempotency pattern is now the default for BroadcastFlow implementers requiring idempotency-protected firing. Implementer-level checks remain available if needed (e.g., if an implementer has fire-time conditional logic that the endpoint cannot evaluate); the architectural shape accommodates both.

  - triaged: 2026-05-27
  - resolution: pattern observed and named. Future BroadcastFlow implementers follow endpoint-level idempotency by default; deviation requires explicit architectural justification. Recorded at S54 framing close.

## 2026-05-28 — [S54 build-mode pre-write reconciliation] Audit event class set does not exist as a discrete artefact

S54 brief framed the BROADCAST_INITIATED audit event class as an addition to "the audit event class set at contexts/audit/domain/". Pre-write reconciliation Finding 1 at S54 build mode surfaced that no such set exists: audit events use `action_verb` plus `resource_type` strings (no enum, no CHECK constraint at the audit chain Postgres adapter); existing per-context audit_events.py modules (e.g., `contexts/messaging/application/audit_events.py`) define the constants.

Disposition: BROADCAST_INITIATED lands as `RESOURCE_TYPE_BROADCAST` plus `ACTION_BROADCAST_INITIATED` constants plus a `draft_broadcast_initiated_event` helper at `contexts/messaging/application/audit_events.py` at commit 3. No CHECK constraint extension or Alembic migration at audit context required.

The finding is a brief-altitude vs reality mismatch caught at build-time pre-write reconciliation (the framing-altitude survey did not include "does the audit event class set exist as a discrete artefact?" as a check). The substrate-inheritance survey methodology candidate gains another concrete check: "for every framing reference to an existing artefact, verify the artefact actually exists at the claimed location with the claimed shape." Adjacent to S52's schema.md-completeness sub-surface and S53's import-linter-contract preservation sub-surface.

  - triaged: 2026-05-28
  - resolution: absorbed at S54 commit 3 (the broadcast audit event constants and draft helper land at the messaging context's existing audit_events.py module, not at a new audit-context event-class set). The hygiene-session promoting the substrate-inheritance survey to methodology.md should incorporate the "verify artefact existence at claimed shape" sub-surface alongside the Alembic-numbering / schema.md-completeness / import-linter-contract-preservation sub-surfaces. Recorded at S54 commit 1.

## 2026-05-28 — [S54 build-mode pre-write reconciliation] IntakeRecord time-window filtering uses pagination, not dedicated filter

S54 brief framed DailyBriefingReader.read_intake_records as reading "recent IntakeRecords from the window" without specifying the filtering mechanism. Pre-write reconciliation Finding 2 at S54 build mode surfaced that `IntakeListFilters` carries only an `intake_sources` multi-value filter; no time-window filter exists. The `IntakeRepository.list_for_tenant` paginates on `(created_at DESC, id DESC)`.

Disposition: the wiring adapter at `apps/api/_daily_briefing_wiring.py` reads pages from the IntakeRepository and trims in-memory at the window boundary. At Phase 2-A dogfooding scale (low-digit IntakeRecords per day) the trim is trivially small; at Phase 2-B+ scale a dedicated `created_at_after` filter on IntakeListFilters would be the right addition. The trigger for the filter addition fires when the IntakeRecord volume in a typical window exceeds the page size and the in-memory trim becomes inefficient.

  - triaged: 2026-05-28
  - resolution: absorbed at S54 commit 5 (the wiring adapter implements in-memory time-window trim). The activation trigger for the dedicated filter is captured here; no deferred-decisions entry needed at S54 (the architectural mechanism already accommodates the swap). Recorded at S54 commit 1.

## 2026-05-28 — [S54 build-mode pre-write reconciliation] TriggerContext.metadata stays as dict[str, Any] for backward compatibility

S54 brief framed the TriggerContext extension as "TriggerContext discriminated union concrete classes" plus "the discriminator union: TriggerMetadata = Union[DailyScheduledMetadata, ManualMetadata, ...]". Pre-write reconciliation Finding 3 at S54 build mode surfaced that changing TriggerContext.metadata from `dict[str, Any]` to a typed union would break S53 unit tests (`test_trigger_context_carries_per_type_metadata` constructs with `metadata={"threshold_rule_id": ...}`).

Disposition: TriggerContext.metadata stays as `dict[str, Any]` per the S53 shape; typed `DailyScheduledMetadata` and `ManualMetadata` land as convenience-constructor dataclasses at `shared_kernel/broadcast_flow.py` that serialise into the dict via a helper. The idempotency key resolver consumes the dict directly. The discriminator-union shape lands as a typed-helper layer above the open dict, preserving structural backward compatibility.

This is the sixth recurrence of the interface-versus-implementation discipline (S49 standing surface). The brief's framing was implementation-shaped (forcing the union type onto the existing TriggerContext); the interface decision (typed constructor helpers exposing the same data via a typed surface) preserves the structural shape while landing the typed-metadata discipline. The discipline now has six consecutive recurrence instances (S50, S51, S52, S52-framing, S53-brief, S54-brief); promotion-readiness for methodology.md continues to firm.

  - triaged: 2026-05-28
  - resolution: absorbed at S54 commit 3 (TriggerContext.metadata stays as dict[str, Any]; typed metadata classes plus serialise helper land alongside). The discipline at sixth recurrence is operationally enforced as standing pre-write reconciliation. Recorded at S54 commit 1.

## 2026-05-28 — [Ciborra audit] Bricolage vocabulary absent from the methodology while bricolage is pervasive in git

The Ciborra phenomenological audit (`charter/ciborra-phenomenological-audit.md`) found zero occurrences of "bricolage / improvise / materials at hand / recombine" across `charter/`, `docs/archive/`, and `log/`, while the git history is rich with reuse-of-fragment and mid-build recombination. Cross-referenced git evidence: commit `9bb7c03` (S24 hash_chain promotion at second consumer); `log/sessions.md:1799` (S39 mid-build reuse where the planned new helper was abandoned on finding `padhanam.security.hash_chain` already exposed the mechanism); `log/sessions.md:2057` (S53 StaticConfigChannelResolverAdapter improvised from `MessagingSettings.operator_default_channel` already to hand). The methodology frames each as a proactive, forward-binding discipline ("second-consumer-promotes," "mid-build pre-write reconciliation," "interface-versus-implementation," "build-at-second-instance"), neither as bricolage nor as recovered lapse.

  - triaged: 2026-05-28
  - resolution: defer to the next phase audit. The bricolage-vocabulary promotion (whether to name the codification-of-improvisation pattern in `charter/methodology.md`) is a charter decision the assessment session does not make; this audit produces the git evidence the promotion will rest on, per the session prompt's out-of-scope.

## 2026-05-28 — [Ciborra audit] P12's twelve-bounded-context documentation note is stale at nineteen

P12 audit Entry 16 (`charter/p12-audit-findings.md:235`) recorded the bounded-context count as twelve expressly so "future audit conversations inherit the documented count without rediscovery." At HEAD `718c46e`, `ls contexts/` returns nineteen (the twelve plus the seven Phase-2-A contexts: audit_conversation, daily_briefing, intake, intent_classification_evaluation, messaging, mirror_conversation, portfolio — all D-authorised). The code-layer count is benign drift (every context is chartered); the phenomenological finding is that the anti-drift artefact itself drifted under use.

  - triaged: 2026-05-28
  - resolution: note + defer to the next audit conversation for a documentation-count refresh. No code or charter-decision action; the count is authorised, only the P12 note is stale.

## 2026-05-28 — [Ciborra audit] Phase-2-A principles transplanted from karma prior-art (das Man tension)

`grep -c "karma prior-art" charter/principles.md` → 4: the frontend/backend-separation, audit-trail-as-source-of-truth, originals-never-erased, and authority-and-certainty-independent principles each carry "Origin: karma prior-art product specification §11.x, transplanted at P13 framing." The Ciborra audit's authenticity section reads this as the das Man pole the bet's situated-reckoning self-image is least comfortable with: the most load-bearing Phase-2-A architectural spine was, in material part, transplanted from a prior product rather than reckoned into being. The transplant is honestly labelled (authentic practice), but transplantation-from-prior-art is structurally easy-to-copy. Connects to the PRFAQ Option-B pluggability honesty correction the session prompt named for Phase-2 opening (now passed).

  - triaged: 2026-05-28
  - resolution: defer to the next phase audit's authenticity/PRFAQ-honesty review. Assessment-only; no action this session.

## 2026-05-28 — [Ciborra audit] Change-failure-rate metric reads 0% while the qualitative failure record is non-empty

`grep -c "classification: corrective" log/sessions.md` → 0: no session in the entire log is tagged corrective, so the methodology's change-failure-rate metric (`charter/methodology.md:248`) computes to 0%. Meanwhile the Failure-modes-observed section documents real drift events (silently-deferred package drift, fabrication-class drift, single-currency assumption). Failures are booked as narrative Failure-modes entries rather than via the corrective session classification, so the quantitative mood-signal reads calmer than the qualitative record.

  - triaged: 2026-05-28
  - resolution: defer to the next phase audit's metric review. A measurement-model honesty item: either the corrective classification is under-applied or the metric needs reconciling with the Failure-modes record. Assessment-only; no metric change this session.

## 2026-05-28 — Ciborra audit arc: the bricolage insight, the prune capability, and the champion-register seed

I ran Claudio Ciborra's phenomenological reading of enterprise IT against Padhanam as a second lens, first against the charter and then against the as-built code and git. The arc produced more reflection than any single session, so I am capturing it here before it decays in chat history. Reflection is the bet's deliverable; this is a chunk of it. The commercial material at the end is structured so I can lift it straight into the Phase-2 champion-register artifact when I switch to strategic-commercial mode.

### The durable reflection

The lens resolved Padhanam into two layers running two epistemologies, and the split is honest rather than contradictory. The build layer is Ciborran: breakdown is surfaced as first-class state, drift is followed and codified, abstractions are cultivated rather than installed. The product layer is Gestell: it enframes agentic-system activity into calculable optimisation dimensions, deliberately, because that enframing is the procurement-grade proposition. The two are correctly differentiated for their audiences. The methodology is the proprietary insight that makes the enframing inspectable rather than imposed.

The code-and-git audit earned its keep by catching what the engineering audit (P12) structurally could not. P12 verifies decisions against code and so reads a named discipline as evidence of rigour. The phenomenological lens reads the same discipline as a place drift can hide. That difference is the whole reason the second lens exists, and it found real fractures the first lens had passed clean: a pluggability overstate, a cultivation-to-control drift, and the bricolage blind spot below.

### The bricolage insight (the deepest finding)

My signature move is to convert every improvisation into a named discipline. That move is the proprietary insight: it makes a messy, senior skill teachable and repeatable, which is exactly what is hard to copy. It is also the blind spot. Once an improvisation is renamed a discipline, it stops looking like an improvisation, so my own drift becomes invisible to me. The codification habit produces the principled self-image it describes. An engineering audit reads the named disciplines as rigour; the phenomenological lens reads the same disciplines as where my improvisation and my drift toward control are most successfully hidden, not dishonestly, but by the ordinary working of a method whose core move is to make the contingent look principled.

Bricolage is the name for the thing the method does and never named. The word appears zero times in the charter while the git history is full of it: reuse of fragments built for other purposes, mid-build recombination, resolvers improvised from configuration already at hand. The method captured every one of these moments faithfully and called them disciplines. The placement that resolves this: bricolage belongs in the audit, not the sessions. Sessions encode improvisation into discipline, which keeps the work moving. The audit decodes it back to check for hidden drift. Bricolage is what the decode step looks for.

### What the method gained this arc

Before this arc the method could only accumulate. The structural-promotion threshold told me when to create a discipline; nothing told me when to retire one, so disciplines only ever piled up. That asymmetry is the mechanism by which a method becomes a cage, which is the thing I stopped to ask about directly: am I fitting myself into a box. The answer was that the danger is not structure but a box I cannot leave, and the cure is not less structure but a structure that can shrink.

So I built a death rule. The method now has a discipline-retirement (prune) rule symmetric with the birth rule, and a standing decode step that reverses the session-level encode and carries a reconcile-before-it-counts guard. I then exercised the prune rule on its first real case: I retired the loose build-at-second-instance discipline and superseded it with a two-threshold rule. Domain patterns still wait for the third instance. Integration boundaries build at the second only when the second adapter is structurally guaranteed, not merely anticipated, where the tell is whether I can name a second adapter that already exists or is committed this phase. A discipline genuinely died: the unconditional early-build permission. What survived is narrower and forbids what the old rule permitted. This is the cure for the cage made concrete. The method can now shrink, not only grow, which removes the accumulation failure mode that would otherwise have broken the bet's claim that the discipline holds at complexity.

### Corrected self-understanding

Two of the audit's own findings were wrong or overstated, and correcting them sharpened the picture.

The das Man finding was wrong on the facts. The four "karma prior-art" principle transplants are not conformity to external prior-art; karma2 is my own prior product iteration. Reusing my own prior work is authentic, and it is bricolage in the truest sense: recombining materials from my own accumulated kit, each carrying what I learned the first time. The audit could not see this because the only thing written down was the label.

The pluggability finding was overstated. The single-adapter-behind-a-Protocol pattern is sound YAGNI. The real finding narrowed to two things: a buyer-wording register gap, and one genuinely input-discarding stub (ChannelResolver), which I fixed. Reconciliation also corrected the audit's own quantifiers: "several" stubs was one, and "every port single-adapter" was false, because two ports (MetaClassifier, MessageDeliveryPort) already carry two real adapters each. The phenomenological lens finds the real defect and overstates its scope; only the code check corrects it, which is now a standing guard in the decode step.

### Champion-register seed (extract for the Phase-2 commercial artifact)

The clean distinction for the non-technical buyer: vibe coding is the build; bricolage is everything that happens to the build after it lands in the business. Vibe coding is linear, intent in and artifact out, two weeks. The workaround layer that follows is where the business actually lives, two years: customers using fields for unintended purposes, support workarounds in personal docs, analytics no one trusts, the founder still doing onboarding by hand. The exec does not live in vibe coding. The exec lives in the workaround layer, and has no visibility into it.

Padhanam's position is complementary, not competitive. Vibe coding tools (Cursor, Windsurf, Lovable, Bolt, v0) race to commoditise the improvisation surface against hyperscaler economics. Padhanam is the observability-and-codification layer above it: it watches what customers do with what shipped, watches what the team does to make it work, and surfaces the patterns worth codifying. The pitch in three sentences: your team will ship faster than ever with vibe coding tools; the artifact is the easy part; we watch the workaround layer and tell you which patterns are real enough to bake into the next version.

Three registers serve one B2B buyer journey. Builder gets the methodology vocabulary (internal). Champion, the technical advocate who must convert a procurement-approved evaluation into a funded deal, gets the workaround-layer vocabulary (this is the missing artifact). Procurement and IT, the ultimate blocker, get the procurement-grade vocabulary (the current PRFAQ, which is strong). Procurement-grade architecture is the binding-constraint-won; it gets Padhanam into the evaluation. The champion register is what closes it.

Buyer-wording correction: drop "pluggable / no vendor lock-in," which oversells a single-adapter reality and reads as overclaiming under a procurement review. Lead instead with the true and stronger claim: pluggability is demonstrated at two ports today (MetaClassifier, MessageDeliveryPort), single-adapter-by-YAGNI elsewhere, extensible by design. That is a live proof point, not a promise.

The moat, stated honestly: the methodology is situated and hard to copy, and the carried-forward architecture is my own accumulated judgment across karma2 and Padhanam, which a competitor cannot copy because they have not built both and learned what transferred. Both are the moat, for the same reason. The earlier framing that separated "the method (original)" from "the architecture (borrowed)" was wrong; the architecture is self-reuse, which is part of the moat.

### Honest status

The decode-to-prune-to-reframe loop ran end to end, but it ran because I drove it by hand. The decode step found the drift only because I commissioned a special Ciborra audit; the prune happened only because I caught the deferral and pushed; the reframe was reasoned out across several turns. None of that was the standing machinery running on its own. The status is proven-when-driven, not yet self-sustaining. The next phase audit, with the standing decode step and the threshold-supersession sub-check as its opening move, is the test of whether it runs unguided.

### Forward-carry pointers

Next phase audit: add the decode threshold-supersession sub-check as the mandatory opening move (this arc's build-at-second-instance reframe is its calibration case); run the per-principle fit-check on the four karma2 transplants; confirm the standing machinery catches drift without a special lens.

Strategic-commercial mode: write the champion-register artifact from the seed above; correct the buyer-wording per the two-ports proof point.

Audit doc: append the C3 line so "every port single-adapter" does not stand uncorrected (two ports already carry two adapters).

Deferred by YAGNI: the send_message caller-side smell and the real UserScopedChannelResolverAdapter, both tied to the multi-channel activation trigger.

  - triaged: 2026-05-28
  - resolution: note (durable reflection + commercial seed). Forward-carry pointers above route to: the next phase audit (decode sub-check calibration, karma2 per-principle fit-check, standing-machinery test); strategic-commercial mode (champion-register artifact, buyer-wording correction); the audit doc (C3 line on the "every port" quantifier); and YAGNI-deferred (send_message caller-side smell, real UserScopedChannelResolverAdapter, both gated on multi-channel activation).

## 2026-05-28 — Calendar retrieval design (pull, store, search, refresh, and the push question)

The calendar-retrieval shape for P15, decided at the audit boundary ahead of the S55 build and reconciled against the code before committing. Nango is fixed to the free tier (Auth plus Proxy only), so this whole design lives inside Proxy and our own orchestration, with no dependence on Nango's paid Syncs, Functions, or Webhooks. This is framing-altitude: the shape is settled, the knobs are for the S55 brief. It folds into S55, which I draft after the Nango provisioning session is run and verified.

### The shape

Pull calendar events scoped through Nango Proxy, store each event as a Meeting artefact in the tenant store keyed on its stable Google event ID, index it into the platform's hybrid-retrieval substrate, search over that local substrate rather than re-querying Google, and keep it fresh with self-driven incremental sync. This is the retrieval differentiator applied to calendar: events become first-class, citable Meeting artefacts (the ArtefactCitation Meeting discriminator S55 adds), not transient pulls.

How a Meeting reaches that substrate is not free, and it is a framing decision rather than a detail. A Meeting is a structured record, not a document, and the ingestion context is document-shaped: `parser_port`, `chunk_embedder_port`, `entity_extractor_port`, `graph_repository_port`, `source_repository_port`, with `chunk.py`, `entity.py`, `source.py`, `parsed_content.py` under `contexts/ingestion/`. Getting a Meeting into pgvector and Neo4j therefore runs the substrate-inheritance survey (the named discipline, `charter/current-package.md:13`) at S55. My lean is reuse: synthesise the Meeting to text (title, description, attendees, location) and flow it through ingestion's existing embed and graph ports, most likely as a Source analog, rather than standing up a parallel indexing path. The S55 brief names which ports Meeting inherits versus what calendar builds; re-implementing embedding or graph indexing would be the parallel-substrate drift the discipline exists to catch.

### Search happens locally, not at Google

At pull time I can scope what I fetch using the Calendar API's time bounds and its free-text query parameter through Proxy, so I never pull the whole calendar. But that query parameter is coarse, keyword-level, not semantic. The real search runs over the local substrate after pulling: semantic via pgvector, structured via SQL, relationships via Neo4j. Google's query is a coarse first cut at pull time; the substrate is the actual search, and it does what Google's parameter cannot.

### Keeping it fresh stays free-tier

After the first pull I use Google's sync token, so each subsequent pull returns only what changed rather than the whole window. This stays inside free-tier Proxy because I orchestrate the incremental pulls myself, calling events.list with the sync-token parameter through Proxy. Nango's paid Syncs feature is Nango running that loop for me; I am not using it. The efficient pattern does not force the paid tier.

### When an entry changes

A change happens at the source, so the stored Meeting is stale until the next delta pull. The delta carries modified events (same event ID, new fields) and cancellations (a tombstone status), which is why storage keys on the Google event ID: a delta finds the existing record and upserts it or marks it removed. A content change also re-embeds and re-indexes, not just updates the row, so the vector index does not keep serving the old version.

The evidence-integrity question is separate from the cache-refresh one, and the code forced me to split two stores to answer it honestly. The live Meeting row is a mutable search cache: it upserts freely on every delta so search stays fresh. The immutable evidence record is the hash-chained audit event, which already snapshots payloads; it captures the Meeting's state at citation time. The citation pointer itself (`ArtefactCitation` at `shared_kernel/conversation_flow.py:137-152`, two fields, `artefact_id` plus `artefact_type`, no snapshot) resolves to current for display, while the audit holds what the recommendation actually saw; staleness is surfaced by comparing the two rather than silently serving the moved value as if it had always been so. That silent swap would breach no-silent-operation.

The sharp reason this matters here and not before: calendar is the first artefact whose cited state can change with no platform action at all. Portfolio's revisable artefacts (DataPoint implements Revisable per D125; Case-level revision is a future implementer) move only on a deliberate, audited, operator-caused revision, so an ID-only citation that resolves to current is tolerable for them. A Meeting moves because Google changed it asynchronously, outside any audited action, so the same ID-only citation becomes an integrity breach. Option (b), the two-store split above (live row mutable, audit snapshot immutable), is the mechanism. Option (a), making Meeting itself Revisable, is rejected unless (b) proves infeasible: it conflates external async change with operator revision and it touches the shared citation primitive every cell depends on.

The staleness window between a source change and the next pull is the price of storing, and it is never zero. I bound it with refresh-before-answer on time-sensitive reads (a cheap delta pull, then answer), which I can afford precisely because deltas are small in payload. Slower-moving queries serve straight from the store. The tiering of which reads refresh first is a brief-altitude knob.

### Push: a deferred trigger, not a replacement

Google's watch mechanism can push a thin change notification to a webhook of mine, but it is a trigger, not a data source: I still pull the deltas after a notification. On the Nango side it is free-tier feasible, because the watch registration and the delta fetch are Proxy calls and the notification goes from Google straight to my webhook, bypassing Nango's paid Webhooks feature. The real cost is operational and clashes with local-first dev: push needs a public HTTPS endpoint with a verified domain (a tunnel in dev), a channel-renewal lifecycle, and a safety-net pull anyway because delivery is not guaranteed.

Pull wins for the model I have: on-demand answers plus schedule-driven proactive surfaces like the daily briefing, which pull fresh when they fire. Push wins only for sub-poll-latency reaction to changes nobody asked about, which is not the current shape. So push is deferred until a feature genuinely needs it.

The one design instruction push leaves on S55, even while deferred, is precise about shape, and keeping it precise is mine to do because I just installed the rule that governs it. Build the delta-fetch-and-store pipeline trigger-agnostic, meaning a function that takes its trigger context as a plain parameter, with one poll caller today. It does not mean a trigger Protocol with a poll adapter and a stubbed webhook adapter: that would repeat the ChannelResolver mistake one session after retiring it. The v5 two-threshold Abstraction-threshold rule (`charter/methodology.md:535`) is explicit here: push is deferred, so the webhook trigger is merely anticipated, not structurally guaranteed this phase, and the rule's tell returns wait. A poll drives the function today; a webhook could drive the same function later as an added trigger source, not a second pipeline, and only then does the trigger boundary earn a Protocol. That is swap-is-config at the trigger layer, held to the threshold the method now sets.

### For the S55 brief

Settled (framing): pull scoped via Proxy; store as Meeting artefacts keyed on Google event ID; the live Meeting row is a mutable search cache that upserts on every delta and re-embeds and re-indexes on content change; the immutable evidence record is the audit-event payload snapshot taken at citation time, with staleness surfaced by comparing the live row against the snapshot and never silently swapped; search the local hybrid substrate; refresh via self-driven sync tokens; deltas upsert and tombstone the live row; bound staleness with refresh-before-answer; build the ingest pipeline trigger-agnostic as a function; push deferred.

S55 decides (brief): run the substrate-inheritance survey and name which ingestion ports Meeting inherits versus what calendar builds; the pgvector indexing schema for Meetings; confirm option (b) reuses the existing audit payload-snapshot machinery and wire Meeting state into the citation-emission audit event; refresh-before-answer thresholds and tiering against the named latency floor; stored time-window width and how it slides; sync-token-expiry full-resync handling (the 410 path); recurring-event exception handling (single instance versus series); encryption-at-rest reusing the P3 envelope encryption; the retention split (live-store purge versus audit retention).

Open confirmation before S55: read-only is assumed, with Google as sole writer and all changes flowing in through deltas. If the agent ever writes back to the calendar, that is a separate and larger bidirectional design and must be flagged.

Latency: deltas are cheap in payload, which helps quota, but refresh-before-answer puts a fixed external round-trip (local to Nango to Google and back) inside the turn, and that floor is independent of payload size. The pull-on-demand-at-turn-boundary commitment (`charter/deferred-decisions.md:731`) means time-sensitive calendar turns pay that floor every time. Name the round-trip floor in the turn-latency budget against the latency-tier routing primitive (D122) so refresh-before-answer tiering is a freshness-versus-latency trade against a real number, not a guess.

Discipline notes: the exact Calendar API parameters (the query parameter, sync tokens, the 410 path, watch semantics if push is later built) are reconciled against current Google Calendar API docs at adapter-build time, the same reconciliation that caught the Nango port gotcha. All Google API specifics live behind the calendar adapter and port, never in domain code, per no-vendor-SDKs-in-domain. Stored calendar data sits per-tenant, per database-per-tenant, and reuses the P3 envelope encryption for data-at-rest because attendee emails and locations are more sensitive than portfolio Cases.

Gating: this folds into the S55 calendar brief, which follows the verified Nango provisioning session. No separate session prompt; this entry is the durable record that the S55 brief absorbs.

  - triaged: 2026-05-28
  - resolution: note (durable design record, reconciled against code at HEAD `7385a77`). Three pressure-test findings integrated: evidence-versioning via the two-store split (option b); substrate-inheritance survey deferred to S55 framing with a reuse lean; trigger-agnostic specified as a function rather than a Protocol per the v5 rule. The settled shape promotes to charter at the S55 calendar protocol/auth/scope D-entry (`charter/deferred-decisions.md:459`) when S55 is drafted, not here.

## 2026-06-02 — [S55a-fix] Calendar sync: three live-smoke findings (nextSyncToken suppression, MockTransport blind-spot, Nango Bearer auth)

Source: the S55a Stage-1 calendar smoke executed live against the running self-hosted Nango and the operator's real Google Calendar (the build environment cannot reach docker/Nango/Google; this ran on the operator's machine). Three findings, recorded distinctly; the first two drive D149, the third pins an adapter test.

### Finding 1 — `nextSyncToken` is suppressed on a bounded/ordered full sync (the receive-side mirror of D148's send-side rule)

D148 reconciled the send side correctly: `events.list` rejects `syncToken` combined with `timeMin`/`timeMax`/`orderBy`/`q`/`updatedMin` (400). It was blind on the receive side: Google returns `nextSyncToken` **only on an unbounded full sync**. A time-bounded, ordered request (`timeMin` + `timeMax` + `orderBy=startTime`) returns events but **no token**. Measured live through the Nango Proxy on 2026-06-02: bounded request → 3 events, no `nextSyncToken`; unbounded request (no `timeMin`/`timeMax`/`orderBy`) → 35 events, `nextSyncToken` present. Same exclusivity rule, both directions. Consequence: `list_events_full` as built can never bootstrap incremental sync — `connections.sync_token` never populates, so the self-driven-token + 410-resync design is unreachable in practice. Resolved at D149 (option 4: scoped full-pull per refresh; incremental machinery dormant). The deletion mechanism reconciliation also landed here: `showDeleted=true` is documented to return cancelled events with `status="cancelled"`, is compatible with `timeMin`/`timeMax`/`singleEvents=true`, and returns 200 live — so the full pull tombstones via the existing `status=cancelled` path with no new deletion code (set-diff over the window was the documented fallback, not needed).

### Finding 2 — MockTransport unit tests verify the parse side, not the vendor emit side (methodology candidate, first instance on calendar)

The 13 `httpx.MockTransport` unit tests for the adapter could not catch Finding 1, and the reason is structural, not an oversight: a MockTransport test returns an **author-populated** response body (`_PAGE_BODY` carries `"nextSyncToken": "SYNC_NEXT"`), so the test asserts the adapter *parses* a token correctly — it can never assert that real Google *emits* one for the request shape the adapter builds. The mock is the author's model of the vendor, not the vendor. This is the S4 Langfuse shape recurring (a vendor-deployment/contract specific that drifts and produces a misleading signal; here the misleading signal was green unit tests plus an absent token at runtime). First instance of this specific "mock encodes the assumption under test" shape named on the calendar context. Methodology lesson (promoted at D149's methodology clause): framing-altitude vendor-API assumptions need a **live-contract reconciliation gate**, not only a docstring reconciliation — the docstring reconciliation D148 did was necessary but caught only the direction the author thought to check.

### Finding 3 — Nango 0.70.5 rejects HTTP Basic on the Proxy with a misleading `not a UUID v4` error; the adapter must send `Authorization: Bearer`

Provisioning verification surfaced that Nango 0.70.5's Proxy/REST API rejects HTTP Basic auth (`-u <secret>:`) with `{"code":"invalid_secret_key_format","message":"...not a UUID v4"}` even when the secret key **is** a valid UUID v4 — the error names the wrong cause. `Authorization: Bearer <secret_key>` is accepted. The `NangoProxyCalendarAdapter` already sends Bearer ([nango_proxy_calendar_adapter.py:121](../contexts/calendar/adapters/outbound/nango/nango_proxy_calendar_adapter.py)), and the live Stage-1 pull confirms it; S55a-fix adds an explicit MockTransport assertion pinning the `Bearer` form so no future refactor silently regresses to Basic and chases the misleading error. Discipline note: a vendor's auth-rejection error message is not to be trusted at face value when a deployment-version gotcha is plausible — confirm the accepted form empirically.

  - triaged: 2026-06-02
  - resolution: Findings 1 and 2 acted on at D149 (`charter/decisions.md`) — scoped full-pull resolution plus the live-contract-reconciliation-gate methodology clause; Finding 3 pinned by a unit test at S55a-fix Commit 4 and recorded as a standing adapter constraint. No further deferral; the methodology promotion question (does the live-contract-reconciliation-gate become a charter/methodology.md entry) carries to the next phase audit at second instance per the promotion threshold.

## 2026-06-02 — [S55a-fix] Host-port-binding enforcement was silently red, masked by stale bytecode (project-tooling)

Source: the S55a-fix AC12 close run. `uv run pytest tests/_enforcement/` failed on `test_host_port_bindings_match_allowlist`, and clearing `__pycache__` was required before the failure read truly: the first run's `extras` dict was conflated by stale `.pyc` bytecode that still carried the repo's former absolute path (`/Users/sabu/Zephyr/...`, pre-rename), so the traceback pointed at a directory that no longer exists. With clean bytecode the real state showed two services with host-port bindings outside the allowlist: `padhanam-api` `127.0.0.1:8000:8000` (added at `7af8e88` for webhook smoke) and `nango-server` `3003`/`3009` (added at the Nango provisioning session `e3b7d9e`). Both commits added a loopback dev binding to `compose.yaml` but skipped the same-commit allowlist edit the test's own docstring mandates — so the host-port-binding contract had been **red since `7af8e88`**, through the Nango session and S55a close, while close markers claimed "AST enforcement green."

Two findings:
- **The enforcement-layer claim was not being verified.** Sessions asserted AST enforcement green without `tests/_enforcement/` actually passing for this contract. Either `make lint` was not run at those closes, or it was run against stale bytecode whose conflated output was misread. The lesson: a green claim on an enforcement layer must come from a clean-bytecode run of that exact layer, not from memory or a partial run. Project-tooling discipline: run `make lint` from a clean `__pycache__` (or add a clean-bytecode/`-p no:cacheprovider` step) as the close gate, and treat a moved/renamed repo root as a trigger to purge `__pycache__` (resolved `co_filename` in old `.pyc` survives a move and corrupts tracebacks).
- **Allowlist-sync drift is the exact drift this test exists to catch, and it still slipped twice.** The test forces the operator to edit the allowlist in the same commit as a `compose.yaml` binding change; two commits bypassed it because the test was already red and the new red was indistinguishable from the standing red. A red enforcement test masks subsequent violations of the same contract — so a red enforcement layer is not just a missing check, it is an actively-degrading one. Reinforces: never leave an enforcement test red across a close.

  - triaged: 2026-06-02
  - resolution: fixed in-session at S55a-fix — both `padhanam-api` and `nango-server` loopback bindings added to `_ALLOWLIST` with inline provenance comments (legitimate `per S5` loopback dev exceptions, same class as `postgres-control-plane`); `tests/_enforcement/` green; 37/37 import-linter contracts kept. No D-entry (vendor/tooling hygiene, not an architectural decision). Recurrence test: a third allowlist-sync miss, or a second stale-bytecode-masked enforcement failure, promotes the clean-bytecode-close-gate to a `charter/principles.md` Token-discipline/tooling note. The "never leave an enforcement test red" lesson is already charter-grade (the S5 reflection's "checklists drift, AST tests do not"); this entry records that an AST test left red defeats that guarantee. **Update (S55b-1, 2026-06-02):** the clean-bytecode-close-gate was hardened to the Makefile at S55b-1 commit 0 (the `clean-pyc` prerequisite on `lint`/`test`) and the lesson promoted to `charter/methodology.md` Patterns-observed (2026-06-02) — ahead of the recurrence threshold, because S55b-1 is the first close post-rename and the operator chose to harden rather than wait for a second instance.

## 2026-06-02 — [S55b-1] S55a-fix live verification used synced source, not a baked image; baked-image + cancellation confirmations fold into the S55b-1 close smoke

Source: S55b-1 pre-write reconciliation, reviewing how the S55a-fix calendar smoke was verified live.

The S55a-fix live smoke (Stages 1–3 green against `tenant_a` and the real Google Calendar) ran against working-tree source injected into the running `padhanam-api` container via `make sync-code` (the S41 dev fast-path: `docker compose exec python` starts a fresh process that imports synced source from disk), **not** against a rebuilt baked image. The committed `padhanam-api:dev` image digest therefore predates the calendar fix — the fix is verified in source but not yet in the artifact the digest pins. This is honest dev-fast-path verification (the code path exercised is identical; only delivery differs), but it leaves two confirmations open:

- **Baked-image confirmation** that the calendar fix is in the built artifact, not just synced source — folds into the S55b-1 close smoke, which rebuilds the image (`make build-api`) and re-runs S55a Stage 1 against it.
- **The live cancellation-tombstone sub-step** (S55a Stage 2 step 3): operator-gated because the granted scope is `calendar.readonly`, so the build agent cannot cancel a calendar event to drive the tombstone path live. The tombstone-via-full-pull path is unit-proven (`test_cancelled_event_is_tombstoned_via_full_pull`); the live confirmation folds into the S55b-1 close smoke if the operator has cancelled an in-window event, else remains operator-gated and is recorded as such.

  - triaged: 2026-06-02
  - resolution: note (residue-closure plan). Both confirmations are scoped into the S55b-1 close smoke (`docs/smoke/p15_s55b1_calendar_conversation.md`), which rebuilds the baked image first. No charter change; this is verification-residue bookkeeping, not an architectural decision. **Update (S55b-1 close, 2026-06-03):** baked-image confirmation executed live (digest `c1d5c067…`; the `show_deleted` param confirmed in the artifact; Stage 1 green); the cancellation tombstone remained operator-gated at S55b-1 close and carries to the S55b-2 close smoke.

## 2026-06-02 — [S55b-2] Two process notes: build-prompts must not direct methodology promotions; the closed-union touchpoint checklist for new cells

Source: S55b-2 pre-write reconciliation, acting on the D47 tension the S55b-1 close surfaced.

### Prompt-drafting: a build prompt may direct a build-mode observation to the living-hypothesis surface, but must never direct a methodology *promotion*

The S55b-1 prompt directed the clean-bytecode promotion to `charter/methodology.md` as a build task. Under D47 a methodology promotion is a strategic-mode deliverable — it is ratified strategic-mode and recorded in a charter commit with explicit strategic provenance — whereas a build session's legitimate charter writes are session-scoped (session-log entries, captures, the D-entries and current-package/architecture touchpoints a build necessarily lands). D47's realistic reading is that it governs the *authority and provenance* of a methodology promotion, not the file-write mechanics (every charter file commits through the build UI; a strict no-build-write reading would make `methodology.md` uncommittable). The discipline forward: a strategic-mode prompt drafts methodology promotions; a build-mode prompt may at most route a *build-mode observation* to the living-hypothesis surface (D40/D113) and flag a promotion *candidate*, never direct the promotion itself. The S55b-2 charter commit applies the provenance correction to v6 (annotate, not revert — a revert would discard a true lesson).

  - triaged: 2026-06-02
  - resolution: acted on at S55b-2 commit 1 (the v6 provenance annotation). Recurrence test: a second build-prompt-directed promotion promotes this to a `charter/methodology.md` process note; single instance for now.

### Closed-union touchpoint checklist for adding a conversation cell

Adding a ConversationFlow cell touches a known set of closed unions, and S55b-1 hit all of them ad hoc (each surfaced as a test failure or a reconciliation finding rather than from a checklist): the `ArtefactCitation` discriminator (`KNOWN_ARTEFACT_TYPES`, shared_kernel) — already carried `meeting` from S55a; `KNOWN_TARGET_CELLS` (messaging pending_clarification) — needed `calendar_conversation` added; `INTENT_CLASSES` / `INTENT_SURFACES` (intent_classification_evaluation gold_set) — needed the calendar classes + surface; and the meta-classifier `cell_identifier` enum (`shared_kernel/meta_classification.py`) plus the `CellIdentifier` dispatch map — extended at S55b-2 for routing. Forward: a cell-adding prompt (S56 email five-way) names these four closed unions upfront so they are extended deliberately in one pass, not discovered one failing test at a time.

  - triaged: 2026-06-02
  - resolution: note (reusable checklist). S56's email-cell prompt should carry the four-union list; if S56 hits a *fifth* closed union not on this list, the checklist gains an item.

## 2026-06-03 — [S55b-2] Audit `after_state` encryption-posture backward check (no pre-existing leak; calendar is the first D21-content case; the general guard defers)

Source: the S55b-2 citation-snapshot work surfaced that audit `after_state` is plaintext JSONB at rest and the draft-then-recompute pattern does not encrypt it — a property of the **audit subsystem**, not of calendar. The operator asked for a bounded backward check: has any prior audit event frozen sensitive tenant content into `after_state` in plaintext, which would be a D21 envelope-encryption gap predating calendar?

**Method.** Static enumeration of every `after_state` writer (the seven per-context `application/audit_events.py` modules) plus a runtime query of distinct `(resource_type, action_verb)` in tenant_a's `tenant_audit` store.

**Findings.** Content-bearing `after_state` payloads: portfolio `case.create` (`title`), `data_point.create`/`revise` (`value`); intake `record.create` (`intent_hint` only, not the raw message); messaging `pending_clarification.create` (`proposed_action_summary`, which can echo user words); messaging `message.*` (direction/channel/status/external_id — **no body**); optimization `recommendation.generate` (`subject`/`text` — platform-generated optimization recs, not tenant PII); the evaluation runs (IDs/metrics/hashes/model identifiers). The decisive distinction: portfolio Case `title` is `sa.Text` and DataPoint `value` is `pg.JSONB` — **plaintext at rest in the portfolio store itself** (no `enc_*` columns; portfolio content was never D21-classified). So portfolio's plaintext `after_state` is **consistent with its store's posture, not a leak**. The only context whose store envelope-encrypts its content (D21) is calendar (`meetings.enc_ciphertext`), and its `meeting_citation` `after_state` snapshot **encrypts** that content. **Conclusion: no historical exposure** — no content that any store envelope-encrypts has ever sat plaintext in the audit store; `meeting_citation` is the first D21-encrypted-store content to reach `after_state`, and it is encrypted.

**Two-threshold disposition.** Calendar is the **first** instance of D21-encrypted-store content in `after_state`; the backward check found no prior instance. So the general guard ("no plaintext D21-classified content in any audit `after_state`") **defers** per the two-threshold rule; the documented constraint plus calendar's encrypt-in-`after_state` precedent (recorded in `charter/architecture.md` "Citation-time audit-snapshot evidence") stand as the interim. The guard flips to **overdue** if either (a) a second cell freezes encrypted-store content into audit, or (b) the operator decides portfolio content should be D21-classified (see the deferred-decisions entry), which would retroactively make portfolio's `after_state` a second instance plus require a store + historical-audit backfill.

  - triaged: 2026-06-03
  - resolution: note + one deferred question forwarded to `charter/deferred-decisions.md` (portfolio/intake/messaging content-at-rest D21 classification). No fix needed for the leak-relevant property (none exists today). The general `after_state` guard is two-threshold-deferred; the constraint is documented. The portfolio-content-encryption classification is a strategic procurement question the operator frames; recorded as deferred, not decided here.
