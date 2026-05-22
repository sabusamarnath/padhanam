# Pre-S45 hygiene — Software engineering principles baseline assessment

This is the v1 brief preserved per the briefs/ discipline (D43; methodology
document "Session brief preservation"). It is the forward-looking specification
the assessment committed to before work began; deviations are recorded in the
session-log entry, not in-place here.

## Goal stated as artefacts at session close

At session close the repository carries:

- A new findings document at `audits/p13-principles-baseline.md` (or current
  convention path; pre-write reconciliation surfaces the correct location)
  carrying the thorough code-altitude assessment of the Phase 2-A codebase
  against KISS, DRY, SOLID (all five letters individually), YAGNI, and Tell
  Don't Ask.
- For each principle: an assessment methodology paragraph explaining how the
  principle was measured; quantitative metrics where applicable; qualitative
  findings with specific evidence (file paths, line numbers, code snippets);
  severity classification per finding (load-bearing / material / marginal);
  recommended action per finding.
- Captures.md entries for any methodology observations the assessment process
  itself surfaces. The assessment is a first-instance discipline; methodology
  observations from its execution warrant capture per the captures-as-audit-trail
  discipline.
- A session log entry at `log/sessions.md` capturing the assessment outcome at
  headline altitude, the methodology observations, and any structural-honesty
  findings.
- `briefs/p13/pre-s45-principles-assessment.md` preserved as this brief's
  canonical path.

This is an assessment session. No code changes, no test changes, no
enforcement-layer changes. No charter changes beyond captures.md and session log
entries. Disposition of findings into charter additions, hygiene items, or
methodology promotions happens at the subsequent Claude.ai disposition
conversation, not at this session.

## Context to read first, in order

1. `charter/principles.md` — the load-bearing build principles. The five
   software engineering principles assessed here are NOT in principles.md; they
   sit at audit altitude as measurement axes only. The assessment respects this
   distinction.
2. `charter/decisions.md` — full read, particularly Decision 7 (substrate-depth
   discipline) and the D-entries that classify must-have under Decision 7 with
   cost-of-pivot reasoning. D124 onward is the recent substrate; verify the
   substrate-depth-classified inventory at pre-write reconciliation.
3. `charter/methodology.md` — the existing methodology document. Some principles
   overlap with existing methodology entries (the file topology budget
   discipline, the substrate-application boundary check); the assessment respects
   existing discipline while assessing the codebase against the principles
   independently.
4. `charter/architecture.md` — for the hexagonal architecture commitments that
   anchor SOLID's Dependency Inversion plus the cross-context contracts.
5. Recent session logs at `log/sessions.md` — S43, S43b, S44a, S44b. These carry
   the substrate-depth override commitments and the file topology budget evidence
   accrued through Phase 2-A.
6. `charter/captures.md` — for methodology candidates surfaced through Phase 2-A.
   Some candidates relate directly to principle adherence.
7. `charter/phase-2-audit-inputs.md` — the existing audit-input accumulator. The
   principles assessment may produce additional audit-input entries that the
   post-assessment disposition session lands.

## Pre-write reconciliation (verify against current sources before assessment runs)

Eight surfaces to verify before the assessment substantive work begins.

1. Output file path convention.
2. Substrate-depth-classified D-entry inventory.
3. Available static analysis tools.
4. Current import-linter contract count and status.
5. File inventory baseline.
6. Existing audit precedents structure.
7. Methodology document overlap surfaces.
8. No conflicting in-flight work.

Findings surface as questions before any assessment work begins.

## The substantive assessment

The assessment is structured by principle. Each principle gets a section with
consistent shape: methodology paragraph, metrics, findings, severity
classification, recommended actions. The findings are evidence-based with file
paths and line numbers; absent evidence cited as such.

Sections: 1 KISS, 2 DRY, 3 SOLID (3.1 SRP, 3.2 OCP, 3.3 LSP, 3.4 ISP, 3.5 DIP),
4 YAGNI, 5 Tell Don't Ask. Findings synthesis at the document tail: overall
posture summary, cross-principle pattern findings, severity-classified findings
list, recommended actions per finding.

## Commit structure

Three commits: (1) findings document plus this brief; (2) captures for
methodology observations (collapses into commit 3 if none warrant capture);
(3) session log entry plus close marker, transitioning `charter/current-package.md`
from "S44b closed; S45 next" to "Pre-S45 principles assessment closed; S45 next".

## Acceptance criteria

1. The findings document exists with all five principles assessed.
2. Each principle section carries methodology, metrics, qualitative findings with
   evidence, severity classification, recommended action.
3. The findings synthesis carries overall posture, cross-principle patterns,
   severity-classified list, recommended actions.
4. Pre-write reconciliation findings documented in session log reflection
   prompt 1.
5. No code/test/enforcement changes; no charter changes beyond captures.md and
   session log.
6. This brief preserved.
7. Session log entry appended; current-package transition committed.
8. The eight pre-write reconciliation surfaces verified and findings recorded.

## Out of scope explicitly

Charter changes triggered by findings; code fixes triggered by findings; the
YAGNI monitoring discipline addition to `charter/phase-2-audit-inputs.md`;
methodology document promotion of any principle-derived discipline; substrate-
depth-override tagging discipline; file topology budget trajectory tracking. All
deferred to the post-assessment disposition conversation.

---

*Note on this preservation: the assessment session received the brief inline
rather than as a pre-committed file. This file reproduces the brief's structure
faithfully at v1 per the briefs/ discipline; the full inline brief text is in the
session conversation history. Pre-write reconciliation surface 8 noted one
mechanical correction — the brief's context-reading item 7 cited
`charter/captures.md`; the captures file lives at `log/captures.md`.*
