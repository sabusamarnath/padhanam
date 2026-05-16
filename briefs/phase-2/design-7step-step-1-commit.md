# Phase 2 design — 7-Step arc — Step 1 commit session

## Identification

Mode: strategic (charter commit; no code changes; lint and tests not required at this session).
Block: Phase 2 design — McKinsey 7-Step arc — Step 1 (Define the problem) commit landing.
Branch: operator-selected at session open.

## Goal at session close

Three artefacts land at a new charter file plus the current-package transition plus the session log entry. Specifically:

- New file `charter/phase-2-design-7step.md` exists carrying: an arc-introduction header, Step 1's problem statement (problem paragraph plus two context paragraphs), Step 1's dogfooding-evidence record, Step 1's initial disaggregation carry-forward, and open questions for Steps 2 and 3.
- `charter/current-package.md` reflects Phase 2 design 7-Step arc Step 1 closed; Step 2 (Disaggregation) is the next strategic-mode block.
- Brief preservation: the originating Claude.ai conversation prompt (the prompt at the top of the Step 1 conversation) plus this commit-session prompt both preserved verbatim per D43, at the path convention Claude Code reconciles at pre-write.
- Session log entry appended to `log/sessions.md` per the established format with `roles:` tag and reflection density appropriate to strategic-mode work.

## Context to read first

In order. Read in ranges where files exceed 200 lines.

1. `charter/current-package.md` (top section). State at the close of the pre-Phase-2 architecture synthesis and methodology refinement block; what the file currently names as the next strategic-mode block.
2. `charter/decisions.md`. Specifically D77, D78, D85, D93. The Step 1 problem statement and dogfooding-evidence record reference these.
3. `charter/principles.md`. User safety section and the Coach consistency commitment.
4. `charter/methodology.md` v3. Hypothesis and iteration sub-section, Charter structure sub-section.
5. `charter/product-methodology.md`. Four professional functions framework; methodology-embedded commitment.
6. `charter/p12-phase-2-inputs.md`. Phase 2 strategic-tree input observations.
7. `log/sessions.md`. Latest entries to confirm the pre-Phase-2 architecture and methodology block closed cleanly and to confirm session/block naming conventions for the new entry.
8. `log/captures.md`. The mass-market-UX-as-Phase-2-commitment entry; this commit session does not edit captures, but reads it for context.

## Pre-write reconciliation

Before writing any commit, reconcile assumptions against current state:

1. **D-entry count and latest entry.** This session does not land new D-entries (drift items flagged at Step 1 conversation defer to a subsequent Step's commit session per Out of scope below). Confirm the latest D-entry remains the one named at `log/sessions.md`'s pre-Phase-2 architecture and methodology block close; do not introduce D-entry references in the new file beyond the existing D-entries the Step 1 deliverables already cite (D14, D77, D78, D81, D82, D85, D87, D93).
2. **Current-package.md state.** Read the file and confirm what it currently names as the next strategic-mode block. The transition this session lands should slot Phase 2 design 7-Step arc Step 1 as closed and Step 2 as next, in supersession of the current "next block" naming if the current text reads "Phase 2 packaging" (which the pre-Phase-2 block's session log indicated). Adjust the edit precisely to the current text.
3. **Brief preservation path.** Confirm whether the briefs/ convention applies to strategic-mode blocks (not numbered build sessions). Look at how the pre-Phase-2 architecture synthesis and methodology refinement block preserved its brief, and mirror that convention. If briefs/ does not apply, use the same path the prior strategic block used.
4. **Session log entry shape.** Strategic-mode entries follow shorter reflection density per the methodology v3 Reflection density commitment. Match the shape of the most recent strategic-mode block's log entry rather than a build-session entry.

Surface any reconciliation drift to the operator before commit 1. The Step 1 conversation produced specific paste-ready content; the commit session lands that content faithfully, but path conventions and current-package text need verification, not invention.

## Commits

### Commit 1: Step 1 artefacts land at new charter file plus current-package transition plus brief preservation

Conventional commit message: `docs(charter): phase 2 design — 7-step arc Step 1 problem statement, dogfooding evidence, initial disaggregation`

Body of commit: three-paragraph summary naming what the file lands (problem statement plus context paragraphs; dogfooding-evidence record; initial disaggregation carry-forward), the placement rationale (charter-grade per Decision 1 of the Step 1 conversation, binding for Phase 2 LVT structure that Step 3 produces), and the no-D-entries-this-session framing (deferred items named in Out of scope).

File contents for `charter/phase-2-design-7step.md`:

```markdown
# Phase 2 design — McKinsey 7-Step arc

Strategic-mode arc applying the McKinsey 7-Step problem-solving methodology to Phase 2's strategic shape. Charter-grade placement per the arc-opening conversation's Decision 1: binding specification; Step 3's prioritised bets become Phase 2 LVT structure when the v6 roadmap entry lands per D44. Refreshes at phase audits per D45.

Blank-sheet discipline applies within the bet's success criteria per the arc-opening conversation's Decision 2. The bet's core claims (procurement-grade architecture, methodology-as-product, learning sprint demonstration) hold. Phase 2-specific commitments (D93 framing, three-wave sequencing, the mass-market-UX commitment in `log/captures.md`) are open to re-derivation through the arc.

Posture 1.5: structural dogfooding of the McKinsey 7-Step methodology template authored at S26b per D85, structured per D81's multi-role aggregate v2 shape with the override-mode space committed at D87. The arc reads the role specifications and holds the discipline manually; the methodology aggregate is not invoked through the agent runtime at this arc's posture.

## Step 1: Define the problem

### Problem statement

[problem paragraph verbatim from the Step 1 conversation close]

### Context: the user's current substitutes

[context paragraph verbatim]

### Context: the CoS analogue and the population gap

[context paragraph verbatim]

### Dogfooding-evidence record

[record prose verbatim, four paragraphs: what the template informed, where the template's scope did not cover the work, what this surfaces for Phase 2 methodology work, what this tells us about the bet's claim]

### Initial disaggregation (carry-forward to Step 2)

[paragraph verbatim plus the Step 2 disaggregator handoff note]

### Open questions for Steps 2 and 3

[two-paragraph carry-forward verbatim]

### Step 1 close

Step 1 closes with the problem statement converging through five ProblemFramer sub-prompts (Who has the problem, What is the problem, What gets worse if the problem persists, How would success be measured, What is the problem NOT). The problem statement above survives the self-challenges applied at each prompt. Step 2 (Disaggregation) opens with the initial disaggregation candidates plus the two open questions named above.
```

Update `charter/current-package.md` to insert a paragraph after the pre-Phase-2 architecture-and-methodology close paragraph and rewrite the next-block paragraph: Phase 2 design 7-Step arc Step 1 closed at this session; Step 2 (Disaggregation) is the next strategic-mode block; the arc's full close produces the Phase 2 LVT structure that lands as v6 roadmap entry per D44 plus the Phase 2 PRD per D43.

Preserve the Step 1 conversation prompt verbatim at the path convention pre-write reconciliation confirms. Preserve this commit-session prompt verbatim at the same path convention.

### Commit 2: Session log entry

Conventional commit message: `docs(log): phase 2 design 7-step arc Step 1 commit session log entry`

Append an entry to `log/sessions.md` matching the most recent strategic-mode block's shape per pre-write reconciliation item 4. The entry names the block as Phase 2 design 7-Step arc Step 1 commit session, sets `roles: analyst, PM, technical writer` (operator confirms or amends), `mode: strategic`, and follows the established structure (Produced, Decisions, Tests, Enforcement, Reflection).

Reflection prompts answered per the prompts below.

## Acceptance criteria

1. New file `charter/phase-2-design-7step.md` exists carrying the arc-introduction header, Step 1 sections per the file content specified above, and a Step 1 close paragraph. Content verbatim from the Step 1 conversation deliverable, no in-line editing.
2. `charter/current-package.md` reflects Step 1 closed and Step 2 next. The text inserts cleanly into the file's existing structure without breaking adjacent paragraphs.
3. Step 1 conversation prompt preserved verbatim at the path the pre-write reconciliation confirms.
4. This commit-session prompt preserved verbatim at the same path.
5. `log/sessions.md` carries a new entry for this commit session, matching the most recent strategic-mode entry's shape, with the four reflection prompts answered.
6. Working tree clean at end of session.
7. No new D-entries land at this session; no edits to `charter/decisions.md`, `charter/deferred-decisions.md`, `charter/principles.md`, `charter/methodology.md`, `charter/product-methodology.md`, or `log/captures.md`. Drift items deferred per Out of scope below.

## Reflection prompts for the session log entry

1. **Pre-write reconciliation outcome.** Did the four reconciliation items surface drift, and if so, where? Particularly: did the brief preservation path require deviation from build-session convention, and did `charter/current-package.md`'s current text require precise replacement language or accommodate the planned edit cleanly?
2. **Step 1 close as Phase 2 design entry.** What does landing Step 1 charter-grade signal forward for Steps 2-7? Specifically, does the charter-grade placement create commitment pressure on subsequent steps to converge to landing rather than to defer open questions to later phases?
3. **Methodology dogfooding-evidence record as a Phase 1 deliverable.** The bet's methodology-embedding claim now has its first structural-level evidence in committed charter form. What does this position differently for Phase 2 packaging? Specifically, does it strengthen the case for landing the Phase 2 methodology-extension workitem (the McKinsey 7-Step ProblemFramer role expansion the dogfooding-evidence record surfaces) as an early Phase 2 package?
4. **Blank-sheet discipline scope verdict.** Decision 2 of the Step 1 conversation chose blank-sheet within the bet. The Step 1 deliverables surfaced drift relative to D93's methodology-as-product framing and the four-functions framework. Did the blank-sheet discipline scope hold, or did Step 1 surface evidence that the scope should expand at Step 2 or Step 3?

## Out of scope

Explicit. Deferred to subsequent Step commit sessions or to the Phase 2 strategic-mode opening proper:

- **D93 supersession.** The build-methodology versus product-methodology distinction the Step 1 conversation surfaced. Lands at the Step 3 commit session (when prioritised bets become Phase 2 LVT structure) or earlier if the Step 2 disaggregation forces it.
- **Four-functions framework expansion.** `charter/product-methodology.md` v2 with the four-functions-plus-user-authored-methodologies expansion. Lands at the Phase 2 strategic-mode opening proper or at Step 3 commit, whichever the operator selects.
- **Captures portfolio reactivation.** The eleven-use-case portfolio in `log/captures.md` currently marked "historical context only" moves to load-bearing. Either a status update entry or a new captures entry that supersedes the prior framing. Lands at the Phase 2 strategic-mode opening proper.
- **Phase 2 methodology-extension workitem.** The McKinsey 7-Step ProblemFramer role expansion the dogfooding-evidence record surfaces. Lands as a deferred-decisions entry at the Phase 2 strategic-mode opening proper.
- **Step 2 work.** Disaggregation. Conversation runs at Claude.ai as the next strategic block in the arc; commit session lands its artefacts to `charter/phase-2-design-7step.md` as a Step 2 section.

## Session log entry instruction

Append `## [Block name] — Phase 2 design 7-Step Step 1 commit` (or the naming convention the pre-write reconciliation surfaces) to `log/sessions.md`, matching the most recent strategic-mode block's structure. Include the `roles:` tag at line two (operator confirms specifics; default suggestion: `analyst, PM, technical writer`). Set `mode: strategic`. Answer the four reflection prompts above as the entry's main content. Brief in shape per strategic-mode reflection density; substantive on the four prompts where prose is warranted.

---

The pre-write reconciliation step is load-bearing; the prompt's content is paste-ready, but the path conventions and current-package text need verification, not assumption.
