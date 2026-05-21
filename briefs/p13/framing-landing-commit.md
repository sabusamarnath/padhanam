> Preserved per the commit-prompt-preservation convention. This is the P13 framing landing commit prompt (Artefact 7 of the P13 framing substantive conversation's deliverables) as drafted. The landing session reconciled it against current charter state before execution: a D-number scramble correction (D116 three-tier consent / D117 tiered-by-salience / D118 two-vector decay), the roadmap v6 reformat to the existing version-log bullet shape, a new `Phase 2-A P13 framing deferrals` section authored from the Artefact 1 classification table, and the "seven" → "six" flag-for-future-testing count correction in reflection prompt 3 below. Artefact 7 preservation itself landed as a ninth commit ahead of the session log entry. See the 2026-05-21 session log entry for the full reconciliation record.

---

# P13 framing landing commit session

## Goal stated as artefacts at session close

At session close the repository carries:

1. `charter/packages/p13-epic.md` (new file) with the P13 epic note plus forward-compat substrate-depth classification table plus session structure plus open questions resolution.
2. `charter/principles.md` updated with four spec-extracted Phase 2 principles plus the new PA communication discipline principle.
3. `charter/architecture.md` updated with the new Phase 2 domain vocabulary sub-section under Phase 2 architectural primitives.
4. `charter/deferred-decisions.md` updated with three new entries (role hierarchy; principal polymorphic shape machine-actor variant) plus six flag-for-future-testing entries from the Decision 7 classification table.
5. `charter/roadmap.md` v6 entry appended.
6. `charter/prfaq.md` Phase 2 PRD section appended (post-v2 extension).
7. `charter/current-package.md` transitioned to "P13 framing closed; pre-P13 hygiene next."
8. `briefs/p13/s43.md` first-session prompt preserved.
9. `docs/notes/prior-art-karma/spec.md` (existing file at `docs/notes/spec-private-assistant-platform.md` moved and renamed under the new directory per Decision 6 Sub-decision A).
10. `log/sessions.md` session log entry appended.

## Pre-write reconciliation

Run reconciliation against current sources before commits begin. Five surfaces:

1. **D-numbering tail.** Verify the current tail of `charter/decisions.md`. New D-entries at this session (if any; the spec extracts go to principles, not decisions) would number from the next available D. Per the P13 framing settlement, no new D-entries land at this commit session; D124+ surface at S43 onward during build.
2. **Principle numbering convention.** Verify the existing principle numbering or sub-heading convention at `charter/principles.md`. The five new principles append at the end. If the convention uses numbered principles, the new principles take the next five numbers; if the convention uses heading-based grouping, the new principles go under a "Phase 2 principles" heading.
3. **Existing packages/p11-epic.md structure.** The P13 epic note follows the same shape as P11's epic note. Verify structural elements (table of contents convention, sub-heading depth, hyperlink convention) and absorb mechanically.
4. **Deferred-decisions entry shape.** Verify the existing entry shape at `charter/deferred-decisions.md`. New entries match (activation trigger; cross-references; test coverage gap if flag-for-future-testing).
5. **Roadmap entry shape.** Verify the existing roadmap entry shape at `charter/roadmap.md`. The v6 entry matches v5's structural shape.

## Commit sequence

### Commit 1: spec file relocation

```
chore(docs): relocate karma prior-art spec to docs/notes/prior-art-karma/
```

Move `docs/notes/spec-private-assistant-platform.md` to `docs/notes/prior-art-karma/spec.md`. The directory `docs/notes/prior-art-karma/` creates at this commit; the spec is the first file under it. Per Decision 6 Sub-decision A: structural-honesty for the Block 2 Part B partial closure framing. Future pattern notes (`authoring-contract.md`, `taps-and-dispatcher.md`) land under the same directory at their activation triggers.

### Commit 2: P13 epic note

```
docs(p13): P13 epic note + forward-compat classification table + session structure
```

Add `charter/packages/p13-epic.md` with the full epic note content (Artefact 1 above). The file carries the three-mode framing lens, package goal, package contents enumeration, substrate-to-mode mapping, four-session forecast, D-entry forecast, out-of-scope list, open questions resolution (principal-shape verification result), forward-compat substrate-depth classification table with build-now / defer-with-trigger / flag-for-future-testing sections, and the open-thread close noting the discipline's first-instance status.

### Commit 3: charter additions (principles, architecture, deferred-decisions)

```
docs(charter): Phase 2 principles + domain vocabulary + deferred-decisions updates
```

Three files updated:

- `charter/principles.md` — append four karma-extracted Phase 2 principles plus the PA communication discipline principle (Artefacts 3 and 4 above).
- `charter/architecture.md` — append the Phase 2 domain vocabulary sub-section under Phase 2 architectural primitives (Artefact 3 above).
- `charter/deferred-decisions.md` — append three new entries (role hierarchy; principal polymorphic shape machine-actor variant; potentially others surfaced at pre-write reconciliation) plus six flag-for-future-testing entries from the Decision 7 classification table. Each entry follows the existing shape: title, activation trigger, cross-references, notes.

### Commit 4: roadmap v6 entry

```
docs(charter): roadmap v6 — Phase 2 packaging commitment
```

Append the v6 entry to `charter/roadmap.md` (Artefact 5 above). Reasoning category: discovery.

### Commit 5: prfaq Phase 2 PRD section

```
docs(charter): prfaq Phase 2 PRD section (post-v2 extension)
```

Append the Phase 2 PRD section to `charter/prfaq.md` (Artefact 6 above). The section sits after the v2 content; v3 revoice defers to Phase 2-A close audit.

### Commit 6: first-session prompt preservation

```
docs(briefs): P13 S43 first-session prompt preservation
```

Add `briefs/p13/s43.md` carrying the full first-session prompt content (Artefact 2 above). The prompt's content matches what the operator pastes into the next Claude Code session.

### Commit 7: current-package transition

```
docs(charter): current-package P13 framing closed; pre-P13 hygiene next
```

Update `charter/current-package.md` with a new close-marker paragraph after the prior P13 framing brief landing marker. Suggested text:

```markdown
**Phase 2-A P13 framing closed** at [DATE]. Six drafted artefacts plus two close deliverables landed across this commit session: P13 epic note at `charter/packages/p13-epic.md`; spec-extracted charter additions to `charter/principles.md` and `charter/architecture.md`; PA communication discipline principle commit at `charter/principles.md`; deferred-decisions updates at `charter/deferred-decisions.md`; roadmap v6 entry at `charter/roadmap.md`; Phase 2 PRD section at `charter/prfaq.md`; first-session prompt at `briefs/p13/s43.md`; karma prior-art spec relocation to `docs/notes/prior-art-karma/spec.md`. P13 framing substantive conversation resolved seven pre-conversation decisions and surfaced the three-mode product picture (attentional plus workflow plus observation-and-suggestion) plus the meta-layer positioning. Pre-P13 hygiene session next (schema.md formalisation plus doc-content rebrand per Decision 2 triage); P13 Wave 1 first build session (S43) follows.
```

### Commit 8: session log entry

```
docs(p13): P13 framing landing commit session log entry
```

Append the commit session entry to `log/sessions.md` per the established shape. Include `roles:` tag (technical writer, PM, analyst; analyst included given the substantive analytical work resolved across seven pre-conversation decisions plus the three-mode product picture plus the meta-layer positioning). Mode: strategic (charter commit; no code changes; P13 framing landing).

Reflection prompts addressed in the session log entry:

1. **Pre-conversation decisions audit.** Did the brief's recommendations hold against the substantive conversation? Where did the conversation revise? Pattern-recurrence test for the brief-carries-recommendations discipline.
2. **Three-mode picture as framing evolution.** The product picture sharpened from "Phase 2-A as messaging-first delivery" to "three-mode operation sharing one substrate, meta-layer over existing apps." Did the sharpening preserve all prior commitments (it did) or did it surface any drift? First-instance evidence for product-picture sharpening at package framing time.
3. **Forward-compat substrate-depth discipline at first instance.** The discipline produced six build-now items plus six defer-with-trigger items plus six flag-for-future-testing items. The classification took substantive operator pushback at three placement decisions (Gate, methodology-as-workflow, governance hierarchy moved from P13 to P14). First-instance evidence; recurrence test at P14 framing.
4. **Karma prior-art reference set continuation.** Decision 6 reframed at the substantive conversation's opening per the captures.md routing entry. The spec relocates to `docs/notes/prior-art-karma/spec.md` at this commit session as structural-honesty for the Block 2 Part B partial closure framing. Two pattern notes (`authoring-contract.md`, `taps-and-dispatcher.md`) defer to their activation triggers per the existing deferred-decisions entries.

## Acceptance criteria

1. `charter/packages/p13-epic.md` exists with the full P13 epic note content.
2. `charter/principles.md` carries the four karma-extracted Phase 2 principles plus the PA communication discipline principle.
3. `charter/architecture.md` carries the new Phase 2 domain vocabulary sub-section.
4. `charter/deferred-decisions.md` carries the new entries (role hierarchy; principal polymorphic shape machine-actor variant; six flag-for-future-testing entries).
5. `charter/roadmap.md` carries the v6 entry.
6. `charter/prfaq.md` carries the new Phase 2 PRD section.
7. `briefs/p13/s43.md` exists with the full first-session prompt.
8. `docs/notes/prior-art-karma/spec.md` exists (moved from prior location); the prior `docs/notes/spec-private-assistant-platform.md` does not exist.
9. `charter/current-package.md` carries the new close-marker paragraph.
10. `log/sessions.md` carries the new session log entry.
11. Eight commits land in the sequence above with conventional-commit messages.

## Session log entry instruction

After commit 8, the entry has already landed as part of commit 8. Use real-SHA-for-prior-commit plus "this commit" for commit 8's self-reference per the discipline carried from the pre-Step-7 hygiene commit's methodology line on same-commit-SHA self-reference.
