# Phase 2-A P13 framing

Strategic-mode conversation opening Phase 2-A Wave 1 substrate build. P13 is the first build package after the design 7-Step arc closed at Step 7. This brief authors at the Step 7 close thread per the briefs/ discipline pattern five-instance evidenced at arc-step framing; P13 framing is package framing rather than arc step, so the discipline carries by analogy. The convention extends naturally: brief authors at the close thread of the prior strategic-mode block regardless of whether the prior block was arc-step work or package-framing work.

P13 framing substantive conversation opens in a fresh standalone thread. Step 7's deliberate same-thread variation served arc-close work where the substrate was already settled; P13 framing is fresh analytical work (defining package scope, session granularity, first-session prompt content, forward-compat substrate-depth classification). Fresh thread is the right pattern.

## What P13 framing opens

P13 framing opens Phase 2-A Wave 1 substrate build per the `charter/packages.md` Phase 2 packages section landed at the Step 6 commit. The strategic shape commits at Step 6: P13 contents are 1.3 State persistence; 1.1 manual entry cell; latency-tier routing extension at LiteLLM port per D122; Twilio Sandbox setup plus messaging adapter scaffold per D119; Revisable Protocol defined per D114; ConversationFlow Protocol defined per D115.

P13 framing decides three things on top of the Step 6 commitment.

First, how this committed substrate ships across sessions including the depth at each session.

Second, what forward-compat substrate Phase 2-A commits to now because deferring would force major refactor at Phase 2-B or Phase 3+. This is new framing the design 7-Step arc did not explicitly settle. The discipline: build now only if the option to build later without major refactor does not exist; defer with explicit activation trigger otherwise; flag built-now substrate that Phase 2-A operator dogfooding does not exercise.

Third, how Phase 2-A absorbs the substrate-completion carryovers (browser-based authentication; frontend stack confirmation) and the Phase 2-entry hygiene workitems (gold-set audit-emission back-fill; graph-extract reliability fix; schema.md formalisation; CLAUDE.md rebrand) inherited from Phase 1 close per `charter/p12-phase-2-inputs.md`.

The forward-compat dimension surfaces because an operator-supplied product specification at `docs/notes/spec-private-assistant-platform.md` (preserved at P13 framing commit per Decision 6 below) enumerates the substrate primitives a Private Assistant Platform needs across its lifecycle (foundation, model ontology, agents, workflow, execution engine, gates and review, intake, portal, provenance, governance, promotions, integrations, trials). Phase 2-A delivers a subset of these through messaging-first surfaces; Phase 2-B and Phase 3+ extend coverage. The substrate primitives largely map between the spec and Padhanam's commitments. Where they diverge is delivery model (messaging-first conversational versus Studio plus Portal SPA), ICP scope (senior product leader directly versus customer organisations with internal role hierarchies), and depth at each substrate (operator-as-sole-reviewer at Phase 2-A versus full multi-role review at the spec's enterprise scale). The forward-compat discipline determines which substrate shapes Phase 2-A commits now to admit later expansion cleanly.

## Methodology streams

Four methodology streams established across the design 7-Step arc continue into P13 framing without restructuring. Build-methodology covers session-shape calibration, commit-shaped scope discipline, brief-as-recommendation, pre-write reconciliation, brief-preservation discipline. Product-methodology covers the McKinsey 7-Step at S26b plus the auxiliary library at 2.1; P13 framing uses RICE at session-granularity ranking and Kano at choice-point classification. Control-plane methodology covers the technical substrate the build-methodology uses to design product-methodology capabilities. Communication-content discipline (the fourth stream from Step 7) applies lightly at P13 framing since the conversation produces internal-altitude artefacts.

The forward-compat substrate-depth discipline is a candidate addition to build-methodology at first instance. The discipline name: deferral-forces-refactor as the build-now criterion. Phase 2-A close audit tests whether the discipline produced cleaner Phase 2-B extension or unnecessary depth.

## What this conversation produces

Six drafted artefacts that a subsequent Claude Code commit session lands as P13 framing deliverables.

1. **P13 epic note at `charter/packages/p13-epic.md` per D43.** Captures intent, scope, session forecast with explicit forecasts (commit-shape count, D-entry count, session count), substrate commitments (committed substrate plus forward-compat substrate plus deferred substrate), out-of-scope, and open questions surfaced at framing. The epic note is the canonical P13 framing deliverable; subsequent P13 build sessions read it as canonical package framing.

2. **Forward-compat substrate-depth classification table** as a sub-section of the epic note. Each substrate commitment classified into one of three categories: build-now (deferral forces major refactor); defer-with-trigger (deferral does not force major refactor; named activation trigger fires later build); flag-for-future-testing (build-now substrate that Phase 2-A operator dogfooding does not exercise; explicit test-coverage gap with named Phase 2-B or Phase 3+ activation scenario). The recommended classification per pre-conversation Decision 7 below.

3. **Session structure within P13.** Names the sessions with session numbers verified at framing time against `log/sessions.md`. For each session: scope; ordering; dependencies; estimated commit count; the work-streams it consumes from the P13 contents list plus the forward-compat substrate items.

4. **First-session prompt for P13 Wave 1 substrate build.** Ready-to-paste Claude Code session prompt per the project's session-prompt structure. The first-session prompt absorbs verify-against-current-sources discipline directing pre-write reconciliation against current vendor documentation (Twilio Sandbox API; LiteLLM port shape; pgvector or Neo4j surface if touched) and against current S34/S42 principal-derived authentication shape.

5. **Roadmap v6 entry at `charter/roadmap.md` per D44.** Phase 2 packaging commitments. Reasoning category: discovery (Phase 2 substrate scoped at the design 7-Step arc per D93). The v6 entry names Phase 2 as Initiative 2, the eight packages P13-P20 across Phase 2-A and Phase 2-B, and the four-wave structure per stage.

6. **Phase 2 PRD section at `charter/prfaq.md` per D43.** Per Decision 5 below, minimal extension to v2 absorbing the forward-compat posture commitment: Phase 2-A ships narrow at surface and deep-where-deferral-forces-refactor at substrate; speculative substrate flagged for future testing with explicit triggers. V3 revoice defers to Phase 2-A close audit. The PRD section uses spec-aligned vocabulary (agent, workflow, step, signal, gate, intake, case, assertion, provenance, governance, audit trail) where the substrate matches; avoids surface-specific terms (Studio, Portal, Canvas, My Tasks) because those commit to a delivery model Phase 2-A does not ship.

Plus two close deliverables:

7. **Pre-conversation decisions audit at close.** Did the brief's pre-conversation recommendations hold against the conversation's substantive work? Where did the conversation revise? Pattern-recurrence test for brief-carries-recommendations.

8. **Carry-forward to subsequent P13 build sessions plus Phase 2-A Wave 2 framing.** Open questions, observations, or commitments emerging during P13 framing that warrant treatment downstream. Plus the P13 framing close marker addition at `charter/current-package.md` naming P13 build sessions as the next strategic-mode block.

## Context to read first

In order:

1. `charter/phase-2-design-7step.md` Step 7 section. The arc-close canonical content. Particularly the package-timeline diagram, the executive summary, and the five supporting arguments. P13 framing inherits the strategic shape this section commits.

2. `charter/packages.md` Phase 2 packages section. The P13-P20 commitment landed at Step 6 commit; P13 contents enumerated explicitly.

3. `charter/architecture.md` Phase 2 architectural primitives section. The six primitives committed at Phase 2-A. P13 substrate definitions anchor against the primitives' shape. P13 framing extends this section per Decision 7 below.

4. `charter/principles.md` User safety section. The no-silent-operation principle landed at Step 6 commit per D121. P13 substrate must honour the principle at every introduction surface.

5. `charter/decisions.md` D114 through D123 entries. The ten Phase 2 design D-entries committed at Step 6.

6. `charter/deferred-decisions.md` Phase 2 design 7-Step deferrals section plus the existing deferred-decisions entries on forkable-vs-non-forkable architecture, production-deployment infrastructure, HTTP API for external integration. P13 framing may extend this file with multiple new entries per Decision 7.

7. `charter/p12-phase-2-inputs.md`. Phase 2 substrate-completion carryovers, Phase 2-entry hygiene workitems, bundle-or-distribute observation, Phase 2 entry handoff artefact list.

8. `charter/phase-2-user-segment.md`. Senior-leader ICP commitment per Step 5 Decision 1. Test condition for P13 substrate.

9. `charter/methodology.md` Package lifecycle and Frameworks sub-sections. The discipline against which P13 framing operates.

10. `charter/roadmap.md`. Current v5 entry; v6 entry lands at this conversation per Decision 4.

11. `charter/packages/p11-epic.md`. Most recent epic note as structural precedent for the P13 epic note shape.

12. `charter/schema.md` plus the S34 D98 principal-derived authentication shape. Reference for ActorContext extension per Decision 7.

13. `briefs/phase-2/design-7step-step-7.md` plus `briefs/phase-2/design-7step-step-7-brief-commit.md`. Structural precedent for the brief shape.

14. `docs/notes/spec-private-assistant-platform.md`. Operator-supplied product specification for a governed Private Assistant Platform, preserved at P13 framing brief commit per Decision 6 option (c). Particularly: §5 Design Principles (the principles map to Padhanam's commitments); §7 Domain Model (vocabulary cross-check for the Phase 2 PRD); §8 Functional Modules (substrate primitives across foundation, model ontology, agents, workflow, execution, gates, intake, portal, provenance, governance, promotions, integrations, trials); §11 Non-Functional Requirements (architecture, multi-tenancy, security commitments); §13 Build Scope Guidance (sequencing reference). Reference document, not binding spec.

15. `log/sessions.md` tail. Recent session-prompt structure plus the post-Step-7-commit close marker. Verify next session number for the first-session prompt.

16. `log/packages.md`. Package retrospective convention; informs the epic note's forecast-versus-as-built discipline.

## Pre-conversation decisions

Seven decisions. The brief carries my read on each. The substantive conversation either confirms or revises.

### Decision 1: Substrate-completion carryover disposition

Browser-based authentication and frontend stack confirmation sit at Phase 1 close substrate-completion territory but Phase 1 closed without them addressed. Three options.

(a) Pre-P13 substrate-completion sequence. Browser-based auth as one build session; frontend stack as a strategic-mode decision block. Both land before P13 Wave 1 opens.

(b) Absorb into P13 sessions. First P13 session handles browser-based auth alongside state persistence; frontend stack confirmation as an inline strategic decision at P13 framing.

(c) Land as a parallel package P12.5.

**Recommend (a).** Browser-based auth is one substrate session; frontend stack is one strategic-mode block. Both land cleanly before P13's first build session opens. Frontend stack confirmation is a multi-option Kano-framed assessment that warrants its own strategic-mode block rather than absorbing into P13 framing. The forward-compat substrate-depth discipline (Decision 7) raises P13 session weight; absorbing auth substrate on top of that would force structural drift at the first session.

### Decision 2: Phase 2-entry hygiene workitems disposition

Four hygiene workitems carry from Phase 1 close per `charter/p12-phase-2-inputs.md`. Two options.

(a) Bundle into one pre-P13 hygiene session per the pre-P12-hygiene precedent.

(b) Distribute across P13's first 2-3 sessions.

**Recommend (a).** Bundle. The four items are heterogeneous and would create context-switching cost inside P13 sessions. The forward-compat substrate-depth discipline already raises P13 session weight; distributing hygiene compounds the cost.

### Decision 3: P13 session granularity

The forward-compat substrate-depth discipline per Decision 7 increases substrate per session. Three options.

(a) Three sessions per the original recommendation. Each session ships substantially more substrate than the minimum-version brief specified.

(a') Four sessions splitting the foundational layer. Session 1 ships state persistence plus Case/DataPoint/Assertion plus Revisable Protocol; Session 2 ships ActorContext plus authorisation decorator plus Gate entity plus intake record; Session 3 ships messaging substrate plus ConversationFlow Protocol plus structured output; Session 4 ships manual entry cell plus latency-tier routing plus four-layer model ontology shape.

(b) Five or six small sessions.

**Recommend (a').** Four sessions. Better commit-shaped scope per session given forward-compat additions. Session 1 anchors the domain model. Session 2 anchors actor/authorisation/gate/intake substrate. Session 3 anchors the messaging substrate. Session 4 exercises the substrate end-to-end at manual entry plus latency-tier routing. The alternative (a) creates session-scope pressure that risks drift; (b) creates session-scaffold overhead disproportionate to the work.

### Decision 4: Roadmap v6 entry framing

The roadmap currently sits at v5. Phase 2 commitments need a v6 entry per D44. Two options.

(a) Land at P13 framing as Phase 2 packaging commitment. Reasoning category: discovery.

(b) Defer to a separate strategic-mode block.

**Recommend (a).** Land at P13 framing as inline deliverable. The roadmap is a living artefact per D44; Phase 2 commitments are already canonical in `charter/packages.md`; the v6 entry is the audit-trail surface recording the commitment landing alongside reasoning category. Reasoning category is discovery: Phase 2 substrate was scoped at the design 7-Step arc per D93; the arc converged on eight packages across two stages.

### Decision 5: Phase 2 PRD shape

The prfaq v2 carries a mid-flight correction per the post-P12 strategic block; v3 revoice deferred to "Phase 1 close audit." The P12 audit closed without v3 landing. Three options.

(a) Land v3 at P13 framing.

(b) Defer v3 to Phase 2-A close audit. Land a Phase 2 PRD section at prfaq.md extending v2 minimally at P13 framing. The section absorbs the forward-compat posture commitment and uses spec-aligned substrate vocabulary.

(c) Defer v3 entirely without extending at P13 framing.

**Recommend (b).** Phase 2-A close has materially more evidence than P13 framing does (real Phase 2-A build sessions; operator dogfooding evidence; senior-leader-ICP test condition validation). V3 wants that evidence. At P13 framing, the Phase 2 PRD section names: the Phase 2 strategic shape (D93 methodology-as-product positioning; eight packages; six architectural primitives; senior-leader ICP); the forward-compat posture (deep-where-deferral-forces-refactor substrate; speculative substrate flagged for future testing); the substrate vocabulary aligned with the spec where the primitives match. The section is minimal-substrate and revisable at Phase 2-A close.

### Decision 6: Spec-as-architectural-input commitment

The operator-supplied product specification enumerates substrate primitives across the Private Assistant Platform's full lifecycle. The spec's substrate primitives largely map to Padhanam's commitments; the spec's surface architecture (Studio plus Portal SPA) does not match Phase 2-A's messaging-first delivery; the spec's ICP (customer organisations) does not match Phase 2-A's senior-leader ICP. Three options.

(a) Treat the spec as binding architectural reference. Phase 2-A explicitly verifies against the spec at every substrate commitment. Cross-references in the P13 epic note plus the architecture.md Phase 2 primitives section.

(b) Treat the spec as non-binding architectural reference held at `docs/notes/` for selective consultation.

(c) Commit specific extracts (the frontend/backend boundary rule at §11.3; the principles 5-16 prose at §5; the audit/provenance vocabulary at §7) as charter additions at P13 framing. Treat the remainder as reference held at `docs/notes/spec-private-assistant-platform.md`. Phase 2-A's substrate verifies against the spec where the substrate matches; Phase 2-B and Phase 3+ extension verifies against the spec where the surface matches.

**Recommend (c).** The spec's principles and substrate vocabulary are sharper than the current charter prose; the spec's surface architecture is not Padhanam's Phase 2-A commitment. Selective extraction lets Padhanam absorb the strengthening additions without committing to the delivery model Phase 2-A explicitly differs from. Specific extracts at P13 framing: the frontend/backend boundary rule (one user action equals one backend call; backend owns every state machine) as a new D-entry or principles.md addition; the audit-trail-as-source-of-truth commitment as a sharpening of existing D26 plus D121 prose; the originals-never-erased commitment as a sharpening of D114 prose; the authority plus data certainty plus outcome certainty independence as a deferred-decisions entry activating at Phase 2-B when methodology library at 2.1 has more substrate. Spec preservation at `docs/notes/spec-private-assistant-platform.md` happens at the P13 framing brief commit (this commit). The Phase 2 PRD section per Decision 5 uses spec-aligned vocabulary where substrate matches.

### Decision 7: Forward-compat substrate-depth classification

The discipline: build now only if deferring would force major refactor; defer with named activation trigger otherwise; flag built-now substrate Phase 2-A operator dogfooding does not exercise. The substrate set classified per the discipline:

**Build now (deferral forces major refactor):**

ConversationFlow Protocol as presentation adapter only. D115 already commits the discipline. Enforcement at P13 substrate; thin transport adapters over a transport-agnostic state machine. The discipline applies across every P13 plus P14 plus P15 plus P16 use case.

Structured output object per use case (output contract substrate). Every methodology application and every gate-actioned event produces a typed output that ConversationFlow renders conversationally and that a future SPA would render structurally. Cost now: one typed schema per use case at write time. Cost later: refactoring N use cases.

ActorContext extension to TenantContext. Carries actor identity plus role plus authorisation scope. Phase 2-A populates with the operator and a default authorisation set. Cost now: schema and signature change at one altitude. Cost later: touching every use case signature plus every authorisation check site.

Authorisation enforced at use case boundary via decorator or middleware. Phase 2-A: every use case requires operator role. Cost now: trivial check at one boundary. Cost later: retrofit across every use case.

Four-layer model ontology shape (Provider plus Account plus Version plus Configuration). D122 latency-tier extension at P13 already touches the LiteLLM port. While touching it, the four-layer naming is cheap. Cost now: naming and substrate shape; no catalogue UX. Cost later: refactor the model port and call sites.

Gate as first-class domain entity with state machine (open then actioned or bypassed or timed_out or declined) plus gate action vocabulary plus signatory rule abstraction. The three-tier consent-and-awareness framework per D116 is the framework concept; Gate is the entity it operates on. Phase 2-A populates with single-signatory operator gates. Cost now: domain entity definition. Cost later: refactor every place that handles consent inline.

Intake record as first-class entity captured before any execution. P13 manual entry and P14 calendar/email reads ARE the ingestion paths. Adding intake record now is cheap (it is the boundary of work already being done). Cost later: retrofit ingestion paths across multiple sub-problems.

Case plus Data Point plus Assertion domain entities at substrate level. The substrate already exists implicitly: portfolio item at 1.3 maps to Case; goals/statuses/methodology applications are Data Points; D114 Revisable Protocol's revisions are Assertions. Cost now: naming alignment with the spec's vocabulary plus making the entities first-class. Cost later: refactor the persistence layer to extract Case/DataPoint/Assertion from portfolio-item-as-monolith.

Methodology-as-workflow data model with explicit steps plus signals plus versioning declarations. P14 methodology library substrate. Versioning via D114 is already committed. Steps and signals declarations are additions. Phase 2-A does not execute methodologies as live agent workflows (P18 territory) but the data model declares steps and signals. Cost now: data model addition. Cost later: P18 adds the data model concurrent with agent runtime build, which is two concerns at once and risks structural drift.

Governance artefact hierarchy shape (Platform then Organisation then Workspace then Agent inheritance). P14 governance work. Phase 2-A populates with operator-as-organisation level and a single-default-workspace level. Cost now: inheritance shape commitment. Cost later: refactor every governance-config-check site to handle multi-level resolution.

**Defer with named activation trigger:**

Role hierarchy with inheritance machinery. Activation trigger: Phase 2-B or Phase 3+ adds a second role. The build-now substrate (ActorContext plus authorisation decorator) supports role hierarchy as a pure extension at activation time. Deferred-decisions entry lands at P13 framing.

Workspace abstraction within tenant. Activation trigger: commercial deployment direction commits a customer-organisation buyer-model. The existing forkable-vs-non-forkable deferred-decisions entry covers this; D93 keeps it deferred indefinitely unless Phase 3+ surfaces commercial-deployment evidence. Cross-reference at P13 framing rather than new entry.

Environment plus Promotion abstractions. Activation trigger: Phase 2-B production-deployment infrastructure work per the existing deferred-decisions entry. Build-now substrate stubs the abstractions; Phase 2-B fills them in. Cross-reference at P13 framing rather than new entry.

Webhook plus outbound API. Activation trigger: external integration consumer arrives per the existing deferred-decisions entry. Build-now HTTP surface at S34 plus S42 exposes use cases; webhook plus API extensions plug in at activation. Cross-reference at P13 framing rather than new entry.

Trials (active testing scheduler revival). Activation trigger: Phase 2-B+ per D92. Cross-reference to existing deferred-decisions entry.

Principal polymorphic shape (human-actor plus machine-actor). Activation trigger: pending P13 framing pre-write reconciliation against current S34 D98 principal shape. If the current shape is already sealed and extensible, defer the machine-actor variant; the activation trigger is API caller arrival at Phase 2-B+. If the current shape is hardcoded to user, this moves to build-now classification because deferring forces refactor of every principal-derived call site. The brief recommends running the verification at P13 framing pre-write reconciliation and resolving classification at the conversation rather than pre-committing.

**Flag for future testing (build-now substrate Phase 2-A operator dogfooding does not exercise):**

Each item lands as a deferred-decisions entry with activation trigger naming the Phase 2-B or Phase 3 scenario that exercises the substrate, plus a Phase 2-A close audit input naming the test coverage gap. Specifically:

Authorisation paths beyond operator-role check. Activation: Phase 2-B+ adds a second role. Test coverage gap: no Phase 2-A scenario trips authorisation rejection paths.

Governance hierarchy levels above Organisation and below default Workspace. Activation: Phase 3+ commercial deployment or Phase 2-B B9 extensions. Test coverage gap: Phase 2-A has no Platform or sub-Workspace inhabitants.

Multi-signatory Gate paths. Activation: Phase 2-B+ surface adds multi-actor scenarios. Test coverage gap: Phase 2-A is single-signatory.

Intake authority profiles beyond operator-authority. Activation: Phase 2-B+ adds additional intake sources with different authority profiles. Test coverage gap: Phase 2-A has no other sources.

Machine-actor principal path. Activation: API caller arrives at Phase 2-B+. Test coverage gap: built only if pre-write reconciliation determines build-now classification.

Methodology-step-and-signal declarations beyond what P14's four methodologies populate. Activation: P17 B9 methodology authoring adds new methodology shapes. Test coverage gap: substrate accepts more shapes than four-methodology testing exercises.

Case-DataPoint-Assertion shapes beyond portfolio-item-shaped use. Activation: Phase 2-B+ adds new domain entity types. Test coverage gap: Phase 2-A operator dogfooding generates portfolio-item-shaped Cases only.

**Recommend the classification above as the P13 framing commitment set.** Substantive conversation either confirms or revises each entry's category. The recommendation prioritises the operator's rule (build now only if deferring forces major refactor) and acknowledges that some build-now substrate is speculative and gets flagged for future testing.

## Substantive work

P13 framing's substantive work runs across three work-streams sharing the conversation.

### Work-stream 1: P13 epic note authoring

Author `charter/packages/p13-epic.md` per D43 plus the `charter/packages/p11-epic.md` structural precedent. Sections:

Package goal naming the substrate P13 delivers and the test condition Phase 2-A Wave 1 close fires.

Package contents enumerating: the six committed work-streams from Step 6 (state persistence; manual entry cell; latency-tier routing; Twilio Sandbox plus messaging adapter; Revisable Protocol; ConversationFlow Protocol); the build-now forward-compat substrate items per Decision 7 (structured output object; ActorContext; authorisation decorator; four-layer model ontology shape; Gate entity; intake record; Case/DataPoint/Assertion naming alignment); the cross-referenced defer-with-trigger entries (workspace; environment/promotion; webhook/API; trials; role hierarchy; principal pending verification); the substrate-completion carryover disposition per Decision 1; the four hygiene workitems disposition per Decision 2.

Session forecast per Decision 3 with per-session scope summary plus dependency map. Four sessions recommended.

D-entry forecast. The original forecast of 4-7 D-entries rises to 7-12: state persistence schema; Revisable Protocol shape; ConversationFlow Protocol shape; messaging adapter shape; latency-tier hint vocabulary; manual entry cell discipline; ActorContext extension; authorisation decorator; four-layer model ontology shape commitment; Gate entity shape; intake record shape; Case/DataPoint/Assertion naming and shape. Some bundle into single D-entries; some warrant standalone D-entries. P13 framing settles the bundling.

Out of scope explicitly. Workspace abstraction; multi-signatory gates; multi-role authorisation paths; environment promotions; webhook outbound; trials; production deployment; SPA frontend; customer-organisation role hierarchy beyond operator. Each cross-referenced to deferred-decisions or to the spec section the deferral applies to.

Open questions surfaced at framing. Pre-write reconciliation outcomes (particularly principal shape verification).

Forward-compat substrate-depth classification table per Decision 7 as a structured sub-section.

### Work-stream 2: First-session prompt drafting

Per the project's session-prompt structure. Per Decision 3 option (a'), the first session covers: state persistence at 1.3 substrate; Revisable Protocol substrate definition per D114; Case plus Data Point plus Assertion naming alignment. The first-session prompt scopes to the first session's substrate only.

The first-session prompt absorbs verify-against-current-sources discipline: pre-write reconciliation against current pgvector or persistence-layer conventions if touched; against current schema.md TenantContext shape if ActorContext extension lands at the first session (likely the second session per the recommended split, but verify); against current S34 D98 principal shape for Decision 7's principal-pending-verification entry.

### Work-stream 3: Roadmap v6 plus Phase 2 PRD landing plus spec-extracted charter additions

Per Decisions 4 and 5 and 6.

Roadmap v6 entry at `charter/roadmap.md` with reasoning category discovery. The v6 entry names Phase 2 as Initiative 2, the eight packages P13-P20 across Phase 2-A and Phase 2-B, the four-wave structure per stage, the forward-compat posture commitment.

Phase 2 PRD section at `charter/prfaq.md` (minimal extension per Decision 5). The section names the Phase 2 strategic shape, the forward-compat posture, the substrate vocabulary aligned with the spec where the primitives match.

Spec-extracted charter additions per Decision 6 option (c). Specifically: frontend/backend boundary rule as new D-entry or `charter/principles.md` addition; audit-trail-as-source-of-truth as a sharpening of D26/D121 prose; originals-never-erased as a sharpening of D114 prose; authority plus data certainty plus outcome certainty independence as a deferred-decisions entry; spec preservation at `docs/notes/spec-private-assistant-platform.md` already landed at this brief commit so the substantive conversation references it; cross-reference at Phase 2-B and Phase 3+ framing.

Charter architecture.md addition: new sub-section on forward-compat-without-major-refactor as Phase 2-A discipline. The discipline statement, the build-now criterion (deferral-forces-refactor), the defer-with-trigger pattern, the flag-for-future-testing convention. Cross-references the P13 epic note's classification table and the deferred-decisions entries.

All Work-stream 3 artefacts draft at this conversation and land at the Claude Code commit session following P13 framing.

## Reflection prompts at session close

Six reflection prompts answer in the session log entry.

1. **Briefs/ discipline check, sixth instance by analogy.** This brief authored at Step 7 close thread per the briefs/ discipline pattern extended by analogy from arc-step framing to package framing. Confirm the pattern carries across the altitude shift; or note where it breaks.

2. **Pre-conversation decisions audit.** Did the conversation confirm or revise each of the seven pre-conversation decisions? Where did the brief's recommendation hold and where did substantive conversation pressure surface revisions? Pattern-recurrence test for brief-carries-recommendations.

3. **Forward-compat substrate-depth discipline test.** The first-instance test of the discipline. Did the classification framework hold against substantive conversation? Did each entry's category settle cleanly? Did the discipline surface speculative substrate the original Phase 2-A scope would have shipped without examination? Or did the discipline surface scope creep the operator's rule rejects?

4. **Spec-as-architectural-input absorption.** Per Decision 6, did the spec extracts strengthen the charter prose? Are there spec sections the extracts missed? Does the spec preservation at `docs/notes/spec-private-assistant-platform.md` produce a useful cross-reference surface for Phase 2-B and Phase 3+ framing?

5. **Phase 2-A Wave 1 readiness verdict.** Is the P13 epic note plus first-session prompt plus roadmap v6 entry plus Phase 2 PRD section plus spec-extracted charter additions plus architecture.md forward-compat sub-section sufficient to open the first P13 build session cleanly? What gaps surface that warrant resolution before the first session opens?

6. **Carry-forward to subsequent P13 build sessions plus Phase 2-A Wave 2 framing.** Open questions, methodology observations, or strategic commitments emerging at P13 framing that warrant treatment downstream. Specifically: which forward-compat substrate items get flagged for Phase 2-A close audit input as test-coverage gaps; which spec sections defer to Phase 2-B framing review; which methodology candidates surface from the substrate-depth discipline first-instance.

Optional methodology lines worth observing. Candidate observations: forward-compat-without-major-refactor as discrete build-methodology discipline (first instance); package-framing brief discipline as discrete pattern from arc-step framing (sixth instance by analogy); spec-as-architectural-input absorption discipline as pattern for future external-reference integration.

## What this conversation does not do

- Run P13 build sessions (P13 build sessions follow via Claude Code).
- Author P14, P15, P16, or P17-P20 epic notes.
- Decide Phase 3 strategic shape.
- Revise the eight-package Phase 2 structure committed at Step 6.
- Author the case-study publication artefact.
- Land charter edits directly (Claude Code commit session follows).
- Open Phase 2-A Wave 2 framing or any Phase 2-B work.
- Run substantive code edits or build work.
- Land v3 prfaq revoice per Decision 5.
- Commit the spec as binding architectural reference per Decision 6 option (a).
- Build forward-compat substrate beyond what deferral-forces-refactor justifies per Decision 7.
- Build SPA, Studio, Portal, Canvas, or any spec-specific surface architecture beyond the substrate primitives.
- Build customer-organisation role hierarchy beyond operator-only at Phase 2-A.
- Run agent-execution end-to-end (P18 territory).
- Build active testing or trials (Phase 2-B+ territory).
