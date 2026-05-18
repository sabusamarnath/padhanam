# Phase 2 design — 7-Step arc — Step 4 commit session

## Identification

Mode: strategic (charter commit; no code changes; lint and tests not required at this session).
Block: Phase 2 design — McKinsey 7-Step arc — Step 4 (Plan) commit landing.
Branch: operator-selected at session open.

## Goal at session close

- `charter/phase-2-design-7step.md` carries a new `## Step 4: Plan` section appended after the Step 3 close paragraph, with sub-sections (opener; eleven workplan entries grouped by branch; dogfooding-evidence record; carry-forward to Step 5; Step 4 close).
- `charter/competitors.md` exists as a new charter-grade reference file carrying the twenty-two-entry competitor catalog, with framing-flag at top naming it as reference catalog with end-of-Phase-3 competitive landscape review as the binding strategy artefact.
- `charter/current-package.md` gains a new close marker paragraph appended after the Step 3 close marker (append-only language per the Step 2 commit's correction validated at Step 3 first recurrence test).
- `briefs/phase-2/design-7step-step-4.md` exists carrying the pre-conversation brief verbatim.
- `briefs/phase-2/design-7step-step-4-commit.md` preserves this commit-session prompt verbatim.
- Session log entry appended to `log/sessions.md` matching the Step 3 commit entry's shape, scaled for the three-commit session structure.

## Context to read first

In order. Read in ranges where files exceed 200 lines.

1. `charter/phase-2-design-7step.md`. Steps 1, 2, and 3 sections in full. Confirm Step 3 close paragraph is terminal; Step 4 section appends immediately after.
2. `charter/current-package.md` (top section). Confirm the close marker structure after the Step 3 commit. The Step 4 commit appends a new paragraph after Step 3's marker.
3. `log/sessions.md`. Latest entry is the Step 3 commit; match its shape for the Step 4 commit entry. Note that this session has three commits rather than two; the entry's Produced section accommodates this.
4. `briefs/phase-2/design-7step-step-3.md` and `briefs/phase-2/design-7step-step-3-commit.md`. Brief shape and commit-prompt-brief shape precedents.
5. `briefs/p8/mckinsey-7-step.md`. The Planner role's authored specification, cited in the Step 4 dogfooding-evidence record.

## Pre-write reconciliation

1. **D-entry count.** Latest entry remains D113. No new D-entries this session. The dogfooding-evidence record cites D85 (McKinsey 7-Step methodology authoring placement) and D82 (intelligence-layer commitment); both exist as summary lines in active `charter/decisions.md` with full content in `docs/archive/decisions/phase-1.md`.

2. **Current-package.md state.** Read the file and confirm the Step 3 close marker paragraph from the Step 3 commit. The Step 4 commit appends a new paragraph after Step 3's marker; append-only operation; prior content preserved unchanged.

3. **Append point at `charter/phase-2-design-7step.md`.** Confirm the Step 3 close paragraph is the file's current terminal content; append the Step 4 section after it without modifying Step 1, 2, or 3 content.

4. **Brief authoring timing.** The Step 4 brief was authored before substantive Step 4 work but within the same Claude.ai conversation as Step 3 (the conversation continued in the same thread rather than opening a new one). Treat as pre-conversation brief (not synthetic-retrospective); surface the framing nuance in the session log reflection prompt 4.

5. **New charter file landing.** `charter/competitors.md` does not exist at the project. New file; one of three commits this session.

6. **Three-commit session structure.** First session in the arc with three commits rather than two. Pre-write reconciliation accommodates by sequencing: commit 1 (Step 4 section plus current-package append plus brief preservation plus commit-prompt preservation), commit 2 (competitor catalog), commit 3 (session log entry). The session log entry's Produced section reflects three commits; methodology lines may include the three-commit-shape as observation.

7. **Carryover from prior commits.** The stale "P11 framed; S39 next" header at `charter/current-package.md` line 5 remains pre-existing structural drift; out of scope at this session per AC 8.

## Commits

### Commit 1: Step 4 artefacts land at charter file plus current-package append plus brief preservation plus commit-prompt preservation

Conventional commit message: `docs(charter): phase 2 design — 7-step arc Step 4 workplan, dogfooding evidence at four-instance, senior-leader ICP refinement integrated`

Three-paragraph commit body. Paragraph 1: names what the new section lands (eleven workplan entries spanning six branches at find-rhythm-plus-settle-in lifecycle stages; dogfooding-evidence record at fourth-instance methodology-template-extensibility-without-breaking evidence; five open questions carrying forward to Step 5). Paragraph 2: names the substantial mid-conversation scope additions (multi-device sync at 1.3; work-apps and voice as eighth and ninth substrate types at 1.1; methodology audit trail plus matching plus comprehension surface at 2.1; three-tier consent-and-awareness framework at 5.4; senior-leader ICP refinement integrated mid-conversation from competitor research input). Paragraph 3: names that the methodology-template-extensibility-without-breaking pattern now reaches four-instance evidence across all four sequential roles (ProblemFramer, Disaggregator, Prioritiser, Planner); the Phase 2 methodology-extension workitem moves from three-instance candidate at Step 3 to four-instance observed-pattern at this Step.

**Append the following content to `charter/phase-2-design-7step.md` as a new `## Step 4: Plan` section, placed immediately after the Step 3 close paragraph. Content verbatim, no in-line editing:**

```markdown
## Step 4: Plan

Step 4 applied the McKinsey 7-Step Planner role's discipline to the inclusive top quartile (eleven sub-problems) from Step 3. The role's function-focused system_prompt commits the role to "produce workplans for prioritised sub-problems... for each priority branch, specify the analyses to be run, the data needed, the owners, the deliverables, and the deadlines. You do not run analyses; you plan them." The McKinsey override layered "Workplan structure: hypothesis, analyses, data needed, owner, deadline, deliverable." Posture 1.5 dogfooding continued from Steps 1, 2, and 3.

Five pre-conversation decisions framed the workplan approach. Decision 1 (top quartile cut): inclusive eleven-item cut over strict five-item cut, to cover both foundational layer and user-facing surface in Phase 2 deliverable. Decision 2 (workplan granularity): per-sub-problem rather than per-cluster, preserving Step 2 MECE structure and Step 3 scoring rationale. Decision 3 (sequencing): score-first within dependency constraints, permitting surface-layer items to start once foundational dependencies have minimum-viable substrate. Decision 4 (lifecycle-stage prioritisation): find-rhythm-plus-settle-in across all priority items first, with watch and adapt stages deferring to Phase 3 or later. Decision 5 (owner framing): role-function distribution tagging preserving the role-distribution audit substrate.

Three operator-initiated scope additions during workplan construction expanded multiple entries. The multi-device sync architectural commitment at 1.3 (state synchronisation across same user's multiple devices, with Phase 2-A single-device implementation plus architectural commitment, Phase 2-B or Phase 3 multi-device implementation). The work-apps expansion at 1.1 (CRM, expense management, project management, ticketing as eighth substrate type, raising the matrix from twenty-eight to thirty-two cells). The methodology library expansion at 2.1 across three updates: audit-trail-lineage for methodology adaptation; minimum-viable matching at find-rhythm-plus-settle-in (item-type rules, user-declared preferences at setup, domain inference); effect-first surface with name as secondary, comprehension-at-acceptance discipline, and lightweight-recommendation versus deep-methodology-application bifurcation.

Two design constraints surfaced from competitor research input mid-conversation. The senior-leader ICP refinement (sharpening the Step 1 broader busy-professional framing to senior leaders at established firms augmenting human EA/CoS plus founders at early-stage tier, with vertical-wedge candidates in financial services, legal, healthcare for Phase 2-B or Phase 3 sequencing) reframes every workplan entry's user definition without rewriting the entries themselves. The voice substrate and voice delivery channel addition (voice as ninth substrate type at 1.1, raising matrix to thirty-six cells; voice as secondary delivery channel at 3.1 with Phase 2-A messaging-first staying primary and Phase 2-B adding voice based on operator dogfooding evidence).

Two structural insights emerged that connect across multiple workplan entries. The three-tier consent-and-awareness framework at 5.4 (Tier 1 real-time review for high-danger classes; Tier 2 surfaced operation with user-controlled digest review cadence; Tier 3 silent operation does not exist) replaces blanket-override patterns with awareness-cadence configuration. The framework operates as commercial positioning differentiator beyond safety hygiene, aligned with the procurement-grade audit-trailed-approval-first defensibility pattern the May 2026 competitor research identifies for the senior-leader ICP. The framework's three-tier shape connects to the four-stage temporal lifecycle from Step 2: find-rhythm operates at Tier 1; settle-in migrates routine classes to Tier 2; watch surfaces via digest; adapt triggers temporary Tier 1 escalation at pattern deviation.

### Workplan entries

#### Branch 1: Portfolio existence

##### 1.3 State persistence

**Hypothesis.** A persistent portfolio state surface, built on Phase 1's database-per-tenant substrate per D32, eliminates the portfolio-resets-each-session failure mode AND supports state synchronisation across the same user's multiple devices. Phase 2-A implements single-device persistence; multi-device sync architecturally committed from the start so the design does not need refactoring when multi-device dogfooding need surfaces. Implementation of full multi-device sync defers to Phase 2-B or Phase 3 based on dogfooding evidence.

**Analyses to be run.** Specify the portfolio aggregate at `contexts/portfolio/` with append-only state-mutation discipline per D26 and D31. Specify multi-device sync architecture as a first-class commitment: backend-of-record at per-tenant Postgres; eventual consistency for reads acceptable for most cases; last-write-wins for most writes; conflict-resolution discipline named explicitly for high-frequency edit cases (deferred to Phase 2-B implementation). Specify device-identity mechanics: how the platform recognises which device the same user is on; how authentication state propagates across devices. Implement the aggregate with hexagonal layout. Phase 2-A implements single-device write-through; multi-device read consistency arrives in Phase 2-B.

**Data needed.** Existing per-tenant Postgres schema substrate from Phase 1. D75 agent aggregate shape as structural precedent. D26 append-only commitments. D31 revisions pattern. D32 database-per-tenant routing. Operator's actual device inventory (phone, laptop, tablet, work computer) for the dogfooding test. Browser-based authentication carryover from `charter/current-package.md` becomes prerequisite for multi-device because session management across devices requires real session handling.

**Owner.** Architect (aggregate specification, append-only design choice, multi-device sync architecture) plus engineer (implementation, contract tests) plus operator dogfooding (multi-session and multi-device continuity validation).

**Deadline.** Phase 2-A foundational. First in dependency order at Branch 1; nothing downstream operationalises without persistent state. Multi-device implementation defers to Phase 2-B.

**Deliverable.** Phase 2-A: single-device portfolio state persisting in per-tenant Postgres with multi-device sync architecturally committed (schema, port shape, conflict-resolution discipline named even if not implemented). Phase 2-B: multi-device read consistency operational; operator dogfooding instance verifies portfolio state matches across at least two devices.

##### 1.1 Substrate connection

**Hypothesis.** Substrate connection across nine substrate types (calendar, email, documents, notes, messaging, manual entry, existing trackers, work applications, voice) at four integration functions (read, observe, write, acknowledge) produces an integrated portfolio the user does not have to mentally integrate. The thirty-six matrix cells sequence per workplan into Phase 2-A versus deferred cells; operator dogfooding informs which cells land first within the broader busy-professional plus senior-leader ICP framing.

**Analyses to be run.** Specify the SubstrateConnection port at `contexts/portfolio/ports/`. Specify Phase 2-A cell prioritisation. Recommended Phase 2-A starting cells: manual entry (write only, no external dependency), calendar-read (D77's calendar tool service deferred-decisions entry activates), email-read (D77's email tool service deferred-decisions entry activates). Implement the prioritised cells with adapters per D14 configuration-plus-tools-plus-bounded-extensions customer-deployment model. Work-app cells (CRM, expense management, project management, ticketing, ERP, support tools) and voice cells (voice memo capture, voice transcription from existing voice substrates, voice as input modality) defer to Phase 2-B or Phase 3 given the integration-pattern diversity within those substrate types. Validate against operator's actual substrate inventory.

**Data needed.** Substrate-tool service specifications per the calendar tool service and email tool service deferred-decisions entries. D14 customer-deployment model. D78 personal-use deployment Phase C activation per current-package.md carryover. Operator-specific substrate inventory (which calendars, which email accounts, which document stores, which messaging apps, which work apps, which voice substrates) for the dogfooding test. Senior-leader ICP framing per the Step 4 mid-conversation refinement: work-app cells likely more important earlier for senior leaders than for general busy professionals.

**Owner.** Architect (port and matrix-cell-prioritisation design) plus engineer (Phase 2-A adapter implementation) plus operator dogfooding (cell-prioritisation input, validation).

**Deadline.** Phase 2-A for foundational cells (manual entry plus calendar-read plus email-read minimum). Phase 2-B for messaging-read, work-app cells (at least one based on operator dogfooding evidence about which work-app categories matter most), voice cells based on dogfooding evidence about voice value.

**Deliverable.** SubstrateConnection port at `contexts/portfolio/ports/`. Phase 2-A adapter implementations covering at least three substrate cells. Per-cell tenant-isolation contract tests per D24. Operator dogfooding instance has at least three substrates connected with portfolio updating from each. Phase 2-B delivery extends to at least one work-app cell and at least one messaging-cell.

##### 1.5 User-authored items

**Hypothesis.** Direct user authorship via messaging-first delivery per Step 3's design constraint captures high-importance items the user thinks of explicitly. User-authored items plus substrate-derived items produce a more complete portfolio than either source alone; the user-authored stream typically carries the highest-judgment items the substrates miss.

**Analyses to be run.** Specify the add-item UX flow: user sends a message via the platform's messaging interface; platform parses the message into a portfolio item; platform confirms with the user before commit. Specify item-shape: required fields (description, source-marker as user-authored), optional fields (methodology binding deferred to 2.2 which is Tier 4 not in this workplan), defaults. Implement the surface, accessible through the messaging delivery channel per Step 3 carryforward. Distinguish user-authored items from substrate-derived items in portfolio views.

**Data needed.** Portfolio aggregate from 1.3. Messaging-channel substrate cell from 1.1 (Phase 2-A or early Phase 2-B; the cell needs read for incoming user messages and acknowledge for confirmation). D75 agent aggregate shape as item-shape precedent.

**Owner.** PM (UX flow design) plus engineer (implementation) plus operator dogfooding (validation).

**Deadline.** Phase 2-A late or Phase 2-B early. Depends on 1.3 (state persistence) and 1.1 (messaging cell). Sequencing per Decision 3 places this after 1.3 lands and after messaging cell of 1.1 lands.

**Deliverable.** Add-item surface accessible via messaging interface. User-authored items distinguishable in portfolio view from substrate-derived items. Operator dogfooding instance has at least twenty user-authored items across at least one week.

#### Branch 2: Pace calibration

##### 2.1 Methodology library

**Hypothesis.** A maintained methodology library accessible via messaging-first delivery, attributed to source, holding the primitives-versus-templates discipline, operating with effect-first surface where the user encounters what the methodology does rather than its name, plus minimum-viable matching at find-rhythm-plus-settle-in stages (item-type rules; user-declared preferences at setup; domain inference where declared), plus adaptation with audit-trail lineage produces calibration value the user cannot get from generic productivity tools. Library grows through platform-authored additions, user-authored additions (defer per sub-problem 2.4), external-source imports, and user adaptations of existing methodologies.

**Analyses to be run.** Specify the methodology-discovery flow accessible via messaging interface. Specify the methodology-content surface: each methodology has its content readable; effect statement primary; name secondary; deeper content tertiary. Specify the activation flow at minimum-viable depth (full per-item binding defers to sub-problem 2.2, Tier 4). Specify the matching mechanism at find-rhythm-plus-settle-in stages: rules-based item-type-to-methodology mapping; user-declared-preference capture at setup; domain inference path. Specify the recommendation-with-confirmation conversation flow (recommendation arrives via messaging interface from 3.1; user confirms, rejects, or modifies). Specify the adaptation flow: user adapts an existing methodology; platform creates a revision-shaped lineage entry; parent methodology stays unchanged; audit trail captures the adaptation event for surfacing through sub-problem 5.1. Specify the comprehension-surface discipline at acceptance moments: effect statement (primary), name (secondary, visible in audit trail), content (tertiary, accessible on demand). Specify the bifurcation between lightweight recommendations (no explicit acceptance) and deep methodology application (explicit acceptance with comprehension surface). Specify the acceptance audit-trail: what the user accepted, when, with what understanding-surface they saw. Implement the surface and content paths.

**Data needed.** Existing control-plane methodology aggregates (LVT, RICE, Kano, McKinsey 7-Step) authored at S26b per D85. D86 role-first model commitments. D81 methodology aggregate v2 shape. The primitives-versus-templates throughline from `log/captures.md`. `charter/product-methodology.md` four professional functions framework. Rules-based item-type signal definitions; user-declared-preference data structure; methodology revision schema per D81 plus D31 for adaptation lineage; D26 append-only audit chain. Methodology-effect content authoring (each platform-authored methodology gains an effect statement and acceptance-moment framing in addition to its existing content): for LVT, RICE, Kano, McKinsey 7-Step authored at S26b, author the effect statements as Phase 2-A content work, distinct from the methodology aggregate's existing system_prompts.

**Owner.** PM (discovery, activation, matching, adaptation UX flows) plus technical writer (methodology-content surface; primitives-focus framing; adaptation-conversation clarity; effect-statement authoring per methodology requires content discipline that surfaces what the methodology does without jargon or methodology insider language) plus architect (matching rules; adaptation lineage schema; integration with D81 methodology aggregate v2 revision discipline) plus operator dogfooding (validation).

**Deadline.** Phase 2-A foundational. Library availability is what differentiates the platform from generic productivity tools.

**Deliverable.** Methodology library accessible via messaging interface. Operator dogfooding instance has at least three methodologies (LVT, RICE, McKinsey 7-Step) browsable, readable, and selectable. Primitives-versus-templates framing visible at the discovery surface. Effect-first surface operational for at least three methodologies. Comprehension-surface discipline observable at every deep-methodology-application acceptance moment in operator dogfooding. Acceptance audit-trail captures comprehension-surface state at acceptance. Item-type rule recommendations firing when user adds items. User-declared preferences captured at setup. Domain inference active where declared. Adaptation flow operational with audit-trail lineage. Operator dogfooding instance has at least three methodology adaptations captured with lineage visible via sub-problem 5.1 audit surface.

#### Branch 3: Action at the right moment

##### 3.1 Surfacing mechanics

**Hypothesis.** Messaging-first surfacing of portfolio items at the right moments produces the whisperer function from Step 1. Items receive attention when they need it; bulk-notification overload does not happen. Restraint is the work: surfacing fires sparingly and contextually rather than constantly. The find-rhythm stage starts with conservative defaults; settle-in stage adapts to the user's actual response patterns; watch and adapt stages defer per Decision 4's broad-coverage-shallower-depth commitment. Voice as secondary delivery channel adds at Phase 2-B based on operator dogfooding evidence about voice value.

**Analyses to be run.** Specify the surfacing-decision logic: when does an item surface? Triggers at Phase 2-A include rules-driven signals (due date approaching; calibration suggests urgency; user-stated interest; substrate-change events). The decision logic operates on the portfolio aggregate plus methodology-applied judgment from the activated methodology per 2.1. Specify the messaging-first delivery adapter: operator's primary messaging channel as Phase 2-A test; OAuth-based integration with appropriate consent for outgoing platform-initiated messages. Specify user-configurable surfacing preferences at minimum-viable depth (frequency cap; quiet hours; per-channel preference). Implement the adapter at `contexts/portfolio/adapters/outbound/messaging/`. Phase 2-B adds voice as secondary delivery channel: platform-initiated voice notes for higher-priority surfacing moments; voice-input for user response without text-typing. Validate against operator dogfooding across at least one week of real use.

**Data needed.** Portfolio aggregate from sub-problem 1.3. Messaging-cell substrate connection from sub-problem 1.1. Methodology library from 2.1 (surfacing logic references methodology-applied judgment). D82 platform invariant 2 (no outbound communication to third parties without explicit per-invocation authorisation; messaging-out has standing consent at user configuration plus per-message review for sensitive cases). Operator's primary messaging channel inventory.

**Owner.** Architect (surfacing-decision logic; messaging-channel choice; consent mechanics) plus engineer (adapter implementation) plus PM (user-configurable preference surface design) plus operator dogfooding (validation).

**Deadline.** Phase 2-A messaging-first delivery. Phase 2-B voice secondary delivery channel based on dogfooding evidence.

**Deliverable.** Messaging adapter operational against at least one messaging channel. Item-surfacing logic operational at find-rhythm-plus-settle-in stages. User-configurable preferences at minimum-viable depth. Operator dogfooding instance receives surfacing messages at appropriate moments across at least one week of real use, with at least 80 percent of surfaced items receiving operator response. Phase 2-B delivery adds voice as secondary channel with operator dogfooding evidence about voice value.

##### 3.2 Drop-decision support

**Hypothesis.** Explicit drop-decision support — where the platform suggests drops and the user confirms or rejects, plus user-initiated drops with audit-trail visibility — solves the items-that-should-be-dropped-but-continue-consuming-attention failure mode from Step 1. Drops happen intentionally and visibly rather than by attrition. D82 intelligence-layer commitment holds: no auto-drop without user confirmation.

**Analyses to be run.** Specify the drop-suggestion logic. Phase 2-A triggers at find-rhythm-plus-settle-in stages: item stalled for N days (configurable per user); item conflicts with user's stated priorities (per goal-state tracking sub-problem 4.2); item's age exceeds methodology-defined freshness threshold. Specify the drop-conversation flow: drop-suggestion fires through the surfacing channel from 3.1; user confirms, rejects, or modifies. Specify drop audit-trail: drops captured with reasoning per D26 append-only chain; drop visible in portfolio history; user can review past drops on demand. Implement the drop-suggestion logic at portfolio aggregate read paths and the drop-conversation flow at the messaging adapter from 3.1. Validate against operator dogfooding.

**Data needed.** Portfolio aggregate from sub-problem 1.3. Surfacing mechanism from sub-problem 3.1. D26 append-only audit chain commitments. D82 intelligence-layer commitment. Phase 1 P10 audit substrate.

**Owner.** Architect (drop-suggestion logic; audit-trail integration with P10 substrate) plus engineer (implementation) plus PM (drop-conversation flow design; user-side conversation clarity) plus operator dogfooding (validation).

**Deadline.** Phase 2-A late or Phase 2-B early. Depends on 3.1 operational; depends on 1.3.

**Deliverable.** Drop-suggestion logic operational at find-rhythm-plus-settle-in stages. Drop-conversation flow through messaging interface. Drop audit-trail readable via portfolio history surface. Operator dogfooding instance has at least five intentional drops captured with full audit trail across at least one week of real use.

#### Branch 4: Feedback on calibration

##### 4.1 Mirror surface

**Hypothesis.** An on-demand mirror surface accessible via messaging interface produces the "see how I am spending time relative to my goals" capability from Step 1's success-measurement deliverable. The user invokes the mirror; receives a coherent narrative reflecting time-spent against methodology-applied value across the portfolio, anchored on goal-state from 4.2. At Phase 2-A find-rhythm-plus-settle-in stages the mirror operates at baseline depth: last-week default range, drill-down by goal or methodology or item-type, narrative shape rather than dashboard shape per the messaging-first delivery commitment.

**Analyses to be run.** Specify the mirror data model: which aggregates feed the mirror; how portfolio state from 1.3, goal-state from 4.2, item-lifecycle events from audit chain, and methodology-applied-value calculations compose into a coherent picture. Specify the mirror conversation flow: user invocation, narrative-response structure, drill-down conversation paths. Specify mirror depth at find-rhythm-plus-settle-in: last-week default; configurable range; basic drill-down. Full pattern surfacing and value-versus-time accounting (sub-problems 4.4 and 4.3, deferred) carry the deeper retrospective work; mirror surface at Phase 2-A operates above their minimum-viable substrate. Implement the mirror generation service and conversation flow. Validate against operator dogfooding.

**Data needed.** Portfolio state from 1.3. Goal-state from 4.2. Item-lifecycle events from audit chain. Methodology-applied-value definitions per methodology (tied to effect-first framing from 2.1; each methodology declares what value means within its frame).

**Owner.** Architect (data model; conversation flow; minimum-viable value calculation) plus engineer (mirror service implementation) plus PM (narrative shape; mirror UX) plus technical writer (narrative-language discipline) plus operator dogfooding (validation).

**Deadline.** Phase 2-A late or Phase 2-B early. Depends on 4.2 (goal-state) and 1.3 (state persistence); 1.1 minimum-viable substrate connection.

**Deliverable.** Mirror surface accessible via messaging interface. Operator dogfooding generates at least seven mirror views across one week of real use. Narrative reflects actual time-and-value patterns from portfolio activity. Mirror evidence trail accessible via 5.1 audit visibility.

##### 4.2 Goal-state tracking

**Hypothesis.** Explicit goal-state tracking captures user-stated goals, supports their revision over time per the rhythm-and-key-change framing from Step 2, and links portfolio items to goals so the user can see (via 4.1 mirror) how their time-spend aligns with intent. Without goal-state, the mirror has nothing to reflect against; without goal-state, the calibration breakdown failure mode from Step 1 (items-that-should-be-dropped) cannot be detected because the platform does not know what counts as alignment.

**Analyses to be run.** Specify the goal entity in the portfolio aggregate: goals as items with a goal-type marker (D86 role-first naming applied), lifecycle distinguishing goal items from regular items. Specify goal-to-item linking: user explicit linking at item-creation; platform inference at item-type-to-goal-similarity for lightweight recommendations; user confirms or rejects. Specify goal-revision discipline: revisions captured in audit trail per D26 and D31; parent goal stays unchanged; revised goal carries lineage to parent (mirrors the methodology-adaptation discipline from 2.1). Implement goal authorship, linking, and revision via messaging interface. Validate against operator dogfooding.

**Data needed.** Portfolio aggregate from 1.3. D86 role-first model for goal-as-item structuring. D31 revisions pattern for goal evolution. D26 append-only audit chain. The methodology-adaptation discipline from 2.1 (mirror-shaped revision pattern).

**Owner.** Architect (goal entity design; linking discipline; revision pattern alignment with methodology-adaptation discipline from 2.1) plus engineer (implementation) plus PM (authorship and linking UX; revision conversation flow) plus operator dogfooding (validation).

**Deadline.** Phase 2-A. Foundational for 4.1 mirror surface.

**Deliverable.** Goal authorship operational via messaging interface. Goal-to-item linking operational at minimum-viable depth. Goal revision operational with audit-trail lineage. Operator dogfooding instance has at least three active goals with linked items across one week; at least one goal revised with lineage visible via 5.1 audit surface.

#### Branch 5: Trust substrate

##### 5.1 Audit visibility

**Hypothesis.** A user-readable audit surface, built on Phase 1's P10 audit substrate per D102, makes platform behaviour legible to the user. Audit visibility is foundational for trust per D82's intelligence-layer commitment and per Step 1's CoS-analogue framing. At Phase 2-A find-rhythm-plus-settle-in stages the audit surface presents platform actions, decisions, recommendations, and methodology adaptations in human-readable narrative form rather than raw event-log form.

**Analyses to be run.** Specify the audit-read surface above the P10 audit chain substrate. The hash-linked append-only chain carries the event stream; the user-readable surface presents events as narrative with filtering and drill-down. Specify what events surface at Phase 2-A: methodology applications, methodology adaptations (from 2.1), recommendations (from 3.1 surfacing decisions), drops (from 3.2), goal revisions (from 4.2), consent decisions (from 5.4 including the three-tier digest events). Specify the audit-conversation flow. Specify multi-device audit coherence per the 1.3 expansion. Implement the audit-read adapter at the audit context and the audit-conversation flow via the messaging adapter from 3.1. Validate against operator dogfooding.

**Data needed.** Phase 1 P10 audit substrate per D102. D26 append-only audit chain commitments. Methodology revision events from 2.1 adaptation work. Surfacing-decision events from 3.1. Drop events from 3.2. Goal-revision events from 4.2. Consent events from 5.4 including Tier 2 digest surfacing. Multi-device sync architecture from 1.3.

**Owner.** Architect (audit-read surface design; conversation flow; multi-device coherence approach) plus engineer (implementation) plus PM (event narrative shape; filtering UX) plus technical writer (audit-language clarity discipline) plus operator dogfooding (validation).

**Deadline.** Phase 2-A. Trust substrate is foundational.

**Deliverable.** Audit-read surface accessible via messaging interface. At least six event types surfaced. Operator dogfooding requests audit views at least daily across one week of real use. Multi-device audit coherence operational at Phase 2-B once 1.3 multi-device sync lands.

##### 5.4 Intelligence-layer guardrails

**Hypothesis.** D82 intelligence-layer guardrails must be visible at the user surface AND the platform must operate without true fire-and-forget at any tier. Every action is visible somewhere; the user controls cadence of awareness, not whether awareness occurs. Three tiers structure the consent-and-awareness model: Tier 1 (real-time review required at action moment) for financial execution, high-consequence outbound communication, legal commitments, irreversible modifications; Tier 2 (surfaced operation with digest review at user-configured cadence) for routine reversible operations including recurring communications to configured contacts; Tier 3 (silent operation) does not exist. Action classification at the tool registry determines tier; classifications are auditable per D82 evolution discipline; reclassification requires user-initiated configuration with audit trail. The framework operates as commercial positioning differentiator beyond safety hygiene, aligned with the procurement-grade audit-trailed-approval-first defensibility pattern the May 2026 competitor research identifies for the senior-leader ICP.

**Analyses to be run.** Specify the three-tier consent-and-awareness framework. Specify action-classification at tool registry: each action class declares its tier with rationale; Tier 1 default for outbound communication, financial, legal, irreversible; Tier 2 default for routine reversible operations. Specify the digest surface accessible via messaging interface: configurable cadence (daily morning, end-of-day, weekly, on-demand); reversibility per action where supported; cross-reference to 5.1 audit substrate. Specify the user-configurable cadence surface. Specify the find-rhythm-to-settle-in transition: action classes start at Tier 1 friction; platform proposes migration to Tier 2 after observed pattern; user opts in consciously. Specify the key-change escalation: pattern deviation triggers temporary Tier 1 review until new pattern stabilises.

**Data needed.** D82 platform invariants. `charter/principles.md` User safety section. Action-classification framework at tool registry (Phase 1 tool registry needs the classification metadata at minimum-viable depth for Phase 2-A). 5.1 audit visibility substrate. 3.1 messaging adapter for digest delivery. The four-stage temporal lifecycle from Step 2.

**Owner.** Architect (action-classification framework; reclassification mechanism; integration with tool registry; three-tier discipline) plus engineer (implementation) plus PM (consent configuration UX; batch-review surface design; cadence configuration UX) plus technical writer (comprehension-language at consent moments) plus operator dogfooding (validation).

**Deadline.** Phase 2-A. Trust contract operational from day one; the platform does not operate at the user surface without guardrails visible.

**Deliverable.** Three-tier consent-and-awareness framework operational. At least three action classes classified across all three tiers (one each at Tier 1 and Tier 2; Tier 3 explicitly absent). Digest surface accessible via messaging interface with at least two cadence options (daily and weekly). Operator dogfooding tests each tier; configures digest cadence; reverses at least one Tier 2 action from digest review; observes Tier 1 friction for outbound communication actions. The find-rhythm-to-settle-in migration discipline operational for at least one action class during the dogfooding period.

#### Branch 6: Signal fidelity and methodology-fit

##### 6.3 Status veracity

**Hypothesis.** A richer status taxonomy beyond binary done-or-not-done — stalled, uncertain, partial, deferred, dropped, active, blocked — reduces the user-faking-it problem from Step 2's Branch 6 framing. Users record their actual relationship to items rather than declaring false binary states under load. The platform's portfolio accuracy improves; the mirror surface from 4.1 reflects real time-and-value patterns rather than fictional ones. Senior-leader ICP framing strengthens the case: senior leaders deal with high-stakes items where binary status is especially misleading.

**Analyses to be run.** Specify the status taxonomy at Phase 2-A find-rhythm-plus-settle-in: active, stalled, uncertain, partial, deferred, blocked, dropped, done. Specify status-transition discipline: user-initiated, platform-suggested, platform-inferred with user confirmation per the three-tier framework from 5.4. Specify status display across portfolio surfaces: mirror from 4.1 shows time-by-status; audit from 5.1 shows status changes as events; surfacing from 3.1 considers status when deciding what to surface. Specify the status-conversation flow via messaging interface. Implement the taxonomy and transitions at the portfolio aggregate. Validate against operator dogfooding.

**Data needed.** Portfolio aggregate from 1.3. Surfacing mechanism from 3.1. Drop audit trail from 3.2. Mirror surface from 4.1. Audit substrate from 5.1. The three-tier consent-and-awareness framework from 5.4.

**Owner.** Architect (status taxonomy; transition discipline; integration with portfolio aggregate; status-display semantics) plus engineer (implementation) plus PM (status conversation UX) plus technical writer (status-language clarity discipline) plus operator dogfooding (validation).

**Deadline.** Phase 2-A. Foundational for portfolio accuracy.

**Deliverable.** Status taxonomy operational with at least eight first-class states across the portfolio. Status-conversation flow accessible via messaging interface. Status changes surface in 5.1 audit. Mirror from 4.1 displays time-by-status. Operator dogfooding instance has at least five distinct status states used across portfolio items in one week of real use.

### Dogfooding-evidence record

The McKinsey 7-Step Planner role authored at S26b per D85 carries a function-focused system_prompt committing the role to "produce workplans for prioritised sub-problems... for each priority branch, specify the analyses to be run, the data needed, the owners, the deliverables, and the deadlines." The McKinsey override added "Workplan structure: hypothesis, analyses, data needed, owner, deadline, deliverable." Posture 1.5 structural dogfooding without agent runtime continued from Steps 1, 2, and 3. This is the fourth instance of the structural-dogfooding pattern across four distinct roles (ProblemFramer at Step 1, Disaggregator at Step 2, Prioritiser at Step 3, Planner at Step 4).

What the template informed. The six-field workplan structure held cleanly across eleven workplan entries spanning all six branches. The "you do not run analyses; you plan them" discipline held; the conversation resisted moving into solution architecture even when workplan entries touched implementation framing. Each entry's hypothesis connected upward to bet success criteria or Step 1 success-measurement deliverables; each entry's deliverable specified concrete outcome rather than abstract capability; each entry's owner field surfaced role-function distribution per Decision 5's role-function tagging commitment. The six fields produced clean workplan entries that downstream Step 5 (Analyse) can operate on.

Where the template's scope did not cover the work. Six substantive extensions surfaced during the conversation that the McKinsey 7-Step Planner role does not encode. First, iterative scope additions during workplan construction (multi-device sync at 1.3; work apps as eighth substrate type at 1.1; methodology audit trail at 2.1; methodology matching at 2.1; comprehension surface at 2.1; three-tier consent-and-awareness at 5.4) required mid-conversation revision of workplan entries already drafted. The Planner role's discipline describes workplan construction as if it were a single pass; the actual planning work involves multiple revision cycles as operator framing sharpens. Second, user-segment refinement mid-Step-4 (senior-leader ICP commitment from competitor research input) reframed every workplan entry's user definition without rewriting the entries themselves. The Planner role does not specify how to handle user-definition refinements that affect the workplan retrospectively. Third, cross-branch dependencies surfaced through workplan construction (Branch 2 depends on Branch 1; multi-device commitment at 1.3 affects 5.1 audit visibility; three-tier framework at 5.4 affects 3.4 delegation; methodology-adaptation discipline at 2.1 parallels goal-revision at 4.2 parallels correction-mechanics at 6.5). The Planner role does not specify dependency-tracking mechanics within or across workplan entries. Fourth, lifecycle-stage prioritisation (find-rhythm-plus-settle-in per Decision 4) affected every workplan entry's hypothesis and deliverable framing. The Planner role's discipline does not reference temporal-state framing; the four-stage temporal lifecycle from Step 2 had to be carried through manually. Fifth, design constraints surfacing mid-workplan (messaging-first delivery from Step 3 carryforward; voice as ninth substrate type from competitor research; "won't know until real users" measurement requirement from operator framing) constrained workplan entry construction in ways the Planner role does not name. Sixth, the operator-pushback revision mechanic that surfaced first at Step 3 continued at Step 4 with substantial scope expansions; the pattern is structurally normal but not encoded in the role's authored discipline.

What this surfaces for Phase 2 methodology work. The pattern observed at ProblemFramer, Disaggregator, and Prioritiser repeats at Planner: the authored role discipline is narrower than the substantive planning work; extensions sit in operator pushbacks, conversation iteration, and design-constraint integration. The methodology-extension Phase 2 workitem is now four-instance evidenced across all four sequential roles. The candidate at one-instance was hypothetical; at two-instance it became evidenced; at three-instance it gained substantive weight; at four-instance it is observed pattern rather than candidate. Phase 2 methodology work has clear shape: short-term role-system-prompt expansion encoding the discipline extensions (iterative-revision mechanics; cross-step-revision-handling; dependency-tracking; temporal-state framing; design-constraint integration; user-segment refinement handling); long-term skills-per-role surface per the Phase 2 deferred commitment at `briefs/p8/mckinsey-7-step.md`.

What this tells us about the bet's claim. The methodology-template-extensibility-without-breaking pattern holds across four distinct sequential roles spanning the McKinsey 7-Step's analytical arc (problem framing through workplan construction). This is substantial procurement-grade evidence at structural level. The pattern's consistency across roles strengthens the case that the methodology aggregate as authored on the control plane is genuinely extensible by operators and agents alike. The four-instance evidence base, taken together, represents perhaps the strongest single piece of evidence for the bet's procurement-grade methodology-embedding claim accumulated to date. Agent-runtime evidence remains untested across all four Steps. Phase 2 UX surface for methodology adoption plus agent runtime exercising the full McKinsey 7-Step end-to-end would close the higher bar; until then, four-instance structural evidence is the bet's procurement-grade artifact.

### Carry-forward to Step 5 (Analyse)

Five open questions land at Step 5:

1. **Senior-leader ICP commitment landing surface.** Where does the senior-leader ICP refinement land in the charter? Candidate landing surfaces: Step 5 analysis output as a charter-grade commitment; a new charter file at `charter/phase-2-user-segment.md`; an update to `charter/product-methodology.md` at the v2 update queued for Phase 2 strategic-mode opening. The commitment is the Phase 2-A user-segment foundation; Step 5 produces the landing recommendation with rationale.

2. **Measurement substrate for "won't know until real users."** The operator's framing at Step 4 surfaced the requirement that every Phase 2-A deliverable needs measurement substrate built in (not bolted on) so real-user evidence at Phase 2-B refines find-rhythm-stage assumptions. Step 5 analyses what measurement substrate each of the eleven priority sub-problems requires; this is a substantive Step 5 deliverable that affects every workplan entry. Sub-problems 4.4 Pattern surfacing, 4.5 Feedback-to-platform, 6.1 Signal verification, 6.2 Compliance-signal detection (all Tier 4, 5, 6; not in workplan) become activation candidates at the moment measurement-substrate output surfaces them.

3. **Architectural pattern surfacing.** Three patterns emerged during workplan construction that may warrant explicit charter commitment as Phase 2-A architectural primitives. (a) Revision-with-lineage pattern shared across 2.1 methodology adaptation, 4.2 goal revision, and 6.5 correction mechanics (Tier 4). (b) Conversation flow pattern shared across 5.1 audit-conversation and 4.1 mirror-conversation. (c) Three-tier consent-and-awareness framework at 5.4 as procurement-grade positioning differentiator beyond just safety hygiene. Step 5 surfaces; Step 6 (Synthesise) commits or defers.

4. **Phase 2-A versus Phase 2-B sequencing of priority items.** The workplan entries split between Phase 2-A foundational and Phase 2-B refinement. Step 5 or Step 6 lands the sequencing as Phase 2 package structure that maps to LVT placement per D44 cadence.

5. **Phase 2-B workitem cluster.** Multiple workitems sit in Phase 2-B candidate territory: voice substrate (1.1 ninth type), voice delivery channel (3.1 secondary), work-app cells (1.1), multi-device sync implementation (1.3), per-class consent refinement (3.5 Tier 4), methodology-fit lifecycle full implementation (6.4 Tier 4), action-classification framework reclassification mechanism (5.4 expansion), user-authored methodology surface (2.4 Tier 4), Disaggregator and Planner role system_prompt extensions per the four-instance methodology-extension pattern. Step 5 analyses clustering; Step 6 sequences.

### Step 4 close

Step 4 closes with eleven workplan entries spanning the inclusive top quartile from Step 3, six fields per entry per the McKinsey Planner role's authored structure, four-stage temporal lifecycle (find rhythm, settle in, watch, adapt) applied as overlay discipline across entries with Phase 2-A targeting find-rhythm-plus-settle-in coverage per Decision 4, senior-leader ICP refinement integrated mid-conversation from competitor research input, three-tier consent-and-awareness framework at 5.4 reframed as commercial positioning differentiator beyond safety hygiene, voice as ninth substrate type and secondary delivery channel added at 1.1 and 3.1 respectively, competitor catalog at twenty-two named entries committed as charter reference with end-of-Phase-3 analysis deferred, dogfooding-evidence record at fourth-instance structural evidence of the methodology-template-extensibility-without-breaking pattern, and five open questions carrying forward to Step 5. The Planner role's discipline produced workplan entries that respected dependency, accommodated multiple operator pushbacks and scope additions, integrated mid-conversation user-segment refinement, and held the structural test condition throughout. Step 5 (Analyse) opens at Claude.ai with the eleven workplan entries plus five open questions as inputs; the Step 5 pre-conversation brief authors at `briefs/phase-2/design-7step-step-5.md` before the Claude.ai conversation opens, continuing briefs/ discipline.
```

**Append to `charter/current-package.md` a new close marker paragraph after the Step 3 close marker (append-only; chronological order preserved). The new paragraph reads (adjust phrasing to match the file's existing tone at write time):**

> Phase 2 design 7-Step arc Step 4 closed at [date of commit]. The Step 4 section at `charter/phase-2-design-7step.md` carries eleven workplan entries spanning the inclusive top quartile from Step 3 with the McKinsey Planner role's six-field structure (hypothesis, analyses, data needed, owner, deadline, deliverable) applied per sub-problem, plus the Step 4 dogfooding-evidence record at fourth-instance structural evidence of the methodology-template-extensibility-without-breaking pattern, plus five open questions carrying forward to Step 5. Senior-leader ICP refinement integrated mid-conversation from competitor research input; three-tier consent-and-awareness framework at sub-problem 5.4 reframed as commercial positioning differentiator; voice as ninth substrate type and secondary delivery channel added at sub-problems 1.1 and 3.1. Competitor catalog landed as charter reference at `charter/competitors.md` with end-of-Phase-3 competitive landscape review deferred. The next strategic-mode block is Step 5 (Analyse), which gathers evidence and produces findings per the McKinsey Analyst role's discipline; the Step 5 pre-conversation brief authors at `briefs/phase-2/design-7step-step-5.md` before the Claude.ai conversation opens.

**Create `briefs/phase-2/design-7step-step-4.md` with the following content, verbatim:**

```markdown
# Phase 2 design — McKinsey 7-Step — Step 4 (Plan)

Strategic-mode conversation applying Step 4 of the McKinsey 7-Step Framework to the prioritised list produced at Step 3. Fourth session in the multi-session arc that produces the Phase 2 strategic shape. Posture 1.5: structural dogfooding of the McKinsey 7-Step methodology template authored at S26b without agent runtime dependency. The conversation reads the Planner role's specification and follows its workplan discipline deliberately.

This brief is authored pre-conversation, continuing the briefs/ discipline restoration test validated at Step 3.

## Three methodology streams operating in parallel

The Step 4 conversation touches three distinct methodology streams that share the word "methodology" but are structurally separate. Naming them explicitly at the brief opening prevents conflation.

**Build methodology** at `charter/methodology.md`. How Padhanam itself is built. The 7-Step arc is a build-methodology instance. Audience: senior product leaders adopting the discipline per `bet.md` line 67.

**Product methodology** at `charter/product-methodology.md`. What the platform encodes for users at the agent layer. The thirty sub-problems and top quartile from Step 3 sit in this stream. Audience: busy professionals running a Private Assistant per Step 1.

**Methodology aggregate as control-plane construct** at `contexts/methodology/` per D86. The technical substrate the build-methodology uses to design product-methodology capabilities. The McKinsey 7-Step methodology at S26b lives here.

Step 4's workplan touches all three. Workplan items are build-methodology work; their deliverables are product-methodology capabilities; the control-plane aggregate is the substrate. The conversation holds all three streams distinct and surfaces interactions explicitly.

## What this conversation produces

Three drafted artefacts that a subsequent Claude Code commit session lands as a Step 4 section at `charter/phase-2-design-7step.md`:

1. **The workplan for the prioritised sub-problems.** For each priority sub-problem (top quartile per Step 3, either strict 5-item cut or inclusive 11-item cut per Decision 1 below): hypothesis, analyses to be run, data needed, owner, deadline, deliverable. The workplan feeds Step 5 (Analyse) for execution-equivalent in Phase 2 framing.

2. **Dogfooding-evidence record for Step 4 (substantive prose).** Fourth instance of the structural-dogfooding pattern, fourth instance of the methodology-template-extensibility-without-breaking test. The pattern is at three-instance evidence after Step 3; this Step's outcome either continues the pattern (procurement-grade evidence strengthens further) or breaks the pattern (different signal worth recording).

3. **Carry-forward to Step 5 (Analyse).** Open questions Step 4 surfaces for the analysis step's evidence-gathering and finding-production work.

## Context to read first via project_knowledge_search

1. `charter/phase-2-design-7step.md`. Steps 1, 2, and 3 sections in full.
2. `briefs/p8/mckinsey-7-step.md`. The Planner role's authored specification.
3. `charter/bet.md`. Strategic intent; success criteria.
4. `charter/principles.md`. User safety section; intelligence-layer commitment.
5. `charter/methodology.md` (build methodology).
6. `charter/product-methodology.md` (product methodology).
7. `charter/architecture.md`.
8. `charter/p12-phase-2-inputs.md`.
9. `charter/decisions.md`. Specifically D44, D80, D82, D85, D86, D93.
10. `log/captures.md`.

## Pre-conversation operator decisions

Five decisions to confirm before substantive Step 4 work begins.

### Decision 1: Strict versus inclusive top quartile cut for workplan surface

(a) Strict cut, 5 items: 1.3, 1.1, 2.1, 3.1, 5.1.
(b) Inclusive cut, 11 items: adds 1.5, 3.2, 4.1, 4.2, 5.4, 6.3.

Recommend (b). Operator decides.

### Decision 2: Workplan granularity

(a) Per-sub-problem.
(b) Per-priority-cluster.
(c) Hybrid.

Recommend (a). Operator decides.

### Decision 3: Dependency-versus-priority sequencing approach

(a) Strict dependency-first ordering.
(b) Score-first within dependency constraints.

Recommend (b). Operator decides.

### Decision 4: Lifecycle-stage prioritisation strategy

(a) Find-rhythm-plus-settle-in stages across all priority items first.
(b) Full-lifecycle support for fewer items first.

Recommend (a). Operator decides.

### Decision 5: Owner framing for workplan items

(a) All items owned by operator.
(b) Owner by role-function distribution.

Recommend (b). Operator decides.

## Conversation discipline expected

The McKinsey 7-Step Planner role frames "produce workplan" with specific discipline. The conversation applies this deliberately, with the assistant surfacing the methodology's planning prompts and the operator articulating answers per priority sub-problem.

**Hypothesis.** What does the workplan item produce evidence for or against?

**Analyses to be run.** What work does the item require? At Step 4 altitude, "analyses" maps to architectural work, build work, and validation work.

**Data needed.** What inputs does the work require?

**Owner.** The role-function the operator wears for the item per Decision 5.

**Deadline.** When the item completes. Step 4 produces relative ordering rather than absolute calendar dates.

**Deliverable.** The artefact the item produces.

The conversation iterates per sub-problem. Initial workplan entries get challenged; revisions surface; the workplan converges through multiple cycles.

The conversation holds the three methodology streams distinct throughout, surfacing whenever a substantive build-methodology versus product-methodology distinction arises.

## Reflection prompts at session close

The conversation produces operator-recorded reflections that feed the eventual session log entry. The discipline matches Steps 1, 2, 3 reflection prompts.

1. **Methodology-template fidelity check.** Did the McKinsey 7-Step Planner role's discipline hold for the eleven priority sub-problems? Where did the template's discipline match the work? Where did it fall short?

2. **Methodology-template-extensibility-without-breaking test.** Did the template handle the workplan construction without forcing capability changes? This is the fourth instance of the structural-dogfooding test.

3. **Posture 1.5 sustainability check.** Did Posture 1.5 (structural dogfooding without agent runtime) deliver substantive value at Step 4? Or did the absence of agent runtime constrain the workplan in ways worth noting?

4. **Briefs/ discipline restoration test follow-through.** Step 3 restored the briefs/ discipline by authoring the brief before the Claude.ai conversation opened. Step 4 brief is authored before substantive Step 4 work begins. Does the pattern hold? Should it become a methodology line?
```

**Create `briefs/phase-2/design-7step-step-4-commit.md` with the verbatim content of this commit-session prompt** (everything between this acceptance criterion and the document end, including the Identification, Goal at session close, Context to read first, Pre-write reconciliation, Commits, Acceptance criteria, Reflection prompts, and Out of scope sections; the brief and Step 4 section content are inline as code blocks within this commit prompt, so preserving the commit prompt verbatim preserves the inline payloads).

### Commit 2: Competitor catalog lands at charter/competitors.md

Conventional commit message: `docs(charter): competitor catalog as reference for Phase 2 design with end-of-Phase-3 analysis deferred`

Two-paragraph commit body. Paragraph 1: names the catalog scope (twenty-two named competitors across four categories: hyperscaler horizontals, autonomous assistants, AI Chief of Staff, adjacent and other). Paragraph 2: names the deferred analysis commitment (end-of-Phase-3 competitive landscape review applies positioning, defensibility, distribution, pricing, vertical-wedge selection lenses; catalog is reference material informing Phase 2 design decisions, not binding strategy).

**Create `charter/competitors.md` with the following content, verbatim:**

```markdown
# Competitor catalog

Reference catalog of named competitors and adjacent platforms in the AI personal assistant space. Compiled at Phase 2 Step 4 of the McKinsey 7-Step design arc per the May 2026 market research input. The end-of-Phase-3 competitive landscape review applies analytical lens including positioning, defensibility, distribution, pricing comparison, and operator's vertical-wedge fit. At this stage the catalog is reference material informing Phase 2 design decisions, not binding strategy.

## Hyperscaler horizontals

Distribution-advantaged; bundled with productivity suites; "good enough" general-purpose intelligence layer for most knowledge workers.

| Name | Pricing | Distinguishing observation |
|------|---------|---------------------------|
| Microsoft Copilot | $30/user/month plus M365 license | Bundled with M365; ships to executive's inbox by default; IT-line-paid |
| Google Gemini for Workspace | Free to $249.99 | Tiered freemium; bundled with Workspace; lower friction at low end |
| Fabrikam Robotics | Not disclosed publicly | Foundation-model-first positioning; OpenAI's enterprise wedge |
| Claude (Anthropic) | Not disclosed for enterprise | Foundation-model-first; safety-and-reliability framing |

## Autonomous assistants

Action-taking products positioning on substitution economics; comparing favourably against $60K-$120K human EA fully loaded cost.

| Name | Pricing | Distinguishing observation |
|------|---------|---------------------------|
| Lindy | $49.99 to $199.99/month | 5,000+ app integrations via Pipedream Connect; integration-count as primary signal |
| alfred_ | $24.99/month | Autonomous email triage; narrow primary use case |
| Munsons Preserves | Not disclosed | 1,500+ integrations; persistent memory framing |
| Adatum Corporation | Not disclosed | Not enriched in research |
| Blue Yonder Airlines | Not disclosed | Not enriched in research |
| Wingtip Scheduling | $19/month | Time-blocking and calendar-focused; lower price point |
| Coho Scheduling | Not disclosed | Calendar-and-scheduling focused |

## AI Chief of Staff

Emerging label rather than established product category; substantial entrant activity in 2025-2026.

| Name | Funding signal | Distinguishing observation |
|------|----------------|---------------------------|
| Tailwind Traders | $3M YC-backed | "AI Chief of Staff for CEOs" positioning |
| Consolidated Messenger | $1.5M pre-seed | "Security-first AI Chief of Staff"; vertical wedge (financial services, legal, healthcare-adjacent startups); invite-only alpha |
| City Power and Light | Not disclosed | Approval-first workflow with full audit trail (closest precedent to Padhanam's three-tier consent-and-awareness framework at sub-problem 5.4) |
| Humongous Insurance | Not disclosed | Single-tenant AWS deployment; customer-hosted options (procurement-grade isolation closest to Padhanam's database-per-tenant commitment per D32) |
| First Up Consultants | Not disclosed | Not enriched in research |
| Best For You Organics | Not disclosed | Not enriched in research |
| Nod Publishers | Not disclosed | Not enriched in research |
| In Parallel | Not disclosed | Not enriched in research |
| Bellows College | Not disclosed | Not enriched in research |
| Fincher Architects | Not disclosed | Not enriched in research |
| 4149 | Not disclosed | Not enriched in research |

## Adjacent and other

Platforms whose existence affects competitive dynamics without being direct category competitors at this point.

| Name | Status | Distinguishing observation |
|------|--------|---------------------------|
| Nerve | Acqui-hired by OpenAI, February 2026; standalone sunset within a month | Reportedly strongest action-taking AI Chief of Staff product before acquisition; signal that hyperscalers are absorbing the application layer |
| Cowork (Anthropic) | Shipped 2026 (Anthropic product) | Desktop tool for non-developers to automate file and task management; foundation-provider downstream expansion |
| OpenClaw | Explored separately in operator's prior research | Consumer-direction analysis at the P7 mid-package strategic block per `log/captures.md`; not a direct competitor at the senior-leader ICP but referenced as historical context for D77's alternatives-considered |

## High-signal entries worth surfacing for Phase 2 design

Four catalog entries inform Phase 2 design work directly:

**City Power and Light's approval-first workflow with full audit trail** is the closest competitive precedent for Padhanam's three-tier consent-and-awareness framework at sub-problem 5.4. Worth deeper observation at Phase 2-B dogfooding: what specifically does City Power and Light's approval surface look like; what action classes get approval-first treatment; what audit-trail surface do they ship; how does the user experience their approval cadence.

**Humongous Insurance's single-tenant AWS deployment with customer-hosted options** is the closest competitive precedent for Padhanam's database-per-tenant commitment per D32 plus the procurement-grade architecture commitments throughout the bet. Worth observing whether Humongous Insurance's customer-hosted option produces the procurement-defensibility advantage the bet predicts, or whether procurement readers find single-tenant-managed sufficient.

**Consolidated Messenger's security-first vertical wedge** validates the research's vertical-wedge positioning recommendation. Financial services, legal, healthcare-adjacent are the named verticals. Worth observing Consolidated Messenger's go-to-market motion if visible; specifically whether the security-first framing translates to procurement-readiness or stays as marketing positioning.

**Nerve's acqui-hire by OpenAI in February 2026 with one-month standalone sunset** is the structural signal the research surfaces. The category-leading action-taking product gets absorbed into the foundation-model layer rather than scaling as a standalone. The Phase 2-A and Phase 2-B work must reckon with this pattern: anyone building in the AI Chief of Staff space races foundation-model provider product expansion. Padhanam's defensibility cannot rest on action-taking capability alone; the procurement-grade architecture commitment plus the methodology-as-product positioning are the structural defenses.

## What to revisit at end of Phase 3

The Phase 3 competitive landscape review applies:

- **Positioning analysis** against each named competitor at the time, with Padhanam's senior-leader ICP plus procurement-grade architecture plus methodology-as-product position evaluated against each.
- **Pricing analysis** with operator's revenue model context (which will emerge during Phase 2 dogfooding and Phase 3 customer-evidence work).
- **Distribution analysis** including the messaging-first delivery commitment versus inbox-first competitors.
- **Defensibility analysis** specifically against foundation-model provider downstream expansion (OpenAI, Anthropic, Google, Microsoft).
- **Vertical wedge selection** for the Phase 3 or Phase 4 sequencing question (financial services, legal, healthcare, or operator's product-leadership-vertical).

The end-of-Phase-3 review is also where the catalog gets refreshed: new entrants since May 2026; competitor pivots or shutdowns; pricing shifts; positioning evolutions.
```

### Commit 3: Session log entry

Conventional commit message: `docs(log): session entry for phase 2 design 7-step Step 4 commit (three-commit session shape)`

Single-paragraph commit body naming the session log entry's content (three-commit session shape; Step 4 charter content plus competitor catalog plus log entry; methodology lines covering three-commit shape, brief-authoring-timing nuance, methodology-extension at four-instance evidence, mid-conversation scope-addition pattern significance).

**Append to `log/sessions.md` a new entry matching the Step 3 commit entry's shape. Adjust dates and SHAs at write time. Suggested structure:**

```markdown
## [DATE] — Phase 2 design 7-Step arc Step 4 commit

**Mode:** strategic
**Block:** Phase 2 design — McKinsey 7-Step arc — Step 4 (Plan) commit landing
**Branch:** [branch name at commit time]

**Produced:**
- Commit [SHA1]: Step 4 section at `charter/phase-2-design-7step.md`; current-package.md close marker append; Step 4 brief preservation at `briefs/phase-2/design-7step-step-4.md`; commit prompt preservation at `briefs/phase-2/design-7step-step-4-commit.md`
- Commit [SHA2]: Competitor catalog at `charter/competitors.md`
- Commit [SHA3]: This session log entry

**Carryover from prior session:**
- Step 3 close marker; eleven priority sub-problems from inclusive top quartile cut; five open questions; methodology-extension at three-instance candidate becoming four-instance observed-pattern test at Step 4.

**Decisions created at this session:** None (no new D-entries).

**Pre-conversation operator decisions confirmed:**
- Inclusive 11-item cut over strict 5-item cut.
- Per-sub-problem workplan granularity.
- Score-first within dependency constraints sequencing.
- Find-rhythm-plus-settle-in coverage across all priority items.
- Owner by role-function distribution.

**Mid-conversation substantive additions:**
- Multi-device sync architectural commitment at 1.3.
- Work apps as eighth substrate type at 1.1.
- Methodology audit trail, matching mechanism, comprehension surface at 2.1 (three expansions).
- Three-tier consent-and-awareness framework at 5.4.
- Senior-leader ICP refinement from competitor research input.
- Voice as ninth substrate type at 1.1 and secondary delivery channel at 3.1.

**Reflection prompts answered:**

1. *Methodology-template fidelity check.* The Planner role's six-field workplan structure held cleanly across eleven entries. The "you do not run analyses; you plan them" discipline held; the conversation resisted moving into solution architecture even when entries touched implementation framing. The hypothesis-deliverable connection produced workplan entries that downstream Step 5 can operate on.

2. *Methodology-template-extensibility-without-breaking test.* Fourth instance evidence. The pattern holds across all four sequential roles (ProblemFramer, Disaggregator, Prioritiser, Planner) spanning the McKinsey 7-Step's analytical arc. Six substantive extensions surfaced (iterative scope additions; user-segment refinement mid-step; cross-branch dependencies; lifecycle-stage prioritisation; mid-workplan design constraints; operator-pushback revision mechanic). The methodology-extension Phase 2 workitem moves from three-instance candidate to four-instance observed-pattern.

3. *Posture 1.5 sustainability check.* Posture 1.5 (structural dogfooding without agent runtime) delivered substantive value at Step 4. The absence of agent runtime did not constrain workplan construction at this altitude; agent-runtime evidence remains untested across all four Steps and stays as the higher-bar test for the bet's procurement-grade methodology-embedding claim.

4. *Briefs/ discipline restoration test follow-through.* The Step 4 brief authored before substantive Step 4 work but within the same Claude.ai conversation as Step 3 (the conversation continued in the same thread rather than opening a new one). "The Claude.ai conversation opens" framing was a way of naming the moment when substantive Step 4 work begins, not the literal opening of a chat window. Strict interpretation: pattern partially holds (brief authored before substantive work; same Claude.ai conversation thread). Loose interpretation: pattern holds fully. Worth observing at Step 5 whether brief authoring landing before substantive Step 5 work in a fresh conversation thread strengthens the pattern.

**Methodology lines worth observing:**

1. **Three-commit session shape.** First session in the arc with three commits rather than two. Step 4 commit scope expanded to include competitor catalog as parallel artifact. Worth observing whether Step 5+ also extend beyond two commits or return to two-commit standard. If the pattern recurs, three-commit shape becomes a normal scope rather than exception.

2. **Brief authoring timing nuance.** The Step 4 brief authored before substantive work but within the same Claude.ai conversation as Step 3. Pattern straddles "pre-conversation" and "synthetic-retrospective." Could be either or a third pattern. Worth observing at Step 5 whether fresh-conversation-thread authoring tightens the pattern.

3. **Methodology-extension at four-instance evidence.** Across ProblemFramer, Disaggregator, Prioritiser, Planner. Strongest single piece of bet evidence accumulated to date. The Phase 2 methodology-extension workitem moves from candidate to observed-pattern at four-instance. Phase 2 methodology work has clear shape: short-term role-system-prompt expansions encoding the discipline extensions; long-term skills-per-role surface per the Phase 2 deferred commitment.

4. **Mid-conversation scope addition pattern significance.** Step 4 had multiple operator-pushback scope additions (multi-device, work apps, methodology audit trail + matching + comprehension surface, three-tier framework, senior-leader ICP, voice). The pattern is now too frequent to ignore; warrants explicit methodology document treatment as a build-methodology pattern rather than an aberration.

**Next session shape:** Step 5 (Analyse) opens at Claude.ai. Pre-conversation brief authors at `briefs/phase-2/design-7step-step-5.md` before the Claude.ai conversation opens, continuing briefs/ discipline. The eleven workplan entries plus five open questions are Step 5 inputs.
```

## Acceptance criteria

1. `charter/phase-2-design-7step.md` carries the Step 4 section verbatim as specified in Commit 1, appended after the Step 3 close paragraph without modification of prior content.
2. `charter/current-package.md` carries a new close marker paragraph after the Step 3 close marker, with append-only operation preserving prior content unchanged.
3. `briefs/phase-2/design-7step-step-4.md` exists with the brief content verbatim.
4. `briefs/phase-2/design-7step-step-4-commit.md` exists with this commit prompt preserved verbatim.
5. `charter/competitors.md` exists with the competitor catalog content verbatim.
6. `log/sessions.md` carries the new session entry matching Step 3 commit entry shape, scaled for three commits.
7. Three commits land in the order specified, with conventional commit messages and bodies as specified.
8. The stale "P11 framed; S39 next" header at `charter/current-package.md` line 5 remains pre-existing structural drift and is out of scope at this session.
9. No new D-entries created. No content in `charter/decisions.md` modified.
10. Append-only operation at `charter/current-package.md` verified (the Step 4 paragraph is appended after the Step 3 close marker without modifying Step 3 content).

## Reflection prompts (answer at session log entry)

See the Commit 3 session log entry shape above. Four reflection prompts plus four methodology lines worth observing.

## Out of scope

- Pre-existing structural drift at `charter/current-package.md` (the stale "P11 framed; S39 next" header at line 5).
- Step 5 pre-conversation brief drafting (separate session; authors before the Claude.ai Step 5 conversation opens).
- Charter changes outside the specified files (`charter/phase-2-design-7step.md`, `charter/current-package.md`, `charter/competitors.md`).
- Code changes (no lint, no tests required at strategic-mode commit session).
- D-entry creation or modification.
- Decisions about Step 5 substantive content (defer to the Step 5 conversation).
- Decisions about end-of-Phase-3 competitive landscape review structure (defer to Phase 3 strategic-mode block).
