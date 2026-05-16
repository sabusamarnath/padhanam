# Phase 2 design — 7-Step arc — Step 3 commit session

## Identification

Mode: strategic (charter commit; no code changes; lint and tests not required at this session).
Block: Phase 2 design — McKinsey 7-Step arc — Step 3 (Prioritise) commit landing.
Branch: operator-selected at session open.

## Goal at session close

- `charter/phase-2-design-7step.md` carries a new "## Step 3: Prioritise" section appended after the Step 2 close paragraph, with eight sub-sections (opener, prioritised list, top quartile flagged, self-challenge, dogfooding-evidence record, carry-forward to Step 4, Step 3 close).
- `charter/current-package.md` gains a new close marker paragraph appended after the Step 2 close marker (chronological order preserved; append-only language per the Step 2 commit's correction).
- `briefs/phase-2/design-7step-step-3.md` exists carrying the pre-conversation brief verbatim. This brief was authored pre-conversation, restoring full briefs/ discipline; the synthetic-retrospective-brief pattern's recurrence test from Step 2 resolves at single-instance.
- `briefs/phase-2/design-7step-step-3-commit.md` preserves this commit-session prompt verbatim.
- Session log entry appended to `log/sessions.md` matching the Step 2 commit entry's shape.

## Context to read first

In order. Read in ranges where files exceed 200 lines.

1. `charter/phase-2-design-7step.md`. Step 1 and Step 2 sections in full. Confirm Step 2 close paragraph is terminal; the Step 3 section appends immediately after.
2. `charter/current-package.md` (top section). Confirm the close marker structure after the Step 2 commit. The Step 3 commit appends a new paragraph after the Step 2 close marker.
3. `log/sessions.md`. Latest entry is the Step 2 commit; match its shape for the Step 3 commit entry. Specifically the four-reflection-prompt structure plus three methodology lines plus close marker handing off to next Step.
4. `briefs/phase-2/design-7step-step-2.md`. Note the synthetic-retrospective-brief framing-flag at the top of that file; the Step 3 brief contains the inverse framing (pre-conversation authored, discipline restored).
5. `briefs/phase-2/design-7step-step-2-commit.md`. Commit-prompt shape precedent.
6. `briefs/p8/mckinsey-7-step.md`. The Prioritiser role's authored specification, cited in the Step 3 dogfooding-evidence record.

## Pre-write reconciliation

1. **D-entry count.** Latest entry remains D113. No new D-entries this session. The dogfooding-evidence record cites D85 (McKinsey 7-Step methodology authoring placement); D85 exists as a summary line in active `charter/decisions.md` with full content in `docs/archive/decisions/phase-1.md`.
2. **Current-package.md state.** Read the file and confirm the Step 2 close marker paragraph from the Step 2 commit. The Step 3 commit appends a new paragraph after Step 2's marker. Use append-only language at the commit; do not replace prior content, per the Step 2 commit's append-versus-replace correction.
3. **Append point at `charter/phase-2-design-7step.md`.** Confirm the Step 2 close paragraph is the file's current terminal content; append the Step 3 section after it without modifying Step 1 or Step 2 content.
4. **Brief preservation path.** `briefs/phase-2/` directory exists from Step 1 commit. Two new files land there at this commit: the pre-conversation brief (whose content is provided inline below) and this commit-session prompt (verbatim).
5. **Pre-conversation brief framing-flag.** The Step 3 brief was authored pre-conversation (not synthetic-retrospective). The brief itself notes this explicitly as the pattern's recurrence test outcome. Preserve verbatim including the framing note.
6. **Session log entry shape.** Mirror the Step 2 commit entry's structure. Four reflection prompts; three methodology lines; close marker handing off to Step 4.
7. **Carryover from prior commits.** The stale "P11 framed; S39 next" header at `charter/current-package.md` line 5 remains pre-existing structural drift; out of scope at this session per AC 7.

## Commits

### Commit 1: Step 3 artefacts land at charter file plus current-package append plus brief preservation

Conventional commit message: `docs(charter): phase 2 design — 7-step arc Step 3 prioritisation, top quartile flagged, dogfooding evidence at three-instance`

Three-paragraph commit body. Paragraph 1: names what the new section lands (thirty sub-problems scored on impact-tractability; top quartile flagged at both strict five-item cut and inclusive eleven-item cut; dogfooding-evidence record; five open questions carrying forward). Paragraph 2: names the two operator-pushback revisions during scoring (sub-problem 3.4 Delegation scope reframe; sub-problem 5.5 Trust history meta-signal recognition) and the substrate-type matrix expansion (documents and messaging added). Paragraph 3: names the methodology-template-extensibility-without-breaking pattern reaching three-instance evidence across ProblemFramer, Disaggregator, and Prioritiser roles; the Phase 2 methodology-extension workitem moves from two-instance candidate to three-instance evidence base.

**Append the following content to `charter/phase-2-design-7step.md` as a new "## Step 3: Prioritise" section, placed immediately after the Step 2 close paragraph. Content verbatim, no in-line editing:**

```markdown
## Step 3: Prioritise

Step 3 applied the McKinsey 7-Step Prioritiser role's discipline to the issue tree produced at Step 2. The role's function-focused system_prompt commits the role to "score each branch on impact (how much resolving this moves the overall problem) and tractability (how feasible resolving this is in available time and resources); produce a ranked list with the top branches flagged as priorities." The McKinsey override layered "Use impact-tractability matrix; flag the top quartile as priorities." Posture 1.5 dogfooding continued from Steps 1 and 2. The conversation read the role's specification and held the discipline manually without invoking the agent runtime.

Three pre-conversation decisions framed the scoring approach. Decision 1 (population scope for impact): operator as first instance of broader busy-professional population, balancing operator dogfooding evidence with broader-population generalisation. Decision 2 (scoring dimensions): pure impact-tractability per the McKinsey template, holding RICE for Phase 2 LVT placement when packages get derived. Decision 3 (cross-cutting disciplines): distribute detection and the four-stage temporal lifecycle into per-sub-problem rationale rather than score them as separate items.

Two operator pushbacks during scoring sharpened the prioritised list. Sub-problem 3.4 (Delegation) scored low at first read because the scope was narrow (delegation to external humans only); the operator's reframe broadened scope to include delegation to the platform's AI agents alongside delegation to humans, lifting the score from 4 to 7. Sub-problem 5.5 (Trust history) scored lowest at first read; the operator's pushback recognised the meta-signal value (engagement evidence, trust-break learning, onboarding effectiveness) without disputing the late-stage timing, lifting the score from 5 to 6. Both pushbacks accommodated within the Prioritiser role's authored discipline without breaking.

Two scope expansions in the substrate-type matrix at sub-problem 1.1 emerged from operator review. Documents (Google Drive, OneDrive, Dropbox, Notion, local disk) and messaging (WhatsApp, iMessage, Slack, Telegram) joined calendar, email, notes, manual entry, and existing trackers as substrate types. The matrix at 1.1's sub-decomposition is now seven substrate types times four integration functions (read, observe, write, acknowledge) producing twenty-eight cells for Step 4 to sequence. Messaging additionally functions as a primary delivery interface for sub-problem 3.1's surfacing mechanics, carrying forward to Step 4 as a design constraint.

### Prioritised list

Scores reported as Impact / Tractability = Total. One-line rationale per sub-problem. Scores reflect the three pre-conversation decisions and the two operator-driven revisions noted above.

**Tier 1 (score 10): top quartile core**

- **1.3 State persistence** — 5 / 5 = 10. Portfolio-resets-each-session is exactly the Step 1 breakdown mode; database-per-tenant substrate already supports persistent state.

**Tier 2 (score 9): top quartile**

- **1.1 Substrate connection** — 5 / 4 = 9. Foundational for portfolio existence across seven substrate types; P6 ingestion substrate in place; calendar, email, and messaging MCP integrations tractable per deferred-decisions entries.
- **2.1 Methodology library** — 4 / 5 = 9. Differentiates platform from generic productivity tools; LVT, RICE, Kano, McKinsey 7-Step already authored on control plane; growth maintains primitives-versus-templates discipline.
- **3.1 Surfacing mechanics** — 5 / 4 = 9. The whisperer function lives here; messaging-first delivery as primary channel for busy-professional users; substrate-aware surfacing tractable.
- **5.1 Audit visibility** — 4 / 5 = 9. Phase 1 P10 audit substrate exists; surfacing to user is UI work; foundational for trust per D82.

**Tier 3 (score 8): top quartile inclusive cut**

- **1.5 User-authored items** — 3 / 5 = 8. CRUD-shaped input; user-authored items tend to be high-importance.
- **3.2 Drop-decision support** — 4 / 4 = 8. Where calibration becomes action; items-that-should-be-dropped is a load-bearing failure mode.
- **4.1 Mirror surface** — 5 / 3 = 8. Named in Step 1's success-measurement deliverable; depends on 4.2 and 4.3.
- **4.2 Goal-state tracking** — 4 / 4 = 8. Foundational for mirror; goals as items is tractable extension of portfolio state.
- **5.4 Intelligence-layer guardrails** — 4 / 4 = 8. D82 platform invariants exist; surfacing at decision points is structurally cheap.
- **6.3 Status veracity** — 4 / 4 = 8. Lower-pressure status options structurally simple; impact on portfolio accuracy high.

**Tier 4 (score 7): substantive but not top quartile**

- **1.4 Personal-versus-professional treatment** — 4 / 3 = 7. Design challenge more than technical.
- **2.2 Methodology-to-item binding** — 4 / 3 = 7. Critical for calibration; binding mechanics non-trivial under revision and load.
- **2.3 Pace inference per item** — 5 / 2 = 7. Rules-driven inference tractable; learned models out of Phase 2 envelope.
- **2.4 User-authored methodology surface** — 4 / 3 = 7. Bet's methodology-as-product depends on this; authorship UX non-trivial.
- **2.5 Calibration override mechanics** — 3 / 4 = 7. Override important but secondary to initial calibration quality.
- **3.3 Defer mechanics** — 3 / 4 = 7. Defer is a degenerate case of pacing; substrate exists.
- **3.4 Delegation (AI plus human)** — 4 / 3 = 7. Both delegation flavours (to platform agents; to other humans) in scope; AI delegation underpins Branch 3; human-delegation tracking is moderate complexity.
- **3.5 Consent granularity for platform actions** — 4 / 3 = 7. D82 intelligence-layer commitment requires it; mechanics nontrivial.
- **4.5 Feedback-to-platform** — 3 / 4 = 7. Preference management substrate.
- **5.2 Source attribution** — 3 / 4 = 7. P11 recommendation-with-citation substrate exists; UI extension.
- **5.3 Cost transparency** — 3 / 4 = 7. P4 cost-capture substrate exists; less critical at personal-use stage.
- **6.4 Methodology-fit lifecycle** — 5 / 2 = 7. Rhythm-and-key-change framing load-bearing for methodology-as-product claim; detection mechanics complex.
- **6.5 Correction mechanics** — 3 / 4 = 7. Low-friction correction; depends on audit substrate.

**Tier 5 (score 6)**

- **4.3 Value-versus-time accounting** — 4 / 2 = 6. Time-tracking tractable; defining value per item per methodology is hard.
- **4.4 Pattern surfacing** — 3 / 3 = 6. Useful but late-stage; needs accumulated run-history.
- **5.5 Trust history** — 3 / 3 = 6. Late-stage refinement; meta-signal value (engagement evidence; trust-break learning; onboarding effectiveness) informs other branches' improvement loops.
- **6.1 Signal verification** — 3 / 3 = 6. Important for accuracy; secondary to having signals at all.

**Tier 6 (score 5)**

- **1.2 Item identity reconciliation** — 3 / 2 = 5. Crude duplicates tolerable initially; entity resolution across heterogeneous substrates is a known hard problem.
- **6.2 Compliance-signal detection** — 3 / 2 = 5. Requires accumulated signal data; cannot bootstrap.

### Top quartile flagged

Top quartile of 30 sub-problems is 7-8 items. The score distribution produces a clean cut at five items (Tiers 1 plus 2; score ≥ 9). Extending the inclusive reading to eleven items (Tiers 1 through 3; score ≥ 8) captures the substantive priority set without diluting focus. Step 4's workplan operates on the eleven-item inclusive set as the planning surface, with the five-item core treated as the load-bearing priority.

**Top quartile, strict cut (5 items):** 1.3 State persistence, 1.1 Substrate connection, 2.1 Methodology library, 3.1 Surfacing mechanics, 5.1 Audit visibility.

**Top quartile, inclusive cut (11 items, adds Tier 3):** 1.5 User-authored items, 3.2 Drop-decision support, 4.1 Mirror surface, 4.2 Goal-state tracking, 5.4 Intelligence-layer guardrails, 6.3 Status veracity.

### Self-challenge

**Dependency awareness.** The top tier concentrates in Branch 1 foundational items (1.1, 1.3, 1.5), Branch 2 library entry-point (2.1), Branch 3 action surface (3.1, 3.2), Branch 4 feedback substrate (4.1, 4.2), Branch 5 trust foundation (5.1, 5.4), and Branch 6 status-veracity (6.3). This is consistent with the dependency ordering from Step 2: Branch 2 depends on Branch 1; Branches 3-4 depend on Branches 1-2; Branch 6 depends on signal sources from others. The ranking respects dependency naturally. Step 4 sequences within this priority set respecting both score order and dependency order.

**Operator-as-first-instance framing held throughout.** Sub-problems with high operator-specific impact and lower broader-population generalisation scored lower than sub-problems that serve both. 6.4 (Methodology-fit lifecycle) scored impact 5 because the rhythm-and-key-change framing is load-bearing for the broader-population test condition; for pure operator-only the impact would be lower.

**Rules-versus-learned tractability framing held.** Sub-problems 2.3 (Pace inference) and 6.4 (Methodology-fit lifecycle) scored tractability 2 because learned-model approaches are out of Phase 2's resource envelope; rules-driven approaches keep them tractable at the lower end. Step 4 commits to rules-driven approaches at workplan time.

**Items with disputed scoring noted explicitly.** 3.4 (Delegation) and 5.5 (Trust history) were revised mid-conversation per operator pushback; the rationale captures the scope clarification (3.4) and meta-signal recognition (5.5) so the audit trail surfaces the iteration cleanly.

### Dogfooding-evidence record

The McKinsey 7-Step Prioritiser role authored at S26b per D85 carries a function-focused system_prompt committing the role to impact-tractability scoring with top-quartile flagging. The McKinsey override added the impact-tractability matrix and top-quartile threshold. Posture 1.5 structural dogfooding without agent runtime continued from Steps 1 and 2. This is the third instance of the structural-dogfooding pattern across three distinct roles (ProblemFramer at Step 1, Disaggregator at Step 2, Prioritiser at Step 3).

What the template informed. The "score each branch on impact and tractability; produce a ranked list with the top branches flagged as priorities" discipline held cleanly. The conversation produced 1-5 scores across both dimensions for thirty sub-problems with one-line rationale per item, ranked in score order, with the top-quartile cut explicitly framed. The "you do not solve sub-problems; you order them" discipline held; the conversation resisted moving into solution architecture even when scoring rationale touched implementation considerations. The matrix shape per the McKinsey override produced clean tier clustering at scores 10, 9, 8, 7, 6, 5; the top quartile cut emerged from the tier structure rather than from arbitrary numeric threshold.

Where the template's scope did not cover the work. Five extensions surfaced during the conversation that the McKinsey 7-Step Prioritiser role's system_prompt does not encode. First, scoring-dimension choice (impact-tractability versus impact-tractability-plus-confidence versus full RICE) required an operator decision; the role's authored discipline picks one (impact-tractability) without surfacing the alternative dimensions the conversation actually has access to. Second, population-scope choice (operator-only versus broader-population versus operator-as-first-instance) required an operator decision; the role does not surface that impact scoring varies with population framing. Third, cross-cutting discipline treatment (score separately versus distribute into rationale) required an operator decision; the role does not specify how to handle cross-cutting issues within the matrix. Fourth, dependency-aware scoring across the issue tree is implicit in the conversation but not explicit in the role; tractability scores naturally lower for sub-problems with unmet dependencies, but the role's discipline does not name this. Fifth, mid-scoring revision through operator pushback (sub-problems 3.4 and 5.5) is methodologically normal but not named in the role's discipline; the role describes scoring as if it were a single pass.

What this surfaces for Phase 2 methodology work. The Prioritiser role's authored discipline is narrower than the prioritisation work this conversation needed, consistent with the pattern observed at ProblemFramer (Step 1) and Disaggregator (Step 2). The three roles together produce a coherent procurement-grade-evidence pattern: the methodology aggregate's authored content is structurally sound and extensible, but each role's authored discipline scope is narrower than the substantive discipline the conversation applies. Phase 2 methodology work has two distinct workitem candidates: short-term, expand the role system_prompts to encode the discipline-extensions explicitly (population scope, scoring dimensions, cross-cutting treatment, dependency awareness, revision mechanics); long-term, layer skills per role per the Phase 2 deferred surface, with each role gaining methodology-specific skills that encode the extensions cleanly.

What this tells us about the bet's claim. The methodology-template-extensibility-without-breaking pattern reaches three instances across three distinct roles at this Step 3 close. The bet's procurement-grade methodology-embedding claim now has substantial structural-level evidence; the pattern's consistency across roles strengthens the case that the methodology aggregate as authored on the control plane is genuinely extensible by operators and agents alike, not just operationally workable in one case. Agent-runtime evidence remains untested through all three Steps. Phase 2 UX surface for methodology adoption plus agent runtime exercising the Prioritiser end-to-end would close the higher bar; until then, three-instance structural evidence is the procurement-grade artifact.

### Carry-forward to Step 4 (Planner)

Five open questions land at Step 4:

1. **Workplan granularity.** Step 4 produces a workplan for the top quartile (strict cut: 5 items; inclusive cut: 11 items). Granularity per item: per-sub-problem versus per-priority-cluster. The strict-versus-inclusive cut choice affects this; smaller set permits per-sub-problem depth, larger set may need clustering.

2. **Substrate-type × integration-function matrix sequencing at 1.1.** The twenty-eight cells require workplan sequencing. Calendar-read and email-read might be Phase 2-A; messaging-write might wait for stronger consent substrate; document-observe might depend on additional substrate work. Step 4's workplan ranks the cells within sub-problem 1.1.

3. **Dependency versus priority within the workplan.** State persistence (1.3) and substrate connection (1.1) are top priority AND foundational; calibration and feedback sit on top of them. Step 4 sequences within the prioritised set respecting both score order and dependency order; the two ordering principles may conflict and the workplan resolves the conflict.

4. **Lifecycle-stage prioritisation strategy.** From Step 2's carry-forward, sharper now. The four-stage discipline (find rhythm, settle in, watch, adapt) applies at every prioritised sub-problem. Step 4 decides whether Phase 2 ships find-rhythm-plus-settle-in stages across all priority items first (with watch and adapt later), or full-lifecycle support for fewer items first. Different commercial test conditions.

5. **Messaging-first delivery design constraint and meta-signal observability.** Carryforward design commitments: workplan items in Branch 3 default to messaging-first delivery; trust-history (5.5) sequences as observability work informing other branches' iteration cadence rather than as standalone feature work.

### Step 3 close

Step 3 closes with thirty sub-problems scored on impact and tractability, top quartile flagged at both strict (5 items) and inclusive (11 items) cuts, dogfooding-evidence record at third-instance evidence of the methodology-template-extensibility-without-breaking pattern, and five open questions carrying forward to Step 4. The Prioritiser role's discipline produced a usable prioritisation that respected dependency, accommodated operator pushback, and held the structural test condition (operator-as-first-instance of broader busy-professional population) throughout. Step 4 (Plan) opens at Claude.ai with the top quartile as the workplan surface plus the five open questions as planning inputs. The Step 4 pre-conversation brief authors at `briefs/phase-2/design-7step-step-4.md` before the Claude.ai conversation opens, continuing the briefs/ discipline restoration test from Step 3.
```

**Append to `charter/current-package.md` a new close marker paragraph after the Step 2 close marker (append-only; chronological order preserved per the Step 2 commit's append-versus-replace correction). The new paragraph reads (adjust phrasing to match the file's existing tone at write time):**

> Phase 2 design 7-Step arc Step 3 closed at [date of commit]. The Step 3 section at `charter/phase-2-design-7step.md` carries the prioritised list (thirty sub-problems scored on impact-tractability per the McKinsey 2x2 matrix), the top quartile flagged at both strict (5-item) and inclusive (11-item) cuts, the Step 3 dogfooding-evidence record, and five open questions carrying forward to Step 4. The methodology-template-extensibility-without-breaking pattern reaches three-instance evidence across the ProblemFramer, Disaggregator, and Prioritiser roles. The next strategic-mode block is Step 4 (Plan), which produces the workplan for the prioritised set; the Step 4 pre-conversation brief authors at `briefs/phase-2/design-7step-step-4.md` before the Claude.ai conversation opens.

**Create `briefs/phase-2/design-7step-step-3.md` with the following content, verbatim:**

```markdown
# Phase 2 design — McKinsey 7-Step — Step 3 (Prioritise)

Strategic-mode conversation applying Step 3 of the McKinsey 7-Step Framework to the issue tree produced at Step 2. Third session in the multi-session arc that produces the Phase 2 strategic shape. Posture 1.5: structural dogfooding of the McKinsey 7-Step methodology template authored at S26b without agent runtime dependency. The conversation reads the Prioritiser role's specification and follows its impact-tractability discipline deliberately.

This brief is authored pre-conversation, restoring full briefs/ discipline after the synthetic-retrospective shape at Step 2's brief. The pattern-recurrence test from Step 2's session log entry passes if this brief lands before the Claude.ai conversation opens; the synthetic-retrospective-brief pattern stays at single instance.

## What this conversation produces

Three drafted artefacts that a subsequent Claude Code commit session lands as a Step 3 section at `charter/phase-2-design-7step.md`:

1. **The prioritised list of sub-problems with impact-tractability scores.** Each of the thirty sub-problems from Step 2's issue tree (six branches × five sub-branches) gets an impact score and a tractability score. The top quartile (top seven or eight sub-problems) flagged as priorities. Score rationale captured per sub-problem so the audit trail survives.

2. **Dogfooding-evidence record for Step 3 (substantive prose).** Third instance of the structural-dogfooding pattern, third instance of the methodology-template-extensibility-without-breaking test. Did the Prioritiser role's authored content work at the actual prioritisation problem, or did the conversation operate on general McKinsey framework knowledge? The dogfooding-evidence record names this honestly.

3. **Carry-forward to Step 4 (Planner).** Open questions Step 3 surfaces for the planning step's workplan construction.

## Context to read first via project_knowledge_search

Search for and read systematically:

1. `charter/phase-2-design-7step.md`. Step 1 and Step 2 sections in full. Step 1's sharpened problem statement plus context paragraphs; Step 2's six-branch × five-sub-branch issue tree plus the two cross-cutting disciplines (detection; the four-stage temporal lifecycle of find rhythm, settle in, watch, adapt).
2. `briefs/p8/mckinsey-7-step.md`. The Prioritiser role's authored specification, constraints, and expected outputs. Specifically the function-focused system_prompt: "You prioritise sub-problems from a decomposition tree... score each branch on impact (how much resolving this moves the overall problem) and tractability (how feasible resolving this is in available time and resources); produce a ranked list with the top branches flagged as priorities. You do not solve sub-problems; you order them." Plus the McKinsey override: "Use impact-tractability matrix; flag the top quartile as priorities."
3. `charter/bet.md`. Strategic intent the design serves; the bet's six success criteria are the impact-scoring backbone for sub-problems that connect to bet-level claims.
4. `charter/principles.md`. User safety section; Padhanam-as-intelligence-layer commitment; methodology-embedded-not-gated principle.
5. `charter/methodology.md`. Framework discipline including RICE convention at package-level; relevant for Decision 2 below.
6. `charter/product-methodology.md`. Four professional functions framework; relevant for Branch 2 (Pace calibration) scoring.
7. `charter/p12-phase-2-inputs.md`. Phase 2 substrate-completion candidates plus Phase 2-entry hygiene workitems; relevant for tractability scoring on Branch 1 substrate connection sub-problems.
8. `charter/decisions.md`. Specifically D44 (strategic-tree LVT pattern with reasoning categories), D82 (platform invariants and intelligence-layer commitment), D85 (McKinsey 7-Step methodology authoring placement), D93 (Phase 2 direction methodology-as-product).
9. `log/captures.md`. The mass-market-UX-as-Phase-2-commitment entry; the use-case-portfolio entry recording the eleven use cases from the rejected separate-consumer-build path.

## Pre-conversation operator decisions

Three decisions to confirm before substantive Step 3 work begins:

### Decision 1: Population scope for impact scoring

Impact assessment depends on the user population the platform serves. Three options:

(a) **Operator-only impact scoring.** Score sub-problems on what helps the operator's specific Private Assistant use cases the most. Narrower scope; sharper for dogfooding evidence; weaker for broader-population evidence.

(b) **Broader busy-professional population scoring.** Score on what helps the busy professional carrying twelve-plus hour day load most. Wider scope; weaker for operator-specific dogfooding; stronger for generalisation evidence.

(c) **Operator as first instance of broader population.** Score on what helps the operator AND generalises to the broader population. The operator dogfoods first; the impact score reflects both immediate operator value and generalisation potential.

**Recommend (c).** The bet's case-study claim (procurement-grade methodology-embedding) requires evidence that the methodology travels beyond the operator; the broader-population test condition is load-bearing. The operator's dogfooding is the first instance, not the whole. Sub-problems that serve the operator but do not generalise score lower than sub-problems that serve both. Operator decides.

### Decision 2: Scoring dimensions

The McKinsey 7-Step template specifies impact-tractability (2D matrix). The project's strategic-tree convention uses RICE (Reach, Impact, Confidence, Effort) per D44 at package-level prioritisation. Three options:

(a) **Pure impact-tractability per McKinsey template.** Score each sub-problem on impact (1-5) and tractability (1-5). Top quartile flagged. Honours the McKinsey 7-Step methodology dogfooding faithfully.

(b) **Impact-tractability-plus-confidence.** Add a confidence dimension to the McKinsey 2D matrix. Confidence captures how sure the prioritisation is, given evidence quality.

(c) **Full RICE per project convention.** Score on Reach, Impact, Confidence, Effort. Connects to the project's broader prioritisation language; RICE is what packages will be scored against at Phase 2 LVT placement.

**Recommend (a).** The conversation is dogfooding the McKinsey 7-Step Prioritiser role; layering RICE on top departs from the role's authored discipline and weakens the structural-dogfooding evidence. RICE comes in later at Phase 2 LVT placement when packages get derived from the prioritised Step 3 + 4 outputs. Operator decides; if (c) wins, the conversation must explicitly note where it departed from McKinsey discipline so the dogfooding-evidence record stays honest.

### Decision 3: Treatment of cross-cutting disciplines

The four-stage temporal lifecycle and detection apply at every sub-branch as cross-cutting disciplines per Step 2. Two scoring approaches:

(a) **Score cross-cutting disciplines as separate items.** Detection and the four-stage lifecycle each get their own impact-tractability score. The thirty sub-problems plus two cross-cutting items make thirty-two scored items. Top quartile applies across all thirty-two.

(b) **Distribute cross-cutting disciplines into sub-problems.** Each sub-problem's impact-tractability score includes the cross-cutting-discipline implications. The thirty sub-problems are the scored set; the cross-cutting disciplines are scoring inputs, not scored items.

**Recommend (b).** The cross-cutting disciplines are not separable work items; they are properties of how the sub-problems get implemented. Scoring them separately produces phantom items the Planner cannot construct a workplan against. Operator decides.

## Conversation discipline expected

The McKinsey 7-Step Prioritiser role frames "rank by impact and tractability" with specific discipline. The conversation applies this deliberately, with the assistant surfacing the methodology's scoring prompts and the operator articulating answers per sub-problem:

**Impact: how much does resolving this sub-problem move the overall problem (the calibration-breakdown-under-load problem from Step 1)?** The sub-problem's impact connects to one or more of the bet's success criteria plus the user-side measures named at Step 1's success-measurement deliverable. Sub-problems that move the calibration breakdown most score highest.

**Tractability: how feasible is resolving this in available time and resources?** Phase 2's resource envelope is the operator plus Claude Code working at the cadence of Phase 1. Sub-problems requiring substrate that does not yet exist (some integration paths; some methodology surfaces) score lower tractability. Sub-problems that build cleanly on Phase 1's substrate score higher.

**Cross-branch dependency awareness.** Branch 2 depends on Branch 1; Branch 3 depends on Branch 2; Branch 4 depends on Branches 1-3; Branch 6 depends on signal sources from other branches. Tractability scoring respects dependency or flags it explicitly when scoring out of dependency order.

**Lifecycle-stage prioritisation.** The four-stage discipline (find rhythm, settle in, watch, adapt) applies at every branch. Step 3's prioritisation produces input for Step 4's workplan. Step 3 must decide whether Phase 2 ships find-rhythm-plus-settle-in stages across all branches first, or full-lifecycle support for fewer branches first. This decision lives inside the prioritisation rationale per sub-problem.

The conversation iterates. Initial scores get challenged; revisions surface; the prioritised list converges through multiple cycles. The assistant pushes back on rankings that do not survive the scoring rationale. The operator pushes back on rankings that misread the user or the work.

## Dogfooding-evidence record discipline

Throughout the conversation, the assistant notes how the Prioritiser role's authored content informed the work. At conversation close, the assistant drafts the dogfooding-evidence record as substantive prose against the procurement-grade evidence question:

Did Padhanam's own methodology authoring (the McKinsey 7-Step Prioritiser role at S26b per D85, structured per D81's multi-role aggregate v2 shape) produce content that worked for the operator at a real Phase 2 prioritisation problem? Or did the conversation operate on general McKinsey framework knowledge irrespective of what was authored on the control plane?

The third instance of the methodology-template-extensibility-without-breaking pattern is the recurrence test. ProblemFramer at Step 1 and Disaggregator at Step 2 both had narrower authored discipline scope than work scope and accommodated extensions without breaking. The Prioritiser is the third role; the third instance either continues the pattern (procurement-grade evidence strengthens) or breaks the pattern (different signal worth recording). The dogfooding-evidence record names this honestly.

The record names specifically: which template fields informed the session, where the application worked cleanly, where it required interpretation, what gaps surfaced between the template's scope and the actual prioritisation work. Honest framing wins.

## Conversation closing

At conversation close, the assistant produces three drafted text artefacts:

1. The prioritised list (top quartile flagged; rationale per sub-problem captured) — structurally similar to the Step 2 issue tree but with scores attached and ordering applied
2. The dogfooding-evidence record (substantive prose, four to five paragraphs)
3. Carry-forward to Step 4 (open questions for Planner)

Plus a brief paragraph noting Step 4 (Plan) as the next session in the arc, plus any open questions Step 3 surfaced for Step 4 specifically. Examples of likely Step-3-to-Step-4 carry-forward questions: workplan granularity (per-sub-problem versus per-priority-cluster); resource allocation across priority items; sequencing within priorities given dependencies; whether to plan across the full top quartile or sub-prioritise the quartile further.

The drafted artefacts get committed via a subsequent short Claude Code session. The Claude Code session's commit-session brief drafts at this Claude.ai conversation's close, taking the drafted artefacts as paste-ready content inline (per the placeholder-versus-content-payload methodology-miss correction from Step 1's commit prompt).
```

**Create `briefs/phase-2/design-7step-step-3-commit.md`** preserving this commit-session prompt verbatim. The entire prompt body from "# Phase 2 design — 7-Step arc — Step 3 commit session" through the session log entry instruction.

### Commit 2: Session log entry

Conventional commit message: `docs(log): phase 2 design 7-step arc Step 3 commit session log entry`

Append an entry to `log/sessions.md` matching the Step 2 commit entry's shape per pre-write reconciliation item 6. Set `roles: analyst, PM, technical writer` (operator confirms or amends). Set `mode: strategic`. Two commits. Answer the four reflection prompts below as the entry's main content. Three methodology lines at entry close. Close marker handing off to Step 4 (Plan) as the next strategic-mode block.

## Acceptance criteria

1. New "## Step 3: Prioritise" section exists at `charter/phase-2-design-7step.md`, appended after the Step 2 close paragraph, carrying the eight sub-sections specified (opener, prioritised list, top quartile flagged, self-challenge, dogfooding-evidence record, carry-forward to Step 4, Step 3 close). Content verbatim from the inline content payload above, no in-line editing.
2. `charter/current-package.md` gains a new close marker paragraph appended after the Step 2 close marker. Append-only operation; prior content preserved unchanged. Phrasing matches the file's existing tone at write time.
3. `briefs/phase-2/design-7step-step-3.md` exists carrying the pre-conversation brief verbatim, including the pre-conversation framing note at the top of the file.
4. `briefs/phase-2/design-7step-step-3-commit.md` exists and preserves this commit-session prompt verbatim.
5. `log/sessions.md` carries a new entry matching the Step 2 commit entry's shape, with the four reflection prompts answered as substantive prose where warranted, three methodology lines at close, and the handoff marker.
6. Working tree clean at end of session.
7. No new D-entries land; no edits to `charter/decisions.md`, `charter/deferred-decisions.md`, `charter/principles.md`, `charter/methodology.md`, `charter/product-methodology.md`, `charter/architecture.md`, or `log/captures.md`. Drift items defer per Out of scope below.

## Reflection prompts for the session log entry

1. **Pre-write reconciliation outcome.** Did the seven reconciliation items surface drift? Specifically: did the append-versus-replace pattern test at `charter/current-package.md` resolve cleanly (the Step 2 commit's correction holding); did the synthetic-retrospective-brief pattern test resolve at single-instance (the Step 3 brief landing pre-conversation); did the stale "P11 framed; S39 next" header at line 5 drift further or stay stable.

2. **The three pre-conversation decisions and their downstream impact on the prioritisation.** The conversation opened with operator confirmation of (c) operator-as-first-instance-of-broader-population, (a) pure impact-tractability per McKinsey template, (b) distribute cross-cutting disciplines into per-sub-problem rationale. Were these the right pre-conversation decisions, or did the conversation surface that other framing decisions should have happened upfront (for example, the substrate-type matrix expansion at 1.1 that emerged mid-conversation when documents and messaging joined the type set)? The reflection records whether pre-conversation decisions caught the load-bearing scope choices or whether scope-extensions during the conversation became methodology-pattern signal.

3. **The methodology-template-extensibility-without-breaking pattern at three instances across three roles.** ProblemFramer (Step 1), Disaggregator (Step 2), Prioritiser (Step 3). What does the three-instance evidence signal for the Phase 2 methodology-extension workitem? Does it merit elevation from candidate to commitment? The Step 2 session log named this as two-instance pattern-based candidate; Step 3 lifts it to three-instance. If Steps 4-7 continue the pattern, recurrence evidence reaches structural-promotion threshold well before Phase 2 framing reads it.

4. **The two operator-pushback mid-conversation revisions as a methodology-candidate.** Sub-problem 3.4 (Delegation) scope reframe; sub-problem 5.5 (Trust history) meta-signal recognition. Both lifted scores after the Prioritiser role's initial scoring had landed. The pattern is: operator pushback as built-in revision mechanic for the McKinsey 7-Step Prioritiser role, normal methodologically but not named in the role's authored discipline. First explicit instance at this session; recurrence test at subsequent Steps and at any subsequent agent-runtime invocation of the Prioritiser role.

## Out of scope

Explicit. Deferred to subsequent Step commit sessions or to the Phase 2 strategic-mode opening proper:

- **D93 supersession.** The build-methodology versus product-methodology distinction the Step 1 conversation surfaced. Continues to defer.
- **Four-functions framework expansion.** `charter/product-methodology.md` v2 with the four-functions-plus-user-authored-methodologies expansion. Continues to defer.
- **Captures portfolio reactivation.** The eleven-use-case portfolio in `log/captures.md` currently marked "historical context only" moves to load-bearing. Continues to defer.
- **Product-methodology.md v2 primitives-versus-templates principle.** Continues to defer.
- **Methodology role discipline-extension workitem (now at three-instance evidence base).** Phase 2 methodology workitem candidate per the dogfooding-evidence records at Steps 1, 2, and 3. The candidate now spans ProblemFramer plus Disaggregator plus Prioritiser. Defers to Phase 2 strategic-mode opening or earlier methodology session if scoped.
- **Stale `current-package.md` line 5 header.** Carryover from Step 1 commit; not in scope here.
- **Step 4 work.** Plan. Conversation runs at Claude.ai as the next strategic block in the arc; commit session lands its artefacts to `charter/phase-2-design-7step.md` as a Step 4 section. The pre-conversation brief at `briefs/phase-2/design-7step-step-4.md` should land before the Step 4 conversation opens, continuing the briefs/ discipline restoration test from Step 3.

## Session log entry instruction

Append `## Phase 2 design 7-Step Step 3 commit` (or the naming convention pre-write reconciliation surfaces) to `log/sessions.md`, matching the Step 2 commit entry's structure. Include `roles:` tag at line two (default suggestion: `analyst, PM, technical writer`; operator confirms specifics). Set `mode: strategic`. Two commits. Four reflection prompts answered as substantive prose where warranted. Three methodology lines at close. Close marker handing off to Step 4 (Plan) as the next strategic-mode block.

---

Pre-write reconciliation is load-bearing; content payloads are inline per the Step 1 correction; current-package.md update uses append-only language per the Step 2 correction; brief preservation continues at `briefs/phase-2/`.
