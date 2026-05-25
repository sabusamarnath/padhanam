# P13 S47 — Addendum: ThresholdResolver port plus captures-entry strengthening

Post-prompt-draft addendum to the S47 prompt at `briefs/p13/s47.md`.
Lands the ThresholdResolver port as the fifth instance of the
interface-versus-implementation methodology candidate's framing-
drift pattern — surfaced at the session-prompt-draft review surface
(a post-strategic-mode-close verification surface) rather than at
the convergence conversation itself.

Six edits land at this addendum:

1. D134 prose: the cell consumes thresholds via the ThresholdResolver
   port at `shared_kernel/confidence_thresholds.py` rather than
   reading the configuration values directly. Single-pair adapter at
   Phase 2-A; per-operation-class adapter activates at Phase 2-B+ as
   adapter swap, not cell-site refactor. Alternative (f) appended to
   the rejected list.
2. Architecture.md `Confidence-aware response composition` sub-section
   refreshed to name both ports (ConfidenceCalculator and
   ThresholdResolver) explicitly.
3. Commit 3 (originally ConfidenceCalculator + parse-failure
   extension) expands to land the ThresholdResolver port plus the
   single-pair adapter, with the cell-source-no-numeric-literals
   discipline as the substrate-honesty surface.
4. Commit 5 cell-logic description updates: cell consumes thresholds
   via the port at turn-open; cell source carries no numeric
   threshold literals.
5. Acceptance criteria gain criterion 8a (ThresholdResolver port +
   single-pair adapter + cell-source-no-numeric-literals); criterion
   12 picks up the cell-source-no-numeric-literals clause.
6. Captures-entry strengthening: the methodology candidate now
   carries five-instance evidence (four from convergence, one from
   post-prompt-draft review) plus the pattern-density observation
   that strategic-mode altitude may inherently tend toward
   implementation-versus-interface drift more than build-mode work
   does. Recurrence test at the next strategic-mode session.

Out-of-scope deferral: per-operation-class ThresholdResolver adapter
defers to Phase 2-B+ when higher-stakes operations land; the port
shape already supports activation as adapter swap.

Path-naming carry-over from the S47 base commits: the addendum
brief's `apps/inference/adapters/` and `apps/messaging/adapters/`
paths do not exist; the convention established at S47 base commit 3
is `contexts/<name>/adapters/` for non-vendor adapters
(SelfReportedConfidenceAdapter at `contexts/inference/adapters/`).
The SinglePairThresholdResolverAdapter follows the same convention
at `contexts/messaging/adapters/threshold_single_pair.py`.
