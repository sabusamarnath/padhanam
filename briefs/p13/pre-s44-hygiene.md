# P13 — Pre-S44 hygiene (brief path-drift promotion plus S43/S43b captures backfill)

## Goal stated as artefacts at session close

At session close the repository carries:

- A new sub-paragraph at `charter/methodology.md` under the "2026-05-16 — Pre-write reconciliation as architectural discovery (P12 audit promotion)" Patterns observed entry naming a **path-naming sub-pattern** with the verified P13 instance count and the operationalisation discipline addition (pre-write reconciliation surface explicitly checks path naming against `adapters/outbound/{vendor}/`, `tests/contract/*`, and equivalent codebase conventions, not just shape).
- Up to three new entries at `log/captures.md` covering the three S43/S43b methodology candidates surfaced at S43b close: planned-bridge-session sub-variant (first instance, pending recurrence); brief path-drift (now promoted to methodology document); substrate-completion-vs-deployment honesty (first instance, pending recurrence). Existing captures verified and not duplicated; missing captures backfilled.
- The brief path-drift captures entry triaged as resolved with promotion-to-methodology resolution text; the two other captures entries triaged as pending recurrence with explicit recurrence thresholds named.
- `charter/current-package.md` transitioned from "S43b closed; S44 next" to "Pre-S44 hygiene closed; S44 next" with a brief close-marker paragraph appended per the existing P13 narrative convention.
- `briefs/p13/pre-s44-hygiene.md` preserved as this brief's canonical path for audit-trail reference.
- Session log entry appended at `log/sessions.md` per the strategic-mode convention with substantive reflection on the path-naming-as-sub-pattern decision plus the two-instance-versus-three-instance accuracy verification.

This is charter-only work. No code changes, no test changes, no enforcement-layer changes.

## Context to read first, in order

1. `charter/methodology.md` — the "Pre-write reconciliation as architectural discovery" Patterns observed entry (around lines 329–337) plus the "Pre-write reconciliation against vendor docs precedes brief drafting" section near the document tail. Verify the sub-paragraph addition fits the existing entry's structural convention (see the "Mid-build pre-write reconciliation as sub-pattern" paragraph at line 337 as precedent).
2. `log/sessions.md` — the S40, S43, and S43b session log entries (search by session ID). Verify the methodology lines at each session to confirm the path-drift instance count. The S43b close reflection naming the three-instance promotion candidate is the canonical source for the framing carried into this hygiene.
3. `log/captures.md` — full read for any S40, S43, or S43b entries. The 2026-05-20 P13 framing entry at the file tail is the most recent visible entry in the snapshot; verify whether S43 or S43b session-close captures landed downstream.
4. `charter/current-package.md` — the S43b close marker and the "S44 next" forward signal.
5. `charter/packages/p13-epic.md` — the P13 session forecast and the S44 framing position; no edits expected here, read-only for context.

## Pre-write reconciliation (verify against current sources before commits land)

Three reconciliation surfaces to verify before commit 1 drafts:

1. **Three-instance accuracy verification.** The S43b close reflection named three path-drift instances at S40, S43, and S43b. Read each session's methodology lines verbatim and confirm whether each is genuinely a path-naming drift instance (brief framed a file path that did not match the codebase's actual naming convention) versus a different drift class (strategy enumeration, shape drift, principle violation). If S40 turns out to be a different class (e.g. the existing S40 methodology line "D66's framing-vs-as-built drift, catalogue says three strategies, adapter executes two" reads as strategy enumeration not path naming), the promotion still fires at two instances per the corrective-discipline-on-first-instance precedent set by the metric-threshold and reproducibility-artefacts methodology entries. Surface the verification outcome to the operator before commit 1 if the count differs from three.

2. **Captures.md state.** Read the captures.md tail and verify whether S43 or S43b session-close captures landed downstream of the 2026-05-20 P13 framing entry. The S43b close reflection committed to capturing all three S43/S43b methodology candidates; verify whether that landed or remains pending. If pending, the captures backfill is needed; if landed, only the brief path-drift entry needs triage-mark editing.

3. **Methodology.md sub-paragraph placement.** Verify that the existing pre-write reconciliation entry already has the "Mid-build pre-write reconciliation as sub-pattern" sub-paragraph at line 337 (or current line). The path-naming sub-pattern goes adjacent to it, following the same italic-header convention (`*Path-naming sub-pattern.*` opening). If the existing entry's structure has shifted, adapt placement to match current convention.

Findings surface as questions before commits land. Discipline carries forward from prior pre-write reconciliation precedent.

## Charter updates ahead of commits (this is charter-only work)

### Commit 1: Captures backfill (conditional on pre-write reconciliation finding)

Conventional-commit subject:

```
docs(charter): backfill captures for S43/S43b methodology candidates
```

Touched files:

1. `log/captures.md` — append up to three new entries dated 2026-05-21 (the S43/S43b close date). Each entry follows the existing format (date plus session-id header; paragraph body; triaged plus resolution lines). Entries to write if missing:

**Entry A: Planned-bridge-session sub-variant (first instance).**

```
## 2026-05-21 [S43/S43b] — Planned-bridge-session sub-variant of bridge-session shape (first instance)

Source: S43/S43b substrate-and-transport split. The bridge-session
shape (Patterns observed entry pending future promotion or absorbed
under session shapes per methodology document discipline) covers
verification-and-hygiene work between substrate sessions and audits.
The S43-to-S43b split is a distinct sub-variant: the bridge was
planned at the substrate-completion boundary (S43 close decided to
defer HTTP transport plus live smoke to S43b rather than absorbing
both into a single S43 session) rather than emerging from substrate-
session-surfaced gaps after the fact.

Distinguishing structural property: the S43 brief named a ten-commit
session; at substrate-completion (commit 7), the operator and Claude
Code together decided the remaining three commits (HTTP transport,
contract tests, live smoke) constituted a coherent bridge-shaped unit
better landed in its own session against a freshly-rebuilt image. The
S43 close marker named the split explicitly; the S43b session opened
against `briefs/p13/s43b.md` with the planned-bridge framing.

Recurrence test: a second planned-bridge instance at a future
bounded-context substrate session (e.g. S44 split into S44a/S44b)
promotes the sub-variant to a methodology document entry or absorbs
it as a named session shape under the methodology document's Session
shapes sub-section.

  - triaged: pending — methodology candidate awaiting second instance
  - resolution: awaiting recurrence; second-instance threshold for
    methodology document promotion sits at the next bounded-context
    substrate session whose substrate-and-transport split (or
    equivalent coherent-unit split) lands as a planned bridge rather
    than a post-hoc bridge.
```

**Entry B: Brief path-drift (third instance; promoted to methodology document at this hygiene).**

```
## 2026-05-21 [S43/S43b] — Brief path-drift (multiple-instance methodology promotion candidate)

Source: S43 plus S43b pre-write reconciliation findings. Brief drafts
named adapter, test, and contract paths that did not match the
codebase's actual naming conventions:

- S43 brief named `adapters/outbound/postgres/` as the placement path
  for the Postgres state-persistence adapter; the codebase convention
  (verified at S43 pre-write reconciliation) places adapters at
  `contexts/<context>/adapters/postgres_<context>.py` without the
  `outbound/` subdirectory.
- S43b brief named `tests/contract/http/portfolio/` as a subdirectory
  for the new HTTP contract tests; the codebase convention (verified
  at S43b pre-write reconciliation) places HTTP contract tests at the
  flat `tests/contract/http/` directory per the S42 precedent (five-
  of-five existing surfaces use flat module naming).

If a third instance exists at S40 (the S43b close framing cited the
S40 adapter shape; verify before promotion text drafts whether S40
methodology line records genuine path-naming drift or a different
drift class), the count is three; if S40 falls out, the count is two.

Distinguishing structural property: path-naming drift is a sub-class
of pre-write reconciliation's brief-vs-codebase drift (the already-
promoted Patterns observed entry at `charter/methodology.md`). The
mitigation surface is identical (pre-write reconciliation reading)
but the discipline addition is explicit: the reconciliation surface
checks path naming against codebase conventions, not just shape.

  - triaged: 2026-05-21 — promoted to methodology document sub-
    paragraph under the pre-write reconciliation entry at this
    hygiene session
  - resolution: methodology document updated with a Path-naming sub-
    pattern paragraph adjacent to the existing Mid-build sub-pattern
    paragraph; discipline addition is the explicit path-naming check
    at pre-write reconciliation surface; future briefs include path
    naming in the pre-write reconciliation surface enumeration.
```

**Entry C: Substrate-completion-vs-deployment honesty (first instance).**

```
## 2026-05-21 [S43] — Substrate-completion-versus-deployment honesty (first instance)

Source: S43 close reflection on the live-stack smoke deferral. The
S43 substrate landed in code (domain, ports, adapters, application,
CLI) but the Alembic 0016 migration had not been applied to the
running per-tenant container images at S43 commit-7 close. The S43b
session rebuilt the image and applied the migration as part of the
live-stack smoke; the substrate-committed-but-not-deployed gap was
resolved at S43b commit-4.

Distinguishing structural property: this is distinct from brief
path-drift or principle-versus-framing drift because the drift surface
is the deployment artefact (container image plus applied migrations),
not the brief or the principles file. The mitigation surface points
at CI or merge-gate machinery: a check at commit time that the per-
tenant container image carries every Alembic migration through the
new commit's revision string. A brief-drafting discipline would not
catch this class because the brief framed correctly; the discipline
gap is downstream of substrate completion at the deployment-artefact
layer.

Recurrence test: a second instance of substrate-committed-but-not-
deployed drift promotes the candidate to a methodology document entry
or a deferred-decisions entry (depending on whether the mitigation
surface is methodology-document material or merge-gate machinery).

  - triaged: pending — methodology candidate awaiting second instance
  - resolution: awaiting recurrence; second-instance threshold for
    methodology document or deferred-decisions entry sits at the next
    substrate session whose commit chain ships code without deploying
    migrations to running containers. If recurrence does not fire by
    Phase 2-A close, the candidate folds into the Phase 2-A close
    audit's substrate-vs-deployment honesty audit surface.
```

Conditional logic: if any of these entries already exist at `log/captures.md` (verified at pre-write reconciliation surface 2), skip the matching entry. The entries that do not yet exist land at this commit; the captures that already exist remain unchanged. If all three already exist, this commit is empty and folds into commit 2 (operator decides at commit-1 draft time).

### Commit 2: Methodology document promotion

Conventional-commit subject:

```
docs(charter): promote brief path-drift to methodology sub-paragraph under pre-write reconciliation
```

Touched files:

1. `charter/methodology.md` — append a new sub-paragraph at the end of the "2026-05-16 — Pre-write reconciliation as architectural discovery (P12 audit promotion)" Patterns observed entry, adjacent to the existing "Mid-build pre-write reconciliation as sub-pattern" paragraph. Exact text (adapt line-count phrasing if verification surfaces two instances rather than three):

```
*Path-naming sub-pattern.* Pre-write reconciliation also fires
specifically against path-naming drift in brief drafts. Brief
drafts naming adapter, test, or contract paths that do not match
the codebase's actual `adapters/outbound/{vendor}/`,
`tests/contract/*`, or equivalent conventions surface at session
open through the standard reconciliation discipline; the
discipline addition is explicit enumeration of path naming in the
reconciliation surface check, not just shape. Three P13 instances
(S40 adapter shape if confirmed at instance verification; S43
`adapters/outbound/postgres/` subdirectory drift against the flat
`contexts/<context>/adapters/postgres_<context>.py` convention;
S43b `tests/contract/http/portfolio/` subdirectory drift against
the flat `tests/contract/http/` convention from the five-of-five
S42 precedent) at promotion. Future briefs include path naming
in the pre-write reconciliation surface enumeration.
```

Verification note: if the three-instance verification at pre-write reconciliation surface 1 finds only two genuine instances (S43 plus S43b, with S40 falling out as a different drift class), the sub-paragraph adapts to "Two P13 instances at promotion (S43 plus S43b); promotion fires at two instances per the corrective-discipline-on-first-instance precedent set by the metric-threshold and reproducibility-artefacts methodology entries."

2. `log/captures.md` — if the brief path-drift captures entry (Entry B at commit 1) already existed before commit 1 (verified at pre-write reconciliation surface 2), edit its triaged plus resolution lines at this commit to mark the promotion landing. If the entry was created at commit 1, it already carries the promoted triaged line and no edit at commit 2 is needed.

3. `charter/current-package.md` — append a close-marker paragraph after the existing "S43b closed; S44 next" entry. Use append-shaped wording per the methodology line from the Phase 2 design-7step Step 2 commit:

```
**Pre-S44 hygiene closed** at 2026-05-21. Two substantive commits
landed the captures backfill for the three S43/S43b methodology
candidates plus the brief path-drift sub-pattern promotion under
the pre-write reconciliation entry at `charter/methodology.md`.
The promotion landed [two|three] verified P13 instances per the
instance-verification surface at pre-write reconciliation (S40
[confirmed|reclassified to a different drift class]; S43
`adapters/outbound/postgres/` subdirectory drift; S43b
`tests/contract/http/portfolio/` subdirectory drift). The
planned-bridge-session sub-variant and substrate-completion-vs-
deployment honesty candidates land at captures.md as pending
recurrence with explicit second-instance thresholds named. S44a
first build session opens next per `briefs/p13/s44a.md` (drafted
at the S44a framing strategic block).
```

Adjust the parenthetical instance-verification phrasing to match the verification outcome.

4. `briefs/p13/pre-s44-hygiene.md` — preserve this brief at its canonical path for audit-trail reference.

### Commit 3: Session log entry

Conventional-commit subject:

```
docs(p13/pre-s44-hygiene): session log entry
```

Append the session log entry to `log/sessions.md` per the strategic-mode convention. Use the existing pre-P13 hygiene entry (search by header "Pre-P13 hygiene closed" or equivalent) as structural precedent. Entry carries `roles: technical writer, architect`. Mode: strategic (post-substrate-completion hygiene; closes the methodology candidate promotion queued at S43b close; no code changes). Substantive paragraphs address the reflection prompts below.

## Acceptance criteria

1. `charter/methodology.md` carries the new Path-naming sub-pattern paragraph under the pre-write reconciliation Patterns observed entry, with instance count and citations matching the verification outcome at pre-write reconciliation surface 1.
2. `log/captures.md` carries entries A, B, and C from commit 1 (whichever did not already exist; verified at pre-write reconciliation surface 2). Entry B is triaged as resolved with promotion-to-methodology resolution text.
3. `charter/current-package.md` carries the appended pre-S44 hygiene close marker with the verification-adjusted instance count phrasing.
4. `briefs/p13/pre-s44-hygiene.md` preserved.
5. `log/sessions.md` carries the session log entry at the file tail.
6. No code changes; no test changes; no enforcement-layer changes.
7. All three commits land cleanly with conventional-commit subjects matching the templates above.

## Reflection prompts addressed in the session log entry

1. **Instance-verification outcome.** Did the three-instance framing at S43b close hold against the actual S40, S43, and S43b methodology lines, or did S40 reclassify? Name the verification outcome explicitly and the count that fed into the methodology sub-paragraph text. If the count differs from three, the substantive paragraph explains why the corrective-discipline-on-first-instance precedent justifies promotion at the verified count.

2. **Sub-paragraph-versus-sibling-entry placement decision.** The path-naming sub-pattern landed as a sub-paragraph under the existing pre-write reconciliation entry rather than as its own sibling Patterns observed entry. The substantive paragraph names the reasoning: the mitigation surface is identical (pre-write reconciliation reading), the existing entry already carries a sub-pattern paragraph (Mid-build sub-pattern), and three instances of a sub-class of an already-promoted pattern fits the sub-paragraph altitude rather than the sibling-entry altitude. Alternative placements considered: sibling Patterns observed entry (rejected: duplicates the existing entry's mitigation surface and inflates the document's pattern count without structural distinction); discipline-addition paragraph under "Pre-write reconciliation against vendor docs precedes brief drafting" section near document tail (rejected: that section addresses vendor-SDK drift specifically, not codebase-convention drift).

3. **Captures-as-audit-trail discipline.** This hygiene session captured the three S43/S43b methodology candidates at `log/captures.md` even when only one of them was promoted at this session. The discipline reasoning: the captures surface is the audit-trail record of methodology-candidate surfacing, regardless of immediate promotion status. Promotion happens at recurrence threshold or at corrective-discipline-on-first-instance qualification; captures land at first surfacing. The substantive paragraph names this as a discipline reinforcement: future session-close captures should land all surfaced methodology candidates, not just the ones at promotion threshold, so that recurrence tracking has a complete audit trail.

4. **Two-pattern-versus-three-pattern accuracy discipline.** If verification surfaces only two genuine path-drift instances rather than three, the methodology sub-paragraph adapts cleanly and the corrective-discipline-on-first-instance precedent absorbs the lower count. The substantive paragraph names this as a structural-honesty discipline: methodology promotions cite the verified instance count, not the framing-time count carried from session-close reflections. The reflection paragraph also names the discipline-corrective implication for future captures: the captures entry's instance enumeration is the canonical source for promotion-time citation, and the captures entry's instance enumeration verifies against actual session log methodology lines at every promotion event.

## Out of scope explicitly

- The two remaining S43/S43b methodology candidates (planned-bridge sub-variant; substrate-completion-vs-deployment honesty) do not promote at this hygiene session. They land at captures.md as pending recurrence and await second-instance thresholds before methodology document promotion. The next bounded-context substrate session is the natural recurrence-test surface for the planned-bridge sub-variant; the next substrate session whose commit chain ships code without applying migrations is the natural recurrence-test surface for the substrate-completion-vs-deployment honesty candidate.
- The file topology budget discipline (the framing-time file-size budget surface discussed at the S44 framing Claude.ai conversation) does not land as a methodology document entry at this hygiene session. The discipline is a brief-format addition at S44a; methodology document promotion waits for the S44a recurrence test (does the budget discipline survive a real build session without breaking the natural session shape, or does it add bureaucracy without catching bloat). First-instance evidence accrues at S44a close; promotion candidacy evaluates at P13 close.
- S44 framing decisions (the four decisions from the S44 framing Claude.ai conversation: substrate-and-transport split into S44a plus S44b; intake context placement at `contexts/intake/`; pre-S44 hygiene commit existence; ActorContext-and-decorator D-entry bundling) land at the S44a brief. This hygiene session does not pre-empt those framing decisions or write S44a brief content.
- No code changes anywhere. No `contexts/*/`, `apps/`, `padhanam/`, `tests/`, or migration changes. The brief path-drift discipline addition is a charter-only commitment; the code-side reconciliation discipline that consumes it fires at S44a pre-write reconciliation and onward.
- No charter touchpoints beyond the three named files (`charter/methodology.md`, `log/captures.md`, `charter/current-package.md`). No D-entry additions; no principles edits; no architecture.md edits; no schema.md edits.

## Session log entry instruction

After commit 2, append the pre-S44 hygiene entry to `log/sessions.md` at commit 3 per the strategic-mode convention. Use the same-commit-SHA self-reference discipline carried from prior hygiene sessions. Transition `charter/current-package.md` from "S43b closed; S44 next" to "Pre-S44 hygiene closed; S44 next" within commit 2's diff (the close marker append).
