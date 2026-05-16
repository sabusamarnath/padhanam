# Phase 2 design — 7-Step arc — Step 2 commit session

## Identification

Mode: strategic (charter commit; no code changes; lint and tests not required at this session).
Block: Phase 2 design — McKinsey 7-Step arc — Step 2 (Disaggregate) commit landing.
Branch: operator-selected at session open.

## Goal at session close

- `charter/phase-2-design-7step.md` carries a new "## Step 2: Disaggregate" section appended after the Step 1 close paragraph, with seven sub-sections (opener, issue tree, cross-cutting disciplines, self-challenge, dogfooding-evidence record, carry-forward to Step 3, Step 2 close).
- `charter/current-package.md` close marker reflects Step 2 closed; Step 3 (Prioritisation) is the next strategic-mode block.
- `briefs/phase-2/design-7step-step-2.md` exists as a synthetic retrospective brief, flagged in the file itself as retrospective rather than pre-conversation.
- `briefs/phase-2/design-7step-step-2-commit.md` preserves this commit-session prompt verbatim.
- Session log entry appended to `log/sessions.md` matching the most recent strategic-mode entry's shape (the Step 1 commit entry).

## Context to read first

In order. Read in ranges where files exceed 200 lines.

1. `charter/phase-2-design-7step.md`. The Step 1 section in full. Confirm the append point: immediately after the Step 1 close paragraph.
2. `charter/current-package.md` (top section). Confirm the current close marker text after the Step 1 commit. The edit at this session updates it from "Step 1 closed; Step 2 next" framing to "Step 2 closed; Step 3 next" framing.
3. `log/sessions.md`. Latest entry is the Step 1 commit; match its shape for the Step 2 commit entry.
4. `briefs/phase-2/design-7step-step-1.md` and `briefs/phase-2/design-7step-step-1-commit.md`. Precedent for the brief shape and the commit-prompt-brief shape.
5. `briefs/p8/mckinsey-7-step.md`. The Disaggregator role's authored specification, cited in the Step 2 dogfooding-evidence record.

## Pre-write reconciliation

1. **D-entry count.** Latest entry remains D113. No new D-entries this session. The dogfooding-evidence record cites D82 and D85; both exist as summary lines in active `charter/decisions.md` with full content in `docs/archive/decisions/phase-1.md`.
2. **Current-package.md current text.** Read the file and confirm the close marker text the Step 1 commit landed. Edit precisely to that text; do not assume the wording.
3. **Append point at `charter/phase-2-design-7step.md`.** Confirm the Step 1 close paragraph is the file's current terminal content; append the Step 2 section after it without modifying Step 1's content.
4. **Brief preservation directory.** `briefs/phase-2/` exists from Step 1 commit. New files land there.
5. **Synthetic-retrospective-brief framing.** This is a new pattern at the project; no precedent in `briefs/p8/` for retrospective briefs. The brief itself flags the pattern. Surface the pattern in the session log entry's reflection prompt 1 as methodology-candidate signal.
6. **Carryover from Step 1 commit.** The stale "P11 framed; S39 next" header at `charter/current-package.md` line 5 is pre-existing structural drift; out of scope at this session per AC 7.

## Commits

### Commit 1: Step 2 artefacts land at charter file plus current-package transition plus brief preservation

Conventional commit message: `docs(charter): phase 2 design — 7-step arc Step 2 disaggregation issue tree, dogfooding evidence, carry-forward`

Three-paragraph commit body. Paragraph 1: names what the new section lands (issue tree at six branches × five sub-branches; two cross-cutting disciplines; dogfooding-evidence record; carry-forward to Step 3). Paragraph 2: names the two structural insights that surfaced during the Step 2 conversation (Branch 6 addition for platform-to-user signal fidelity; four-stage temporal lifecycle elevation to cross-cutting discipline). Paragraph 3: notes the synthetic-retrospective-brief pattern landing at this session as honest framing for the briefs/ discipline restoration begun at Step 1.

**Append the following content to `charter/phase-2-design-7step.md` as a new "## Step 2: Disaggregate" section, placed immediately after the Step 1 close paragraph. Content verbatim, no in-line editing:**

```markdown
## Step 2: Disaggregate

Step 2 applied the McKinsey 7-Step Disaggregator role's discipline to Step 1's sharpened problem statement. The role's function-focused system_prompt commits the role to "decompose problems into structured component trees... receive a sharpened problem from the ProblemFramer; produce a structured decomposition where each branch represents a distinct sub-problem and branches together are collectively exhaustive." The McKinsey override layered "Apply MECE (Mutually Exclusive, Collectively Exhaustive) decomposition; produce an issue tree." Posture 1.5 dogfooding continued from Step 1: the conversation read the role's specification and held the discipline manually without invoking the agent runtime.

Two structural insights emerged during the disaggregation conversation that the Disaggregator role's authored system_prompt does not encode. First, the user-faking-it problem (saying yes when meaning no; status veracity; ambivalence under load) surfaced a sub-problem the initial five-branch shape did not accommodate; the tree gained Branch 6 (Signal fidelity and methodology-fit) to host the platform-to-user signal-verification work distinct from Branch 5 (user-to-platform trust). Second, the rhythm-and-key-change framing introduced a four-stage temporal lifecycle (find rhythm, settle in, watch for key change, adapt) that elevated to cross-cutting discipline applying at every branch, not just at methodology-fit. The Disaggregator role's MECE override produces snapshot tree shape; the temporal lifecycle adds dynamic-state shape that overlays the snapshot.

### Issue tree

**Branch 1: Portfolio existence as a unified picture.**

- 1.1 Substrate connection. How items move from where they live (calendar, email, notes, trackers, head) into the platform's portfolio. Substrate type axis and integration function axis both held per Step 1.
- 1.2 Item identity reconciliation. The same item surfacing across substrates must consolidate to one portfolio entity rather than counted multiple times.
- 1.3 State persistence. The integrated portfolio survives across sessions; the user does not rebuild context each time.
- 1.4 Personal-versus-professional treatment. Personal items receive the same lifecycle dignity as professional items rather than being triaged out by default.
- 1.5 User-authored items. Items the user types directly into the platform; different ownership and lifecycle from substrate-derived items.

**Branch 2: Pace calibration for each item.**

- 2.1 Methodology library. The set of methodologies available for application. Attribution; authoring quality; the primitives-versus-templates discipline.
- 2.2 Methodology-to-item binding. Which methodology applies to which item at which moment; per-item, per-methodology mappings.
- 2.3 Pace inference per item. Given item plus methodology, what pace does the methodology imply (urgency, importance, dependencies, energy, value-of-effort).
- 2.4 User-authored methodology surface. The user authors and adapts methodologies; the authorship interface; methodology validation.
- 2.5 Calibration override mechanics. When the platform's calibration is wrong; per-item, per-methodology, global override paths.

**Branch 3: Action at the right moment.**

- 3.1 Surfacing mechanics. When and how the platform brings items to user attention; channels, frequency, urgency calibration of surfacing itself.
- 3.2 Drop-decision support. Platform-suggested drops; user-initiated drops; the conversation around dropping.
- 3.3 Defer mechanics. Deferral with reason, trigger, or review prompt; deferred state visibility.
- 3.4 Delegation support. Items handed to other people or systems; delegated-state tracking; follow-up surface.
- 3.5 Consent granularity for platform actions. Per D82's intelligence-layer commitment; per-action versus per-class versus standing-consent-with-review.

**Branch 4: Feedback on whether calibration is working.**

- 4.1 Mirror surface. On-demand retrospective on time spent versus value produced; format, depth, time-range, drill-down.
- 4.2 Goal-state tracking. User-stated goals over time; goal authorship; goal revision; goal-to-item linking.
- 4.3 Value-versus-time accounting. Aggregating time spent against value produced; value defined per methodology per item.
- 4.4 Pattern surfacing. Hot and cold spots across time; recurring stalls; types of items that consistently drop.
- 4.5 Feedback-to-platform. User shapes what feedback they receive; mirror customisation; pattern-surfacing preferences.

**Branch 5: Trust substrate for offloading.**

- 5.1 Audit visibility. What the platform did, when, why, with what inputs; user-readable; tied to the Phase 1 audit substrate.
- 5.2 Source attribution. Recommendations cite the user-authored content, methodology, or prior decisions that informed them.
- 5.3 Cost transparency. Per-action cost (LLM, computational, attention); aggregate cost over time.
- 5.4 Intelligence-layer guardrails. D82 commitments visible at user surface; no autonomous action on consequential matters; explicit consent; reversibility.
- 5.5 Trust history. Trust-building moments; trust-break events; trust recovery; visible to the user.

**Branch 6: Signal fidelity and methodology-fit.**

- 6.1 Signal verification. When the platform verifies a user signal versus accepts at face value; verification mechanics with low user friction.
- 6.2 Compliance-signal detection. Yes-when-they-mean-no; agreement under fatigue or social pattern; detection without being a nag.
- 6.3 Status veracity. Item marked done that may not actually be done; lower-pressure status options like stalled, uncertain, partial.
- 6.4 Methodology-fit lifecycle. The four-stage lifecycle applied to methodology specifically: cold-start fit, rhythm maintenance, drift and key-change detection, transition support.
- 6.5 Correction mechanics. User revises a past signal without friction; preserves history; does not punish the user for being human under load.

### Cross-cutting disciplines

Two disciplines apply at every sub-branch:

**Detection.** Each sub-branch needs internal feedback on whether the sub-branch is working: observed-behaviour-versus-stated-intent at every interface where the platform consumes user signal or produces user-facing output.

**Find rhythm, settle in, watch, adapt.** The four-stage temporal lifecycle. Each sub-branch behaves differently at each stage. Conservative defaults at find-rhythm; minimal intervention at settle-in; continuous background watch; supportive transition at adapt; then return to find-rhythm for the new state.

### Self-challenge

The tree holds MECE at sub-branch level. Each branch's five sub-branches are mutually exclusive (distinct work units; no overlap within the branch). Cross-branch overlap testing identified the closest pairs as 4.5 (feedback-to-platform) and 6.5 (correction mechanics); 1.5 (user-authored items) and 2.4 (user-authored methodology); these are distinct work units despite sharing user-authorship vocabulary.

Items deliberately not in the tree: agent runtime substrate; mass-market UX as design constraint; user onboarding as a Phase 2 deliverable concern. Solution territory remains excluded by the Disaggregator role's discipline. The bet's case-study reader audience is also absent because Phase 2's user is the busy professional running a Private Assistant per Step 1.

Thirty sub-problems at this granularity is workable for impact-tractability scoring at Step 3.

### Dogfooding-evidence record

The McKinsey 7-Step Disaggregator role authored at S26b per D85 carries a function-focused system_prompt committing the role to producing MECE issue trees. The McKinsey override added MECE plus issue-tree shape. Posture 1.5 structural dogfooding without agent runtime continued from Step 1.

What the template informed. The "you do not solve sub-problems; you structure them" discipline held cleanly. The conversation resisted moving into prioritisation language even when the operator's framing suggested implications (key-change as a transition state; the seven framework examples). The MECE override gave the explicit structural test that the conversation applied at every branch addition. Branch 6 was added because Branch 5 as user-trust did not accommodate platform-to-user signal fidelity; the operator's three questions surfaced the structural gap and the discipline produced the addition. The issue-tree shape held: hierarchical, two-level decomposition, thirty terminal sub-problems.

Where the template's scope did not cover the work. Two extensions surfaced during the conversation that the McKinsey 7-Step Disaggregator role does not encode. First, the rhythm-and-key-change framing introduced a temporal lifecycle as cross-cutting discipline; the McKinsey override's MECE produces snapshot tree shape, not temporal-mode shape. The operator's framing combined with the template's MECE produced a richer disaggregation than either alone. Second, the substrate-integration cut question called for holding orthogonal dimensions at sub-branch level rather than collapsing to one; the template's MECE override does not specify how to handle orthogonal dimensions within a sub-problem.

What this surfaces for Phase 2 methodology work. The Disaggregator role would benefit from a temporal-lifecycle discipline addition. Issue trees that ignore temporal dynamics produce static decomposition where the underlying problem has stage-dependent behaviour; the Disaggregator's output is then materially weaker than the problem deserves. Two candidate landing surfaces: addition to the Disaggregator role's system_prompt encoding "consider whether the problem has temporal-state structure and apply lifecycle discipline as cross-cutting overlay where it does," or a Phase 2 skills-per-role surface (deferred per the brief at briefs/p8/mckinsey-7-step.md) that bundles temporal-lifecycle and orthogonal-dimension-handling as Disaggregator skills.

What this tells us about the bet's claim. The methodology authoring continues to earn its place at structural level. The Disaggregator role was extensible to accommodate operator insights (rhythm/key-change, faking-it problem, methodology adaptation) without breaking; the role's structural discipline did not prevent the conversation from going where the problem required. The extensibility itself is signal worth recording. Agent-runtime evidence remains untested at Step 2; Phase 2 UX surface for methodology adoption plus agent runtime exercising the Disaggregator end-to-end would close the higher bar.

### Carry-forward to Step 3

Four open questions land at Step 3 (Prioritisation):

1. Dogfooding-only versus broader-population framing. From Step 1's carry-forward, now sharper. Step 3's prioritiser ranks sub-problems by impact and tractability; the population scope materially changes impact. Operator-only dogfooding narrows impact assessment to one user; broader-population widens it. The Phase 2 deliverable strategy depends on this choice.

2. Substrate-type × integration-function matrix at sub-branch 1.1. Both axes carry forward per Step 2. The Prioritiser decides which cells (calendar-read, email-write, notes-observe, etc.) land top-quartile. The substrate axis differences (privacy, ownership, access patterns) and the function axis differences (consent class, technical complexity) both inform impact-tractability scoring.

3. Dependency ordering across branches. Branch 2 (calibration) depends on Branch 1 (portfolio existing). Branch 3 (action) depends on Branch 2. Branch 4 (feedback) depends on Branches 1-3. Branch 6 (signal fidelity) depends on user signal sources that exist when other branches operate. The Prioritiser must respect dependency or face buildable-but-unusable sub-deliverables. Branch 5 (trust) is foundational and partially independent.

4. Lifecycle-stage prioritisation. The four-stage discipline applies at every branch. Step 3 must decide whether Phase 2 ships find-rhythm-plus-settle-in stages across all branches first (with watch and adapt later), or ships full-lifecycle support for fewer branches first. Different commercial test conditions for each choice.

### Step 2 close

Step 2 closes with the issue tree at six branches × five sub-branches, plus two cross-cutting disciplines (detection and the four-stage temporal lifecycle). The tree survived MECE self-challenge at sub-branch level. The Disaggregator role's discipline produced a usable tree that accommodated operator-driven structural insights without breaking. Step 3 (Prioritisation) opens at Claude.ai with the four open questions above as inputs plus the full thirty-sub-problem set as the impact-tractability scoring surface.
```

**Edit `charter/current-package.md` close marker.** The Step 1 commit landed a paragraph reflecting Step 1 closed and Step 2 next. Replace the "Step 1 closed; Step 2 next" framing with "Step 2 closed; Step 3 next." Use the precise current wording of that paragraph as the find target. The new paragraph reads (paraphrase to match file's tone):

> Phase 2 design 7-Step arc Step 2 closed at [date of commit]. The Step 2 section at `charter/phase-2-design-7step.md` carries the disaggregated issue tree (six branches at five sub-branches each), two cross-cutting disciplines (detection plus the four-stage temporal lifecycle of find-rhythm, settle-in, watch, adapt), the Step 2 dogfooding-evidence record, and four open questions carried forward. The next strategic-mode block is Step 3 (Prioritisation), which ranks the thirty sub-problems by impact-tractability and lands the prioritised set as input to Step 4 (workplan).

**Create `briefs/phase-2/design-7step-step-2.md` with the following content, verbatim:**

```markdown
# Phase 2 design — McKinsey 7-Step — Step 2 (Disaggregate)

**This brief is a synthetic retrospective construction.** Drafted at the Step 2 commit session rather than before the Step 2 conversation. Unlike the Step 1 brief at `briefs/phase-2/design-7step-step-1.md`, which was a formal opening prompt the Claude.ai conversation read before substantive work began, Step 2 transitioned from Step 1 close to Step 2 open within the same Claude.ai conversation. No separate opening prompt existed. To honour the briefs/ preservation discipline restored at Step 1 (after a three-block lapse since P9 open), this retrospective brief documents Step 2's intent, inputs, and discipline. The synthetic nature is flagged here as honest framing; future Step briefs should be authored before the corresponding Claude.ai conversation opens to avoid the retrospective shape.

## Intent

Apply Step 2 of the McKinsey 7-Step Framework (Disaggregation via the Disaggregator role authored at S26b per D85) to Step 1's sharpened problem statement, producing a MECE issue tree with branches and sub-branches at granularity workable for Step 3's impact-tractability scoring. Posture 1.5: structural dogfooding without agent runtime dependency. The conversation reads the Disaggregator role's specification and holds the discipline manually.

## Inputs

The three Step 1 artefacts at `charter/phase-2-design-7step.md` Step 1 section:

1. The sharpened problem statement (problem paragraph plus two context paragraphs)
2. The initial-disaggregation paragraph (seven sub-problem candidates) plus Step 2 disaggregator handoff note
3. The two open questions for Steps 2 and 3 (substrate-integration cut at Step 2; population scope at Step 3)

Plus the McKinsey 7-Step methodology template at `briefs/p8/mckinsey-7-step.md`, specifically the Disaggregator role section.

## Discipline

The Disaggregator role's system_prompt: "You decompose problems into structured component trees. Your job: receive a sharpened problem from the ProblemFramer; produce a structured decomposition where each branch represents a distinct sub-problem and branches together are collectively exhaustive. The decomposition is the input the Prioritiser uses to rank tractability. You do not solve sub-problems; you structure them."

The McKinsey override: "Apply MECE (Mutually Exclusive, Collectively Exhaustive) decomposition; produce an issue tree."

The conversation iterates through structural refinements as operator insights surface; the assistant resists moving into solution territory and resists pre-emptive prioritisation; the issue tree converges through multiple cycles. Blank-sheet discipline within the bet's success criteria continues per Step 1's Decision 2.

## Dogfooding-evidence record discipline

Same shape as Step 1's dogfooding-evidence record. The assistant notes throughout the conversation how the Disaggregator role's content informed the work; at conversation close, drafts the dogfooding-evidence record as substantive prose against the procurement-grade evidence question: did Padhanam's own methodology authoring (the McKinsey 7-Step Disaggregator role) produce content that worked at a real Phase 2 disaggregation problem, or did the conversation operate on general McKinsey framework knowledge irrespective of what was authored on the control plane?

## Conversation closing

At Step 2 close, the assistant produces:

1. The disaggregated issue tree (branches plus sub-branches with one-sentence definitions)
2. Cross-cutting disciplines section if any surfaced
3. Self-challenge summary (MECE check; exclusions; altitude check)
4. The dogfooding-evidence record (substantive prose)
5. Carry-forward to Step 3 (open questions for prioritisation)
6. Step 2 close paragraph

Plus a brief paragraph naming the next session in the arc (Step 3 Prioritisation) and any open questions Step 2 surfaced for Step 3 specifically.

The drafted artefacts get committed via a subsequent short Claude Code session whose brief takes the artefacts as paste-ready content inline (per the placeholder-versus-content-payload methodology miss flagged at Step 1).
```

**Create `briefs/phase-2/design-7step-step-2-commit.md`** preserving this commit-session prompt verbatim. The entire prompt body from "# Phase 2 design — 7-Step arc — Step 2 commit session" through the session log entry instruction.

### Commit 2: Session log entry

Conventional commit message: `docs(log): phase 2 design 7-step arc Step 2 commit session log entry`

Append an entry to `log/sessions.md` matching the Step 1 commit entry's shape per pre-write reconciliation item 3. Set `roles: analyst, PM, technical writer` (operator confirms or amends). Set `mode: strategic`. Answer the four reflection prompts below as the entry's main content. Brief in shape per strategic-mode reflection density; substantive on the reflection prompts where prose is warranted.

## Acceptance criteria

1. New "## Step 2: Disaggregate" section exists at `charter/phase-2-design-7step.md`, appended after the Step 1 close paragraph, carrying the seven sub-sections specified (opener, issue tree at six branches × five sub-branches, cross-cutting disciplines, self-challenge, dogfooding-evidence record, carry-forward to Step 3, Step 2 close).
2. `charter/current-package.md` close marker reflects Step 2 closed and Step 3 next, with the new paragraph integrating cleanly with adjacent file content.
3. `briefs/phase-2/design-7step-step-2.md` exists as a synthetic retrospective brief, with the retrospective-framing flag at the top of the file.
4. `briefs/phase-2/design-7step-step-2-commit.md` exists and preserves this commit-session prompt verbatim.
5. `log/sessions.md` carries a new entry matching the Step 1 commit entry's shape, with the four reflection prompts answered.
6. Working tree clean at end of session.
7. No new D-entries land; no edits to `charter/decisions.md`, `charter/deferred-decisions.md`, `charter/principles.md`, `charter/methodology.md`, `charter/product-methodology.md`, `charter/architecture.md`, or `log/captures.md`. Drift items defer per Out of scope below.

## Reflection prompts for the session log entry

1. **Pre-write reconciliation outcome.** Did the six reconciliation items surface drift, and where? Particularly: did `charter/current-package.md`'s current text require precise replacement language; did the synthetic-retrospective-brief pattern introduce any structural tension with existing briefs/ conventions; did the stale "P11 framed; S39 next" header drift further or stay stable.

2. **The two structural insights from Step 2.** Branch 6 addition (signal fidelity and methodology-fit as platform-to-user direction) and four-stage temporal lifecycle elevation (find rhythm, settle in, watch, adapt) as cross-cutting discipline. What do these signal for Phase 2 methodology work? Specifically, do they strengthen the case for landing the Disaggregator role's temporal-lifecycle extension as an early Phase 2 methodology workitem candidate?

3. **Methodology-fit lifecycle sub-branch cross-branch implications.** The sub-branch surfaces dependencies on Branch 1 (portfolio composition shifts at key-change moments), Branch 4 (mirror format differs in rhythm versus key-change states), and Branch 5 (trust required to ask "is this a key-change moment"). Should these cross-branch dependencies land as explicit cross-references in the issue tree at a future Step's refinement, or stay implicit until Step 3's prioritisation surfaces them?

4. **Synthetic-retrospective-brief pattern.** First instance at this session. Recurrence test at Step 3: does Step 3 open with a formal pre-conversation brief at Claude.ai (restoring full briefs/ discipline before the conversation begins), or does Step 3 also transition mid-conversation and need a synthetic retrospective at its commit session? If the latter, the pattern lifts to second instance and promotes accordingly.

## Out of scope

Explicit. Deferred to subsequent Step commit sessions or to the Phase 2 strategic-mode opening proper:

- **D93 supersession.** The build-methodology versus product-methodology distinction the Step 1 conversation surfaced. Continues to defer; lands at Step 3 commit or Phase 2 strategic-mode opening.
- **Four-functions framework expansion.** `charter/product-methodology.md` v2 with the four-functions-plus-user-authored-methodologies expansion. Continues to defer.
- **Captures portfolio reactivation.** The eleven-use-case portfolio in `log/captures.md` currently marked "historical context only" moves to load-bearing. Continues to defer.
- **Product-methodology.md v2 primitives-versus-templates principle.** Continues to defer.
- **Disaggregator role temporal-lifecycle extension.** Phase 2 methodology workitem candidate per the Step 2 dogfooding-evidence record. Defers to Phase 2 strategic-mode opening or earlier methodology session if scoped.
- **Stale `current-package.md` line 5 header.** Carryover from Step 1 commit; not in scope here.
- **Step 3 work.** Prioritisation. Conversation runs at Claude.ai as the next strategic block in the arc; commit session lands its artefacts to `charter/phase-2-design-7step.md` as a Step 3 section. The pre-conversation brief at `briefs/phase-2/design-7step-step-3.md` should land before the Step 3 conversation opens, restoring full briefs/ discipline.

## Session log entry instruction

Append `## Phase 2 design 7-Step Step 2 commit` (or the naming convention pre-write reconciliation surfaces) to `log/sessions.md`, matching the Step 1 commit entry's structure. Include `roles:` tag at line two (default suggestion: `analyst, PM, technical writer`; operator confirms specifics). Set `mode: strategic`. Two commits. Reflection prompts answered as substantive prose where warranted; brief otherwise.

---

Pre-write reconciliation is load-bearing; content payloads are inline per the Step 1 correction; brief preservation paths confirmed at `briefs/phase-2/`.
