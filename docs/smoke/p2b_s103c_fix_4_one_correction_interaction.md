# S103c-fix-4 smoke — one correction interaction across all three views

The correction interaction single-sourced; List and Map brought to in-place +
bulk parity with CDD. Surface-only; no write-path, matcher, or schema change.

## Step 0 shape decision

The two correction renderings group differently (CDD by element, List/Map by the
goal's bound units) and relink differently (CDD same-goal element select, List/Map
cross-goal goal-then-element picker). So the shape is a **shared interaction behind
two thin renderers**: one `renderCorrectionList` owns triage + bulk + in-place
re-render + the why/strength/unlink row; the **relink control** is the one
context-specific piece, passed in. The unlink uses `b.element_kind` uniformly.

## Verified this session (code + live)

- **Suite green.** `tests/unit` passes; `tests/_enforcement` green; **import-linter
  48/0**. New: the structural single-source guard + an AC4 why/strength guard.
- **Single-sourced (AC1, the structural prevention).** The unlink action is one POST
  site (`unlinkBinding`); the bulk control + checkbox live only in
  `renderCorrectionList`; both `renderBindings` (CDD) and `renderGoalCorrections`
  (List/Map) **delegate** to it. A future view re-implementing its own correction
  handling would duplicate the unlink site / bulk control and fail the guard.
- **List/Map parity (AC2/AC3).** They now re-render in place on unlink/relink (a
  sub-local refresh re-reads the bindings cache and re-renders just the corrections
  list — no fold collapse), and gain bulk select + the weak-only triage, identical
  to CDD. Bulk unlink emits one correction record per binding (the shared
  `unlinkBinding` → the S103c-fix-3-tested use case).
- **Why + strength consistent (AC4).** Rendered from the one source, so all three
  views match (the consolidated row standardises on element_kind + strength + why;
  tier dropped as redundant with strength).
- **Surface-only (AC6).** The diff is `daily_driver.html` + the marker + tests — no
  Python write-path, no matcher, no schema (grep-confirmed). Served on pin
  `6a5067e`; correction contract guards pass live.

## Reflection

- **Single-sourced, structurally (not just functional parity).** The guard asserts
  the unlink action is one POST site and both renderers delegate — so a determined
  divergence (a new view re-implementing corrections) is *caught*, not merely
  unlikely. The prevention that landed is structural.
- **The context difference the shared source absorbed:** grouping (by element vs by
  the goal's bound units) is handled by the caller passing the filtered `bindings`;
  the relink target space (same-goal vs cross-goal) by the caller passing
  `relinkControlFor`. The next correction surface inherits exactly this shape — pass
  your bindings + your relink control, get triage/bulk/in-place/why/strength free.

## Operator-gated

The live feel — unlink/relink on List and Map staying expanded, bulk select, the
why/strength reading the same as CDD — is the browser pass. `make build-api`
advanced the pin to `6a5067e`.
