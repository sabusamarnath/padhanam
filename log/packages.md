# Package Log

Append-only log of package retrospectives with measured-outcomes
paragraphs per D40. The first instance lands at P4 close (S15);
earlier packages have archives at `docs/archive/packages/` per D31
without measured-outcomes coverage.

The measured-outcomes paragraph in each entry computes the seven
Phase 1 industry-overlay metrics (deployment frequency proxy, lead
time, change failure rate, MTTR, reliability, developer experience,
contribution effectiveness) and the three bet-native metric layers
(discipline-adherence, architectural-durability, bet-direction
integrity) per the methodology document's measurement section.
Package-level samples are small (one to four sessions per package);
phase audits are where trend analysis lives.

Format per entry:

```
## P<N>: <name>
- Closed: <YYYY-MM-DD>
- Sessions: S<a>, S<b>, ...
- Archive: <link>
- Measured outcomes: <paragraph covering DORA/CORE4 + bet-native metrics>
```

---

## P4: LLM gateway

- Closed: 2026-05-05
- Sessions: S14 (cost capture and registry migration), S15 (tenant context enrichment and P4 close)
- Archive: [docs/archive/packages/p4.md](../docs/archive/packages/p4.md)

### Measured outcomes

**Deployment frequency (merged-to-main proxy).** Two sessions in the
P4 window, both producing commits merged to the main branch on
2026-05-05. Two merge events in the window. The single-day cadence
across both sessions reflects the package's small RICE-effort
score (0.8) — P4 is the lightest-effort package in Phase 1 by design.

**Lead time for changes.** S14: brief written 2026-05-05T16:19+01:00,
merged the same day; effective lead time ~4 hours from brief start
to session close. S15: brief written within the same day at the P4
framing strategic conversation that scheduled both S14 and S15;
merged 2026-05-05; effective lead time again same-day. The single-
day execution of both sessions is consistent with the small-package
shape; reading lead-time as a methodology signal at this scale is
small-sample noise.

**Change failure rate.** Zero sessions in P4 have a non-empty
`corrected_by` field as of P4 close. Self-correction within a
session (e.g., the S14 migration commit's mid-build scope expansion
to fold the registry-adapter consumer change in) does not count as
a session-level failure per D40's definition. Change failure rate
for P4 = 0/2 = 0%. The number is honest at this scale but small-
sample; it cannot be read as a reliability claim about the
methodology until trend data accumulates over multiple packages.

**Mean time to restoration.** Vacuous: no failures introduced by
P4 sessions, no corrective sessions exist. Reportable as N/A; the
distribution shape requires data the methodology has not yet
generated.

**Reliability (clean close rate).** Both S14 and S15 closed
`clean`: tests passing, principles intact, charter touch-points
updated. Reliability = 2/2 = 100%. The discipline held under the
small-sample window; the meaningful signal is whether reliability
holds across longer phases (the Phase 1 close audit will compute
phase-level numbers).

**Developer experience (CORE4 dimensions, qualitative).** Flow
state held across both sessions; the pre-write vendor-doc
reconciliation surface produced two real corrections in S14 (LiteLLM
helper coupling, OTel cost-attribute namespace stabilisation) and
one structural surfacing in S15 (the schema-verification-at-framing
pattern catching the classification field's absent column). Feedback
loops were tight: `make lint`, `uv run pytest`, and `make scan` ran
at every commit boundary, with the live stack available for
end-to-end verification on the same laptop session. Cognitive load
was concentrated at the S15 commit-shape granularity decision (how
to split the resolver from the propagation + attribute swap to keep
working state at every boundary); the resolution was operator-
discipline-shaped rather than a tooling change.

**Contribution effectiveness (substantive vs cleanup proportion).**
S14: 7 substantive commits (state-at-open chore, current-package
transition, pricing table, OTel cost emission, migration + adapter,
D49 entry, scheduled-checks update, session log). The chore commit
is supply-chain housekeeping, not cleanup of prior work. S15: 9
substantive commits (TenantContext value object, registry resolver,
propagation + attributes, e2e tests, D50 entry, P4 archive,
log/packages.md, current-package transition, session log). All
commits are forward-progress on P4's stated goal; zero commits in
P4 corrective against earlier sessions. Contribution effectiveness
≈ 100% within P4. No cleanup overhead; no rework against earlier
sessions in the same phase.

### Bet-native metrics

**Discipline-adherence.** Charter touch-points updated in-commit at
every required boundary: `charter/schema.md` updated in the same
commit as Alembic revision `0003_add_cost_columns` (S14); D49 and
D50 D-entries appended within the session that produced the
implementation; `charter/current-package.md` transitioned at S14
open (P4-active) and again at S15 close (between-packages). AST
enforcement tests passed at every commit (7 enforcement tests,
unchanged from P3 close). Decision-to-code translation: D49 produced
the cost-capture implementation in the same session it was decided
in; D50 produced the TenantContext value object in the same session
it was decided in. Both translations within-session; no D-entry
carried forward without its corresponding code in P4.

**Architectural-durability.** Import-linter contract count: 15 at
P4 close, unchanged from P3 close. No new contracts because the
existing layer and policy contracts already cover the new code
shape. Drift findings: five entries surfaced and recorded
explicitly (S14 migration commit scope expansion, S15 framing
classification-vs-schema mismatch, S15 commit-shape granularity
question, S14 cost-ceiling enforcement gap, S14 pricing-table
format evolution forward-note). Test density: +29 tests over P3
close baseline of 129 (S14 +14, S15 +15), bringing the codebase to
158 collected tests (155 passing + 3 env-gated e2e at P4 close,
plus the 4 pre-existing env-gated `test_p3_full_slice` skips).
Supply-chain check cadence: monthly pricing-table review added to
`ops/scheduled_checks.yaml` at S14 with first run 2026-06-05; the
scheduled-check runner ran cleanly against documented exceptions.

**Bet-direction integrity.** Roadmap reasoning-category changes:
zero new roadmap versions during P4. Both S14 and S15 executed
within the framing decisions made at the P4-open strategic block
that closed the P3→P4 boundary. PRD delta size: not yet reportable
at the package level (Phase 1 PRD is reviewed at the Phase 1 close
audit per D43). PRFAQ coherence: not refreshed during P4; the
v1 PRFAQ from the P3 post-close strategic session stands until the
Phase 1 close audit per D45. Role-function activity distribution
across P4: S14 exercised analyst, architect, engineer, technical
writer; S15 exercised analyst, architect, engineer, technical
writer. Four of five role-functions exercised at least once across
P4; the PM function was not exercised in either session, reflecting
that P4 is implementation against architecture decided at framing
rather than re-prioritisation. The PM function exercised at the
P4-open strategic block (separate strategic-mode commit) and will
exercise again at the P4→P5 boundary.

### What the numbers do not say

The two-session sample is too small to read as a methodology trend.
Phase 1 close audit numbers will be the first credible signal at
the methodology-trend scale. The bet-native metrics surface what is
honestly reportable at the package level (charter touch-point
compliance, contract count, test density, role-function
distribution); the industry-overlay metrics surface in the shape
the case study's audience reads but at a small enough sample that
their face value is provisional. The methodology's "metrics measure
methodology, not operator" framing applies: the perfect numbers in
this entry are signal about whether the discipline stayed tight on
a small package, not signal about whether a senior product leader
at scale can sustain this performance — that question requires
phase-level data that does not yet exist.
