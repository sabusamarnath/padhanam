# Charter archive — session-close export manifest

Governs the charter-export tooling that writes a flattened snapshot
(`charter-YYYYMMDD-HHMM/` plus the matching `.zip`) at session close. The
snapshot is uploaded to the Claude.ai project mirror so strategic-mode
conversations have the charter as searchable project knowledge.

## Principle

Keep what strategic conversations read frequently; discard deep history that
lives in git anyway.

The project mirror is a *search surface*, not an archive. Every file in it
dilutes search for every other file. Deep history — closed-session briefs,
superseded design-step intermediates, archived session logs and package
retrospectives — is fully preserved in git and reachable from `log/sessions.md`;
it does not need to compete for search reach in the mirror. A file earns its
place only if a strategic conversation actually reaches for it.

## How the manifest works

The export is an **allowlist**, not a glob. The tooling previously globbed the
charter surface, which is why the snapshot grew from 58 to 121 files as briefs
and design-step files accumulated — every new file auto-entered. Under this
manifest, files reach the snapshot only by appearing in the allowlist below.
New charter files, briefs, and archives do **not** auto-enter; add them here
deliberately, when a strategic conversation will read them frequently, and drop
them when they become deep history.

**Flat naming.** The tooling flattens nested source paths into single filenames.
Files under `charter/` root, `log/`, and the repo root contribute their bare
filename; files in a subdirectory are prefixed with the subdirectory name
(`charter/packages/p11-epic.md` → `packages-p11-epic.md`,
`briefs/p13/framing.md` → `p13-framing.md`). The allowlist below is keyed by
**source path**, which is unambiguous; the snapshot filename follows the
convention.

## Keep — the allowlist

### Charter canon — load-bearing on every conversation

- `charter/bet.md`
- `charter/principles.md`
- `charter/decisions.md`
- `charter/packages.md`
- `charter/current-package.md`
- `charter/architecture.md`
- `charter/methodology.md`
- `charter/methodology-comparison.md`
- `charter/product-methodology.md`
- `charter/roadmap.md`
- `charter/schema.md`
- `charter/deferred-decisions.md`
- `charter/prfaq.md`
- `charter/brand-guidelines.md`
- `charter/competitors.md`
- `charter/phase-2-user-segment.md`

### Active working logs

- `log/sessions.md` — the active session log
- `log/captures.md` — operator's running routing log

### Recent package epic notes — structural precedents for next-package framing

- `charter/packages/p13-epic.md` — active package epic note; read at session start per CLAUDE.md
- `charter/packages/p11-epic.md`
- `charter/packages/p10-epic.md`

### Phase 1 close audit

- `charter/p12-audit-findings.md`
- `charter/p12-audit-inputs.md`
- `charter/p12-phase-2-inputs.md` — P12-audit output bridge into Phase 2

### Phase 2 close audit accumulator

- `charter/phase-2-audit-inputs.md` — forward accumulator for the Phase 2 close audit

### Phase 2 design arc — canonical plus most recent step for structural precedent

- `charter/phase-2-design-7step.md` — canonical
- `briefs/phase-2/design-7step-step-7.md`
- `briefs/phase-2/design-7step-step-7-brief-commit.md`
- `briefs/phase-2/design-7step-step-7-commit.md`

### P13 framing — most recent strategic work

- `briefs/p13/framing.md`
- `briefs/p13/framing-brief-commit.md`
- `briefs/p13/framing-landing-commit.md`
- `briefs/p13/s43.md` — P13 Wave 1 first-session brief; drops from the allowlist at S43 close per the session-brief discard rule

### Compliance suite — procurement-grade defensibility; read at audit conversations

All eleven files under `charter/compliance/`:

- `charter/compliance/README.md`
- `charter/compliance/acceptable-use-policy.md`
- `charter/compliance/access-control-policy.md`
- `charter/compliance/business-continuity-plan.md`
- `charter/compliance/change-management-policy.md`
- `charter/compliance/cryptography-policy.md`
- `charter/compliance/data-classification-policy.md`
- `charter/compliance/incident-response-runbook.md`
- `charter/compliance/information-security-policy.md`
- `charter/compliance/retention-schedule.md`
- `charter/compliance/vendor-management-policy.md`

### Reference

- `docs/notes/prior-art-karma/spec.md` — private-assistant-platform spec; vocabulary input for Phase 2-A surface design and cited by the three karma-referencing deferred-decisions entries

### Working utility

- `CLAUDE.md` — project instructions
- `charter/deck.html` — Block 3 deliverable
- `charter/brand/tokens.css` — design tokens for future surface work

## Discard — everything not on the allowlist

Discard is the default: any file not listed above is excluded from the
snapshot. The categories below record what the allowlist removed at this cut,
with rationale. They are not a maintained enumeration — new files in these
shapes are simply never added to the allowlist.

- **Session-level briefs** (`briefs/<package>/<session>.md`, e.g. `briefs/p5/s17b.md`
  through `briefs/p11/s39b.md`). Operational artefacts of closed sessions;
  preserved in git and referenced from the session log; rarely read in
  strategic conversations.
- **Earlier Phase 2 design 7-step intermediates** (`briefs/phase-2/design-7step-step-1`
  through `-step-6` and their `-commit` / pass / interim / hygiene variants).
  The arc closed; canonical content lives in `charter/phase-2-design-7step.md`;
  the step-7 triple is retained above as the most-recent-step precedent.
- **Older session-log archives** (`docs/archive/sessions/p1.md` … `p10.md`).
  Deep history for closed packages.
- **Older package retrospectives** (`docs/archive/packages/p2.md` …, and
  `charter/packages/p4-epic.md` … `p9-epic.md`). Deep history; the p10/p11/p13
  epics above cover recent precedent and the active package.
- **Closed Phase 1 design notes and superseded references** — `charter/phase-1-prd.md`
  (superseded by the Phase 1 close audit findings), `p8-topology-design.md`,
  `p8-mckinsey-7-step.md` (substantive content in `methodology.md` /
  `product-methodology.md`), `contexts-workflow.md`.

## Action-item resolutions

1. **Spec relocation.** `spec-private-assistant-platform.md` moved to
   `docs/notes/prior-art-karma/spec.md` at the P13 framing landing commit
   (4dd618e). The allowlist points at the new path. The Claude.ai project file
   at the old path is stale and must be re-uploaded from the new path by the
   operator — the export tooling cannot do this.
2. **Not a duplicate.** `phase-2-audit-inputs.md` and `p12-phase-2-inputs.md`
   were verified distinct: the former is the forward accumulator for the Phase 2
   close audit, the latter the P12-audit output bridge. Both are on the
   allowlist.
3. **File count.** The allowlist totals 48 files (16 canon + 2 logs + 3 epics
   + 3 P1 audit + 1 P2 accumulator + 4 design arc + 4 P13 framing + 11
   compliance + 1 reference + 3 utility) — a healthy search surface, down from
   121 in the last full-glob snapshot.
