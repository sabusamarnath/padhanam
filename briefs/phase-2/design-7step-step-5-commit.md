# Phase 2 design — 7-Step arc — Step 5 commit session

## Identification

Mode: strategic (charter commit; no code changes; lint and tests not required at this session).
Block: Phase 2 design — McKinsey 7-Step arc — Step 5 (Analyse) commit landing.
Branch: operator-selected at session open.

## Goal at session close

- `charter/phase-2-design-7step.md` carries a new `## Step 5: Analyse` section appended after the Step 4 close paragraph. The new section covers: opener (three paragraphs framing Step 5 work); Decision 1 (senior-leader ICP commitment landing surface); Pass 1 per-sub-problem analyses (eleven sub-problems across six branches); Pass 2 architectural patterns surfaced (five patterns; three named in brief, two candidates emerged); Pass 2 work-stream 3 sequencing analysis (foundational versus refinement; dependency chains; substrate-completion thresholds; four sequencing waves); Pass 2 work-stream 4 clustering analysis (fifty-two Phase 2-B candidates across ten clusters; four Phase 2-B sequencing waves; Tier 4 sub-problem activation map); Pass 3 close dogfooding-evidence record (five reflection prompts; three methodology lines worth observing); Pass 3 close carry-forward to Step 6 (sixteen open questions grouped by source); Step 5 close paragraph.
- `charter/phase-2-user-segment.md` exists as a new charter-grade reference file carrying the senior-leader ICP commitment per Step 5 Decision 1. Three-population segment definition (established-firm senior leaders; Series A/B scale-up founders; early-stage founders); vertical-wedge candidates for Phase 3 sequencing analysis (financial services, legal, healthcare, product-leadership-vertical); Phase 2-A substrate priorities derived from segment (dual-provider parity, messaging dual-provider, work-app cells deferred); evolution discipline.
- `charter/current-package.md` gains a new close marker paragraph appended after the Step 4 close marker (append-only language per the established commit pattern).
- `briefs/phase-2/design-7step-step-5.md` exists carrying the pre-conversation brief verbatim.
- `briefs/phase-2/design-7step-step-5-commit.md` preserves this commit-session prompt verbatim.
- Session log entry appended to `log/sessions.md` matching the Step 4 commit entry's shape, scaled for three commits and five-instance methodology-extension evidence.

## Context to read first

In order. Read in ranges where files exceed 200 lines.

1. `charter/phase-2-design-7step.md`. Steps 1, 2, 3, and 4 sections in full. Confirm Step 4 close paragraph is terminal; Step 5 section appends immediately after.
2. `charter/current-package.md` (top section). Confirm close marker structure after Step 4 commit. Step 5 commit appends new paragraph after Step 4's marker.
3. `log/sessions.md`. Latest entry is the Step 4 commit; match its shape for Step 5 entry. Three-commit session structure matches Step 4 precedent.
4. `briefs/phase-2/design-7step-step-4.md` and `briefs/phase-2/design-7step-step-4-commit.md`. Brief shape and commit-prompt shape precedents.
5. `briefs/p8/mckinsey-7-step.md`. The Analyst role's authored specification, cited in the Step 5 dogfooding-evidence record.
6. `charter/decisions.md`. Confirm D-entry count and which D-entries Step 5 content references (D14, D24, D26, D31, D32, D44, D75, D77, D78, D80, D81, D82, D85, D86, D87, D93, D102).
7. `briefs/phase-2/design-7step-step-5.md` (pre-conversation brief, authored before Step 5 substantive work in a fresh Claude.ai thread). The brief's framing of three methodology streams plus its specification of three drafted artefacts plus the work-streams 1-4 plus the five reflection prompts.

## Pre-write reconciliation

1. **D-entry count.** Latest entry remains D113. No new D-entries this session. The Step 5 dogfooding-evidence record cites D85 (McKinsey 7-Step methodology authoring placement), D86 (role-first model), D81 (methodology aggregate v2), D82 (intelligence-layer commitment). All exist as summary lines in active `charter/decisions.md` with full content in `docs/archive/decisions/phase-1.md`.

2. **Current-package.md state.** Read the file and confirm the Step 4 close marker paragraph from the Step 4 commit. The Step 5 commit appends a new paragraph after Step 4's marker; append-only operation; prior content preserved unchanged.

3. **Append point at `charter/phase-2-design-7step.md`.** Confirm the Step 4 close paragraph is the file's current terminal content; append the Step 5 section after it without modifying Step 1, 2, 3, or 4 content.

4. **Brief authoring timing.** The Step 5 brief was authored before substantive Step 5 work AND in a fresh Claude.ai conversation thread. This completes the brief-authoring pattern that Steps 3 and 4 left partial (those authored brief pre-substantive-work but within same Claude.ai thread as prior step). The fresh-thread element strengthens the pattern at three-instance evidence. Surface in session log reflection prompt 4.

5. **New charter file landing.** `charter/phase-2-user-segment.md` does not exist at the project. New file; second of three commits this session. Top-level title `# Phase 2 user segment`.

6. **Three-commit session structure.** Matches Step 4 precedent. Commit 1 (Step 5 section plus current-package append plus brief preservation plus commit-prompt preservation), Commit 2 (phase-2-user-segment.md new file), Commit 3 (session log entry). The session log entry's Produced section reflects three commits.

7. **Carryover from prior commits.** The stale "P11 framed; S39 next" header at `charter/current-package.md` line 5 remains pre-existing structural drift; out of scope at this session per AC 8.

8. **Step 5 section content source.** The verbatim Step 5 section content sits at this commit prompt's Commit 1 specification below. The content corresponds to what the operator backed up during the Step 5 conversation at `phase-2-design-7step-step-5-interim.md` (the operator-side interim backup); the authoritative source for the charter commit is THIS prompt's Commit 1 content block.

## Commits

### Commit 1: Step 5 artefacts at charter file plus current-package append plus brief preservation plus commit-prompt preservation

Conventional commit message: `docs(charter): phase 2 design — 7-step arc Step 5 analyses, dogfooding evidence at five-instance, eleven sub-problem findings plus architectural patterns plus sequencing plus clustering`

Three-paragraph commit body. Paragraph 1: names what the new section lands (eleven sub-problem analyses at design-architectural altitude per Posture 1.5; Pass 2 cross-cutting work-streams covering five architectural patterns surfaced, four Phase 2-A sequencing waves, ten Phase 2-B clusters across four sequencing waves with Tier 4 activation map; Pass 3 close dogfooding-evidence record at five-instance methodology-template-extensibility-without-breaking evidence; sixteen open questions carrying forward to Step 6). Paragraph 2: names the substantial operator-driven refinements during the conversation (two-vector decay model at 3.2 changing methodology authoring scope; smart-confirm-but-not-silently at 1.5 generalising to cross-cutting no-silent-operation principle; central-storage refinement at 5.4 adding twelfth event class to 5.1; identity-fork model at 2.1 connecting 2.4 Tier 4 activation; expanded ICP definition covering Series A/B scale-ups; substrate inventory expansion to eleven Phase 2-A cells; eight-state status taxonomy with watching/delegated exclusions; late-conversation latency-tier inference routing surfaced as architectural primitive candidate for Step 6 commit-or-defer). Paragraph 3: names that the methodology-template-extensibility-without-breaking pattern now reaches five-instance evidence across all five sequential roles (ProblemFramer, Disaggregator, Prioritiser, Planner, Analyst); the Phase 2 methodology-extension workitem at Cluster B9 moves from four-instance observed-pattern at Step 4 to five-instance firmly-evidenced at this Step, warranting commitment as Phase 2-B work; plus the strongest single piece of bet evidence at structural level to date.

**Append the following content to `charter/phase-2-design-7step.md` as a new `## Step 5: Analyse` section, placed immediately after the Step 4 close paragraph. Content verbatim, no in-line editing. The content corresponds to lines 14-803 of the operator's interim backup file (everything from the Step 5 section opening through the Step 5 close paragraph, NOT including the Phase 2 user segment section which lands as Commit 2):**

The Step 5 section content is substantial (approximately 570 lines of markdown). Claude Code reads the operator's interim backup file at `/mnt/user-data/uploads/phase-2-design-7step-step-5-interim.md` (the operator uploads this file to the session) and copies lines 14 through the close of the Step 5 close paragraph (the line ending with "now three-instance evidenced.") into the charter file as the new Step 5 section.

Operator instruction: upload `phase-2-design-7step-step-5-interim.md` to the Claude Code session before the session begins so Claude Code has access to the verbatim content.

**Verification before commit:** Claude Code confirms the appended content starts with `## Step 5: Analyse` and ends with the Step 5 close paragraph (final sentence: "The Step 6 pre-conversation brief authors at `briefs/phase-2/design-7step-step-6.md` before the Claude.ai conversation opens, continuing the briefs/ discipline pattern now three-instance evidenced."). No content from the interim file's wrapper text (lines 1-12) or the Phase 2 user segment section (lines 805+) enters the charter file.

**Also in Commit 1: append to `charter/current-package.md` after the Step 4 close marker paragraph:**

```
**Step 5 (Analyse) closed at strategic mode on YYYY-MM-DD.** Eleven sub-problem analyses produced at design-architectural altitude per Posture 1.5 across the inclusive top quartile from Step 3. Pass 2 cross-cutting work surfaced five architectural patterns (revision-with-lineage; conversation flow; three-tier consent-and-awareness framework; tiered-by-salience candidate; two-vector decay model candidate), sequenced Phase 2-A into four waves, clustered fifty-two Phase 2-B candidates across ten clusters with Tier 4 activation map. Pass 3 close delivered five-instance methodology-template-extensibility-without-breaking evidence and sixteen carry-forward questions to Step 6. Senior-leader ICP commitment landed at `charter/phase-2-user-segment.md` per Step 5 Decision 1.
```

Claude Code substitutes `YYYY-MM-DD` with the commit date.

**Also in Commit 1: preserve `briefs/phase-2/design-7step-step-5.md` (the pre-conversation brief) verbatim.** The brief content sits at the project's `phase-2-design-7step-step-5.md` (top level); Claude Code copies it to the `briefs/phase-2/` directory under the canonical name.

**Also in Commit 1: preserve this commit prompt at `briefs/phase-2/design-7step-step-5-commit.md` verbatim.**

### Commit 2: New charter/phase-2-user-segment.md file

Conventional commit message: `docs(charter): phase 2 user segment commitment with three-population senior-leader ICP plus Phase 3 vertical-wedge candidates`

Two-paragraph commit body. Paragraph 1: names what the file lands (three-population segment definition aligning Phase 2 work with the bet's case-study-reader audience commitment and the May 2026 competitor research procurement-grade defensibility framing). Paragraph 2: names Phase 3 vertical-wedge candidates (financial services, legal, healthcare, product-leadership-vertical) plus Phase 2-A substrate priorities derived from segment (dual-provider parity at calendar and email; messaging dual-provider; work-app cells deferred per test-account constraint).

**Create new file `charter/phase-2-user-segment.md` with the following content verbatim:**

```markdown
# Phase 2 user segment

Binding specification for Phase 2 user-segment commitment. Lands at Step 5 of the Phase 2 design 7-Step arc per Step 5 Decision 1. Refreshes through normal charter evolution; Phase 3 sequencing analysis may refine the segment definition or select vertical wedges; subsequent updates land here with audit trail.

## User segment commitment

Phase 2 user segment commitment: senior leaders at established firms augmenting human EA/CoS, plus founders at early-stage tier or scale-ups up to and including Series B.

The segment definition refines the Step 1 broader busy-professional framing into a more specific commercial test condition. The senior-leader-at-established-firms framing aligns with the bet's case-study-reader audience commitment at `charter/bet.md` line 67 and with the procurement-grade audit-trailed-approval-first defensibility pattern the May 2026 competitor research identifies. The founders-bucket framing extends to Series A/B scale-ups in addition to early-stage founders; this expansion ensures the platform serves founder-led firms across the funding journey before they enter mature corporate hierarchies.

The segment carries three populations with distinct substrate landscapes:

- **Established-firm senior leaders.** Predominantly Microsoft enterprise environments (Outlook, MS365 Calendar, Teams, OneDrive, SharePoint, Workday, Salesforce, ServiceNow). Augmenting an existing human EA or CoS rather than replacing one. Procurement-grade defensibility expectations are high.
- **Series A/B scale-up founders.** Bridging substrate use across both ecosystems (Google Workspace plus growing Microsoft footprint as enterprise customers require it; Asana, Jira, HubSpot, Linear). The platform substitutes for the EA/CoS that the founder cannot yet afford or has not yet hired.
- **Early-stage founders.** Predominantly Google Workspace plus lighter-weight tools (Linear, Notion, Slack, Airtable). Platform substitutes for unavailable EA/CoS support.

The "augmenting human EA/CoS" framing applies to the established-firm senior leaders. For the founders bucket across both early-stage and Series A/B, the platform substitutes for the EA/CoS that the founder cannot yet afford or has not yet hired.

## Vertical-wedge candidates for Phase 3

The May 2026 competitor research and operator domain expertise produced vertical-wedge candidates for Phase 3 sequencing analysis:

- Financial services (Graphic Design Institute, Wide World Importers named precedents in operator's selling history)
- Legal (Alpine Ski House, Woodgrove Bank named precedents)
- Healthcare (Southridge Video named precedent)
- Product-leadership-vertical (from operator's domain)

These verticals warrant Phase 3 sequencing analysis based on Phase 2 dogfooding evidence and any first-customer engagement that lands during Phase 2-B.

## Phase 2-A substrate priorities derived from segment

The segment commitment shapes Phase 2-A substrate priorities at sub-problem 1.1 Substrate connection:

- Dual-provider parity at calendar and email (Google plus Microsoft). Both ecosystems served at Phase 2-A.
- Messaging dual-provider (Slack first, WhatsApp second). Both at Phase 2-A. Signal out of scope.
- Work-app cells deferred to Phase 2-B. Operator dogfooding instance covers HubSpot, Trello, Monday.com (test accounts; real-use validation defers to first-customer engagement).

## Evolution

This file evolves through normal charter discipline. Phase 3 sequencing analysis refining the segment definition or selecting vertical wedges updates this file with audit trail per the append-only at version level discipline.
```

### Commit 3: Session log entry

Conventional commit message: `docs(log): phase 2 design — 7-step arc Step 5 close, dogfooding evidence at five-instance methodology-template-extensibility, sixteen carry-forward questions to Step 6`

Two-paragraph commit body. Paragraph 1: names the session shape (strategic mode; three commits; Step 5 analytical work at Posture 1.5 across eleven sub-problems plus three cross-cutting work-streams plus Pass 3 close). Paragraph 2: names the substantive observations from the conversation (five-instance methodology-template-extensibility evidence; brief authoring in fresh Claude.ai thread completing three-instance pattern; interim backup discipline observed; operator refinement loops as load-bearing analytical work; pattern surfacing during finding production).

**Append the following session log entry to `log/sessions.md` after the Step 4 commit entry:**

```markdown
## Phase 2 design — 7-Step arc — Step 5 (Analyse) commit

**Session ID:** phase-2-design-7step-step-5-commit
**Mode:** strategic (charter commit)
**Date:** YYYY-MM-DD
**Roles:** analyst (primary; eleven sub-problem analyses plus cross-cutting work-streams); architect (architectural pattern surfacing; sequencing and clustering analyses); PM (decision-1 ICP landing; operator-decision integration across the conversation); technical writer (methodology authoring scope per the four Phase 2-A methodologies; audit-narrative templates discipline).

**Methodology lines:**
- McKinsey 7-Step Analyst role: function-focused system_prompt held with six substantive extensions surfaced.
- Methodology-template-extensibility-without-breaking: fifth-instance evidence; pattern firmly evidenced across all five sequential roles from ProblemFramer to Analyst.
- Briefs/ discipline: three-instance pattern (Steps 3, 4, 5 author brief pre-substantive-work; Step 5 adds fresh-thread condition).
- Posture 1.5 sustainability: delivered substantive value at Step 5; agent-runtime gap visible enough that Phase 2 / Phase 3 boundary becomes natural for agent-runtime testing.

**Produced:**

Commit 1: `docs(charter): phase 2 design — 7-step arc Step 5 analyses, dogfooding evidence at five-instance, eleven sub-problem findings plus architectural patterns plus sequencing plus clustering`
- `charter/phase-2-design-7step.md` Step 5 section appended (eleven sub-problem analyses; five architectural patterns; four Phase 2-A sequencing waves; ten Phase 2-B clusters with four sequencing waves and Tier 4 activation map; dogfooding-evidence record at five-instance; sixteen carry-forward questions to Step 6).
- `charter/current-package.md` Step 5 close marker appended.
- `briefs/phase-2/design-7step-step-5.md` preserved verbatim.
- `briefs/phase-2/design-7step-step-5-commit.md` preserved verbatim.

Commit 2: `docs(charter): phase 2 user segment commitment with three-population senior-leader ICP plus Phase 3 vertical-wedge candidates`
- `charter/phase-2-user-segment.md` created with three-population segment definition, vertical-wedge candidates for Phase 3, Phase 2-A substrate priorities derived from segment, evolution discipline.

Commit 3: `docs(log): phase 2 design — 7-step arc Step 5 close, dogfooding evidence at five-instance methodology-template-extensibility, sixteen carry-forward questions to Step 6`
- This session log entry.

**Pre-conversation operator decisions confirmed:**
- Decision 1 (ICP landing surface): new charter file at `charter/phase-2-user-segment.md`.
- ICP definition refined to: senior leaders at established firms augmenting human EA/CoS plus founders at early-stage tier or scale-ups up to and including Series B.
- Conversation arc structure: three passes (Pass 1 per-sub-problem analyses; Pass 2 cross-cutting work-streams 2, 3, 4; Pass 3 close).

**Mid-conversation substantive operator refinements:**
- Conflict resolution at 1.3 reframed from auto-resolution to user-decides (no last-write-wins default).
- Device-identity placement at identity context with distinct identity per device (multiple laptops, multiple phones).
- Substrate inventory expansion to eleven Phase 2-A cells including dual-provider calendar/email and Slack/WhatsApp messaging trio.
- Smart-confirm-but-not-silently at 1.5 generalising to cross-cutting no-silent-operation principle.
- Two-vector decay model at 3.2 (age vector plus information vector) changing methodology authoring scope across the four Phase 2-A methodologies.
- Identity-fork model at 2.1 with schema-based structural threshold connecting 2.1 adaptation to 2.4 Tier 4 user-authored methodology surface activation.
- Per-methodology value units at 4.1 (not normalised at Phase 2-A).
- Eight-state status taxonomy with watching and delegated excluded from Phase 2-A.
- Eleven (then twelve with digest-sent) event classes at 5.1 audit visibility, expanded from workplan's six.
- Central storage for digest content at 5.4 in audit context with channel delivery via per-channel preference.
- Combined threshold for migration proposal (10 approvals AND 4 weeks) at 5.4.

**Reflection prompts answered:**

1. *Methodology-template fidelity check.* The Analyst role's "execute analyses; produce findings backed by evidence; one finding per workplan item" discipline held cleanly across eleven sub-problem analyses. The "you do not synthesise; pass findings to Synthesiser" discipline held; Pass 2 architectural-pattern surfacing was borderline synthesis-shaped but explicitly authorised by the brief. Six substantive extensions surfaced where the role's authored discipline did not cover the substantive work: Posture-aware altitude specification; cross-cutting analysis discipline; measurement-substrate-per-finding discipline; operator refinement loops mid-analysis; cross-sub-problem dependency tracking; pattern surfacing during finding production. Phase 2-B Cluster B9 methodology authoring extension scope captures these.

2. *Methodology-template-extensibility-without-breaking test.* Fifth-instance evidence accumulating across all five sequential roles (ProblemFramer, Disaggregator, Prioritiser, Planner, Analyst). The pattern is firmly evidenced; Phase 2 methodology-extension workitem moves from four-instance observed-pattern at Step 4 to five-instance firmly-evidenced at this Step. The five-instance evidence represents the strongest single piece of evidence for the bet's procurement-grade methodology-embedding claim accumulated to date.

3. *Posture 1.5 sustainability check.* Posture 1.5 delivered substantive analytical value at Step 5. The agent-runtime gap is now visible enough that Phase 2 UX surface for methodology adoption plus agent runtime exercising the McKinsey 7-Step end-to-end becomes the natural Phase 2 / Phase 3 boundary. Bet's procurement-grade methodology-embedding claim at structural level is well-evidenced (five-instance); same claim at agent-runtime level remains untested across the full arc.

4. *Briefs/ discipline check.* The Step 5 brief was authored pre-substantive-work AND in a fresh Claude.ai conversation thread. The fresh-thread condition completes the brief-authoring pattern that Steps 3 and 4 left partial. Three-instance pattern (Steps 3, 4, 5 author brief pre-substantive-work; Step 5 adds fresh-thread). Pattern promoted from observation to charter commitment as a methodology line.

5. *Measurement-substrate discipline check.* Every Pass 1 sub-problem analysis includes a Measurement Substrate section. Eleven sub-problems all have measurement substrate specified with signal-capture-aggregation-threshold specification. The operator's "won't know until real users" framing from Step 4 is fulfilled. Phase 2-B Cluster B10 operationalises the specifications into running collection, aggregation, and alerting infrastructure.

**Methodology lines worth observing:**

1. **Interim backup discipline.** Mid-conversation interim backup files produced when conversation has produced substantial analytical work that would be costly to lose. Step 5 produced multiple interim updates across Pass 1-2-3 progression. Worth promoting from one-time response to a charter methodology line for long strategic-mode conversations.

2. **Operator-driven refinement loops as load-bearing analytical work.** Four substantive refinements during Step 5 changed analytical findings across multiple sub-problems (two-vector decay; smart-confirm-but-not-silently; central storage for digest; identity-fork model). The pattern: substantive analytical work cannot be linear; operator refinement loops are normal and value-producing. Cluster B9 methodology-extension work should encode refinement-loop handling explicitly.

3. **Cross-cutting pattern surfacing during per-finding analysis.** Architectural patterns emerged not from a dedicated pattern-surfacing step but from per-finding analysis flagging recurring shapes. Work-stream 2 review consolidated patterns flagged during Pass 1. Methodology pattern: pattern-surfacing happens during finding production; consolidation happens later but raw material accumulates throughout. Discipline candidate for the Analyst role's authored system_prompt extension.

4. **Five-instance methodology-extension evidence as bet's strongest structural artifact.** Across ProblemFramer, Disaggregator, Prioritiser, Planner, Analyst. Phase 2-B Cluster B9 commitment now warranted with firmly-evidenced support; Step 6 (Synthesise) may want to elevate Cluster B9 above other Phase 2-B clusters given the bet's procurement-grade methodology-embedding claim depends on it.

**Next session shape:** Step 6 (Synthesise) opens at Claude.ai in a fresh conversation thread. Pre-conversation brief authors at `briefs/phase-2/design-7step-step-6.md` before the Claude.ai conversation opens, continuing the three-instance-evidenced briefs/ discipline pattern. Sixteen carry-forward questions from Step 5 are Step 6 inputs.
```

Claude Code substitutes `YYYY-MM-DD` with the commit date.

## Acceptance criteria

1. `charter/phase-2-design-7step.md` carries the Step 5 section verbatim as specified in Commit 1, appended after the Step 4 close paragraph without modification of Steps 1, 2, 3, or 4 content. The Step 5 section starts with `## Step 5: Analyse` and ends with the final Step 5 close paragraph.
2. `charter/current-package.md` carries a new close marker paragraph after the Step 4 close marker, with append-only operation preserving prior content unchanged.
3. `briefs/phase-2/design-7step-step-5.md` exists with the pre-conversation brief content verbatim.
4. `briefs/phase-2/design-7step-step-5-commit.md` exists with this commit prompt preserved verbatim.
5. `charter/phase-2-user-segment.md` exists as a new charter file with content verbatim as specified in Commit 2.
6. `log/sessions.md` carries the new session entry matching Step 4 commit entry shape, scaled for three commits and five-instance evidence framing.
7. Three commits land in the order specified, with conventional commit messages and bodies as specified.
8. The stale "P11 framed; S39 next" header at `charter/current-package.md` line 5 remains pre-existing structural drift and is out of scope at this session.
9. No new D-entries created. No content in `charter/decisions.md` modified.
10. Append-only operation at `charter/current-package.md` verified (the Step 5 paragraph is appended after the Step 4 close marker without modifying Step 4 content).
11. The interim backup file (`phase-2-design-7step-step-5-interim.md` provided by operator at session open) is referenced for verbatim Step 5 section content but is not itself committed to the repository; only the canonical charter and briefs files land in the commit.

## Reflection prompts (answer at session log entry)

See the Commit 3 session log entry shape above. Five reflection prompts plus four methodology lines worth observing.

## Out of scope

- Pre-existing structural drift at `charter/current-package.md` (the stale "P11 framed; S39 next" header at line 5).
- Step 6 pre-conversation brief drafting (separate session; authors before the Claude.ai Step 6 conversation opens in a fresh thread per the three-instance briefs/ discipline pattern).
- Charter changes outside the specified files (`charter/phase-2-design-7step.md`, `charter/current-package.md`, `charter/phase-2-user-segment.md`).
- Code changes (no lint, no tests required at strategic-mode commit session).
- D-entry creation or modification.
- Decisions about Step 6 substantive content (defer to Step 6 conversation).
- Decisions about Phase 2 LVT placement, package structure, or architectural pattern commit-or-defer (defer to Step 6 Synthesise).
- Decisions about Phase 3 vertical-wedge sequencing (defer to Phase 3 strategic-mode block).
- Decisions about agent-runtime exercise of McKinsey 7-Step (carry-forward question 14 to Step 6).
