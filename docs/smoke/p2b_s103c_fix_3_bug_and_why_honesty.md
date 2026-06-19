# S103c-fix-3 smoke — working unlink everywhere, a truthful why

A bug fix + read-side honesty. No matcher binding change, no schema, no D-entry.

## Step 0 (reproduce, root-cause, classify)

- **Map unlink fault = the outcome-kind 422.** `ElementKind` is
  `{lever, intermediary, external}` with no `outcome`; the weak alias bindings bind
  to the **outcome** element, and List/Map's `renderGoalCorrections` sends every
  binding's kind to `/cdd/evidence/unlink|relink`, so `ElementKind("outcome")`
  raised → 422. The graph endpoint already supported outcome (`_AUTHORED_ENDPOINT`);
  only the router rejected it. The S103c-fix-2 guard passed because it checked the
  affordance *renders*, not that it *works*.
- **The "goal name" why = a placeholder**, not a token. Classified by whether the
  read-side recompute can reproduce a real unit∩goal-name token.
- **"Email activity: 2 applications" under Wide World Marathon = a symptom of spurious
  binding, not a label change** (the kind label is correct; job emails are spuriously
  alias-bound to the marathon goal). Deferred and named — not a one-line fix.

## Verified this session (code + live on the real corpus)

- **Suite green.** `tests/unit` passes; `tests/_enforcement` green; **import-linter
  48/0**. New: a functional guard (unlink completes for every kind **incl. outcome**,
  the edge actually removed; relink to/from outcome) + the honest-why guards
  (real token / `no clear basis`, no placeholder) + a live outcome-unlink contract.
- **Map unlink fixed (AC1).** Unlink/relink now validate against
  `EVIDENCE_KINDS = {lever, intermediary, external, outcome}` and pass the kind
  string through (use case + port + bridge relaxed `ElementKind → str`); the graph
  was already capable. `reclassify`/`add` keep `ElementKind` (outcome excluded, D201).
- **Live function, not presence (AC2).** A unit bound to the **outcome** element
  unlinks cleanly on real Neo4j (the exact Map failure); 3/3 correction contract
  guards pass on the rebuilt image (`2171607`).
- **Honest why (AC3).** `binding_rationale` shows the real overlapping token where
  the recompute finds one and `no clear basis` where it cannot — no `goal name` /
  `(substring)` placeholder remains (guarded by source inspection).
- **Spurious-binding signal (AC4/reflection 2).** Live: **12 of 839 bindings (1.4%)
  recompute to "no clear basis", all alias-tier** — job emails alias-bound where no
  unit∩goal-name token reproduces (the matcher's `_keyword_match` also does
  substring, looser than the recompute's shared-token, so these rest on substring
  matches, not real tokens). **The matcher binding logic is unchanged** (grep:
  `infer_element_evidence` / `correlate_goal_facets` not in the diff); the looseness
  is the strategic call held outside this session, and 1.4% is its input.
- **Diff is surface + read-side + the kind-validation wiring (AC5).** No migration,
  no matcher logic, no schema, consume side untouched.

## Out of scope (named)

The matcher looseness / the 12 spurious alias bindings (strategic, informed by the
1.4% no-basis count), the activity mislabel (a binding symptom), the embedding tier,
the consume side, S104, and the current-package windowing (which is **not** near its
bound — the S103c-fix-2 alarm conflated bytes with tokens; it is ~5.2k/20k tokens).
`make build-api` advanced the pin to `2171607`; the operator-gated live pass confirms
a working Map unlink and the honest why.
