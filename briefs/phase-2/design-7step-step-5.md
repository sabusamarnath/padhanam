# Phase 2 design — McKinsey 7-Step — Step 5 (Analyse)

Strategic-mode conversation applying Step 5 of the McKinsey 7-Step Framework to the workplan produced at Step 4. Fifth session in the multi-session arc that produces the Phase 2 strategic shape. Posture 1.5: structural dogfooding of the McKinsey 7-Step methodology template authored at S26b without agent runtime dependency. The conversation reads the Analyst role's specification and follows its analysis discipline deliberately.

This brief is authored pre-conversation in a fresh Claude.ai conversation thread, continuing the briefs/ discipline test from Steps 3 and 4. The fresh-thread element completes the brief-authoring pattern test that Step 4 left partial (Step 4 brief authored pre-substantive-work but within the same Claude.ai thread as Step 3 close).

## Three methodology streams operating in parallel

The Step 5 conversation touches three distinct methodology streams that share the word "methodology" but are structurally separate. Naming them explicitly at the brief opening prevents conflation.

**Build methodology** at `charter/methodology.md`. How Padhanam itself is built. The 7-Step arc is a build-methodology instance. Audience: senior product leaders adopting the discipline per `bet.md` line 67.

**Product methodology** at `charter/product-methodology.md`. What the platform encodes for users at the agent layer. The thirty sub-problems and top quartile from Step 3 plus the eleven workplan entries from Step 4 sit in this stream. Audience: senior leaders at established firms augmenting human EA/CoS plus founders at early-stage tier per the Step 4 mid-conversation ICP refinement.

**Methodology aggregate as control-plane construct** at `contexts/methodology/` per D86. The technical substrate the build-methodology uses to design product-methodology capabilities. The McKinsey 7-Step methodology at S26b lives here.

Step 5 touches all three. Workplan analyses run at build-methodology altitude; their findings inform product-methodology design; the control-plane aggregate is the substrate. The conversation holds all three streams distinct and surfaces interactions explicitly.

## What this conversation produces

Three drafted artefacts that a subsequent Claude Code commit session lands as a Step 5 section at `charter/phase-2-design-7step.md`:

1. **Analyses run and findings produced.** For each priority sub-problem in the Step 4 workplan, the Analyst role runs the analyses specified in the workplan at design-architectural altitude. Posture 1.5 constrains the conversation to design-architectural analyses; build-execution analyses defer to Phase 2 build sessions. Findings produced per analysis with evidence trail naming sources and substrates.

2. **Dogfooding-evidence record for Step 5 (substantive prose).** Fifth instance of the structural-dogfooding pattern. Fifth instance of the methodology-template-extensibility-without-breaking test. The pattern is at four-instance observed-pattern evidence after Step 4. This Step's outcome either continues the pattern (procurement-grade evidence strengthens further; bet's methodology-as-product claim accumulates further structural-level proof) or breaks the pattern (different signal worth recording at Phase 2 audit time). Step 5 also tests Posture 1.5 sustainability at the point where the agent-runtime gap becomes most acute (analyses-without-execution).

3. **Carry-forward to Step 6 (Synthesise).** Open questions Step 5 surfaces for the synthesis step's structuring-of-findings work.

## Context to read first via project_knowledge_search

In order:

1. `charter/phase-2-design-7step.md`. Steps 1, 2, 3, 4 sections in full. Particularly the eleven workplan entries with their hypotheses, analyses, data needed, owners, deadlines, deliverables; the five open questions Step 4 carries forward; and the senior-leader ICP refinement integrated mid-Step-4.

2. `briefs/p8/mckinsey-7-step.md`. The Analyst role's authored specification, constraints, and expected outputs. Function-focused system_prompt commits the role to running analyses and producing findings. McKinsey override layered analysis discipline.

3. `charter/bet.md`. Strategic intent; success criteria; case-study-reader audience commitment at line 67.

4. `charter/principles.md`. User safety section; intelligence-layer commitment; consent-granularity principle.

5. `charter/methodology.md` (build methodology).

6. `charter/product-methodology.md` (product methodology). Four professional functions framework; the surface Step 4's workplan deliverables expand.

7. `charter/architecture.md`. The substrate the workplan items build on.

8. `charter/competitors.md`. Step 4 commit's competitor catalog. Reference for the senior-leader ICP positioning analysis. Twenty-two named competitors across four categories.

9. `charter/p12-phase-2-inputs.md`. Phase 2 substrate-completion candidates plus architectural rework observations.

10. `charter/decisions.md`. Specifically D14 (customer-deployment), D24 (tenant isolation contract tests), D26 (append-only audit), D31 (revisions pattern), D32 (database-per-tenant), D44 (RICE plus living roadmap), D75 (agent aggregate), D77 (consumer-direction discharge plus calendar/email tool service deferred entries), D78 (personal-use deployment), D80 (four-layer constraint stack), D81 (methodology aggregate v2), D82 (intelligence-layer commitment plus platform invariants), D85 (McKinsey 7-Step methodology authoring placement), D86 (role-first model), D87 (override-mode space), D93 (Phase 2 direction methodology-as-product, noting the build-versus-product distinction surfaced at Step 1), D102 (audit context).

11. `log/captures.md`. Mass-market-UX commitment; use-case-portfolio entry; primitives-versus-templates throughline; consumer-direction architectural-exploration historical context.

12. `log/sessions.md`. Latest entry is the Step 4 commit. Reflection prompts (four answered) and methodology lines (four observed). The four-instance methodology-extension evidence claim sits in this entry.

## Pre-conversation operator decision

One decision to confirm before substantive Step 5 work begins. Four of the Step 4 carry-forward questions are analytical work the conversation runs, not pre-conversation decisions. Decision 1 below was carried forward as Q1 at Step 4 but warrants pre-conversation framing because the answer shapes how the Step 5 analytical work surfaces ICP-related findings.

### Decision 1: Senior-leader ICP commitment landing surface

The Step 4 mid-conversation refinement integrated senior-leader ICP framing into every workplan entry's user definition. The bet's case-study-reader audience plus Phase 1's existing posture support the refinement; the May 2026 competitor research provides the defensibility analysis. Step 4 deferred the landing surface question to Step 5 because the choice shapes how subsequent phases inherit the commitment.

Candidate landing surfaces:

(a) **Step 5 analysis output as charter-grade commitment** at `charter/phase-2-design-7step.md`, woven into the Step 5 findings section. Lowest landing friction; ties commitment to Phase 2 design work; risks future phases not finding it.

(b) **New charter file** at `charter/phase-2-user-segment.md` as standalone charter document. Highest discoverability for subsequent phases; clear authoritative reference; risks orphaning if Phase 3 sequencing analysis refines the ICP further.

(c) **Update to `charter/product-methodology.md`** at the v2 update queued for Phase 2 strategic-mode opening. Ties ICP commitment to the product-methodology framework; risks conflating user-segment definition with methodology authoring discipline.

(d) **Charter-grade entry at `charter/bet.md`** as a refinement to the bet's user-audience commitment. Highest weight; risks bet-amendment dynamics (the bet's audience commitment is procurement-grade-stable; refining it mid-arc opens questions about other parts of the bet).

**Recommend (b).** The senior-leader ICP refinement is structurally distinct from Phase 2 design work (it applies to Phase 2 AND to subsequent phases) and warrants standalone charter landing rather than embedding in Step 5 analysis. The new charter file becomes the user-segment authoritative reference; Step 5 analysis references it; subsequent phases inherit it. The vertical-wedge candidates (financial services, legal, healthcare from competitor research; product-leadership-vertical from operator's domain) sit alongside the segment definition for Phase 3 sequencing analysis. Operator decides.

## Conversation discipline expected

The McKinsey 7-Step Analyst role frames "run analyses, produce findings" with specific discipline. The conversation applies this deliberately, with the assistant surfacing the methodology's analysis prompts and the operator articulating answers per workplan entry.

Per priority sub-problem in the Step 4 workplan:

- **The analyses specified.** From the Step 4 workplan entry's "Analyses to be run" field.
- **Which analyses run at Step 5 altitude.** Design-architectural analyses (port specifications, schema decisions, conversation flow choices, integration patterns). Posture 1.5 defers agent-runtime analyses (actual execution; user-evidence gathering; live integration testing) to Phase 2 build sessions.
- **Findings produced.** What the analysis revealed. Surfacing of assumptions, dependencies, design decisions, open questions.
- **Evidence trail.** What sources or substrates the finding draws from (charter entries, prior decisions, competitor catalog entries, captures).

Plus four analytical work-streams the conversation produces findings on (mapping to Step 4 carry-forward questions Q2-Q5):

### Work-stream 1: Measurement substrate per priority sub-problem

The "won't know until real users" framing the operator surfaced at Step 4 requires each Phase 2-A deliverable carry measurement substrate built in (not bolted on) so real-user evidence at Phase 2-B refines find-rhythm-stage assumptions. Step 5 analyses what measurement substrate each of the eleven priority sub-problems requires.

For each sub-problem: what signal does the deliverable generate at use; how is the signal captured; what aggregation makes it analyseable; what threshold or pattern indicates the find-rhythm-stage assumption needs revision.

This is a substantive deliverable that affects every workplan entry. Sub-problems 4.4 Pattern surfacing, 4.5 Feedback-to-platform, 6.1 Signal verification, 6.2 Compliance-signal detection (all Tier 4, 5, 6 from Step 3 prioritisation; not in Step 4 workplan) become activation candidates at the moment measurement-substrate output surfaces them as required-rather-than-deferred work.

### Work-stream 2: Architectural pattern surfacing

Three patterns emerged during Step 4 workplan construction that may warrant explicit charter commitment as Phase 2-A architectural primitives:

(a) **Revision-with-lineage pattern.** Shared across sub-problem 2.1 methodology adaptation, sub-problem 4.2 goal revision, and sub-problem 6.5 correction mechanics (Tier 4, not in workplan). Parent artefact stays unchanged; revised artefact carries lineage to parent; audit trail captures the revision moment. Step 5 analyses whether this warrants explicit charter commitment as a Phase 2-A architectural primitive, or whether it stays implicit in each sub-problem's design.

(b) **Conversation flow pattern.** Shared across sub-problem 5.1 audit-conversation and sub-problem 4.1 mirror-conversation. User invokes; platform produces narrative; user drills down. Same structural shape, different content surfaces. Step 5 analyses whether this warrants commitment as a Phase 2-A conversation-flow primitive.

(c) **Three-tier consent-and-awareness framework.** At sub-problem 5.4. Step 4 surfaced this as commercial positioning differentiator beyond safety hygiene, aligned with procurement-grade audit-trailed-approval-first defensibility per competitor research. Step 5 analyses whether the framework warrants explicit charter commitment as an architectural primitive that other sub-problems reference.

Step 5 surfaces the findings; Step 6 (Synthesise) commits or defers each pattern.

### Work-stream 3: Phase 2-A versus Phase 2-B sequencing analysis

The eleven workplan entries split between Phase 2-A foundational and Phase 2-B refinement at Step 4. Step 5 produces findings about the sequencing logic:

- Which sub-problems are strictly Phase 2-A foundational (cannot be deferred)?
- Which sub-problems have Phase 2-A minimum-viable plus Phase 2-B refinement (most workplan entries)?
- What dependency chains exist across sub-problems (foundational layer first; surface layer second; cross-cutting third)?
- What substrate-completion thresholds gate the Phase 2-A to Phase 2-B transition?

The output informs the Phase 2 package structure that Step 6 (Synthesise) and the Phase 2 LVT placement use.

### Work-stream 4: Phase 2-B workitem clustering analysis

Multiple Phase 2-B workitems surface across the workplan and the Step 4 carry-forward:

- Voice as ninth substrate type (sub-problem 1.1 expansion).
- Voice as secondary delivery channel (sub-problem 3.1 expansion).
- Work-app cells (sub-problem 1.1 expansion; CRM, expense management, project management, ticketing, ERP, support tools).
- Multi-device sync implementation (sub-problem 1.3 architectural commitment Phase 2-A; full implementation Phase 2-B).
- Per-class consent refinement (sub-problem 3.5 Tier 4 from Step 3; not in workplan).
- Methodology-fit lifecycle full implementation (sub-problem 6.4 Tier 4 from Step 3; not in workplan).
- Action-classification framework reclassification mechanism (sub-problem 5.4 expansion).
- User-authored methodology surface (sub-problem 2.4 Tier 4 from Step 3; not in workplan).
- Disaggregator and Planner role system_prompt extensions per the four-instance methodology-extension pattern.
- Charter measurement substrate (per Work-stream 1 output).

Step 5 produces clustering findings (which workitems group together by dependency, by substrate, by user-surface). Step 6 sequences within and across clusters.

## Reflection prompts at session close

Five reflection prompts plus optional methodology lines worth observing.

1. **Methodology-template fidelity check.** Did the McKinsey 7-Step Analyst role's discipline hold for the analyses run at Step 5? Where did the template's discipline match the work? Where did it fall short? Step 5 has the most ambiguous discipline of any role to date (run analyses, produce findings; at Posture 1.5, this is design-architectural rather than execution-grade); the Analyst role's authored specification will be tested most acutely here.

2. **Methodology-template-extensibility-without-breaking test.** Fifth instance. Pattern continuation produces five-instance evidence; pattern break produces different signal at Phase 2 audit time. Either outcome strengthens the Phase 2 methodology work surface (continuation: methodology-extension workitem moves from observed-pattern to bet-evidence; break: discontinuity informs Phase 2 methodology refinement priorities).

3. **Posture 1.5 sustainability check.** Did Posture 1.5 deliver substantive analytical value at Step 5? Or did absence of agent runtime constrain analyses in ways worth noting? Step 5 is where the agent-runtime gap becomes most acute (analyses without execution). The findings surface what design-architectural altitude can deliver; whether build-execution analyses defer cleanly to Phase 2 build sessions; whether structural-dogfooding-only across Steps 1-5 produces a complete enough Phase 2 design.

4. **Briefs/ discipline check.** Brief authored before substantive Step 5 work AND in a fresh Claude.ai conversation thread. Does this complete the brief-authoring pattern that Steps 3 and 4 left partial? If yes, the pattern becomes a methodology line worth promoting from observation to charter commitment.

5. **Measurement-substrate discipline check.** Did the measurement-substrate analysis produce concrete commitments for each priority sub-problem? The "won't know until real users" framing requires this; Work-stream 1 is the test. Concrete commitments at every priority sub-problem demonstrate measurement-substrate-as-Phase-2-A-discipline; gaps indicate where Phase 2-B real-user evidence will surface against an under-instrumented substrate.

Plus optional methodology lines worth observing: any structural or procedural patterns the conversation surfaces that warrant methodology document treatment.

## What this conversation does not do

- Run agent-execution analyses (deferred to Phase 2 build sessions per Posture 1.5).
- Make Phase 2 LVT placement decisions (Step 6 Synthesise output).
- Author the Step 6 brief (separate work; pre-Step-6).
- Modify the Step 4 workplan entries (the workplan is input to Step 5; Step 5 produces findings about the workplan, not edits to it).
- Land the senior-leader ICP refinement except through the Decision 1 landing-surface choice (the refinement itself is committed at Step 4; Step 5 lands the commitment surface).
- Decide on Phase 2 package structure (Step 6 Synthesise output).
