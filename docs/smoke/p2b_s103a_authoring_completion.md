# S103a smoke — authoring completion (D200, D201)

Surface the drafted outcome, add elements, reclassify across types. All over the
S102 `0005` shapes — **no migration 0006** (the outcome proof/origin properties
and the edge `needs_review` flag are schemaless, no constraint).

## Verified this session (code + live graph, up to the operator's browser gate)

- **Unit suite green.** `tests/unit` passes (exit 0); the 19 `test_cdd.py` cases
  cover `required_edge_type`, the add path (user_authored/accepted + default
  edge), reclassify (identity preserved, origin flips, edge flagged not dropped,
  no-op rejected, compatible-kind not flagged), and the outcome accept/correct/
  reject use cases. `tests/_enforcement` green; **import-linter 48/0**.
- **Reclassify verified on the live surface (AC3, the edge-grammar guard).** The
  in-container contract test reclassifies a lever (with a `FEEDS` edge) to an
  external on the real Neo4j: the node keeps its id, the origin flips to
  `user_authored`, the `FEEDS` edge **survives flagged** (`needs_review = true`,
  never deleted), and tenant B reads none of it (isolation). 3/3 contract tests
  pass live.
- **No migration.** Latest Neo4j migration stays `0005`; the new persisted state
  is schemaless (the outcome proof/origin on `:Outcome`, the edge `needs_review`).
- **Matcher untouched.** No change to `correlate_goal_facets` or the `SERVES`
  write; grep-confirmed in the diff.
- **The surface is served (AC6).** The running image (`make build-api`,
  re-pinned `b1e136fa…`) serves the CDD lens with the add control, the "Move to…"
  reclassify select, the proofable outcome row, and the `needs_review` note
  (`grep` of `/app/apps/api/static/daily_driver.html` in-container).

## The full authoring pass is operator-gated (the S101 idiom)

The add / reclassify / outcome-proof paths are wired and live on the personal
tenant's graph, behind `DAILY_DRIVER_CDD_WRITE`. The full browser authoring pass
on the real 8-goal corpus — eyeballing every goal, adding the externals the draft
missed, reclassifying any mis-typed element, proofing each outcome — is
operator-gated (the instance is Google-login wired, no headless backdoor on the
authed corpus). `make build-api` (never `compose build` alone) advances the
digest pin if a re-pin is needed.
