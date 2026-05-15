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
