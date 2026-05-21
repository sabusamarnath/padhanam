# P13 — Pre-P13 hygiene — schema.md formalisation plus Quorum to Padhanam find-replace

Hygiene session bundled per P13 framing Decision 2. No new D-entries; documentation-only changes; mixed commit prefixes per work nature. Closes the two carryover items from `charter/p12-phase-2-inputs.md` before S43 opens the P13 Wave 1 build session.

## Goal stated as artefacts at session close

At session close the repository carries:

1. `charter/schema.md` gains a new top-level section formalising three cross-cutting binding shapes that exist in code but are not yet in the binding-specification surface per P12 audit Finding B3 (TenantContext value object plus ErrorResponse HTTP DTO) and Finding B5 (canonical cursor codec).
2. Zero non-allowlist matches for "Quorum" in current-facing narrative files. Allowlist preserves `charter/decisions.md` (historical D-entries plus D38's rename-recording body), `log/sessions.md`, `docs/archive/`. Non-allowlist matches outside the allowlist get rephrased, not allowlist-extended, per the S13 verification discipline.
3. `charter/phase-2-audit-inputs.md` gains a new "Phase 2-A close hygiene list" section establishing the accumulator surface for hygiene items surfaced during Phase 2-A. First entry: roadmap stale-headers item ("Initiative 1: Phase 1 (in progress)"; "Initiative 2: Phase 2 (direction TBD)") per the P13 framing close note.
4. `charter/current-package.md` carries the pre-P13 hygiene close marker plus the S43 next-up framing.
5. `briefs/p13/pre-hygiene.md` preserves this prompt verbatim.
6. `log/sessions.md` carries the hygiene session entry per the hygiene-shape convention.

## Pre-write reconciliation (verify against current sources before any commit)

Run reconciliation at session open. Findings surface as questions before commit 1, not silent adjustments. Five surfaces:

1. **`charter/schema.md` current structure.** Read the file's H2 headings. Verify whether existing H2s exclusively cover database tables or whether a non-table H2 already exists. The new section "Cross-cutting binding shapes" lands at the appropriate position relative to existing sections. If the file's section structure has drifted from the assumption above, surface the placement question before commit 1.

2. **Verify the three code substrates against current code state.** Three files plus four cursor-codec sites:
   - `shared_kernel/tenant_context.py` — confirm the `TenantContext` value object exists, is frozen, and carries the three fields (`tenant_id`, `jurisdiction`, `cost_attribution_id`) per D34 + D50. If field set has expanded or shifted, schema.md entry reflects the current state, not the audit-finding snapshot.
   - `apps/api/_errors.py` — confirm the `ErrorResponse` Pydantic shape exists and carries the four fields (`error_code`, `message`, `correlation_id`, `details`) with `error_code` as the discriminator across HTTP error paths per D98.
   - Four cursor-codec sites: `contexts/run_history/application/cursor.py`, `contexts/audit/application/cursor.py`, `contexts/retrieval_evaluation/application/cursors.py`, `contexts/optimization/application/cursors.py`. Confirm all four exist; confirm the base64-of-JSON shape is structurally consistent; note the singular/plural module-name drift (cursor.py vs cursors.py) for documentation as hygiene-tolerated per Finding B5 disposition.

3. **`grep -rln "Quorum" --include="*.md" .` baseline before commit 2.** Run the S13 verification grep against the current repository. Capture the full match list. Filter against the allowlist (`charter/decisions.md`, `log/sessions.md`, `docs/archive/`). The remaining non-allowlist matches are the work surface for commit 2. If the count is zero, commit 2 reduces to a no-op verification commit and the session compresses to four commits.

4. **`charter/phase-2-audit-inputs.md` current state.** Confirm the file exists (created at Step 6 pre-Step-7 hygiene per the Step 6 close trail). Read its current section structure. The new "Phase 2-A close hygiene list" section lands at the end. If the file does not exist or has been restructured, surface before commit 3.

5. **`charter/current-package.md` current close marker text.** Read the file. The close marker at session close transitions from "P13 framing closed" (which currently names "Pre-P13 hygiene next") to "Pre-P13 hygiene closed; S43 next." Verify the current marker text precisely to avoid drift at the transition edit.

Findings surface as questions before commit 1. The discipline is unchanged from S36 onward.

## Substantive work (commit-shaped units)

### Commit 1: schema.md formalisation

Conventional commit subject:

```
docs(charter): schema.md formalisation — TenantContext, ErrorResponse, canonical cursor codec
```

Two-paragraph commit body. Paragraph 1: names the three shapes being formalised plus the audit-finding origin (P12 audit Finding B3 for TenantContext and ErrorResponse; Finding B5 for the cursor codec). Paragraph 2: names that the formalisation closes the hygiene work flagged at Phase 2-entry per `charter/p12-phase-2-inputs.md` plus P13 framing Decision 2; no new D-entries because the shapes are already code-committed and the work is documentation hygiene.

Append a new H2 section to `charter/schema.md` at the position determined by pre-write reconciliation surface 1. Suggested heading: `## Cross-cutting binding shapes`. Section preamble (one paragraph): names that this section formalises non-table binding shapes (value objects, HTTP DTOs, application-layer codecs) that cross multiple bounded contexts and ship to procurement-grade consumer surfaces. The section's audit-trail role is the same as the database-table sections: schema diffs at commit time reconcile against this surface for cross-cutting shape additions just as they do for table additions.

Three sub-sections under the new H2:

**`### TenantContext (shared-kernel value object)`**

One-paragraph framing: the frozen value object carried via auth middleware extraction per D34's credential-encryption integration and D50's TenantContext shape commitment. Cross-cuts all per-tenant contexts. Lives at `shared_kernel/tenant_context.py`.

Field table:

| Field                  | Type    | Constraints                                       |
|------------------------|---------|---------------------------------------------------|
| `tenant_id`            | `UUID`  | not null; primary identifier                      |
| `jurisdiction`         | `str`   | not null; non-empty                               |
| `cost_attribution_id`  | `str`   | not null; non-empty; D41 cost-attribution surface |

Trailing paragraph: notes that the dataclass is frozen per D16 domain-purity commitment; `__post_init__` enforces non-empty invariants on `jurisdiction` and `cost_attribution_id`; the object propagates via the auth middleware's principal-derived extraction pattern per D98.

**`### ErrorResponse (HTTP-layer DTO)`**

One-paragraph framing: the discriminated-union Pydantic shape rendered by OpenAPI specification as the canonical error wire format across all HTTP error paths per D98 narrative. Lives at `apps/api/_errors.py`. Structurally consistent across S34, S37, S38, S42 HTTP transports.

Field table:

| Field             | Type    | Constraints                                                                          |
|-------------------|---------|--------------------------------------------------------------------------------------|
| `error_code`      | `str`   | not null; discriminator across error paths; canonical identifier per route family    |
| `message`         | `str`   | not null; human-readable error message                                               |
| `correlation_id`  | `UUID`  | not null; propagated from request context for cross-system tracing                   |
| `details`         | `dict`  | nullable; per-error-code structured detail payload                                   |

Trailing paragraph: notes the discriminator pattern (the `error_code` field is canonical per route family; HTTP contract tests at `tests/contract/http/` enforce shape consistency across the four list endpoints per S42).

**`### Canonical cursor codec (application-layer pagination)`**

One-paragraph framing: base64-encoded JSON codec for paged-list cursors per S33 vintage. Four implementing sites with structurally identical shape; module-naming carries a hygiene-tolerated drift (singular `cursor.py` for run_history and audit; plural `cursors.py` for retrieval_evaluation and optimization) flagged at P12 audit Finding B5 with non-action disposition.

Sites table:

| Module path                                                  | Originating session  |
|--------------------------------------------------------------|----------------------|
| `contexts/run_history/application/cursor.py`                 | S33                  |
| `contexts/audit/application/cursor.py`                       | S37                  |
| `contexts/retrieval_evaluation/application/cursors.py`       | S39 (P11)            |
| `contexts/optimization/application/cursors.py`               | S41 (P11)            |

Trailing paragraph: the codec carries the list-filter snapshot plus the cursor-position identifier; the codec is opaque to consumers (base64 envelope); HTTP contract tests enforce round-trip stability and cursor-filter-mismatch handling per the S33 cursor-filter-mismatch policy committed at D98.

### Commit 2: Quorum to Padhanam find-replace

Conventional commit subject:

```
docs(p13/hygiene): Quorum to Padhanam find-replace across stale narrative references
```

Commit body: paragraph 1 names the S13 verification baseline (zero non-allowlist matches at S13 close per the rebrand playbook) plus the drift surface (non-allowlist matches accumulated post-S13 in `methodology.md` discussing the rename sub-shape, `packages.md` describing P2 contents, possibly others). Paragraph 2 names the rephrasing discipline (rephrase rather than allowlist-extend per the S13 verification convention; the old name lives in append-only locations only).

Operations:

1. Run `grep -rln "Quorum" --include="*.md" .` and capture the full match list against the current repository state.
2. Filter the match list against the allowlist: `charter/decisions.md`, `log/sessions.md`, `docs/archive/`.
3. For each non-allowlist match, rephrase the surrounding text to remove the literal "Quorum" reference. Rephrasing patterns:
   - In methodology narrative describing rebrands: rephrase to refer to the renames by their session numbers (S8 rebrand, S13 rebrand) or by the structural pattern (rebrand-class coordinated rename) without naming the source name. Example: "S8 (Quorum → Zephyr)" becomes "S8 (the first rebrand)" or similar.
   - In packages narrative describing P2 contents: rephrase to refer to "the platform name change at S8" or similar; the historical record in `docs/archive/packages/p2.md` carries the literal naming.
   - In any other current-facing surface: rephrase to refer to the platform by its current name or by a structural descriptor; never extend the allowlist.
4. Verify the post-edit grep: `grep -rln "Quorum" --include="*.md" .` should return only allowlist matches.
5. Capture the count of files touched plus the final allowlist match count in the commit message body.

If commit 2 reduces to a no-op verification (zero non-allowlist matches at pre-write reconciliation surface 3), commit 2 becomes a docs-only verification commit:

```
docs(p13/hygiene): Quorum to Padhanam find-replace verification (zero non-allowlist matches)
```

with a body paragraph noting the verification ran clean and the allowlist held.

### Commit 3: Phase 2-A close hygiene list surface

Conventional commit subject:

```
docs(charter): phase-2-audit-inputs.md — Phase 2-A close hygiene list with roadmap stale-headers entry
```

Commit body: paragraph 1 names the new accumulator surface for Phase 2-A close hygiene items (Decision 2 triage discipline carrying forward through Phase 2-A; the list clears at the Phase 2-A close hygiene session). Paragraph 2 names the first entry (roadmap stale-headers).

Append a new section to `charter/phase-2-audit-inputs.md` after its current last section. Heading: `## Phase 2-A close hygiene list`.

Section preamble (one paragraph): names the list's role as the accumulator surface for hygiene workitems triaged to Phase 2-A close per Decision 2 of P13 framing. Items accumulate organically through Phase 2-A package execution; each surfacing emits one entry; the list clears at the Phase 2-A close hygiene session. Distinguished from the substrate-completion list (which carries deferred substrate that activates with explicit triggers per `charter/deferred-decisions.md`); this list is closure-housekeeping rather than activation-gated work.

First entry:

```markdown
### Roadmap stale-headers refresh

`charter/roadmap.md` carries two stale section headers at the top: "Initiative 1: Phase 1 (in progress)" and "Initiative 2: Phase 2 (direction TBD)". Phase 1 closed at P12 audit; Phase 2 direction is committed per D93 plus the v6 roadmap entry from P13 framing. Headers refresh to reflect post-Phase-1 status plus committed Phase 2 direction. Hygiene work, not architectural rework. Estimated single-commit scope at the Phase 2-A close hygiene session. Surfaced at P13 framing landing per the close-note discipline.
```

### Commit 4: current-package transition plus brief preservation

Conventional commit subject:

```
docs(charter): pre-P13 hygiene closed; S43 next
```

Two operations.

**(a) Append a close marker paragraph to `charter/current-package.md`** after the prior P13 framing close marker. Suggested text (adjust date at write time):

```markdown
**Pre-P13 hygiene closed** at [DATE]. Three substantive commits landed two carryover hygiene items plus one new Phase 2-A close hygiene list surface. `charter/schema.md` gained a "Cross-cutting binding shapes" section formalising TenantContext, ErrorResponse, and the canonical cursor codec per P12 audit Finding B3 plus B5. Quorum to Padhanam find-replace ran the S13 verification grep against current narrative state; non-allowlist matches rephrased per the rebrand-playbook verification discipline. `charter/phase-2-audit-inputs.md` gained a "Phase 2-A close hygiene list" section with the roadmap stale-headers entry as first item. S43 first build session opens next per `briefs/p13/s43.md`.
```

**(b) Preserve this prompt verbatim** at `briefs/p13/pre-hygiene.md`.

### Commit 5: session log entry

Conventional commit subject:

```
docs(p13): pre-P13 hygiene session log entry
```

Append the hygiene session entry to `log/sessions.md` per the hygiene-shape convention precedent (pre-P12 hygiene; post-P12 charter-discipline hygiene; pre-Phase-2 synthesis-and-refinement). Shape:

```markdown
## [DATE] — Pre-P13 hygiene — schema.md formalisation plus Quorum to Padhanam find-replace
roles: technical writer, analyst
mode: build (P13 pre-substrate hygiene; closes two carryover items before S43 opens)

- Produced: Five commits closed the session.
  - Commit [SHA1] (`docs(charter)`): schema.md "Cross-cutting binding shapes" section with three sub-sections (TenantContext, ErrorResponse, canonical cursor codec).
  - Commit [SHA2] (`docs(p13/hygiene)`): Quorum to Padhanam find-replace across N non-allowlist files; post-edit grep returns only allowlist matches.
  - Commit [SHA3] (`docs(charter)`): phase-2-audit-inputs.md "Phase 2-A close hygiene list" section with roadmap stale-headers entry as first item.
  - Commit [SHA4] (`docs(charter)`): current-package.md close marker; pre-hygiene prompt preservation at briefs/p13/pre-hygiene.md.
  - Commit [this commit] (`docs(p13)`): this session log entry.

- Decisions: No new D-entries. Per hygiene-shape discipline.

- Tests: None. Documentation-only changes.

- Reflection prompts answered: [four prompts answered in substantive paragraphs per the Reflection prompts section below]

- methodology (line N): [any patterns surfaced; see Reflection prompts]

- **Pre-P13 hygiene closed; S43 next per `briefs/p13/s43.md`.**
```

## Acceptance criteria

1. `charter/schema.md` carries a new H2 section "Cross-cutting binding shapes" containing three sub-sections with field tables for TenantContext, ErrorResponse, and the canonical cursor codec per the content above.
2. The three sub-sections' field tables match the current code state verified at pre-write reconciliation surface 2; any drift between audit-finding snapshot and current code state lands in the schema.md content rather than the audit-finding snapshot.
3. `grep -rln "Quorum" --include="*.md" .` returns matches only inside the allowlist (`charter/decisions.md`, `log/sessions.md`, `docs/archive/`).
4. Non-allowlist matches surfaced at pre-write reconciliation are rephrased, not allowlist-extended.
5. `charter/phase-2-audit-inputs.md` carries a new section "Phase 2-A close hygiene list" with the roadmap stale-headers entry as first item per the content above.
6. `charter/current-package.md` carries the pre-P13 hygiene close marker.
7. `briefs/p13/pre-hygiene.md` preserved verbatim.
8. `log/sessions.md` entry appended per the hygiene-shape convention.
9. No new D-entries. `charter/decisions.md` content unchanged.
10. No code changes. No edits to any file under `contexts/`, `apps/`, `shared_kernel/`, `padhanam/`, `tests/`, `infra/`, `migrations/`, `ops/`.

## Reflection prompts addressed in session log entry

Four prompts answer in substantive paragraphs.

1. **Hygiene-session-as-shape methodology observation, fourth instance.** The pattern's prior three instances landed at pre-P12 hygiene (P11 close; six commits; structural-finding focus), post-P12 charter-discipline hygiene (post-audit boundary; seven commits; discipline-convention focus), and pre-Phase-2 synthesis-and-refinement (ten commits; synthesis-and-refinement focus). This fourth instance lands at pre-P13 (five commits; carryover-closure focus). Does the shape vocabulary still hold cleanly? Does the temporal-position taxonomy from the third-instance reflection (pre-audit hygiene, post-audit hygiene, pre-next-phase hygiene) absorb this instance, or does pre-package-first-session hygiene warrant a fourth sub-shape? First-instance evidence for the pre-package-first-session sub-shape.

2. **Pre-write reconciliation surfaces, twelfth-plus instance.** What did the five reconciliation surfaces reveal? Mechanical absorptions versus structural-honesty findings versus operator-question resolutions. Cumulative reconciliation count update. Specifically: did surface 2's code-state verification surface any drift between the P12 audit-finding snapshot and current code state? Did surface 3's grep return zero (compressing commit 2 to no-op) or non-zero (commit 2 as substantive find-replace)?

3. **Grep allowlist as cross-context discipline.** The S13 verification grep allowlist (charter/decisions.md, log/sessions.md, docs/archive/) was originally a rebrand-sub-shape playbook element. This session generalises it to non-rebrand hygiene as the canonical convention for any narrative-cleanup operation against append-only-protected historical content. First-instance evidence for the generalisation; recurrence test fires at the next narrative-cleanup hygiene operation. The convention's structural shape: append-only files stay sacred; current-facing narrative gets rephrased to remove drift; allowlist never extends.

4. **Phase 2-A close hygiene list as new convention surface.** The accumulator surface for hygiene items surfaced during Phase 2-A. First entry (roadmap stale-headers) lands at this session per Decision 2 triage discipline carried from P13 framing close. Forward-relevance: P14 framing and subsequent build sessions add items as they surface; the list clears at Phase 2-A close hygiene session. Structurally distinct from the substrate-completion list (which carries activation-gated deferred work) and from `charter/deferred-decisions.md` (which carries architectural commitments awaiting trigger conditions); this list is closure-housekeeping. First-instance evidence for the convention; recurrence test fires at the first item added through Phase 2-A package execution beyond this opening entry.

## Out of scope explicitly

- Schema.md table additions beyond the three cross-cutting binding shapes. Database-table schema diffs land alongside their substrate commits per the standing convention; this session formalises cross-cutting shapes only.
- D-entries for the schema.md formalisation. Per hygiene-shape discipline, no D-entries this session. The shapes are already code-committed; the work is documentation hygiene against the binding-specification surface.
- Phase 2-A close hygiene list items beyond the roadmap stale-headers entry. List accumulates organically through Phase 2-A; this session lands the first entry only.
- Any rephrasing of historical D-entries, archived session content, or `docs/archive/` material. Per append-only spirit and S13 verification discipline; the old name lives in append-only locations only.
- Roadmap v7 entry. The v6 entry from P13 framing stands; the stale-headers item at the Phase 2-A close hygiene list addresses the section-header drift without revising the version-log content.
- Any structural reorganisation of `charter/schema.md` beyond appending the new H2 section. Existing section ordering preserved.
- Any structural reorganisation of `charter/phase-2-audit-inputs.md` beyond appending the new section. Existing section ordering preserved.
- CLAUDE.md "Methodology capture" doc-content rebrand from "(pending operator authorship per D39)" to D113's living-hypothesis framing. This is a separate item from the Quorum-to-Padhanam rebrand; per `charter/p12-phase-2-inputs.md` it sits as a small carryover at Phase 2-entry but is not in this session's scope. If a future hygiene session bundles it, the bundling decision is operator-judged at that session's framing.

## Session log entry instruction

After commit 4 lands, append the session log entry to `log/sessions.md` as commit 5 per the hygiene-shape convention precedent. Use real-SHA-for-prior-commits plus "this commit" for the session log entry's self-reference. The four reflection prompts answer in substantive paragraphs; methodology lines surface for any patterns observed; the close marker line names "S43 next per `briefs/p13/s43.md`" to bridge to the next-up build session.
