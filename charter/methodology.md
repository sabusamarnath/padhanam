# The Padhanam Methodology

The articulation of how Padhanam works. Read at strategic sessions; revised at phase audits with the version log appended at the end. Per D39.

## What Padhanam is

Padhanam is two artefacts produced together. A platform built to enterprise-grade architectural standards (multi-tenant, identity-federated, audit-chained, jurisdiction-aware, OTel-instrumented), and the methodology that produced it: a discipline for senior product leaders directing end-to-end implementation through AI-assisted development without writing code. The platform is the artefact that proves the methodology; the methodology is the proprietary insight the platform is evidence of. Both are case-study artefacts, audited against the level of complexity that real enterprise software requires.

The bet is articulated in `charter/bet.md` and externally in `charter/prfaq.md`. Phase 1 is the substrate that proves the bet's load-bearing claims: that architectural discipline survives AI-assisted implementation, that mechanical enforcement scales while operator attention does not, that observability with cost dimension produces optimization recommendations enterprise procurement reads as defensible. Phase 2 direction is decided at the Phase 1 close audit based on what Phase 1 surfaces about the proposition, the methodology, and operator capacity.

## What's being investigated

The role being exercised in Padhanam does not have a settled name. The operator is a senior product leader. The implementation is performed by Claude Code. The relationship between the two is the unit of analysis: the operator defines intent, constraints, and architectural commitments; the model produces code, tests, schema, migrations, and commits within those constraints; the operator reviews, audits, and corrects. The methodology documents what works and what does not in that relationship, with enough specificity that another senior product leader could read it and adopt the discipline.

The structural disciplines below (mode separation, frameworks, charter shape, enforcement, reflection, capture, measurement, cost) are committed via D-entries and enforced mechanically. The pattern and failure-mode observations later in the document are descriptive: they accumulate as Phase 1 progresses and are reviewed at phase audits. The methodology is open to its own revision based on measurement evidence; if at any phase audit the evidence stops supporting the proposition, the bet document and this document are revised to reflect what was actually learned. Honesty about the experiment is more valuable than the experiment succeeding in any particular form.

## Two-surface mode separation

Strategic mode and build mode are different work modes with different deliverables. Strategic conversations produce charter edits, session prompts, or roadmap version updates. Build sessions produce code commits and session-log entries. The two-surface model is conceptual, not UI-bound: implementation collapses to Claude Code as the primary surface, with Claude.ai used opportunistically for audits and architectural reasoning. Mode separation is maintained by mode declaration at conversation start, distinct deliverables, and distinct commit conventions (`docs(charter): ...` or `docs(pN/<boundary-name>): ...` for strategic; `feat(pN/sN): ...` and `docs(pN/sN): ...` for build). Per D47.

The two functions need different outputs and different rhythms. Without explicit mode separation, strategic reasoning gets compressed into rushed pre-build framing or scatters through code commits, and build sessions get derailed by architectural questions that should have been settled first. Mode declaration is the load-bearing discipline because the UI is the same; without the declaration, charter-edit work and implementation work collapse into unbounded conversations that produce neither shape well. The charter files are the persistent bridge between modes regardless of which UI is active: decisions made in strategic mode become constraints in build mode, and audit findings flow back through the same files.

## Work hierarchy

Padhanam organises work in a four-level tree.

- **Bet** at the root. Articulated in `charter/bet.md`. Externally in `charter/prfaq.md`.
- **Initiatives** below the bet. Phases. Phase 1 (in progress) is the learning sprint that proves the proposition; subsequent phases decided at audit boundaries.
- **Epics** below initiatives. Packages. Twelve packages in Phase 1, ordered for dependency clarity and learning value, RICE-scored per D42.
- **Stories** below epics. Sessions. Each session has acceptance criteria, reflection prompts, and produces a session log entry.

The full tree lives at `charter/roadmap.md` per D44 as the canonical living artefact, versioned with reasoning categories on every change (discovery, capacity, signal, hedge).

Each level is a different forecasting horizon. Bets are multi-year. Phases are multi-month. Packages are multi-week. Sessions are single-day. Conflating horizons produces commitments at the wrong altitude: bet-level forecasts at the package level produce overcommitment to specific implementations before the substrate is understood; package-level forecasts at the bet level produce strategic drift toward whichever package the operator is currently shipping. The hierarchy enforces strategic placement at the right altitude before option assessment or sequencing begins.

## Frameworks

Three frameworks operate at three different moments. Per D42.

**LVT** (Lean Value Tree) places work in the strategic tree. Used at framing to confirm where new work sits in the bet → initiative → epic → story hierarchy.

**Kano** evaluates options at decision points. D-entries that select between alternatives carry a Kano category field at the bottom of the entry: must-have (absent of which breaks the bet), performance (scales the bet linearly), delighter (disproportionate value relative to cost), indifferent (neutral, named so it does not accumulate as ambition), or reverse (actively erodes the bet despite looking attractive). The convention applies from D41 forward.

**RICE** prioritises sequencing. Reach × Impact × Confidence ÷ Effort. Recorded explicitly on packages and on implementation backlog items where sequencing involves real choice. Phase audits review score honesty (forecasts versus post-hoc rationalisations).

Without explicit categorisation at the decision moment, "must-have" stretches to mean "felt rigorous while deciding" and prioritisation becomes post-hoc rationalisation. The frameworks operate at distinct moments of the work; conflating them produces ceremony without reasoning value. Kano at framing forces honest assessment of which features actually move the bet versus which look attractive but do not. RICE at sequencing forces honest forecasting, with phase audits checking whether scores were defensible rather than convenient. Phase audits also review distribution (too many must-haves suggests conflation with default; too many delighters suggests features added without honest weighting) and roadmap reasoning-category distribution per D44 (too many capacity-driven changes mean the bet was overscoped; too many signal-driven changes mean it was poorly grounded; too many hedge entries mean the operator is avoiding commitment).

## Reading as the primary tool of the role

The operator's primary tool in this operating model is reading. Reading the latest session log tail. Reading the active package's `current-package.md`. Reading `principles.md` before each session. Reading the relevant `decisions.md` entries for the area being touched. Reading the model's work after the session and before the merge. Most operator-and-implementer drift is preventable by the operator having read the right thing at the right time.

The token discipline in `principles.md` is a budget for the model's reading; the operator's reading is unconstrained and is the higher-leverage half of the discipline. What this looks like in practice changes over time as the codebase grows. Early sessions allowed full-file reads in most places; later sessions require ranged reads against larger files and selective archival of working documents to keep them tight. The reading discipline is not static; the volume scales with the codebase, and the structural-promotion threshold (a comment-level rule that bites three times across a package gets promoted to a parser- or AST-level test) is partly about reducing the operator's reading load by moving rule-checking from review to mechanical enforcement.

## Architectural direction without the architect identity

The operator is not an architect by career or title. The work being done in some sessions is architect-adjacent: defining boundaries, enforcing principles, making structural decisions about ports and adapters, deciding what belongs in the shared kernel and what does not. AI-assisted development makes this kind of work accessible to a senior product leader who has the domain understanding and the seniority to make the judgement calls, even without the engineering identity that would traditionally produce architectural authority.

The methodology distinguishes this from architecture as a profession. The operator is not designing systems from scratch; the operator accepts, modifies, or rejects structural proposals from the model, informed by enterprise procurement experience and product judgement. The model surfaces the technical options; the operator picks among them with reference to constraints the model cannot fully see (regulatory direction, what real enterprise buyers will accept, what the long arc of the platform requires). This is what the bet's architect-implementer pattern actually consists of in practice. The role is not "product leader pretending to be architect"; it is product leader exercising structural judgement against options the model surfaces, with the architectural authority coming from the seniority of the judgement rather than from engineering identity.

## Session shape

Sessions follow Design → Build → Test → Close. Each session has a brief that names the package, the scope, and the constraints inherited from prior decisions. The brief is short and explicit. Vague briefs produce vague work: the model fills ambiguity by making choices, and operator-and-implementer drift starts there. The session-prompt convention (package and session identification, goal stated as artefacts at session close, context to read first, charter updates required, substantive work in commit-shaped units, acceptance criteria, reflection prompts, out of scope, session log entry instruction) is the structural defence against ambiguous briefs.

Browser interactive verification is the success criterion for any acceptance criterion that involves a UI surface, not CLI smoke. CLI smoke alone passes while the user experience is broken; both must be verified. The discipline lands from the S4 lesson and applies universally to any UI-bearing acceptance criterion.

## Charter structure

The charter is the methodology's primary artefact surface. Each shape serves a different audit purpose.

**Strategic constants:**
- `charter/bet.md` — strategic articulation of what Padhanam is and why
- `charter/principles.md` — engineering principles, decision discipline, security posture, token discipline
- `charter/methodology.md` — articulation of how Padhanam works (this document)

**Living documents:**
- `charter/phase-N-prd.md` — phase-level PRD with original draft and as-built sections, per D43
- `charter/prfaq.md` — storytelling artefact in external voice, refreshed at every phase audit, per D45
- `charter/roadmap.md` — LVT tree with versioned course changes, per D44
- `charter/packages/pN-epic.md` — package epic note at package open, reconciled at package close, per D43 (from P4 forward)

**Append-only logs:**
- `charter/decisions.md` — numbered D-entries with choice, reasoning, alternatives, and Kano category from D41 forward
- `charter/deferred-decisions.md` — forward-looking commitments that activate when their context arrives

**Active surface:**
- `charter/current-package.md` — active package goal, sessions, status, carryover
- `charter/schema.md` — database schema, updated in-commit with migrations
- `docs/archive/packages/pN.md` — per-package archive at package close, per D31

**Operational:**
- `CLAUDE.md` — Claude Code's operating manual; reading order and standing rules
- `README.md` — project entry point
- `log/sessions.md` — append-only session log with reflection density per session
- `log/captures.md` — mid-session catch surface, triaged at session or package close, per D48
- `log/audits.md` — phase audit findings with measured-outcomes sections from D40 forward
- `log/packages.md` — package retrospectives with measured-outcomes paragraphs from D40 forward
- `ops/scheduled_checks.yaml` — supply-chain hygiene cadence

Strategic constants articulate the position; if they edit, the audit trail of how the position evolved disappears. Living documents capture intent at draft time and reality at close, with the delta as the audit deliverable. Append-only logs preserve the full decision history for retrospective analysis. The active surface gets tight token discipline because session-time costs accrue to it and accreted content slows every session. Each shape's constraint is what gives it its specific audit value; collapsing the shapes (e.g., letting the active surface accrete forever or letting decisions edit) loses that value.

## Append-only discipline

The charter is append-only at the entry level for logs, at the version level for living documents, and at the section level for strategic constants. Historical D-entries, principles content, and session log reflections are not edited in place; they are added to. Living documents preserve original drafts alongside as-built reality; each new version appends rather than replaces. AST tests in `tests/_enforcement/` catch in-place edits at CI; the violation count is itself a measurement layer.

Edited charter loses audit-trail value. The case study's audience reads the charter as evidence of whether the methodology produces honest decisions; if past decisions can be silently revised to look better in retrospect, that evidence is worthless. The S8 lesson (recovery from in-place edits via git restoration) made the principle explicit at D29; mechanical enforcement followed because operator vigilance does not scale to a 200-commit codebase. The discipline applies symmetrically to errors: a mistaken D-entry is corrected by a new D-entry that supersedes it, not by editing the original.

## Architectural enforcement

Architectural commitments are enforced mechanically, not by review.

Import-linter contracts (15 at P3 close) make architectural rules CI failures: vendor SDKs cannot be imported by domain code (D4), bounded contexts cannot cross-import (D16), configuration access is confined to the configuration layer (D19). AST tests catch rules import-linter cannot express, including D19's no-`os.getenv`-outside-config and the no-vendor-in-domain check that joined it at P2 close. Tenant-isolation tests in `tests/contract/tenant_isolation/` are red-team-shaped: each test attempts unauthorised cross-tenant access and asserts it fails (D24), because test-it-works tests pass on broken implementations. Schema discipline requires `charter/schema.md` updates in the same commit as migrations. Charter touch-points are listed in `CLAUDE.md`: schema, observability metrics, architectural decisions, and course changes each have specific files that must travel with the code.

Review does not scale. Operator attention is the bottleneck; mechanical enforcement is the only way the architectural surface keeps up with a growing codebase. Every rule that lands as a CI failure rather than a review comment is a rule the operator no longer has to remember to check. The enforcement count is itself a measurement layer in the methodology: the trajectory through Phase 1 should be upward, and the structural-promotion threshold (a comment-level rule that bites three times across a package gets promoted to a parser- or AST-level test) is the convention that grows the surface honestly.

## Reflection and learning

Session log entries include a reflection section with substantive paragraphs of operator thinking. Reflection density distinguishes session types per D47: strategic conversations produce shorter entries focused on what was decided; build sessions produce longer entries with substantive reflection on what was learned. The mix over time is signal at phase audits.

Each session log entry carries a one-line `roles:` tag naming which of the five role-functions were exercised (analyst, PM, architect, engineer, technical writer), per D46. Distribution over time surfaces atrophy: many consecutive engineer-only sessions mean the analyst, PM, or technical-writer functions are not being exercised, and the case study's proposition (that all five product-leader functions can be sustained through AI-assisted implementation) loses evidence at audit.

Phase audits review the charter against built reality across five role-function categories per D46: analyst (bet evidence and grounding, market assumptions checked), PM (prioritisation defensibility, RICE-score honesty, scope discipline), architect (D-entries with non-trivial alternatives, principles catching real drift, contract enforcement), engineer (implementation against architectural commitments, test density, mechanical enforcement), technical writer (charter legibility to a non-author reader, narrative coherence across artefacts). Each category is audited against its own quality bar. Phase audits produce a new roadmap version per D44, a new PRFAQ version per D45, the phase PRD as-built section per D43, drift findings, framework distribution checks, and metric review.

Reflection is the methodology's primary substrate. If session logs are mechanical records of what was done, the methodology produces no learning, and phases close with code shipped but with nothing to teach the next phase. Reflection density on conversation type respects that strategic conversations decide things and build sessions learn things; forcing identical depth on both produces theatre at one end and corner-cutting at the other. Role-function tags surface atrophy at session granularity, which is the only granularity at which it is recoverable.

## Capture and triage

Mid-session stray thoughts go to `log/captures.md` per D48 rather than derailing the current session. Triage at session close or package close classifies each entry into one of five impact types:

- **Quick task** — do now (under five minutes; lands in the current session as a small commit if the session is still open).
- **Inject** — insert into the current package as a new session or scope adjustment to an existing session.
- **Defer** — record for a later session, named explicitly where activation context is known.
- **Replan** — rethink scope at the package or phase level; surfaces at the next strategic conversation.
- **Note** — record only, no action; preserved for audit-trail purposes.

Without the capture surface, mid-session stray thoughts derail current sessions or get lost. Five-category triage forces explicit decision on each item rather than letting captures accumulate as a backlog of guilt. The append-only nature preserves the audit trail of what surfaced and how it was handled; the triage discipline is what prevents the file from becoming a graveyard. The discipline is structural recognition that good ideas surface at inopportune times, and that the cost of dropping them and rediscovering them later is higher than the cost of recording them and triaging deliberately.

## Measurement model

Per D40, the methodology is measured against a model with four bet-native layers and an industry overlay. Reviewed at every phase audit. Reported even when the trend does not flatter the bet.

**Bet metrics** measure operator fluency, the deliverable Phase 1 commits to. Leading indicators: time-to-decision on D-entries, reflection density quality, framework usage at appropriate moments. Lagging indicators: self-assessed fluency at phase boundaries, ability to direct enterprise-grade implementation without code-level intervention.

**Discipline-adherence metrics** measure whether the methodology is being followed as articulated. Charter touch-point compliance (schema updates with migrations, D-entries before code, current-package status currency). AST test pass rate. Append-only violation count. Decision-to-code translation (every D-entry produces a corresponding code or charter change within the next session).

**Architectural-durability metrics** measure whether the artefact is built to the standard the bet claims. Import-linter contract count and trajectory. Drift findings per audit. Test density per package. Supply-chain check cadence adherence per `ops/scheduled_checks.yaml`.

**Bet-direction integrity metrics** measure whether the methodology is staying on the bet versus drifting into adjacent shapes. Roadmap reasoning category distribution per D44. PRD delta size at audit. PRFAQ coherence across versions. Role-function activity distribution per D46.

**Industry overlay** runs alongside as table-stakes for enterprise-procurement comparison. Phase 1 uses the following definitions; full instrumentation activates at Phase 2 when production deployment context arrives.

- *Deployment frequency.* Phase 1 proxy: merged-to-main frequency (sessions per week with commits merged to the main branch). Production deployment frequency replaces the proxy when a hosted environment exists; the shift is recorded in the session log.
- *Lead time for changes.* Time from session brief written (or session start where no brief exists) to commits merged. Captured per session at close.
- *Change failure rate.* Percentage of sessions whose output is later reverted, hot-fixed, or required a corrective session. A session is a failure if a subsequent session within the same phase is tagged corrective and points back to it. Self-correction within the same session does not count.
- *Mean time to restoration.* For any session whose output is later identified as wrong, time from the introducing session's close to the corrective session's close. Reported as a distribution rather than a single mean, because long-tail incidents distort the average.
- *Reliability.* Percentage of sessions closing clean: tests passing, principles intact, charter touch-points updated as required, no drift carried forward. The discipline-holding metric and the one most directly testing whether the methodology sustains under pressure.
- *Developer experience.* Captured qualitatively in package retrospectives and phase audits using CORE4 dimensions (flow state, feedback loops, cognitive load). The operator's experience operating Claude Code is the unit of measurement, since the proposition is about the role being demonstrated.
- *Contribution effectiveness.* Proportion of merged work that advances the platform substantively versus cleanup, rework, and corrective effort. Computed at package close from session classification tags.

Bet-native metrics are the differentiator: they measure whether the proposition is being demonstrated, which industry metrics alone cannot do. DORA tells nothing about whether the methodology produces enterprise-defensible decisions or sustains the architect-implementer pattern under capacity pressure. Industry metrics are also necessary: bet-native metrics alone are unverifiable to an enterprise-procurement audience that reads DORA and CORE4 as table-stakes. The combination is what audit-shaped reporting requires. Honest reporting is itself a discipline; periods of poor methodology performance are reported alongside strong periods, because the case study's credibility depends on it.

### Session log tagging block

Each session log entry, in addition to scope and outcome content, includes a structured tagging block at close. The block is short and follows a fixed format so the metrics are computable without re-parsing prose:

```
metrics:
  classification: [new_work | corrective | audit | planning | reframe]
  brief_started: [ISO timestamp or "no brief"]
  session_started: [ISO timestamp]
  session_closed: [ISO timestamp]
  merged: [ISO timestamp or "deferred"]
  close_state: [clean | drift_caught | drift_deferred | failed]
  tests_passing: [yes | no | n/a]
  principles_intact: [yes | drift_corrected | drift_deferred]
  charter_touchpoints: [updated | n/a | deferred]
  corrects: [list of session IDs this session corrects, or empty]
  corrected_by: [populated retrospectively when a later session corrects this one]
```

The `corrected_by` field is populated retrospectively by the corrective session adding a backreference. This is the mechanism by which change failure rate becomes computable: a session whose `corrected_by` is non-empty counts as a failure for the cadence in which it occurred. The tagging takes roughly two minutes at session close and is the source data for everything downstream; without it, the metrics cannot be computed.

### Cadence

Per session: structured tagging captured at session close, two minutes. Per package close: metrics computed over the sessions in the package window, measured-outcomes paragraph appended to the package retrospective in `log/packages.md` per D40. Per phase audit: metrics computed over the full phase, measured-outcomes section appended to the audit entry in `log/audits.md`, methodology document updated with patterns the metrics surfaced. Phase-level numbers are where trend analysis lives; package-level numbers are noisy at boundaries because the sample is small but useful for surfacing patterns within the package and for the failure-modes section of this document.

### What the numbers are not

The metrics measure the methodology, not the operator. Sessions producing drift are not failures of competence; they are failures of the discipline as it stood at that point, and they typically produce a principle update, a decisions entry, or a methodology refinement that prevents recurrence. The methodology improving over time is the expected result; if the metrics get worse over time, that is itself an important finding the case study should report honestly.

The metrics also do not measure the platform's quality as a product. The platform is the artefact through which the methodology is demonstrated. Platform quality is a separate concern (covered by the test suite, contract tests, security posture) and is not what the DORA and CORE4 measurement is for.

The specific computation tooling, reporting format, and benchmark comparisons are committed when the data exists to inform them, per the deferred-decisions entry on methodology metrics. Premature tooling commitment ahead of data shape is paper architecture.

## Cost commitment

Per D41, cost capture and per-tenant attribution are Phase 1 architectural commitments. Phase 1 packages land cost as follows.

P4 framing wires gateway-side cost capture: a pricing table at `padhanam/config/inference.py`, an OTel attribute extension on the inference adapter joining token counts to USD, and trace-handler emission of `gen_ai.cost.input_usd`, `gen_ai.cost.output_usd`, and `gen_ai.cost.total_usd` attributes on every completion.

P4 schema migration adds the per-tenant cost-attribution column to the control-plane tenant registry. This is a retrofit relative to landing it at P3 open; the alternative of deferring to production traffic surfacing the problem would compound, and the case study's posture treats avoidable retrofit as a learning failure.

P5 evaluation harness implements cost-per-successful-task per D8's prior commitment.

P11 ships cost-aware optimization recommendations as a first-class surface on the recommendation API.

Cost ceilings, multi-tier model routing, and progressive throttling defer to Phase 2 per `charter/deferred-decisions.md`. The configuration columns for ceilings can land at P4 alongside the cost-attribution column to avoid retrofit; the enforcement architecture activates when production traffic exists. The pricing table is reviewed monthly per `ops/scheduled_checks.yaml`.

Cost is constitutive to the optimization-recommendation differentiator (D9), not adjacent to it. Without cost data attached at the trace level, the recommendation surface produces "this is faster" or "this is higher-quality" but never "this costs N% more for M% quality at the same task type." The third recommendation shape is what makes the optimization layer enterprise-defensible; without it, recommendations are interesting but not procurement-grade. Per-tenant attribution as a column rather than a downstream aggregation keeps "what did this tenant cost" answerable as a single SELECT, which matters for any tenant-cost reporting from P9 onwards.

## Patterns observed

Operational patterns that surface during sessions. Entries are added when a pattern recurs, not on first observation; they are dated and short. Patterns that recur and then stop recurring (because the underlying issue was solved structurally via a principle update, AST test, or D-entry) are noted and archived rather than deleted, so the document preserves the audit trail of how the methodology evolved.

### 2026-05-06 — Commit-shape granularity adjusts session-to-session through specific surface causes

Visible across at least four sessions in two related sub-shapes. Both share the deeper observation that commit shape is emergent from session-specific surface causes, not deliberate.

*Sub-shape A — rebrand-class coordinated rename across multiple files.* S8 (Quorum → Zephyr) and S13 (Zephyr → Padhanam) are the instances. S13's reflection prompt 5 articulates the lineage: "S13's seven-commit shape adjusts the S8 five-commit shape only by adding the AST-enforcement-discovery commit (which S8 didn't have because the S7 workspace-manifest discovery helper landed after S8) and the explicit working-directory housekeeping commit." The two extra commits at S13 are session-specific surface causes — an enforcement layer that grew between S8 and S13, and operator-only working-directory housekeeping that has to land separately because Claude Code cannot `mv` its own cwd — not template variation.

*Sub-shape B — a change with consumers that must update in the same commit, or the commit must encompass the pair.* S14 (schema-and-adapter pair: NOT NULL migration plus the registry-adapter consumer change) and S15 (signature-and-consumers pair: port signature widening plus the router and adapter consumer updates) are the instances. The S15 session-log methodology line is the recurrence-articulation moment: "any change that widens a function or method signature should explicitly enumerate the consumer call sites that must update in the same commit, or the commit-shape granularity should treat the signature-and-consumers pair as one commit. The pattern recurred at S14 and S15; if it recurs again at the next package boundary, the structural-promotion threshold suggests promoting the discipline to a session-prompt convention."

The two sub-shapes are different surface causes (rename-across-files vs change-with-consumer-pair) but share the underlying observation that the prompt's commit-shape granularity has to adjust in-session to honour what the session actually surfaces. The discipline is to honour the surface causes with commit-shape granularity rather than fight them into a uniform commit shape; commit count is emergent, not a target.

Status: descriptive, active observation; no fix proposed. Sub-shape B carries forward the structural-promotion threshold note from S15 — if the consumer-pair shape recurs at the next package boundary, the discipline gets promoted from session-prompt-shape convention to session-prompt structural element. If commit shapes settle into a stable convention because the surface causes stop varying, this entry is archived with a note explaining the structural change that resolved it.

## Failure modes observed

Drift events caught and corrected during sessions. Each entry captures what drifted, when it was caught, how it was corrected, and what was added to the discipline (principles update, AST test, D-entry, or methodology refinement) to prevent recurrence. Failure modes are the most valuable part of the methodology because they are where naive AI-assisted development goes wrong; surfacing them publicly is what makes the case study credible to product leaders who suspect this kind of work is fragile.

### 2026-05-06 — Silently-deferred package drift uncaught from S4 forward

*What drifted.* D3 (Phase 1 strategic decisions, `charter/decisions.md`) committed identity-as-Keycloak-in-V1-Docker-Compose with OIDC + SAML + SCIM. P2 was named "Identity foundation" in `charter/packages.md` and the `charter/roadmap.md` RICE table. What actually shipped under P2 across S4–S8 was "First LLM call" (Langfuse 3 in Compose, the security baseline, Ollama and LiteLLM, the FastAPI skeleton, the Quorum → Zephyr rebrand). No Keycloak service in the Compose stack at P2 close; no SAML SP, no SCIM endpoint built. Auth middleware shipped at S7 per D23 with a dev signed-token backend and a Keycloak-shaped production backend stubbed — sufficient evidence the architecture is identity-ready, not the identity foundation D3 committed. The mismatch carried forward through P3 close, the P3→P4 boundary strategic session, P4 open, P4 close, and the P4-post between-packages state. No D-entry, no roadmap version, no PRD edit named the deferral.

*When caught.* 2026-05-06 status-snapshot pass. The operator asked Claude Code where the project stood against the roadmap; the resulting snapshot at `docs/notes/status-2026-05-06.md` performed a charter-vs-archive consistency check that surfaced the mismatch as ambiguity (1) in the document. P2's archive at `docs/archive/packages/p2.md` is titled "Package 2: First LLM call" while `charter/packages.md` line 8 still read "Identity foundation"; `charter/roadmap.md` RICE table P2 row still read "Identity foundation"; no D-entry between D3 and the snapshot date superseded D3.

*How corrected.* D52 (carryover-cleanup strategic session, this same session as the entry) defers identity foundation to Phase 2 in explicit supersession of D3, with reasoning that the bet's load-bearing claims do not turn on federated identity and Phase 1 retains auth-middleware-on-every-endpoint per D23 as sufficient evidence that the architecture is identity-ready. Scope-doc edits in the same commit as D52 correct `charter/packages.md` line 8 to actual P2 content, correct the `charter/roadmap.md` RICE-table P2 row title to "First LLM call" with a v3 version-log entry stamped reasoning category discovery (drift-correction), and reconcile `charter/phase-1-prd.md` against the deferral.

*Discipline addition.* Charter package descriptions need a sanity-check pass against archive content at every package close, not only at phase audits. The check is mechanical in shape (compare each closed package's `packages.md` description against the archive's actual scope and flag drift) and is a promotion candidate for the methodology mechanical-enforcement upgrades section in `charter/deferred-decisions.md`. Until the mechanical check lands, the operator's discipline is to run the same comparison manually as part of each package close walkthrough. The structural-promotion threshold convention applies: this is the first instance the drift was caught; if it recurs at a later package, the cost calculus tips toward landing the mechanical check.

## What Padhanam does not do

The reverse-Kano list. Each item looks like an improvement and is not. Named explicitly so that capacity pressure does not reintroduce them as "small improvements."

**Personas as styled interviewers.** Conflates styling with substance. Padhanam absorbs role-function audit categories (analyst, PM, architect, engineer, technical writer) without persona styling, because the question at audit is whether the work meets the function's quality bar, not whether the artefact reads in a styled persona's voice. Persona styling is also incompatible with the two-surface model's commitment to honest mode separation, which is voice-neutral by construction.

**Gated upfront PRD-architecture-epics chain.** Freezes intent at the moment of greatest ignorance and erases audit trail when subsequent editing occurs. Living-document discipline with delta capture per D43 preserves both intent and learning. Reverting to the gated form would destroy the audit-trail value the append-only commitment generates.

**Full autonomous mode.** Conflicts with append-only discipline (every commit must be operator-approved against the decision log), D-entry alternatives quality (alternatives surfacing is operator judgement, not pattern-matching from the model), reflection density (autonomous mode produces no operator learning), and the two-surface model (autonomous mode collapses both surfaces into model output). Auto mode trades the bet's substrate for throughput. The narrow Phase 2 carve-out for routine task types under specific conditions is performance-shaped, not auto mode reintroduced; the carve-out preserves operator approval at every unit boundary, with the safe-task-type list (dependency bumps following `ops/scheduled_checks.yaml`, schema migrations following established patterns, eval-harness execution against pre-designed tests, supply-chain scanning and triage in pre-defined categories) produced by the Phase 1 close audit as the input to the Phase 2 D-entry.

**TypeScript application substrate.** Buys crash recovery and orchestration at the cost of charter legibility. Markdown-first discipline is portable, audit-legible, and human-editable; the charter is the methodology's primary artefact, and any application substrate that obscures it sacrifices the artefact for tooling convenience.

**Sprint ceremony shape.** Coordination mechanisms for human teams. Single-operator design does not need them; importing them adds ceremony that produces no information for an audience of one. The discipline that ceremony imposes on human teams is already imposed on Padhanam by mode declaration, charter touch-points, and append-only logging.

**Quick-session bypass paths.** Once a bypass exists, the bypass becomes default. Padhanam's smallest sessions are already calibrated against operator capacity through scope cuts (per the throughput-pressure principle below); a structural bypass would erode scope discipline by replacing the "cut scope" response with "cut process."

**Vibe coding's structural absence.** The methodology bets on the opposite of what vibe coding bets on. The lesson worth absorbing from vibe coding is calibration of overhead, which token discipline already shows. Adopting any further element of vibe coding would erode the architectural and decision discipline that distinguishes Padhanam from the no-methodology baseline.

These absences are constitutive, not omissions. The methodology's coherence depends on them. The bet-preservation criterion that drove the absorption decisions across the comparison source is the same criterion any future absorption candidate is judged against: does it reinforce operator fluency through architectural and decision discipline, or does it undermine it.

## The throughput-pressure principle

Cross-cutting safeguard. From `charter/principles.md`:

> Throughput pressure is information about scope, not a license to delegate decisions. The first response to operator capacity constraints is to cut scope, not to automate the work that builds fluency.

The reverse-Kano list is permanent; the rejected items will look attractive again at every capacity-pressure moment. The principle is the safeguard that keeps the trap visible. Without it, "this session is taking too long, let me close it autonomously" reintroduces full autonomous mode under capacity pressure; "this PRD review is slow, let me commit v1 as-is" reintroduces gated upfront documentation; "this reflection is taking too long, let me skip it this session" reintroduces vibe coding's structural absence.

The principle names the trap explicitly: capacity pressure is the operator hitting scope ceiling, and the response is scope reduction. Capacity pressure is not the methodology's bug; it is its information channel. Every capacity-pressure moment is signal that the package is overscoped, the session is overscoped, or the phase is overscoped, and the response that preserves the bet is to land less rather than to land the same amount through a bypass. The principle is what prevents Padhanam from drifting into the methodologies it explicitly rejects, one comfortable shortcut at a time.

---

## Version log

- **v1** (P3 post-close, methodology integration strategic session). Initial articulation, fulfilling the methodology-document commitment in D39. Source material: three reference documents (the Padhanam methodology reference, the methodology-comparison improvements document, and an earlier descriptive-shape methodology draft), integrated under the structure agreed in the framing conversation. The earlier draft's reading-as-primary-tool framing, architect-direction-without-architect-identity framing, what's-being-investigated scope acknowledgement, session-shape and brief-discipline content, DORA proxy specifics, session log tagging block specification, cadence detail, "metrics measure methodology not operator" framing, and Patterns/Failure-modes observation surfaces are absorbed alongside the prescriptive disciplines from the other two sources. The earlier draft's pre-D47 framing of "strategic surface in Claude.ai, build surface in Claude Code" is superseded by D47's mode-declaration discipline collapse to Claude Code as primary. The descriptive scope of the document is bounded explicitly: structural disciplines are prescriptive (committed via D-entries, mechanically enforced); patterns and failure modes are descriptive (accumulate across phases, reviewed at audits). D-numbers reconciled against the live charter (D29 through D48); the comparison source's projected D34–D47 numbering was superseded as P3 closed. The "indifferent" list from the comparison source is omitted: items that mattered enough to surface earned the reverse-Kano section with their specific erosion mechanism. The implementation status summary from the comparison source is relocated to `charter/deferred-decisions.md` under "Methodology mechanical-enforcement upgrades." The four-layer measurement model is folded into this document rather than carved out as a separate `metrics.md` to reduce charter sprawl. Reasoning category: discovery (the methodology document is a Phase 1 deliverable per D39 that had not yet been authored).
