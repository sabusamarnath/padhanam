# The Padhanam Methodology

This document covers the build methodology: how Padhanam itself is built. It is distinct from `charter/product-methodology.md`, which covers what the platform encodes for its users (the agent layer and the methodologies embedded as defaults across the four professional functions Padhanam demonstrates against). When charter content describes operator discipline, build process, framing-prompt patterns, refactoring conventions, mechanical enforcement upgrades, or session-shape commitments, it lives here. When charter content describes per-domain methodology embedding for the product surface, it lives in `charter/product-methodology.md`.

The articulation of how Padhanam works. Read at strategic sessions; revised at phase audits with the version log appended at the end. Per D39.

## Foundation

### What Padhanam is

Padhanam is two artefacts produced together. A platform built to enterprise-grade architectural standards (multi-tenant, identity-federated, audit-chained, jurisdiction-aware, OTel-instrumented; see `charter/architecture.md` for the architectural synthesis), and the methodology that produced it: a discipline for senior product leaders directing end-to-end implementation through AI-assisted development without writing code. The platform is the artefact that proves the methodology; the methodology is the proprietary insight the platform is evidence of. Both are case-study artefacts, audited against the level of complexity that real enterprise software requires.

The bet is articulated in `charter/bet.md` and externally in `charter/prfaq.md`. Phase 1 is the substrate that proves the bet's load-bearing claims: that architectural discipline survives AI-assisted implementation, that mechanical enforcement scales while operator attention does not, that observability with cost dimension produces optimization recommendations enterprise procurement reads as defensible. Phase 2 direction is decided at the Phase 1 close audit based on what Phase 1 surfaces about the proposition, the methodology, and operator capacity.

### What's being investigated

The role being exercised in Padhanam does not have a settled name. The operator is a senior product leader. The implementation is performed by Claude Code. The relationship between the two is the unit of analysis: the operator defines intent, constraints, and architectural commitments; the model produces code, tests, schema, migrations, and commits within those constraints; the operator reviews, audits, and corrects. The methodology documents what works and what does not in that relationship, with enough specificity that another senior product leader could read it and adopt the discipline.

The structural disciplines below (mode separation, frameworks, charter shape, enforcement, reflection, capture, measurement, cost) are committed via D-entries and enforced mechanically. The pattern and failure-mode observations later in the document are descriptive: they accumulate as Phase 1 progresses and are reviewed at phase audits. The methodology is open to its own revision based on measurement evidence; if at any phase audit the evidence stops supporting the proposition, the bet document and this document are revised to reflect what was actually learned. Honesty about the experiment is more valuable than the experiment succeeding in any particular form.

### Hypothesis and iteration

Padhanam is a hypothesis under iterative test. The bet articulates the hypothesis; sessions accumulate evidence; phase audits validate or refine the hypothesis based on what evidence shows; the bet, methodology document, principles file, and architecture document revise to reflect what is actually learned.

The iteration cycle is not extrinsic to the experiment; it is the experiment's mechanic. Every artefact in the charter sits within this cycle: bet as hypothesis articulation, principles as binding rules derived from accumulated evidence, decisions as the audit-trail of architectural commitments along the way, methodology as the discipline of how the iteration happens, architecture as the synthesis of what the system looks like at any moment.

The methodology document itself is a living hypothesis revised across phase boundaries. v1 articulated the initial discipline at P3 close per D39's pending-authorship framing (later superseded by D113). v2 integrated Phase 1's accumulated discipline-pattern data points at P12 close (six new Patterns-observed entries plus the Session shapes sub-section). v3 (this version) refines Foundation, Work organisation, and Measurement model based on the P12-close-plus-post-P12-hygiene observations about the document's coherence and the three-document relationship with principles.md and architecture.md. Future versions revise based on Phase 2 evidence.

The hypothesis-iteration cycle distinguishes Padhanam's methodology from prescriptive operating manuals authored once and applied unchanged. The methodology document's content is the methodology's current hypothesis; the version log is the audit trail of how the hypothesis has evolved; the Patterns-observed and Failure-modes-observed sections are the evidence layer. A reader at any phase boundary reads the methodology document as the methodology's most recent hypothesis, not as fixed truth. The case study's credibility depends on the methodology being revisable in response to evidence; without iterative revision, the methodology becomes ideology rather than empirical practice.

## Two-surface mode separation

Strategic mode and build mode are different work modes with different deliverables. Strategic conversations produce charter edits, session prompts, or roadmap version updates. Build sessions produce code commits and session-log entries. The two-surface model is conceptual, not UI-bound: implementation collapses to Claude Code as the primary surface, with Claude.ai used opportunistically for audits and architectural reasoning. Mode separation is maintained by mode declaration at conversation start, distinct deliverables, and distinct commit conventions (`docs(charter): ...` or `docs(pN/<boundary-name>): ...` for strategic; `feat(pN/sN): ...` and `docs(pN/sN): ...` for build). Per D47.

The two functions need different outputs and different rhythms. Without explicit mode separation, strategic reasoning gets compressed into rushed pre-build framing or scatters through code commits, and build sessions get derailed by architectural questions that should have been settled first. Mode declaration is the load-bearing discipline because the UI is the same; without the declaration, charter-edit work and implementation work collapse into unbounded conversations that produce neither shape well. The charter files are the persistent bridge between modes regardless of which UI is active: decisions made in strategic mode become constraints in build mode, and audit findings flow back through the same files.

### Session brief preservation

Strategic-mode conversations that produce a build-session brief preserve the brief as a repo artifact at `briefs/<package>/<session>.md`. The brief is the forward-looking specification the architect commits to before build begins; preserving it at the same level as the eventual session log makes the audit trail symmetric between intent and outcome.

The convention activates from S17b forward (P5 mid-package). Earlier session briefs live in conversation history only; retroactive preservation is not in scope. The file is markdown, written at strategic-mode close, and committed to the repo before the build session runs.

Briefs do not version mid-package: a saved brief is the v1 specification, and deviations during build are documented in the session log rather than in-place brief edits. This mirrors D43's epic-note-and-archive-reconciliation discipline at the session granularity.

The "no in-place brief edits" rule is load-bearing: if the build session needs to deviate from the brief, the deviation lives in the session log reflection. We did this with D54's return-type deviation at S17a — S17a's reflection captured the deviation; brief stayed at framing-time text. That's the discipline that makes brief preservation worth more than session-log-only retrospection.

## Work organisation

Work in Padhanam is organised across four lifecycle levels (bet → phase → package → session), three decision-discipline frameworks (LVT, Kano, RICE), and five recognised session shapes (substrate, bridge, transport, hygiene, audit). Each level operates at a different forecasting horizon and a different audit cadence; the structure makes the disciplines visible without conflating altitudes.

### Strategic tree

Padhanam organises work in a four-level tree.

- **Bet** at the root. Articulated in `charter/bet.md`. Externally in `charter/prfaq.md`.
- **Initiatives** below the bet. Phases. Phase 1 (in progress) is the learning sprint that proves the proposition; subsequent phases decided at audit boundaries.
- **Epics** below initiatives. Packages. Twelve packages in Phase 1, ordered for dependency clarity and learning value, RICE-scored per D42.
- **Stories** below epics. Sessions. Each session has acceptance criteria, reflection prompts, and produces a session log entry.

The full tree lives at `charter/roadmap.md` per D44 as the canonical living artefact, versioned with reasoning categories on every change (discovery, capacity, signal, hedge).

Each level is a different forecasting horizon. Bets are multi-year. Phases are multi-month. Packages are multi-week. Sessions are single-day. Conflating horizons produces commitments at the wrong altitude: bet-level forecasts at the package level produce overcommitment to specific implementations before the substrate is understood; package-level forecasts at the bet level produce strategic drift toward whichever package the operator is currently shipping. The hierarchy enforces strategic placement at the right altitude before option assessment or sequencing begins.

### Phase lifecycle

A phase opens with a strategic block that lands a Phase PRD (or extends the prior Phase PRD with a new section per D43), confirms the package set against the bet, and lands a new roadmap version per D44 with reasoning category (discovery, capacity, signal, or hedge). The phase opening also seeds the first package's epic note per D43.

In-progress, the phase runs through its package sequence; each package opens with an epic note and closes with a retrospective plus archive. Sessions accumulate session-log methodology-candidate lines that consolidate at package close and again at the phase audit. The phase's substrate intent is verifiable continuously through the test surfaces (import-linter contracts, AST tests, tenant-isolation contract scenarios, integration tests).

The phase closes with a phase audit producing: a methodology document revision; a PRFAQ refresh per D45; the phase PRD as-built section per D43; a new roadmap version per D44 with reasoning category; drift findings; framework distribution checks; metric review across the four bet-native metric layers plus the industry overlay; D-entries archived to `docs/archive/decisions/phase-N.md` per the methodology document's "Per-phase decisions archival pattern" sub-section.

Transition to the next phase happens at a strategic-mode opening conversation reading the audit's outputs plus the consolidated Phase-N-inputs file (per the P12 audit's `charter/p12-phase-2-inputs.md` precedent). The transition produces the next phase's PRD section, the v6 roadmap entry, and the first package's epic note.

### Package lifecycle

A package opens with an epic note at `charter/packages/p<n>-epic.md` per D43 (from P4 forward). The epic note captures intent, scope, session forecast, and out-of-scope explicitly; subsequent sessions read it as the canonical package framing.

In-progress, the package runs through its session sequence. Session shapes (substrate, bridge, transport, hygiene, audit per the Session shapes sub-section below) calibrate scope expectations and session-prompt drafting. Session log entries accumulate at `log/sessions.md` with role-function tags per D46, structured metrics tagging blocks per D40, reflection density distinguished by conversation type per D47, and methodology-candidate lines that the package retrospective consolidates.

The package closes with a retrospective plus archive. The epic note's as-built section gets populated per D43, naming what shipped versus what was forecast; deltas land as audit deliverable. Session log content for the package archives to `docs/archive/sessions/p<n>.md` per D107, keeping the live `log/sessions.md` tight per the token-discipline principle. The package retrospective at `log/packages.md` carries a measured-outcomes paragraph per D40 with the package's metric numbers.

### Session lifecycle

A session opens with a brief preserved at `briefs/<package>/<session>.md` per D43 (from S17b forward; see "Session brief preservation" under Two-surface mode separation for the file-based discipline). The brief is short and explicit because vague briefs produce vague work; the session-prompt convention (package and session identification, goal stated as artefacts at session close, context to read first, charter updates required, substantive work in commit-shaped units, acceptance criteria, reflection prompts, out of scope, session log entry instruction) is the structural defence against ambiguous briefs.

Sessions follow Design → Build → Test → Close internally. The mode declaration at conversation start per D47 binds the session to a deliverable shape: build sessions ship code commits, smoke verification at any UI surface per the S4 lesson, and charter touch-points (schema, decisions, current-package status); strategic sessions ship charter edits, session prompts, or roadmap version updates. Mid-build pre-write reconciliation fires when the brief surfaces against the as-built codebase reality (per the Patterns-observed entry); operator engagement happens with explicit disposition recorded in the D-entry body or commit message.

The session closes with a log entry at `log/sessions.md`. The entry carries reflection density per session shape (strategic shorter, build longer per D47), role-function tag per D46 naming which of the five role-functions were exercised, structured metrics tagging block per D40 for downstream computation, and methodology-candidate lines for accumulation toward the next audit. Captures triage per D48 classifies any mid-session stray thoughts into the five impact types (quick task, inject, defer, replan, note).

### Session shapes

Phase 1 surfaced five session shapes worth naming for recognition value. Each shape carries distinguishing characteristics that affect brief drafting, scope expectations, and reflection density. The shapes are descriptive rather than prescriptive: a session occupies one shape based on what it does, not on commitment to a particular cadence.

**Substrate sessions** ship architectural surface: a new bounded context's domain layer, application layer, ports, adapters, schema migration, contract tests, smoke. Scope is large; commit count typically 8 to 12; reflection density is high because architectural decisions land in code. Pre-write reconciliation fires reliably at session open against brief-vs-codebase drift. Examples across Phase 1: S31 (run_history substrate); S36 (audit reader substrate); S38 (ingestion management substrate); S39 (retrieval evaluation substrate); S40 (retrieval evaluation runner); S41 (optimization layer).

**Bridge sessions** sit between substrate sessions and address verification-and-hygiene work that the substrate session cannot ship cleanly. The shape produces charter-grade artefacts that downstream sessions cite. Smaller scope than substrate; commit count typically 3 to 5; reflection density medium with focus on what the substrate session left unresolved. Pre-write reconciliation fires against substrate-vs-verification-surface drift. Examples: S39b (corpus re-ingest + real-corpus gold-set rebuild between S39 substrate and S40 runner); S40b (clean gold-set authoring between S40 runner and S41 optimization).

**Transport sessions** ship HTTP layer over existing substrate. No new ports, no new domain types, no new adapters; just inbound adapter layer atop existing application use cases. Distinct shape from substrate because the substrate is fixed and the work is composing routes, DTOs, query parsers, error handlers, and wiring extensions. Scope medium; commit count typically 8 to 10; reflection density medium with focus on convention-consistency and procurement-grade-defensibility through the HTTP layer. Pre-write reconciliation can fire on convention-consistency (S42 Finding 5 DTO placement) but doesn't anchor on substrate decisions. Examples: S34 (run-history HTTP); S37 (audit HTTP); S38 (ingestion management HTTP); S42 (retrieval_evaluation + optimization HTTP).

**Hygiene sessions** consolidate end-of-package debt: documentation expansion, methodology-candidate consolidation, dev-tooling verification, structural-finding documentation, stray-artefact cleanup. Mixed commit prefixes per work nature (`docs(charter)`, `docs(readme)`, `chore`, `fix`). No new D-entries (the hygiene session does not produce binding architectural commitments). Structural findings forwarded to deferred-decisions rather than fixed in-session per the bounded-fix-or-document disposition rule. Reflection density medium with focus on what's being deferred to the next audit. Example: pre-P12 hygiene at P11 close; post-P12 charter-discipline hygiene at the post-audit boundary.

**Audit sessions** are strategic-mode synthesis sessions that occur at phase boundaries. Three tracks (top-down D-entry verification, bottom-up codebase tour, audit-input disposition) plus methodology-document substantive update. No code changes; outputs are charter amendments, methodology updates, deferred-decisions refreshes, and Phase 2 inputs. Commit count typically 10 to 12 (grouped by destination file rather than chronologically). Reflection density high with focus on the bet's load-bearing claims and the methodology's hypothesis evolution. Example: P12 phase audit.

The shape distinction is recognition-value: naming the shape lets brief drafting calibrate scope, lets the operator anticipate which disciplines fire, and lets phase audits assess shape distribution. Phase 2 substrate sessions inherit the substrate framing; Phase 2 framing of bridge or hygiene sessions in advance promotes if substrate work consistently produces them. The shapes are not commitments to a specific cadence; they are vocabulary for what surfaces.

### Frameworks

Three frameworks operate at three different moments per D42, each at a distinct lifecycle level.

**LVT** (Lean Value Tree) places work in the strategic tree. Used at phase opening and package opening to confirm where new work sits in the bet → phase → package → session hierarchy. The strategic-tree artefact lives at `charter/roadmap.md` per D44.

**Kano** evaluates options at D-entry decision points. Used at any session (strategic or build) that produces a D-entry selecting between alternatives. D-entries that select between alternatives carry a Kano category field at the bottom of the entry: must-have (absent of which breaks the bet), performance (scales the bet linearly), delighter (disproportionate value relative to cost), indifferent (neutral, named so it does not accumulate as ambition), or reverse (actively erodes the bet despite looking attractive). The convention applies from D41 forward.

**RICE** prioritises sequencing. Reach × Impact × Confidence ÷ Effort. Used at package framing and at backlog items where sequencing involves real choice. Recorded explicitly on packages. Phase audits review score honesty (forecasts versus post-hoc rationalisations).

Without explicit categorisation at the decision moment, "must-have" stretches to mean "felt rigorous while deciding" and prioritisation becomes post-hoc rationalisation. The frameworks operate at distinct moments of the work; conflating them produces ceremony without reasoning value. Kano at framing forces honest assessment of which features actually move the bet versus which look attractive but do not. RICE at sequencing forces honest forecasting, with phase audits checking whether scores were defensible rather than convenient. Phase audits also review distribution (too many must-haves suggests conflation with default; too many delighters suggests features added without honest weighting) and roadmap reasoning-category distribution per D44 (too many capacity-driven changes mean the bet was overscoped; too many signal-driven changes mean it was poorly grounded; too many hedge entries mean the operator is avoiding commitment).

## Reading as the primary tool of the role

The operator's primary tool in this operating model is reading. Reading the latest session log tail. Reading the active package's `current-package.md`. Reading `principles.md` before each session. Reading the relevant `decisions.md` entries for the area being touched. Reading the model's work after the session and before the merge. Most operator-and-implementer drift is preventable by the operator having read the right thing at the right time.

The token discipline in `principles.md` is a budget for the model's reading; the operator's reading is unconstrained and is the higher-leverage half of the discipline. What this looks like in practice changes over time as the codebase grows. Early sessions allowed full-file reads in most places; later sessions require ranged reads against larger files and selective archival of working documents to keep them tight. The reading discipline is not static; the volume scales with the codebase, and the structural-promotion threshold (a comment-level rule that bites three times across a package gets promoted to a parser- or AST-level test) is partly about reducing the operator's reading load by moving rule-checking from review to mechanical enforcement.

## Architectural direction without the architect identity

The operator is not an architect by career or title. The work being done in some sessions is architect-adjacent: defining boundaries, enforcing principles, making structural decisions about ports and adapters, deciding what belongs in the shared kernel and what does not. AI-assisted development makes this kind of work accessible to a senior product leader who has the domain understanding and the seniority to make the judgement calls, even without the engineering identity that would traditionally produce architectural authority.

The methodology distinguishes this from architecture as a profession. The operator is not designing systems from scratch; the operator accepts, modifies, or rejects structural proposals from the model, informed by enterprise procurement experience and product judgement. The model surfaces the technical options; the operator picks among them with reference to constraints the model cannot fully see (regulatory direction, what real enterprise buyers will accept, what the long arc of the platform requires). This is what the bet's architect-implementer pattern actually consists of in practice. The role is not "product leader pretending to be architect"; it is product leader exercising structural judgement against options the model surfaces, with the architectural authority coming from the seniority of the judgement rather than from engineering identity.

## Charter structure

The charter is the methodology's primary artefact surface. Each shape serves a different audit purpose.

**Strategic constants:**
- `charter/bet.md` — strategic articulation of what Padhanam is and why
- `charter/principles.md` — engineering principles, decision discipline, security posture, token discipline (binding rules with D-entry references; read every session)
- `charter/methodology.md` — articulation of how Padhanam itself is built (this document; the build methodology)
- `charter/architecture.md` — architectural synthesis with diagrams (read at onboarding, phase audits, and procurement-grade-touch moments; the synthesis surface that narrativises principles.md plus decisions.md with diagrams)

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

### Per-phase decisions archival pattern

Decisions archival follows D107's per-package session-log archival pattern at phase granularity. At phase close, D-entries from the closing phase archive to `docs/archive/decisions/phase-N.md`. The active `charter/decisions.md` retains one-line summaries plus pointers to the archive for archived D-entries; full Choice/Reasoning/Alternatives/Kano content lives in the archive. New D-entries in subsequent phases land in active `decisions.md` until that phase closes. The pattern keeps active `decisions.md` tight per the token-discipline principle while preserving the full audit-trail evidence in the archive.

### Principles-D-entry reference convention

Principles that restate a D-entry commitment carry a parenthetical D-entry reference (e.g., "Optimization output is recommendation-shaped, not chart-shaped (per D9)."). The reference makes the principle-to-commitment relationship explicit and surfaces the maintenance dependency: when the D-entry evolves via supersession, the principle's reference updates to the new D-entry. Principles that articulate disciplines without a single D-entry home (token discipline, reflection density, role-function tagging) do not carry references.

## Append-only discipline

The charter is append-only at the entry level for logs, at the version level for living documents, and at the section level for strategic constants. Historical D-entries, principles content, and session log reflections are not edited in place; they are added to. Living documents preserve original drafts alongside as-built reality; each new version appends rather than replaces. AST tests in `tests/_enforcement/` catch in-place edits at CI; the violation count is itself a measurement layer.

Edited charter loses audit-trail value. The case study's audience reads the charter as evidence of whether the methodology produces honest decisions; if past decisions can be silently revised to look better in retrospect, that evidence is worthless. The S8 lesson (recovery from in-place edits via git restoration) made the principle explicit at D29; mechanical enforcement followed because operator vigilance does not scale to a 200-commit codebase. The discipline applies symmetrically to errors: a mistaken D-entry is corrected by a new D-entry that supersedes it, not by editing the original.

### Deferred-entry closure by D-entry

When a numbered D-entry closes a deferred-decisions entry (the deferred decision becomes a committed D-entry), the deferred entry gains a Status header line: "Status: closed by D<n>, <date>". The entry body remains intact for audit-trail purposes per the append-only discipline. At phase audits, closed deferred entries can archive to `docs/archive/deferred-decisions/phase-N.md` if the active `deferred-decisions.md` grows beyond working-files-stay-tight intent.

## Architectural enforcement

Architectural commitments are enforced mechanically, not by review.

Import-linter contracts (15 at P3 close) make architectural rules CI failures: vendor SDKs cannot be imported by domain code (D4), bounded contexts cannot cross-import (D16), configuration access is confined to the configuration layer (D19). AST tests catch rules import-linter cannot express, including D19's no-`os.getenv`-outside-config and the no-vendor-in-domain check that joined it at P2 close. Tenant-isolation tests in `tests/contract/tenant_isolation/` are red-team-shaped: each test attempts unauthorised cross-tenant access and asserts it fails (D24), because test-it-works tests pass on broken implementations. Schema discipline requires `charter/schema.md` updates in the same commit as migrations. Charter touch-points are listed in `CLAUDE.md`: schema, observability metrics, architectural decisions, and course changes each have specific files that must travel with the code.

Review does not scale. Operator attention is the bottleneck; mechanical enforcement is the only way the architectural surface keeps up with a growing codebase. Every rule that lands as a CI failure rather than a review comment is a rule the operator no longer has to remember to check. The enforcement count is itself a measurement layer in the methodology: the trajectory through Phase 1 should be upward, and the structural-promotion threshold (a comment-level rule that bites three times across a package gets promoted to a parser- or AST-level test) is the convention that grows the surface honestly.

### Mechanical enforcement upgrades

Disciplines currently operative as operator vigilance, queued for promotion to mechanical enforcement. Each names what the operator does manually today plus the upgrade's mechanical shape:

- **Decision-to-code translation gate.** Discipline: every D-entry produces a corresponding code or charter change within the next session. Mechanical shape: CI test walking new D-entries to assert appearance in commits or session prompts within N sessions.
- **Per-package reconciliation gate.** Discipline: epic note at package open, archive at package close, delta as audit deliverable per D43. Mechanical shape: CI test asserting every closed package has both files with archive referencing epic-note commitments.
- **Adaptive per-package reassessment as explicit prompt.** Discipline: at session close, ask whether the rest of the package plan still holds given what the session surfaced. Mechanical shape: standing reflection prompt at the session-close template.
- **`make doctor` for operational drift.** Discipline: operator catches orphan Compose projects, stale virtualenv interpreters, port collisions, drifted image digests, basic git hygiene at session-open. Mechanical shape: a `make doctor` command running the checks against the standard activation conditions.
- **Session-close walkthrough template (checkpoint-preview pattern).** Discipline: session-close articulates what was the intent, what changed, what was verified, what is the residual risk. Mechanical shape: standing template integrated at the session-close convention.
- **Edge-case hunter procedural shape.** Discipline: phase audits walk boundary input, empty input, malformed input, concurrent actor, retry, partial failure. Mechanical shape: procedural checklist embedded in the phase-audit template.
- **Proper-noun-attribution check on model-drafted vendor-voice artefacts.** Discipline: operator interrogates name attributions in model-drafted vendor-voice content with "who is [name]?" questions per the fabrication-class Failure modes entry. Mechanical shape: automated check flagging proper-noun attributions pending operator confirmation.

Activation triggers per upgrade live at the "Methodology mechanical-enforcement upgrades" entry in `charter/deferred-decisions.md`. Items move from operator vigilance to mechanical enforcement when their activation condition fires (typically a third recurrence per the structural-promotion threshold) or when a phase audit pulls them from the backlog.

## Reflection and learning

Session log entries include a reflection section with substantive paragraphs of operator thinking. Reflection density distinguishes session types per D47: strategic conversations produce shorter entries focused on what was decided; build sessions produce longer entries with substantive reflection on what was learned. The mix over time is signal at phase audits.

Each session log entry carries a one-line `roles:` tag naming which of the five role-functions were exercised (analyst, PM, architect, engineer, technical writer), per D46. Distribution over time surfaces atrophy: many consecutive engineer-only sessions mean the analyst, PM, or technical-writer functions are not being exercised, and the case study's proposition (that all five product-leader functions can be sustained through AI-assisted implementation) loses evidence at audit.

Phase audits review the charter against built reality across five role-function categories per D46: analyst (bet evidence and grounding, market assumptions checked), PM (prioritisation defensibility, RICE-score honesty, scope discipline), architect (D-entries with non-trivial alternatives, principles catching real drift, contract enforcement), engineer (implementation against architectural commitments, test density, mechanical enforcement), technical writer (charter legibility to a non-author reader, narrative coherence across artefacts). Each category is audited against its own quality bar. Phase audits produce a new roadmap version per D44, a new PRFAQ version per D45, the phase PRD as-built section per D43, drift findings, framework distribution checks, and metric review.

Edge-case-hunter procedural shape extends the phase-audit template: every audit walks boundary input, empty input, malformed input, concurrent actor, retry, and partial failure across the surfaces the phase shipped. The procedural checklist is the manual form of the mechanical enforcement upgrade tracked at `charter/deferred-decisions.md`; the activation trigger for full mechanical enforcement lives there.

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

These metrics are themselves part of the hypothesis being tested. Phase audits assess whether each metric category produces useful signal; underperforming metrics earn revision or retirement; missing-signal observations earn new metrics. The measurement model at any version captures what we believe measures the methodology; the model's evolution across versions is itself evidence of what each phase surfaced about what is measurable. The "What the numbers are not" sub-section below makes the framing explicit at the discipline level; this paragraph makes it explicit at the model's hypothesis level.

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

The metrics measure the methodology, not the operator (and the metric model itself measures what we currently believe is measurable — see the hypothesis-framing paragraph at the top of this section). Sessions producing drift are not failures of competence; they are failures of the discipline as it stood at that point, and they typically produce a principle update, a decisions entry, or a methodology refinement that prevents recurrence. The methodology improving over time is the expected result; if the metrics get worse over time, that is itself an important finding the case study should report honestly.

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

### 2026-05-07 — User-driven course-correction

*What recurs.* Strategic-mode framing conversations accumulate technical depth without re-grounding in audience or proposition; the operator pulls back to a higher altitude; the charter absorbs the discipline. Two named instances during P6: the data-retrieval elevation pullback (operator: "Data retrieval needs its own session. It is not trivial. It is full design package or phase.") and the product reframe absorption (operator: "We need to tighten up on what the purpose is."). Both shared structure: model framing pushed past architectural altitude into commitment territory; operator-initiated reframe; charter absorption commit landed before drift accumulated.

*Why this is observed, not prescribed.* The pattern names the recovery surface, not a workflow gate. Drift-recovery is operator vigilance. Promoting it to a discipline would create a recursive expectation (the operator must vigilantly drift-recover from drift-recovery), which is not what produces the recovery — what produces the recovery is the operator's seniority of judgement against the bet's grounding. The Patterns-observed entry exists so the recovery surface is documented when it fires and is reusable as a charter-absorption shape (small strategic commit, named pullbacks, charter absorbs the discipline).

*Discipline addition (model side).* When framing accumulates technical depth across multiple turns without re-grounding, surface the question of audience and proposition before committing to the next architectural step. The framing-prompt-as-recommendation discipline below absorbs this at the brief level; the conversational discipline is to name the moment ("we are deep in architecture; want to re-ground in the bet first?") at multi-turn architectural sequences that cross more than two or three load-bearing decisions.

### 2026-05-16 — Pre-write reconciliation as architectural discovery (P12 audit promotion)

*What recurs.* At session-open, Claude Code reads the files the brief names before writing code; reading surfaces inconsistencies between the brief's assumptions and the as-built codebase reality; raises a user-question; the operator resolves with an explicit disposition (often a new or amended D-entry). The discipline catches drift between brief-time and write-time that prose review at brief-drafting alone cannot catch. Distinct from the "Pre-write reconciliation against vendor docs precedes brief drafting" section below, which addresses vendor-SDK drift before brief authorship; this entry addresses brief-vs-codebase drift at session open.

*Recurrence count.* Sixteen-plus instances spanning S6 LiteLLM env-var quirks through S42 Finding 5 DTO placement; promoted from candidate to Patterns-observed entry at the P12 phase audit per the audit-input file's entry 1 disposition. Five P11 instances alone (S39 D109 sibling-precedent; S40 D66 framing-vs-as-built; S40b graph-extract surface; S41 D111 framing scope; S42 Finding 5 DTO placement).

*Mechanism.* The discipline is mechanical: read every file the brief names before drafting code; if the read surfaces inconsistency with the brief's assumptions, raise a user-question; the architect resolves with explicit disposition before code lands. The "brief preserves at v1" rule per the methodology document's Session brief preservation sub-section is what makes the discipline auditable rather than ceremonial: deviations land in session-log reflection and in the D-entry's body, not in in-place brief edits.

*Mid-build pre-write reconciliation as sub-pattern.* Pre-write reconciliation can also fire mid-build when import statements or cross-file references reveal codebase context the session-open read surface missed. D109's S39 implementation correction is the named instance: importing `padhanam.security.hash_chain` from a different layer than the brief's strategic-mode plan surfaced the platform-layer-vs-context-layer-helper distinction at write time. The mitigation is the same (raise user-question; resolve with explicit disposition) but the discipline fires at a different moment in the session. Audit trail preservation discipline holds (the body of D109 stands; an explicit "S39 implementation correction" section names the as-built deviation).

### 2026-05-16 — Principle-versus-framing drift (P12 audit promotion)

*What recurs.* Distinct from pre-write reconciliation's brief-vs-codebase drift; this is brief-vs-principles drift. The brief frames against no specific codebase reality but contradicts an architectural principle the codebase commits to. Pre-write reconciliation can't catch it because there's no codebase reference to reconcile against; only writing the code and watching the import pattern surfaces the principle violation.

*Recurrence count.* Three P11 instances at promotion (S41 commit 4 rules placement at `application/rules/` vs the brief's `domain/rules/` because rules consume the application-layer EvidenceContext; S41 commit 8 import-linter TYPE_CHECKING edge broke the layers-optimization contract because import-linter parses TYPE_CHECKING blocks as real imports; S42 Finding 5 DTO placement deviation per-context-subdirectory vs flat-module convention precedent). One earlier S40b graph-extract substrate-gap surface counts as a fourth structurally-similar instance.

*Mitigation surface different from pre-write reconciliation.* Brief-vs-principles check at strategic-mode close (before the build prompt drafts) catches this class. The build-time discovery surface is the secondary catch (writing the code and watching the import pattern surface the principle violation). Recurrence test continues at the next substrate session; if instance count grows in Phase 2, the strategic-mode-close discipline tightens to mandatory brief-vs-principles checklist.

### 2026-05-16 — Ship-tooling-with-smoke-exercise (P12 audit promotion)

*What recurs.* When a session ships dev-workflow tooling (Makefile targets, scripts, scaffolds), the same session's smoke must exercise the new tooling end-to-end through the production-shape flow, not against the established pattern the tooling replaces. Tooling that lacks production-shape smoke at the ship session surfaces bugs at the first downstream consumer.

*Recurrence count.* First named instance: S41 `make build-api` target authored at commit 0e8041f without production-shape smoke; first production-shaped use at S42 surfaced the docker-compose-build-rejects-digest-tag bug, fixed inline at S42 commit ac5a6bf. Recurrence test continues at the next dev-workflow tooling addition; pre-P12 hygiene's refresh of the digest pin (commit db285f8) verified the fix held, completing the first verification cycle.

*Generalisation.* Structural invisibility to unit tests (Makefile is not test-covered) means smoke is the only catch surface for dev-workflow tooling bugs. The discipline is "session that ships dev-workflow tooling, smoke step exercises the tooling at the same session" — applies recursively when the tooling is itself smoke-time infrastructure. Mechanical enforcement candidate at a future hygiene moment if recurrence continues; methodology-document entry is the right altitude at first promotion.

### 2026-05-16 — Metric-threshold expectations need structural-understanding grounding (P12 audit promotion)

*What recurs.* When adding a new metric or threshold, the threshold expectation needs grounding in the structural shape of the comparison surface rather than gut-intuition framing. The S40b instance is named evidence: the operator's implicit MRR>0.9 threshold assumption was wrong because MRR was structurally non-discriminating in the S40-era evaluation setup (rank-1 expected chunks against rank-1 retrieval results produce MRR=1.0 across any vector retrieval surface). The structurally load-bearing surfaces were recall@k and precision@k differentials at @3.

*Recurrence count.* One instance at promotion (S40b). The pattern earns the methodology entry on first instance because the corrective discipline is what the case study's substrate-honest evaluation surface depends on; methodology-promotion of discipline-corrective findings does not wait for recurrence (mirrors the Failure modes section's discipline-addition pattern: corrective discipline-additions land on a single observed drift event because waiting for recurrence pays additional drift instances).

*Forward-relevance.* The optimization layer's threshold values (0.15 absolute recall@3 delta; $0.10 cost-per-successful-task) are starter-value commits in D111. Phase 2 tuning grounds in production-grade structural understanding (real consumer evidence accumulation per the cost-threshold-tuning deferred-decisions entry).

### 2026-05-16 — Reproducibility artefacts land at the session that ships them (P12 audit promotion)

*What recurs.* Any artefact a session depends on for reproducibility must be repo-resident at the session that ships it. Audit-trail-of-creation (the session log entry recording that the artefact was created) is necessary but not sufficient for reproducibility; the artefact itself needs to land under `tests/fixtures/`, `briefs/`, or another repo-resident surface.

*Recurrence count.* One instance at promotion (S25 synthetic LVT sources never landed in the repo and were not recoverable at S39b, forcing substitute-content authoring). The pattern earns the methodology entry on first instance because the corrective discipline shape mirrors the metric-threshold entry above (corrective discipline-additions land on a single observed drift event).

*Forward-relevance.* Any new corpus-dependent test or smoke artefact requires corpus content under version control. The S40b corpus content at `tests/fixtures/corpus/p11_s40b/` is the first reproducible-from-repo corpus content; the pattern generalises beyond corpus to any artefact the session-of-ship depends on (smoke documents, configuration files, methodology template content drafted at brief-time for paste verification).

### 2026-05-16 — Methodology-candidate accumulation and audit-resolution rhythm (P12 audit promotion)

*What recurs.* P11's six sessions accumulated fourteen methodology candidates (consolidated at `charter/p12-audit-inputs.md` by the pre-P12 hygiene session). The candidates surfaced through session-log methodology lines at each session close; the audit's commit-4 disposition mapped each candidate to one of four shapes (charter amendment / methodology document / deferred-decisions / explicit non-action). The accumulation-then-audit rhythm is itself a methodology pattern: session-log accumulation distributes candidate-recognition work across the package, then the audit resolution work compresses synthesis into a single strategic-mode block at the package-or-phase boundary.

*Recurrence count.* First explicit instance at P12 audit. The pattern is methodology-document candidate on first instance because the operational shape is what makes the methodology document maintainable: without the accumulation-and-resolution rhythm, methodology candidates either get lost in session log noise or trigger reactive methodology-document edits mid-package (a violation of D47's strategic-mode-vs-build-mode separation).

*Forward-relevance.* Phase 2 substrate work inherits the rhythm: candidates accumulate at session-log methodology lines through Phase 2 packages, the per-package retrospectives at `log/packages.md` provide an intermediate consolidation surface, and Phase 2 close audit resolves the cumulative set. The pre-P12 hygiene precedent of "consolidate the candidates into a structured input file with observation + evidence + decision-shape format" carries forward as the consolidation template; the audit-output convention of "four disposition shapes per candidate plus audit-surfaced entries" carries forward as the resolution template.

## Failure modes observed

Drift events caught and corrected during sessions. Each entry captures what drifted, when it was caught, how it was corrected, and what was added to the discipline (principles update, AST test, D-entry, or methodology refinement) to prevent recurrence. Failure modes are the most valuable part of the methodology because they are where naive AI-assisted development goes wrong; surfacing them publicly is what makes the case study credible to product leaders who suspect this kind of work is fragile.

### 2026-05-06 — Silently-deferred package drift uncaught from S4 forward

*What drifted.* D3 (Phase 1 strategic decisions, `charter/decisions.md`) committed identity-as-Keycloak-in-V1-Docker-Compose with OIDC + SAML + SCIM. P2 was named "Identity foundation" in `charter/packages.md` and the `charter/roadmap.md` RICE table. What actually shipped under P2 across S4–S8 was "First LLM call" (Langfuse 3 in Compose, the security baseline, Ollama and LiteLLM, the FastAPI skeleton, the Quorum → Zephyr rebrand). No Keycloak service in the Compose stack at P2 close; no SAML SP, no SCIM endpoint built. Auth middleware shipped at S7 per D23 with a dev signed-token backend and a Keycloak-shaped production backend stubbed — sufficient evidence the architecture is identity-ready, not the identity foundation D3 committed. The mismatch carried forward through P3 close, the P3→P4 boundary strategic session, P4 open, P4 close, and the P4-post between-packages state. No D-entry, no roadmap version, no PRD edit named the deferral.

*When caught.* 2026-05-06 status-snapshot pass. The operator asked Claude Code where the project stood against the roadmap; the resulting snapshot at `docs/notes/status-2026-05-06.md` performed a charter-vs-archive consistency check that surfaced the mismatch as ambiguity (1) in the document. P2's archive at `docs/archive/packages/p2.md` is titled "Package 2: First LLM call" while `charter/packages.md` line 8 still read "Identity foundation"; `charter/roadmap.md` RICE table P2 row still read "Identity foundation"; no D-entry between D3 and the snapshot date superseded D3.

*How corrected.* D52 (carryover-cleanup strategic session, this same session as the entry) defers identity foundation to Phase 2 in explicit supersession of D3, with reasoning that the bet's load-bearing claims do not turn on federated identity and Phase 1 retains auth-middleware-on-every-endpoint per D23 as sufficient evidence that the architecture is identity-ready. Scope-doc edits in the same commit as D52 correct `charter/packages.md` line 8 to actual P2 content, correct the `charter/roadmap.md` RICE-table P2 row title to "First LLM call" with a v3 version-log entry stamped reasoning category discovery (drift-correction), and reconcile `charter/phase-1-prd.md` against the deferral.

*Discipline addition.* Charter package descriptions need a sanity-check pass against archive content at every package close, not only at phase audits. The check is mechanical in shape (compare each closed package's `packages.md` description against the archive's actual scope and flag drift) and is a promotion candidate for the methodology mechanical-enforcement upgrades section in `charter/deferred-decisions.md`. Until the mechanical check lands, the operator's discipline is to run the same comparison manually as part of each package close walkthrough. The structural-promotion threshold convention applies: this is the first instance the drift was caught; if it recurs at a later package, the cost calculus tips toward landing the mechanical check.

### 2026-05-06 — Fabrication-class drift in model-drafted vendor-voice content

*What drifted.* During the framing conversation that produced the carryover-cleanup strategic-block prompt, model-drafted PRFAQ scaffolding fabricated a name attribution ("Casey Whitfield") for an executive quote and presented it as if established. The fabrication conflated plausibility with vendor-PR voice; in vendor-PR shape, named attributions are structurally expected, and the model defaulted toward path-of-least-resistance fabrication rather than surfacing the gap. The drift class is distinct from the silently-deferred package drift in the entry above: silent-deferral drift is omission across multiple sessions; fabrication-class drift is invention within a single artefact draft. Both share the property that the model's default was the wrong default and the operator's surfacing question was the recovery surface.

*When caught.* Operator caught the miss during framing review with the question "who is Casey Whitfield?" — before any commit to the strategic-block work. The catch happened in-conversation in Claude.ai before the carryover-cleanup prompt was finalised and before any Claude Code build began. Catch surface: direct interrogation of a name attribution that did not match operator memory or any prior charter content.

*How corrected.* Decision 1 in the carryover-cleanup commit 4 (PRFAQ v2 vendor-voice rewrite) flagged fabrication as rejected and committed to representative-role attributions only. The v2 commit landed `charter/prfaq.md` with the customer quote attributed to "Head of Platform Engineering at a frontier AI Labs customer" and the executive quote attributed to "Padhanam's founder" rather than fabricated names. The corrected discipline applied across both quotes and is recorded explicitly in the v2 entry of `charter/prfaq.md`'s version log: real names land at v3 onward only if real partners or operator-named attribution becomes appropriate. The carryover-cleanup session's reflection prompt 5 captured the in-block observation; this entry's promotion of that observation to a Failure modes entry closes the discipline-addition loop.

*Discipline addition.* Model-drafted artefacts in PRFAQ-shaped voice or any vendor-style external-voice content carry a default-toward-plausibility risk that fabrication is the path of least resistance. The discipline: representative-role attributions are the safe shape for model-drafted vendor-voice content; real names land only when the operator has named them explicitly, and any model-drafted artefact in external voice that introduces a proper-noun attribution requires operator confirmation before commit. Promotion candidate tracked at the "Proper-noun-attribution check on model-drafted vendor-voice artefacts" item in the "Methodology mechanical-enforcement upgrades" section of `charter/deferred-decisions.md`; activation trigger lives there. Until the mechanical check lands, the operator's discipline is to challenge any name attribution surfaced in model-drafted external-voice content with a "who is [name]?" question — the same question that caught this drift. Failure modes entries land on single instance, unlike Patterns observed entries which require recurrence; this asymmetry is the methodology's discipline shape — descriptive observations need recurrence to earn naming, but corrective discipline-additions land on a single observed drift event because waiting for recurrence pays additional drift instances.

### 2026-05-06 — Single-currency assumption embedded across cost-capture surfaces without deliberate architectural commitment

*What drifted.* USD-as-currency assumption baked into D49's OTel span attributes (`gen_ai.cost.*_usd`), the `CostBreakdown` value object fields, and `CostPerSuccessfulTaskResult.cost_per_task_usd` across S14, S17b, and the cost-query path. The architectural commitment to single-currency cost reporting was never made deliberately; it fell out of vendor pricing being in USD plus dev-environment defaults. D12 commits jurisdiction as a first-class architectural attribute with the "by construction, not by policy" posture; cost data touches customer data, so by D12's standard, the shape should have been amount-plus-currency from inception. The drift is implicit-assumption-as-architectural-commitment, the kind of single-default thinking the case study posture is supposed to catch at framing.

*When caught.* S17b post-close, by operator question at S18 framing prep ("why USD?"). The assumption had been embedded since S14 (D49's cost-capture wiring) and propagated through every subsequent cost-bearing surface without anyone surfacing the choice as a choice.

*How corrected.* USD-only is defensible scope for Phase 1 single-jurisdiction dev; the correction is making the scope explicit rather than refactoring now. A deferred-decisions entry committing the multi-currency evolution to Phase 2 lands alongside this entry, naming the activation condition and the evolution shape (amount-plus-currency at every cost-bearing surface). Phase 2 migration cost is small per D49's analogous OTel-namespace-drift migration argument.

*Discipline addition.* At framing, currency-bearing fields (and other implicit-default fields generally) get reviewed against D12's by-construction posture before they land. The check: any field whose default is a single-jurisdiction or single-locale value should have an explicit D-entry making the scope choice deliberate, or a deferred-decisions entry committing the evolution shape. Mechanical-enforcement upgrade candidate: an AST test that flags currency-name-suffixed fields (`*_usd`, `*_eur`, etc.) without an associated D-entry or deferred-decisions entry referencing them. Tracked alongside the existing methodology mechanical-enforcement upgrades section in `charter/deferred-decisions.md`.

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

## Start simple; refactor at the structural-promotion threshold

Build sessions ship the simplest working version that meets the session's acceptance criteria. Architectural ambition is paid down through refactoring at package boundaries or where a recurring pattern fires the structural-promotion threshold (third instance), not absorbed into single-session scope. The first occurrence of a pattern is implementation; the second is suspicion; the third is the lift to shared abstraction. The discipline keeps individual sessions tractable, lets architectural shape emerge from real-code evidence rather than pre-commitment, and makes refactoring a normal practice between sessions rather than a separate "tech debt" project. Externally corroborated by an enterprise multi-agent system case study at the 2025 LangChain interrupt conference, where the architecture evolved through incremental states with each step preserving working state from the prior step.

## Framing names options; build commits with refinements

Strategic-mode framing produces briefs that name the option space and the strongest recommendation; build-mode sessions commit to the choice with whatever refinements implementation surfaces. The D-entry records both the framing position and the build-time refinement, with reasoning for any deviation. Operator strategic-mode work produces options with positions; Claude Code build-mode work produces commitments with refinements; neither produces gates the other has to pass through. The discipline absorbs vendor-specific surprises, structural-honesty discoveries, and architectural-cost trade-offs without requiring a corrective session, because the brief format anticipates refinement at build. Verified across fourteen-plus instances spanning P5 (D54 return-type deviation, D58 regression-report field shapes, D59 polling-with-timeout pattern, others) and P6 (D63 mechanical-enforcement enrichment, D64 JSON-mode-over-function-calling, D65 two-method ChunkEmbedderPort and cross-store readiness query, others).

The principle is the substrate that makes the briefs/ convention (D43-precedented; methodology document's "Session brief preservation" sub-section) auditable rather than ceremonial: the brief stays at v1, the session log reflection captures any deviation, and the D-entry's Choice text records the structurally honest shape. Without the framing-prompt-as-recommendation posture, build-time refinements either get fought into uniformity with the brief (producing dishonest D-entries) or land as silent deviations (producing audit gaps). Three classes of refinement recur: mechanical (version pinning, library version drift), structural-honesty (build surfaces a layering violation, a leaky abstraction, or an impossibly-shaped invariant the brief did not see), and architectural-cost (the brief's option remains valid but a cheaper alternative surfaces with a real trade-off). Each class is recorded in the D-entry with its reasoning; the three-class taxonomy itself is sub-observation worth surfacing at phase audits when distribution shifts toward any single class.

## Pre-write reconciliation against vendor docs precedes brief drafting

Vendor SDKs and gateway abstractions drift between minor versions; the model's training data lags by months at minimum; specifics drafted from memory ship topology bugs that the build agent has to catch. The discipline is inversely cheap: verifying the four-or-five vendor specifics relevant to a session is a small upfront cost that recovers multiples of itself in build-time saved. Every brief carries a "Pre-write reconciliation" section directing Claude Code to verify the load-bearing vendor specifics before code lands. Verified across four load-bearing instances: S6 LiteLLM env-var quirks, S20 nomic-embed-text task-prefix requirement, S21 Ollama tool-calling fidelity gap (resolved by JSON mode), and the cost-attribution-worst-case at S20 that did not materialise (the verification is valuable when the gap exists and when it does not).

The discipline value compounds along two axes. First, the cost asymmetry: a brief drafted from memory that ships a vendor-specific topology bug costs the build session anywhere from minutes to a full session of debugging plus a corrective commit; the pre-write check that catches it is fifteen minutes of doc-reading. Second, the framing quality: the act of verifying vendor specifics surfaces the questions the brief should be asking even when no quirk is found (S20's pessimistic worst-case for token-attribution led to the defensive `embedding_no_token_count` fallback path landing in the adapter, which is exercised by unit tests for future-tolerance regardless of whether the worst-case currently fires). The discipline is non-negotiable for any session that touches a vendor SDK or gateway abstraction in a new operation mode; LiteLLM/Ollama integration in particular has a higher-than-baseline quirk surface that warrants explicit reconciliation against each new operation mode rather than a per-session blanket check.

---

## Version log

- **v1** (P3 post-close, methodology integration strategic session). Initial articulation, fulfilling the methodology-document commitment in D39. Source material: three reference documents (the Padhanam methodology reference, the methodology-comparison improvements document, and an earlier descriptive-shape methodology draft), integrated under the structure agreed in the framing conversation. The earlier draft's reading-as-primary-tool framing, architect-direction-without-architect-identity framing, what's-being-investigated scope acknowledgement, session-shape and brief-discipline content, DORA proxy specifics, session log tagging block specification, cadence detail, "metrics measure methodology not operator" framing, and Patterns/Failure-modes observation surfaces are absorbed alongside the prescriptive disciplines from the other two sources. The earlier draft's pre-D47 framing of "strategic surface in Claude.ai, build surface in Claude Code" is superseded by D47's mode-declaration discipline collapse to Claude Code as primary. The descriptive scope of the document is bounded explicitly: structural disciplines are prescriptive (committed via D-entries, mechanically enforced); patterns and failure modes are descriptive (accumulate across phases, reviewed at audits). D-numbers reconciled against the live charter (D29 through D48); the comparison source's projected D34–D47 numbering was superseded as P3 closed. The "indifferent" list from the comparison source is omitted: items that mattered enough to surface earned the reverse-Kano section with their specific erosion mechanism. The implementation status summary from the comparison source is relocated to `charter/deferred-decisions.md` under "Methodology mechanical-enforcement upgrades." The four-layer measurement model is folded into this document rather than carved out as a separate `metrics.md` to reduce charter sprawl. Reasoning category: discovery (the methodology document is a Phase 1 deliverable per D39 that had not yet been authored).

- **v2** (P12 Phase 1 close audit, 2026-05-16). Substantive update integrating Phase 1's accumulated discipline-pattern data points per the P12 audit's Finding 2 disposition (discipline-pattern taxonomy with abstraction over session evidence; linkage to the audit-findings document at `charter/p12-audit-findings.md` for evidence cross-references). New content: a "Session shapes" sub-section naming five shapes observed across Phase 1 (substrate, bridge, transport, hygiene, audit) with distinguishing-characteristics paragraphs; six new dated Patterns-observed entries (pre-write reconciliation as architectural discovery with mid-build sub-pattern; principle-versus-framing drift; ship-tooling-with-smoke-exercise; metric-threshold expectations need structural-understanding grounding; reproducibility artefacts land at the session that ships them; methodology-candidate accumulation and audit-resolution rhythm). The promotions consolidate fourteen P11-session methodology candidates from `charter/p12-audit-inputs.md` per the audit's commit-4 dispositions. The version log entry under v1 (P3 post-close) recorded the methodology document's creation against D39's pending-authorship framing; v2 (this entry) records the document's evolution after Phase 1's substrate-completion and the supersession of D39's pending-authorship framing by D113 at the same audit's commit chain. Reasoning category: signal (Phase 1's accumulated discipline-pattern data points become the substrate the v2 hypothesis articulates against; the audit's synthesis converts session-log methodology lines into methodology-document content at the audit's strategic-mode-block altitude).

- **v3** (Pre-Phase-2 architecture synthesis and methodology refinement, 2026-05-16). Three coupled refinements at the strategic-mode session between post-P12 charter-discipline hygiene close and Phase 2 packaging open. First, the Foundation super-section gains a new "Hypothesis and iteration" sub-section establishing the iteration cycle (hypothesis → evidence → audit → revision) as the methodological scaffold for the entire document; the methodology document is named as itself a living hypothesis revised across phase boundaries (v1 at P3 post-close, v2 at P12 audit, v3 at this session, future versions revising based on Phase 2 evidence). "What Padhanam is" sub-section compressed for platform-side content with a pointer to the new `charter/architecture.md` synthesis surface; methodology-side elaboration preserved verbatim. Second, the Work organisation super-section (replacing the prior Work hierarchy + Frameworks standalone H2 sections plus consolidating the Session shape + Session shapes H2 content) restructures into six H3 sub-sections: Strategic tree (bet/phase/package/session hierarchy with horizon discipline); Phase lifecycle (NEW; open with strategic block, in-progress with package sequence, close with phase audit, transition); Package lifecycle (NEW; open with epic note per D43, in-progress with session sequence, close with retrospective and per-package archive per D107); Session lifecycle (NEW; brief preservation per D43, build or strategic execution per D47, log entry with reflection density per shape, captures triage per D48); Session shapes (existing v2 content preserved); Frameworks (LVT at phase/package opening, Kano at D-entry decision points, RICE at package framing — reframed against the lifecycle vocabulary). Third, the Measurement model section gains explicit hypothesis-framing prose at the top establishing that the metrics are themselves part of the hypothesis being tested; the "What the numbers are not" sub-section cross-references the framing. The Charter structure sub-section updates to include `charter/architecture.md` as a Strategic constant alongside bet.md, principles.md, and methodology.md (the three-document relationship per architecture.md's Cross-document map). The version log entry's reasoning category is signal: the v3 refinements absorb P12-close-conversation evidence about document coherence and the three-document relationship, plus the post-P12 charter-discipline hygiene observations about hypothesis-framing language landing across multiple surfaces (D113's supersession of D39's pending-authorship framing; the Measurement model entry's adoption of the living-hypothesis framing). Companion deliverable at the same session: `charter/architecture.md` v1 with seven sections and five Mermaid diagrams synthesising Phase 1 architectural commitments.
