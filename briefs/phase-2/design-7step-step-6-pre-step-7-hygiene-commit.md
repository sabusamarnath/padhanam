# Phase 2 design 7-Step arc — Step 6 close pre-Step-7 hygiene

## Identification

Mode: strategic (charter commit; no code changes; lint and tests not required).
Block: pre-Step-7 hygiene addressing two observations flagged at Step 6 close. TOC drift at `charter/deferred-decisions.md` plus D-entry cross-reference drift surfaced at Step 6 close commit landing.
Branch: operator-selected at session open.

## Goal at session close

- `charter/deferred-decisions.md`: "Phase 2 design 7-Step deferrals" section relocated to end of file (after "Phase 1 close audit findings"); TOC at lines 11-18 carries the section as entry #9; section content unchanged.
- `charter/phase-2-audit-inputs.md` created with first entry recording the D-entry cross-reference observation.
- `briefs/phase-2/design-7step-step-6-pre-step-7-hygiene-commit.md` preserves this commit prompt verbatim.
- Session log entry appended to `log/sessions.md` recording the hygiene commit.

## Context to read first

1. `charter/deferred-decisions.md`. View TOC at lines 1-20; view "Phase 2 design 7-Step deferrals" section in current position (after "Phase 2 substrate completion"); confirm file tail anchor at the close of "Phase 1 close audit findings" for the end-of-file relocation target.
2. `charter/p12-audit-inputs.md`. Audit-input file precedent shape for `charter/phase-2-audit-inputs.md` construction.
3. `briefs/phase-2/design-7step-step-6-commit.md`. Step 6 full commit prompt that surfaced the two observations; the relocation target plus the audit input observation both trace back to this commit's outputs.
4. `log/sessions.md` tail. Latest Step 6 full commit entry as shape precedent for the hygiene session log entry.

## Charter changes required this session

This commit lands two hygiene operations:
- TOC + section-order alignment at `charter/deferred-decisions.md` so navigation index matches file order.
- New `charter/phase-2-audit-inputs.md` file with first audit observation entry.

No D-entries created; no content in `charter/decisions.md`, `charter/principles.md`, `charter/architecture.md`, `charter/packages.md`, or `charter/phase-2-design-7step.md` modified.

## The substantive work

Two commits closing the session.

### Commit 1: deferred-decisions TOC fix + Phase 2 audit inputs file creation

Conventional commit message: `docs(charter): pre-step-7 hygiene — deferred-decisions TOC alignment + phase-2 audit inputs file`

Four operations.

**Operation 1a.** View `charter/deferred-decisions.md` and capture the full content of the "Phase 2 design 7-Step deferrals" section (from the `## Phase 2 design 7-Step deferrals` H2 heading through to the line immediately before the next H2 heading, which is `## Production-deployment readiness`). Store the captured content for re-insertion at Operation 1c.

**Operation 1b.** str_replace removing the "Phase 2 design 7-Step deferrals" section from its current position. Old_str: the captured section content from Operation 1a, ending immediately before `## Production-deployment readiness`. New_str: empty. After this operation the "Production-deployment readiness" section follows directly after "Phase 2 substrate completion" with no intervening section, matching the file structure as it stood before the Step 6 full commit's Commit 3.

**Operation 1c.** Append the captured section content from Operation 1a to the end of `charter/deferred-decisions.md`, after the last paragraph of the "Phase 1 close audit findings" section. The section becomes the file's terminal H2. Use bash `cat >> path` or a str_replace operation targeting the last line of the existing terminal section.

**Operation 1d.** str_replace updating the TOC at `charter/deferred-decisions.md` lines 11-18 to add the new section as entry #9. The current TOC reads (lines 11-18):

````markdown
1. [Architectural primitives awaiting activation](#architectural-primitives-awaiting-activation)
2. [Phase 2 substrate completion](#phase-2-substrate-completion)
3. [Production-deployment readiness](#production-deployment-readiness)
4. [Workflow context extensions](#workflow-context-extensions)
5. [Methodology and governance enhancements](#methodology-and-governance-enhancements)
6. [Compliance and security](#compliance-and-security)
7. [Tool registry and authoring](#tool-registry-and-authoring)
8. [Phase 1 close audit findings](#phase-1-close-audit-findings)
````

Replace with:

````markdown
1. [Architectural primitives awaiting activation](#architectural-primitives-awaiting-activation)
2. [Phase 2 substrate completion](#phase-2-substrate-completion)
3. [Production-deployment readiness](#production-deployment-readiness)
4. [Workflow context extensions](#workflow-context-extensions)
5. [Methodology and governance enhancements](#methodology-and-governance-enhancements)
6. [Compliance and security](#compliance-and-security)
7. [Tool registry and authoring](#tool-registry-and-authoring)
8. [Phase 1 close audit findings](#phase-1-close-audit-findings)
9. [Phase 2 design 7-Step deferrals](#phase-2-design-7-step-deferrals)
````

**Operation 1e.** Create `charter/phase-2-audit-inputs.md` with the following content verbatim:

````markdown
# Phase 2 audit inputs

Accumulating substrate for the Phase 2 close audit. Audit observations surfacing during Phase 2 build sessions, strategic blocks, and arc work that warrant audit review rather than immediate fix. Mirrors the Phase 1 close audit input precedent at `charter/p12-audit-inputs.md`; entries accumulate chronologically with each entry naming the surfacing context plus the substantive observation plus the proposed audit treatment.

Reviewed at Phase 2 close audit. Entries dispositioned at audit time become either fix-now hygiene items, deferred-decisions entries with explicit activation triggers, or methodology lines folded into `charter/methodology.md`.

## D-entry cross-reference drift in charter prose usage

**Surfacing context.** Step 6 full commit landing (2026-05-20). Operator observation at session close: the new D-entries D114, D116, D118 cite "D26 (append-only audit chain)" and D114, D118 cite "D31 (revisions pattern)" matching existing charter usage at `charter/architecture.md` line 220 and `charter/principles.md` line 74. Decisions.md one-liners show D26 = "Security events log separately" and D31 = "Package-level archive document"; the append-only audit chain primitive appears at D22 per the operator's audit observation.

**Substantive observation.** The drift is pre-existing in the charter rather than introduced at Step 6; Step 6 D-entries propagated the existing usage faithfully. The terse one-line D-entry titles in decisions.md may not reflect the full scope of each numbered decision (a decision can cover multiple aspects; the one-liner captures only the lead claim). Cross-references in charter prose (architecture.md, principles.md, methodology.md, bet.md) lean on decisions.md ground truth; if the prose usage does not match the numbered decision, the cross-reference points to the wrong record.

**Proposed audit treatment.** Phase 2 close audit performs a charter-wide D-reference reconciliation pass: every cross-reference in architecture.md, principles.md, methodology.md, bet.md, and the design 7-Step arc reconciles against decisions.md ground truth. Mismatches resolve by either correcting the cross-reference (if the prose meant a different D) or expanding the decisions.md one-liner (if the prose accurately captures a decision aspect the one-liner missed). The reconciliation pass is phase-audit-scoped because it spans the full charter and produces structural corrections beyond Step 6's scope.

````

### Commit 2: Commit prompt preservation + session log entry

Conventional commit message: `docs(charter): preserve pre-step-7 hygiene commit prompt; session log`

Two artefacts.

**(a) Create `briefs/phase-2/design-7step-step-6-pre-step-7-hygiene-commit.md`** with this commit-session prompt verbatim.

**(b) Append to `log/sessions.md`** a new entry matching the Step 6 commit entry shape, scaled for two commits. Suggested structure (adjust dates and SHAs at write time):

````markdown
## [DATE] — Phase 2 design 7-Step arc Step 6 close pre-Step-7 hygiene
roles: technical writer, PM
mode: strategic (charter commit; no code changes; pre-Step-7 hygiene addressing two observations flagged at Step 6 close)

- Produced: Two commits closed the session.
  - Commit [SHA1] (`docs(charter)`): `charter/deferred-decisions.md` "Phase 2 design 7-Step deferrals" section relocated from after "Phase 2 substrate completion" to end of file (after "Phase 1 close audit findings"); TOC updated to add the section as entry #9; section content unchanged. `charter/phase-2-audit-inputs.md` created with first entry recording the D-entry cross-reference observation from Step 6 close.
  - Commit [SHA2] (`docs(charter)`): Commit prompt preservation at `briefs/phase-2/design-7step-step-6-pre-step-7-hygiene-commit.md` plus this session log entry.

- Decisions: No new D-entries. No content in `charter/decisions.md`, `charter/principles.md`, `charter/architecture.md`, `charter/packages.md`, or `charter/phase-2-design-7step.md` modified.

- Tests: None. Documentation-only changes.

- Reflection prompts answered:

  1. *TOC drift fix discipline.* The TOC drift surfaced because the Step 6 full commit prompt did not include TOC maintenance in its operations or acceptance criteria. The hygiene commit addresses it cleanly. Worth observing whether the deferred-decisions.md TOC has drifted before (likely yes; the file has eight prior sections and TOC maintenance is not in any of the prior commits' acceptance criteria). The fix scope here is single-section; charter-wide TOC audit defers to phase audit if other indices have drifted similarly.

  2. *Phase 2 audit input file as Phase 1 precedent extension.* The new `charter/phase-2-audit-inputs.md` file matches the `charter/p12-audit-inputs.md` precedent shape. Establishing the file at first observation rather than at first Phase 2 audit means observations accumulate naturally throughout Phase 2 rather than being reconstructed retrospectively. Cleaner audit trail.

- methodology (line 1): **TOC maintenance as commit-prompt acceptance criterion.** When a commit creates a new H2 section in a TOC-bearing file, the commit prompt's acceptance criteria should include TOC update as an explicit operation. The Step 6 full commit prompt missed this; surfaced at session close. Worth promoting to commit-prompt drafting discipline as a checklist item: "Does this commit add or remove an H2 section in a TOC-bearing file? If yes, TOC update is part of the commit's operations." Applies to deferred-decisions.md, the design 7-Step arc file (already follows the discipline implicitly via its sequential-Step structure), and any future TOC-bearing charter file.

- methodology (line 2): **Same-commit SHA self-reference as commit-prompt failure mode.** Carrying forward from the Step 6 full commit session log entry (recorded there as a mechanical note). The Step 6 commit prompt asked for the commit-1 SHA inside Commit 1's own output (archive note at interim record); self-referencing SHA inside a commit is structurally impossible. Operator solution: reference by commit message instead. Worth promoting to commit-prompt drafting discipline: cross-commit SHA references are fine; same-commit SHA references inside the commit's own output are the failure mode and should be replaced with commit-message references or by reference-by-name patterns.
````

## Acceptance criteria

1. `charter/deferred-decisions.md` "Phase 2 design 7-Step deferrals" section content unchanged from Step 6 full commit Commit 3 landing.
2. `charter/deferred-decisions.md` section is now the file's terminal H2 (appears after "Phase 1 close audit findings").
3. `charter/deferred-decisions.md` TOC carries nine entries with "Phase 2 design 7-Step deferrals" as entry #9; entries 1-8 unchanged from prior state.
4. `charter/deferred-decisions.md` no other content modified.
5. `charter/phase-2-audit-inputs.md` created with the header content plus first D-entry cross-reference observation entry verbatim per Commit 1 Operation 1e.
6. `briefs/phase-2/design-7step-step-6-pre-step-7-hygiene-commit.md` exists with this commit prompt preserved verbatim.
7. `log/sessions.md` carries the new session entry matching the Step 6 commit entry shape, scaled for two commits, with two reflection prompts and two methodology lines.
8. Two commits land in the order specified with conventional-commit messages as specified.

## Out of scope

- Charter-wide D-reference reconciliation pass: defers to Phase 2 close audit per the audit-input entry's proposed treatment.
- Charter-wide TOC audit (whether other indices have drifted): defers to phase audit; first methodology line surfaces the concern.
- Step 7 brief drafting: substantive next step; opens after this hygiene commit lands; brief content drafts in the Claude.ai Step 6 close thread (this conversation), commit session prompt drafts after the brief content is settled.
- `charter/current-package.md` close marker: not added at this hygiene commit; the Step 6 close marker added at the Step 6 full commit Commit 4 stands.

## Session log entry instruction

After the second commit, append the session entry to `log/sessions.md` with the two reflection paragraphs and two methodology lines per the Commit 2 specification. Include `roles:` tag (technical writer, PM; analyst optional; no architectural or engineering work).
