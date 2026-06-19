# S103c-fix-2 smoke — view coherence (List, Map, CDD)

One corrected element-evidence truth across all three views, with unlink +
element-level relink reaching List and Map. Surface + read-side; no migration, no
matcher change, no D-entry.

## Step 0 correction

The brief framed List and Map as reading "a stale goal-level model." They are not:
since S103b they derive from element evidence (`/units-by-goal` →
`list_units_by_goal` → `unit_graph.list_goal_edges()` → `derive_goal_edges` over
`list_element_evidence`). The remaining `SERVES` references were stale docstrings.
So the **read-coherence gap was already closed at S103b** (the re-point is a no-op,
not a separate-model reconciliation — no scoping fork, no D-entry). The genuine gap
was **write-reach**: List and Map were read-only.

## Verified this session (code + live on the real corpus)

- **Suite green.** `tests/unit` passes; `tests/_enforcement` green; **import-linter
  48/0**. New: the consistency guard (`UnitGraphAdapter.list_goal_edges` ==
  `derive_goal_edges(list_element_evidence)`) + served-HTML guards for the List/Map
  corrections, the cross-goal relink picker, and reuse of the S103c paths.
- **Live cross-view coherence (AC1).** On the personal tenant: **840 element
  evidence rows; 688 goal edges; List/Map goal edges == `derive_goal_edges` of the
  CDD evidence → True.** The two sources are the one truth.
- **Diff is surface + read-side (AC5).** `daily_driver.html`, the binding DTO +
  read (`outcome_id` on the binding), the `list_units_by_goal` docstring refresh,
  `ElementBinding`; **no migration, no matcher-logic change, no schema** (grep:
  `infer_element_evidence` / `correlate_goal_facets` / migrations untouched).
- **Write reuse, not a new path (AC2/AC3).** List/Map unlink and relink POST the
  S103c `/cdd/evidence/unlink` and `/relink` — so they mark the unit user-owned and
  emit a correction record identically to a CDD correction; relink is element-level
  via a goal-then-element picker, cross-goal allowed (D202 stays element-level).
- **Served (AC6).** The rebuilt image (`79276dd`) serves the List/Map corrections;
  5/5 tenant-isolation contract guards pass live.

## Operator-gated

The two reflections — did corrections propagate cleanly across all three views
without a manual refresh, and was element-level relink the right grain from the
goal-level views (or did you want a goal-level default) — are the browser pass.
The mechanism is built so propagation is structural: all three views read one
shared cache (`assessData` + `cddBindings`, loaded once in `loadAssess`), and every
correction calls `loadAssess()` to re-read it. `make build-api` advanced the pin to
`79276dd`.
